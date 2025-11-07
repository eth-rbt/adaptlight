"""
AWS S3 uploader for AdaptLight logs.

Handles scheduled uploads of log files to AWS S3:
- Uploads logs every 6 hours
- Compresses logs before upload
- Retries failed uploads
- Marks successfully uploaded files
"""

import gzip
import threading
import time
from pathlib import Path
from datetime import datetime, timezone

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    print("Warning: boto3 not available. AWS uploads will be disabled.")


class AWSUploader:
    """Handles scheduled uploads of logs to AWS S3."""

    def __init__(self, config, log_manager):
        """
        Initialize AWS uploader.

        Args:
            config: Configuration dict with AWS settings
            log_manager: LogManager instance
        """
        self.config = config
        self.log_manager = log_manager
        self.is_running = False
        self.upload_thread = None
        self.upload_interval = 6 * 60 * 60  # 6 hours in seconds

        # Initialize S3 client
        self.s3_client = None
        if BOTO3_AVAILABLE and config.get('enabled', False):
            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=config['aws']['access_key_id'],
                    aws_secret_access_key=config['aws']['secret_access_key'],
                    region_name=config['aws']['region']
                )
                self.s3_bucket = config['aws']['s3_bucket']
                self.log_prefix = config.get('log_prefix', 'adaptlight-logs/')
                print(f"AWS S3 uploader initialized: {self.s3_bucket}")
            except (KeyError, NoCredentialsError) as e:
                print(f"Warning: Could not initialize S3 client: {e}")
        else:
            print("AWS uploads disabled")

    def start_scheduled_uploads(self):
        """Start the scheduled upload thread."""
        if not self.s3_client:
            print("AWS uploads not configured")
            return

        if self.is_running:
            print("Upload scheduler already running")
            return

        self.is_running = True
        self.upload_thread = threading.Thread(target=self._upload_loop)
        self.upload_thread.daemon = True
        self.upload_thread.start()
        print(f"Started scheduled uploads (every {self.upload_interval / 3600} hours)")

    def stop_scheduled_uploads(self):
        """Stop the scheduled upload thread."""
        self.is_running = False
        if self.upload_thread:
            self.upload_thread.join(timeout=5.0)
        print("Stopped scheduled uploads")

    def _upload_loop(self):
        """Main upload loop that runs every 6 hours."""
        while self.is_running:
            try:
                self.upload_pending_logs()
            except Exception as e:
                print(f"Error in upload loop: {e}")

            # Wait for next upload interval
            time.sleep(self.upload_interval)

    def upload_pending_logs(self):
        """Upload all pending log files to S3."""
        if not self.s3_client:
            print("S3 client not available")
            return

        pending_files = self.log_manager.get_pending_upload_files()

        if not pending_files:
            print("No pending log files to upload")
            return

        print(f"Uploading {len(pending_files)} log files to S3...")

        for log_file in pending_files:
            try:
                self._upload_file(log_file)
                self.log_manager.mark_file_uploaded(log_file)
            except Exception as e:
                print(f"Failed to upload {log_file}: {e}")

    def _upload_file(self, file_path: Path, max_retries=3):
        """
        Upload a single file to S3 with retries.

        Args:
            file_path: Path to file to upload
            max_retries: Maximum number of retry attempts
        """
        # Compress file before upload
        compressed_data = self._compress_file_data(file_path)

        # Generate S3 key
        relative_path = file_path.relative_to(self.log_manager.log_dir)
        s3_key = f"{self.log_prefix}{relative_path}.gz"

        # Upload with retries
        for attempt in range(max_retries):
            try:
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=s3_key,
                    Body=compressed_data,
                    ContentType='application/gzip',
                    Metadata={
                        'original_name': file_path.name,
                        'upload_time': datetime.now(timezone.utc).isoformat()
                    }
                )
                print(f"Uploaded to S3: {s3_key}")
                return

            except ClientError as e:
                print(f"Upload attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

    def _compress_file_data(self, file_path: Path) -> bytes:
        """
        Compress file data with gzip.

        Args:
            file_path: Path to file to compress

        Returns:
            Compressed file data as bytes
        """
        with open(file_path, 'rb') as f_in:
            return gzip.compress(f_in.read())

    def upload_now(self):
        """Trigger an immediate upload (outside of scheduled interval)."""
        print("Triggering immediate upload...")
        self.upload_pending_logs()

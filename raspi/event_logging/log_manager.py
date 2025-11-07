"""
Log manager for AdaptLight.

Manages local log files including:
- Log rotation and cleanup
- Compression of old logs
- Tracking uploaded logs
- Disk space management
"""

from pathlib import Path
from datetime import datetime, timedelta
import gzip
import json


class LogManager:
    """Manages local log file storage and cleanup."""

    def __init__(self, log_dir='data/logs', retention_days=30):
        """
        Initialize log manager.

        Args:
            log_dir: Base directory for log files
            retention_days: Number of days to keep logs locally
        """
        self.log_dir = Path(log_dir)
        self.retention_days = retention_days
        self.upload_tracking_file = self.log_dir / '.uploaded.json'

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Load upload tracking
        self.uploaded_files = self._load_upload_tracking()

        print(f"LogManager initialized: {self.log_dir}, retention: {retention_days} days")

    def _load_upload_tracking(self):
        """Load the list of uploaded files."""
        if self.upload_tracking_file.exists():
            with open(self.upload_tracking_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_upload_tracking(self):
        """Save the list of uploaded files."""
        with open(self.upload_tracking_file, 'w') as f:
            json.dump(self.uploaded_files, f, indent=2)

    def mark_file_uploaded(self, file_path: Path):
        """
        Mark a file as uploaded to AWS.

        Args:
            file_path: Path to the uploaded file
        """
        file_key = str(file_path.relative_to(self.log_dir))
        self.uploaded_files[file_key] = {
            'uploaded_at': datetime.now().isoformat(),
            'size': file_path.stat().st_size
        }
        self._save_upload_tracking()
        print(f"Marked as uploaded: {file_key}")

    def is_file_uploaded(self, file_path: Path) -> bool:
        """
        Check if a file has been uploaded.

        Args:
            file_path: Path to check

        Returns:
            True if file has been uploaded
        """
        file_key = str(file_path.relative_to(self.log_dir))
        return file_key in self.uploaded_files

    def get_pending_upload_files(self):
        """
        Get list of log files that haven't been uploaded yet.

        Returns:
            List of file paths pending upload
        """
        all_log_files = list(self.log_dir.rglob('log-*.jsonl'))
        pending = [f for f in all_log_files if not self.is_file_uploaded(f)]
        return sorted(pending)

    def compress_old_logs(self, days_old=7):
        """
        Compress log files older than specified days.

        Args:
            days_old: Compress files older than this many days
        """
        cutoff_date = datetime.now() - timedelta(days=days_old)

        for log_file in self.log_dir.rglob('log-*.jsonl'):
            # Skip if already compressed
            if log_file.suffix == '.gz':
                continue

            # Check file age
            file_date = datetime.fromtimestamp(log_file.stat().st_mtime)
            if file_date < cutoff_date:
                self._compress_file(log_file)

    def _compress_file(self, file_path: Path):
        """Compress a log file with gzip."""
        compressed_path = file_path.with_suffix(file_path.suffix + '.gz')

        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                f_out.writelines(f_in)

        # Remove original file
        file_path.unlink()
        print(f"Compressed: {file_path} -> {compressed_path}")

    def cleanup_old_logs(self):
        """Delete logs older than retention period."""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        for log_file in self.log_dir.rglob('log-*'):
            # Check if uploaded and old
            if self.is_file_uploaded(log_file):
                file_date = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_date < cutoff_date:
                    log_file.unlink()
                    print(f"Deleted old log: {log_file}")

    def get_disk_usage(self):
        """
        Get disk usage statistics for log directory.

        Returns:
            Dict with total size, file count, etc.
        """
        total_size = 0
        file_count = 0

        for log_file in self.log_dir.rglob('*'):
            if log_file.is_file():
                total_size += log_file.stat().st_size
                file_count += 1

        return {
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'file_count': file_count
        }

    def run_maintenance(self):
        """Run all maintenance tasks (compress, cleanup)."""
        print("Running log maintenance...")
        self.compress_old_logs(days_old=7)
        self.cleanup_old_logs()
        usage = self.get_disk_usage()
        print(f"Log disk usage: {usage['total_size_mb']:.2f} MB, {usage['file_count']} files")

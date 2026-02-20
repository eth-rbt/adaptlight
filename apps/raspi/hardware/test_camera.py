#!/usr/bin/env python3
"""
Test camera script for debugging vision issues.

Usage:
    python -m apps.raspi.hardware.test_camera
    python -m apps.raspi.hardware.test_camera --index 1
    python -m apps.raspi.hardware.test_camera --save
    python -m apps.raspi.hardware.test_camera --picamera  # Use Pi Camera (libcamera)
"""

import sys
import time


def test_picamera(save_frame: bool = False):
    """Test Pi Camera using picamera2 (libcamera stack)."""
    print("=" * 60)
    print("Pi Camera (picamera2/libcamera) Test")
    print("=" * 60)

    try:
        from picamera2 import Picamera2
        print("✅ picamera2 installed")
    except ImportError:
        print("❌ picamera2 not installed!")
        print("   Install with: sudo apt install python3-picamera2")
        return False

    try:
        # List cameras
        print("\n📷 Checking for Pi Cameras...")
        print("-" * 40)

        picam2 = Picamera2()
        camera_info = picam2.global_camera_info()

        if not camera_info:
            print("❌ No Pi Camera detected!")
            print("\nTroubleshooting:")
            print("  1. Check ribbon cable connection")
            print("  2. Enable camera: sudo raspi-config → Interface Options → Camera")
            print("  3. Test with: libcamera-hello")
            return False

        for i, cam in enumerate(camera_info):
            print(f"   Camera {i}: {cam}")

        # Configure camera
        print("\n🎬 Testing capture...")
        print("-" * 40)

        config = picam2.create_still_configuration(
            main={"size": (320, 240), "format": "RGB888"}
        )
        picam2.configure(config)
        picam2.start()

        # Wait for camera to warm up
        time.sleep(0.5)

        # Capture frames
        frames = []
        for i in range(5):
            frame = picam2.capture_array()
            if frame is not None:
                print(f"   Frame {i+1}: ✅ {frame.shape}")
                if len(frames) < 3:
                    frames.append(frame)
            else:
                print(f"   Frame {i+1}: ❌ Failed")
            time.sleep(0.1)

        picam2.stop()

        # Test base64 encoding
        if frames:
            print("\n🔄 Testing base64 encoding...")
            print("-" * 40)
            import cv2
            import base64

            # picamera2 returns RGB, OpenCV uses BGR
            frame_bgr = cv2.cvtColor(frames[0], cv2.COLOR_RGB2BGR)
            _, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
            base64_data = base64.b64encode(buffer).decode('utf-8')
            print(f"   ✅ Encoded frame: {len(base64_data)} chars")

            # Test HOG detector
            print("\n🧍 Testing HOG person detector...")
            print("-" * 40)

            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

            for i, frame in enumerate(frames[:3]):
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                boxes, weights = hog.detectMultiScale(
                    frame_bgr,
                    winStride=(8, 8),
                    padding=(8, 8),
                    scale=1.05
                )
                print(f"   Frame {i+1}: Found {len(boxes)} person(s)")

            # Save frame
            if save_frame:
                filename = "test_frame_picamera.jpg"
                cv2.imwrite(filename, frame_bgr)
                print(f"\n💾 Saved test frame to: {filename}")

        print("\n" + "=" * 60)
        print("✅ Pi Camera test complete!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_camera(camera_index: int = 0, save_frame: bool = False):
    """Test camera capture and display diagnostics."""

    print("=" * 60)
    print("Camera Diagnostic Test (OpenCV/V4L2)")
    print("=" * 60)

    # Check OpenCV
    try:
        import cv2
        print(f"✅ OpenCV version: {cv2.__version__}")
    except ImportError:
        print("❌ OpenCV not installed!")
        print("   Install with: pip install opencv-python-headless")
        return False

    # List available cameras
    print(f"\n📷 Testing camera index: {camera_index}")
    print("-" * 40)

    # Try to open camera
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"❌ Cannot open camera {camera_index}")
        print("\nTroubleshooting:")
        print("  1. Check if camera is connected: ls /dev/video*")
        print("  2. Check camera permissions: sudo usermod -a -G video $USER")
        print("  3. For Pi Camera (ribbon), use: --picamera")
        print("  4. Try different index: --index 1")

        # Try to list video devices
        print("\n🔍 Checking for video devices...")
        import subprocess
        try:
            result = subprocess.run(['ls', '-la', '/dev/'], capture_output=True, text=True)
            video_devices = [line for line in result.stdout.split('\n') if 'video' in line]
            if video_devices:
                print("   Found video devices:")
                for dev in video_devices:
                    print(f"   {dev}")
            else:
                print("   No /dev/video* devices found")
                print("\n💡 Hint: For Pi Camera Module, try: --picamera")
        except Exception as e:
            print(f"   Could not list devices: {e}")

        return False

    print(f"✅ Camera {camera_index} opened successfully")

    # Get camera properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    backend = cap.getBackendName()

    print(f"   Resolution: {width}x{height}")
    print(f"   FPS: {fps}")
    print(f"   Backend: {backend}")

    # Test frame capture
    print("\n🎬 Testing frame capture...")
    print("-" * 40)

    # Try multiple captures (first few might fail)
    success_count = 0
    fail_count = 0
    frames = []

    for i in range(10):
        ret, frame = cap.read()
        if ret and frame is not None:
            success_count += 1
            if len(frames) < 3:
                frames.append(frame)
            print(f"   Frame {i+1}: ✅ {frame.shape}")
        else:
            fail_count += 1
            print(f"   Frame {i+1}: ❌ Failed")
        time.sleep(0.1)

    print(f"\n   Success: {success_count}/10, Failed: {fail_count}/10")

    if success_count == 0:
        print("\n❌ Camera opened but cannot capture frames!")
        print("   This might be a driver or permission issue.")
        cap.release()
        return False

    # Test different resolutions
    print("\n📐 Testing resolutions...")
    print("-" * 40)

    resolutions = [
        (320, 240),
        (640, 480),
        (1280, 720),
    ]

    for w, h in resolutions:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        ret, frame = cap.read()
        if ret and frame is not None:
            actual_h, actual_w = frame.shape[:2]
            match = "✅" if (actual_w == w and actual_h == h) else "⚠️"
            print(f"   {w}x{h}: {match} Got {actual_w}x{actual_h}")
        else:
            print(f"   {w}x{h}: ❌ Failed")

    # Save a test frame
    if save_frame and frames:
        filename = f"test_frame_{camera_index}.jpg"
        cv2.imwrite(filename, frames[0])
        print(f"\n💾 Saved test frame to: {filename}")

    # Test base64 encoding (what vision runtime does)
    print("\n🔄 Testing base64 encoding...")
    print("-" * 40)

    if frames:
        import base64
        try:
            _, buffer = cv2.imencode('.jpg', frames[0], [cv2.IMWRITE_JPEG_QUALITY, 80])
            base64_data = base64.b64encode(buffer).decode('utf-8')
            data_url = f"data:image/jpeg;base64,{base64_data}"
            print(f"   ✅ Encoded frame: {len(data_url)} chars")
            print(f"   ✅ Data URL prefix: {data_url[:50]}...")
        except Exception as e:
            print(f"   ❌ Encoding failed: {e}")

    # Test HOG detector
    print("\n🧍 Testing HOG person detector...")
    print("-" * 40)

    if frames:
        try:
            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

            for i, frame in enumerate(frames[:3]):
                boxes, weights = hog.detectMultiScale(
                    frame,
                    winStride=(8, 8),
                    padding=(8, 8),
                    scale=1.05
                )
                print(f"   Frame {i+1}: Found {len(boxes)} person(s)")

        except Exception as e:
            print(f"   ❌ HOG detector failed: {e}")

    cap.release()
    print("\n" + "=" * 60)
    print("✅ Camera test complete!")
    print("=" * 60)

    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Test camera for vision')
    parser.add_argument('--index', '-i', type=int, default=0, help='Camera index (default: 0)')
    parser.add_argument('--save', '-s', action='store_true', help='Save test frame to file')
    parser.add_argument('--picamera', '-p', action='store_true', help='Use Pi Camera (picamera2/libcamera)')
    args = parser.parse_args()

    if args.picamera:
        success = test_picamera(save_frame=args.save)
    else:
        success = test_camera(camera_index=args.index, save_frame=args.save)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

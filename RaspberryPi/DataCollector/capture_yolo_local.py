"""Run on your PC: stream the Pi CSI camera over SSH and save JPEGs locally."""
import argparse
import base64
import math
import json
from datetime import datetime
from pathlib import Path
import queue
import shutil
import struct
import subprocess
import threading
import time


REMOTE_CODE = r'''
import io
import json
import signal
import struct
import sys
import time

# Keep camera logs off the binary SSH stream.
output = sys.stdout.buffer
sys.stdout = sys.stderr
from picamera2 import Picamera2
from libcamera import controls

width, height, fps, quality, shutter_us = map(int, sys.argv[1:6])
gain = float(sys.argv[6])
focus_mode = sys.argv[7]
lens_position = float(sys.argv[8])
camera = Picamera2()
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
signal.signal(signal.SIGHUP, lambda *_: sys.exit(0))
try:
    camera.configure(camera.create_video_configuration(
        main={"size": (width, height), "format": "RGB888"},
        controls={"FrameRate": fps},
        buffer_count=4,
    ))
    camera.options["quality"] = quality
    supports_af = "AfMode" in camera.camera_controls
    if supports_af:
        focus_controls = {"AfMode": {
            "once": controls.AfModeEnum.Auto,
            "continuous": controls.AfModeEnum.Continuous,
            "manual": controls.AfModeEnum.Manual,
        }[focus_mode]}
        if "AfRange" in camera.camera_controls:
            focus_controls["AfRange"] = controls.AfRangeEnum.Full
        if focus_mode == "manual":
            low, high, _ = camera.camera_controls["LensPosition"]
            if not low <= lens_position <= high:
                raise ValueError(f"Lens position must be in {low}..{high}")
            focus_controls["LensPosition"] = lens_position
        camera.set_controls(focus_controls)
    elif focus_mode == "manual":
        raise RuntimeError("Camera does not support software focus")
    camera.start()
    time.sleep(3)  # Focus with automatic exposure before applying a short shutter.
    if supports_af and focus_mode == "once":
        print("Focusing: keep an object stationary in the centre...", file=sys.stderr, flush=True)
        if not camera.autofocus_cycle():
            raise RuntimeError("Autofocus failed. Add light or use --focus manual --lens-position N")
        focused = camera.capture_metadata().get("LensPosition")
        if focused is None:
            raise RuntimeError("Camera did not report LensPosition")
        camera.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": focused})
        print(f"Focus locked | LensPosition: {focused:.3f}", file=sys.stderr, flush=True)
    if shutter_us:
        exposure_controls = {"ExposureTime": shutter_us, "AnalogueGain": gain}
        # New camera stacks have separate manual modes; older ones use AeEnable.
        if "ExposureTimeMode" in camera.camera_controls and "AnalogueGainMode" in camera.camera_controls:
            exposure_controls["ExposureTimeMode"] = controls.ExposureTimeModeEnum.Manual
            exposure_controls["AnalogueGainMode"] = controls.AnalogueGainModeEnum.Manual
        else:
            exposure_controls["AeEnable"] = False
        camera.set_controls(exposure_controls)
        print(f"Manual shutter: {shutter_us} us | gain: {gain}", file=sys.stderr, flush=True)
    time.sleep(1)
    metadata = camera.capture_metadata()
    print(f"Actual exposure: {metadata.get('ExposureTime')} us | "
          f"gain: {metadata.get('AnalogueGain')} | LensPosition: {metadata.get('LensPosition')}",
          file=sys.stderr, flush=True)
    while True:
        started = time.monotonic()
        buffer = io.BytesIO()
        metadata = camera.capture_file(buffer, format="jpeg")
        jpeg = buffer.getvalue()
        # A small JSON packet precedes each JPEG, keeping metadata tied to its image.
        details = json.dumps({key: metadata.get(key) for key in
                             ("ExposureTime", "AnalogueGain", "LensPosition", "AfState")}).encode()
        output.write(struct.pack("!I", len(details)))
        output.write(details)
        output.write(struct.pack("!I", len(jpeg)))
        output.write(jpeg)
        output.flush()
        time.sleep(max(0, 1 / fps - (time.monotonic() - started)))
except (BrokenPipeError, KeyboardInterrupt):
    pass
finally:
    camera.close()
'''


def read_exact(stream, size):
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            raise EOFError("SSH stream ended. Check the Pi error in the terminal.")
        data.extend(chunk)
    return bytes(data)


def receive_frames(stream, frames, errors):
    try:
        while True:
            metadata_size = struct.unpack("!I", read_exact(stream, 4))[0]
            if not 0 < metadata_size <= 16384:
                raise ValueError("Invalid camera metadata packet")
            metadata = json.loads(read_exact(stream, metadata_size))
            size = struct.unpack("!I", read_exact(stream, 4))[0]
            if not 0 < size <= 32 * 1024 * 1024:
                raise ValueError("Invalid JPEG packet. Check for extra SSH stdout output.")
            jpeg = read_exact(stream, size)
            frame = (time.monotonic(), time.time(), jpeg, metadata)
            # Show only the newest frame; avoid accumulating delayed images.
            try:
                frames.get_nowait()
            except queue.Empty:
                pass
            frames.put_nowait(frame)
    except Exception as exc:
        errors.put(exc)


def publish_live(directory, jpeg, received_at, metadata, settings):
    """Atomically replace one snapshot; MCP readers never see a half-written image."""
    snapshot = {"received_at": received_at, "camera": metadata, "settings": settings,
                "jpeg_base64": base64.b64encode(jpeg).decode("ascii")}
    temporary = directory / "latest.tmp"
    temporary.write_text(json.dumps(snapshot), encoding="utf-8")
    temporary.replace(directory / "latest.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="pi@192.168.1.175",
                        help="SSH user@hostname or SSH config alias (default: pi@192.168.1.175)")
    parser.add_argument("--output", required=True, type=Path, help="LOCAL dataset directory")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--identity", type=Path, help="Optional SSH private key")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--quality", type=int, default=95)
    parser.add_argument("--shutter-us", type=int, default=0,
                        help="Fixed exposure in microseconds; 0 = auto. Try 2000 for a moving belt")
    parser.add_argument("--gain", type=float, default=2.0,
                        help="Fixed analogue gain when --shutter-us is set (default: 2)")
    parser.add_argument("--focus", choices=("once", "continuous", "manual"), default="once",
                        help="Focus once and lock (default), continuously, or manually")
    parser.add_argument("--lens-position", type=float,
                        help="Manual focus in dioptres (approximately 1 / distance in metres)")
    parser.add_argument("--live-dir", type=Path, default=Path(__file__).resolve().parent / ".live",
                        help="Directory for the latest MCP snapshot (updated once per second)")
    parser.add_argument("--interval", type=float, default=0,
                        help="Auto-save every N seconds; 0 means manual capture")
    parser.add_argument("--no-preview", action="store_true", help="Requires --interval > 0")
    args = parser.parse_args()
    if args.host.startswith("-"):
        parser.error("Invalid SSH host")
    if args.focus == "manual" and args.lens_position is None:
        parser.error("--focus manual requires --lens-position")
    if args.lens_position is not None:
        if args.focus != "manual" or not math.isfinite(args.lens_position) or args.lens_position < 0:
            parser.error("Use a finite nonnegative --lens-position with --focus manual")
    if min(args.width, args.height, args.fps) <= 0 or not 1 <= args.quality <= 95:
        parser.error("Dimensions/FPS must be positive; quality must be 1..95")
    if args.shutter_us < 0 or not math.isfinite(args.gain) or args.gain < 1:
        parser.error("Shutter must be >= 0 and gain must be finite and >= 1")
    if args.shutter_us > 1_000_000 / args.fps:
        parser.error("Shutter must not exceed the frame duration (1000000 / fps)")
    if not math.isfinite(args.interval) or args.interval < 0 or (args.no_preview and args.interval == 0):
        parser.error("Use a positive --interval with --no-preview")
    if not shutil.which("ssh"):
        parser.error("ssh was not found. Install/enable the OpenSSH client on your PC.")

    try:
        import cv2
        import numpy as np
    except ImportError:
        parser.error("Run on your PC: python -m pip install opencv-python numpy")

    images = args.output.expanduser().resolve() / "images"
    images.mkdir(parents=True, exist_ok=True)
    live_dir = args.live_dir.expanduser().resolve()
    live_dir.mkdir(parents=True, exist_ok=True)
    settings = {"host": args.host, "fps_requested": args.fps, "shutter_us_requested": args.shutter_us,
                "gain_requested": args.gain, "focus": args.focus, "images_dir": str(images)}
    print(f"LOCAL images: {images}", flush=True)
    print("SPACE/S: save | A: toggle auto-save | Q/ESC: quit | Ctrl+C: quit", flush=True)

    encoded = base64.b64encode(REMOTE_CODE.encode()).decode("ascii")
    # The payload contains no shell-sensitive characters; it runs in RAM on the Pi.
    remote = ("python3 -u -c \"import base64;exec(base64.b64decode('"
              + encoded + "'))\" "
              + f"{args.width} {args.height} {args.fps} {args.quality} {args.shutter_us} {args.gain} "
              + f"{args.focus} {args.lens_position if args.lens_position is not None else -1}")
    command = ["ssh", "-T", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=10",
               "-o", "ServerAliveCountMax=3", "-p", str(args.port)]
    if args.identity:
        command.extend(["-i", str(args.identity.expanduser())])
    command.extend([args.host, remote])
    frames, errors = queue.Queue(maxsize=1), queue.Queue()
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    reader = threading.Thread(target=receive_frames, args=(process.stdout, frames, errors), daemon=True)
    reader.start()
    automatic = args.interval > 0
    interval = args.interval or 2.0
    last_saved = 0.0
    last_published = 0.0
    live_warning_shown = False
    last_received = time.monotonic()
    count = 0
    window = "Pi camera - save to LOCAL PC"
    try:
        if not args.no_preview:
            cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        while True:
            if not errors.empty():
                raise errors.get_nowait()
            try:
                received, received_at, jpeg, metadata = frames.get(timeout=0.1)
            except queue.Empty:
                if time.monotonic() - last_received > 60:
                    raise TimeoutError("No frame for 60s. Check SSH login and the Pi camera.")
                if not args.no_preview and cv2.waitKey(1) & 0xFF in (27, ord("q")):
                    break
                continue
            last_received = received
            if received - last_published >= 1.0:
                try:
                    publish_live(live_dir, jpeg, received_at, metadata, settings)
                    live_warning_shown = False
                except OSError as exc:
                    if not live_warning_shown:
                        print(f"MCP snapshot unavailable: {exc}", flush=True)
                        live_warning_shown = True
                last_published = received
            key = -1
            if not args.no_preview:
                preview = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if preview is None:
                    raise ValueError("Cannot decode JPEG received from Pi")
                cv2.putText(preview, f"Saved: {count} | Auto: {'ON' if automatic else 'OFF'}",
                            (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.imshow(window, preview)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")) or cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                    break
                if key == ord("a"):
                    automatic = not automatic
            now = time.monotonic()
            if key in (32, ord("s")) or (automatic and now - last_saved >= interval):
                filename = images / (datetime.now().strftime("img_%Y%m%d_%H%M%S_%f") + ".jpg")
                # Save the original JPEG, without text overlays or re-encoding.
                with filename.open("xb") as target:
                    target.write(jpeg)
                count += 1
                last_saved = now
                print(f"Saved {filename}", flush=True)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"Error: {exc}", flush=True)
        return 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        reader.join(timeout=2)
        if not reader.is_alive():
            process.stdout.close()
        if not args.no_preview:
            cv2.destroyAllWindows()
        print(f"Session saved {count} image(s) in {images}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

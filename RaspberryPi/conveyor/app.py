"""Điểm chạy UART và pipeline phân loại bằng camera Picamera2."""

import argparse
import sys
import time
from .config import load_config


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Conveyor UART diagnostics and Picamera2 sorting pipeline."
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--ping", action="store_true", help="Check STM32 communication only")
    action.add_argument("--start", action="store_true", help="Set STM32 to RUNNING and start conveyor motor")
    action.add_argument("--run", action="store_true", help="Run Picamera2 detection and send products to STM32")
    action.add_argument("--dashboard", action="store_true", help="Show statistics without opening camera or UART")
    parser.add_argument("--port", help="Serial device, for example /dev/ttyUSB0")
    parser.add_argument("--config", metavar="PATH", help="Path to the TOML configuration file")
    parser.add_argument("--debug-tracking", action="store_true", help="Log track IDs and normalized centers with --run")
    args = parser.parse_args(argv)

    if not args.ping and not args.start and not args.run and not args.dashboard:
        parser.print_help()
        return 0
    if args.port is None and args.config is None:
        parser.error("--config or --port is required with --ping, --start or --run")
    if args.port is not None and not args.port.strip():
        parser.error("--port must not be empty")
    if (args.run or args.dashboard) and args.config is None:
        parser.error("--config is required with --run or --dashboard")

    serial_options = {}
    protocol_options = {}
    if args.config is not None:
        try:
            config = load_config(args.config)
        except (OSError, ValueError) as exc:
            print(f"Config error: {exc}", file=sys.stderr)
            return 1
        settings = config["serial"]
        serial_options = {
            field: settings[field]
            for field in ("port", "baudrate", "read_timeout", "write_timeout")
        }
        protocol_options = {
            field: settings[field]
            for field in (
                "transaction_timeout", "frame_timeout", "max_attempts",
                "retry_delay", "temporary_status_delay",
            )
        }
    # Command-line port takes precedence over the validated file configuration.
    if args.port is not None:
        serial_options["port"] = args.port

    if args.dashboard:
        from .dashboard.runtime import Runtime
        try:
            with Runtime(config, history_only=True) as runtime:
                runtime.web.wait()
        except KeyboardInterrupt:
            return 130
        except Exception as exc:
            print(f"Dashboard failed: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.run:
        try:
            run_pipeline(config, serial_options, protocol_options, debug_tracking=args.debug_tracking)
        except KeyboardInterrupt:
            return 130
        except Exception as exc:
            print(f"Pipeline failed: {exc}", file=sys.stderr)
            return 1
        return 0
    #Run ping or start
    import serial
    from .communication.protocol import Command, ProtocolError, Status, UartProtocol
    from .communication.serial_link import UartLink

    try:
        with UartLink(**serial_options) as uart:
            command = Command.START if args.start else Command.PING
            response = UartProtocol(uart, **protocol_options).exchange(command)
    except (ProtocolError, serial.SerialException, OSError) as exc:
        print(f"UART command failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130

    expected = Status.ACK if args.start else Status.PONG
    if response.status != expected:
        print(f"Unexpected STM32 status: {response.status.name}", file=sys.stderr)
        return 1
    if args.start:
        print(f"STM32 START ACK: RUNNING; motor LPWM enabled (sequence={response.sequence})")
    else:
        print(f"STM32 PONG (sequence={response.sequence})")
    return 0


def run_pipeline(config, serial_options, protocol_options, *, debug_tracking=False):
    from .dashboard.runtime import Runtime

    with Runtime(config) as runtime:
        try:
            return _run_pipeline(config, serial_options, protocol_options, runtime,
                                 debug_tracking=debug_tracking)
        except KeyboardInterrupt:
            runtime.camera_state(False, "Camera đã dừng")
            raise
        except BaseException as exc:
            runtime.camera_state(False, f"Pipeline lỗi: {exc}")
            raise


def _run_pipeline(config, serial_options, protocol_options, runtime, *, debug_tracking=False):
    """Nối các thành phần; chỉ import vision khi chạy --run trên Pi."""
    from .vision.camera import Camera
    from .communication.protocol import Command, Status, UartProtocol
    from .communication.serial_link import UartLink
    from .communication.sender import Sender
    from .vision.detector import Detector
    from .vision.tracker import Tracker
    from .vision.crossing import CrossingDetector

    crossing_settings = config.get("crossing")
    sender_settings = config.get("sender")
    if not isinstance(crossing_settings, dict) or not isinstance(sender_settings, dict):
        raise ValueError("--run requires crossing and sender configuration tables")
    crossing = CrossingDetector(
        axis=crossing_settings.get("axis"),
        position=crossing_settings.get("position"),
        direction=crossing_settings.get("direction"),
    )
    tracker_settings = config.get("tracker", {})
    if not isinstance(tracker_settings, dict):
        raise ValueError("tracker must be a configuration table")
    tracker = Tracker(
        max_distance_px=tracker_settings.get("max_distance_px", 80.0),
        max_age_seconds=tracker_settings.get("max_age_seconds", 0.5),
    )
    settings = config.get("detector", {})
    detector = Detector(settings.get("model"), settings.get("confidence"), settings.get("imgsz"))

    def on_result(event, response, error):
        outcome = "accepted" if error is None else "unknown"
        if error is not None and response is not None:
            outcome = "rejected"
        runtime.store.result(event, outcome, response=response, error=error)
        if error is not None:
            print(f"UART ERROR track={event.track_id}: {error}", file=sys.stderr, flush=True)
        else:
            print(f"STM32 ACK track={event.track_id} label={event.label} "
                  f"sequence={response.sequence} (accepted, not confirmed sorted)", flush=True)

    with UartLink(**serial_options) as uart:
        protocol = UartProtocol(uart, **protocol_options)
        if protocol.exchange(Command.PING).status != Status.PONG:
            raise RuntimeError("STM32 did not return PONG")
        sender = Sender(protocol, on_result, queue_capacity=sender_settings.get("queue_capacity"))
        settings = config["camera"]
        camera = Camera(settings["width"], settings["height"], settings["fps"])
        start_attempted = False
        unsent = {}
        try:
            camera.start()
            # Thử camera và warmup model trước khi START làm motor quay.
            frame, _ = camera.read()
            detector.predict(frame, color_order=camera.color_order)
            runtime.camera_state(True, "Camera đang hoạt động")

            start_attempted = True
            if protocol.exchange(Command.START).status != Status.ACK:
                raise RuntimeError("STM32 rejected START; check FSM state")
            sender.start()
            print("Pipeline RUNNING; Ctrl+C exits. Motor STOP remains debugger command 3.", flush=True)
            while True:
                runtime.check()
                if sender.failure.is_set():
                    raise RuntimeError(f"UART sender failed: {sender.error}")
                frame, observed_at = camera.read()
                started = time.monotonic()
                detections = detector.predict(frame, color_order=camera.color_order)
                inference_ms = (time.monotonic() - started) * 1000
                if sender.failure.is_set():
                    raise RuntimeError(f"UART sender failed: {sender.error}")
                tracks = tracker.update(detections, observed_at)
                height, width = frame.shape[:2]
                if debug_tracking:
                    if not tracks:
                        print(f"TRACK time={observed_at:.3f} none", flush=True)
                    for track in tracks:
                        x1, y1, x2, y2 = track.detection.xyxy
                        center_x = (x1 / 2 + x2 / 2) / width
                        center_y = (y1 / 2 + y2 / 2) / height
                        print(f"TRACK time={observed_at:.3f} id={track.track_id} "
                              f"label={track.detection.label} confidence={track.detection.confidence:.2f} "
                              f"x={center_x:.3f} y={center_y:.3f} "
                              f"line={crossing.axis}:{crossing.position} direction={crossing.direction}",
                              flush=True)
                events = crossing.update(tracks, frame_width=width, frame_height=height)
                # Ghi toàn bộ quả trong frame trước khi submit có thể báo queue đầy.
                for event in events:
                    runtime.store.record(event)
                    unsent[event.track_id] = event
                for event in events:
                    print(f"CROSS track={event.track_id} label={event.label} "
                          f"confidence={event.confidence:.2f}", flush=True)
                    sender.submit(event)
                    unsent.pop(event.track_id)
                runtime.frame(frame, detections, (crossing.axis, crossing.position), camera.color_order)
                print(f"FRAME tracks={len(tracks)} inference_ms={inference_ms:.0f}", flush=True)
        finally:
            # Hoàn tất giao dịch đang chạy trước khi đóng cổng UART.
            try:
                sender.stop()
                for event in (*sender.pending_events, *unsent.values()):
                    runtime.store.result(event, "not_sent", error="Pipeline stopped before sending")
                    print(f"NOT SENT track={event.track_id} label={event.label}",
                          file=sys.stderr, flush=True)
            finally:
                runtime.camera_state(False, "Camera đã dừng")
                camera.close()
                if start_attempted:
                    print("Pi pipeline stopped; use STM32 debugger command 3 to stop motor.",
                          file=sys.stderr, flush=True)

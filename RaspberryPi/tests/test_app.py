import contextlib
import io
import tempfile
import threading
import tomllib
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import serial

from conveyor.app import main, run_pipeline
from conveyor.events import Detection
from conveyor.communication.protocol import Command, Response, Status


class AppTests(unittest.TestCase):
    def test_run_requires_config(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(["--run", "--port", "test-port"])
        self.assertEqual(caught.exception.code, 2)

    @patch("conveyor.app.run_pipeline")
    def test_run_dispatches_and_reports_errors(self, pipeline):
        path = Path(__file__).resolve().parents[1] / "config.example.toml"
        for error, expected in ((None, 0), (RuntimeError("camera failed"), 1),
                                (KeyboardInterrupt(), 130)):
            with self.subTest(error=error):
                pipeline.reset_mock()
                pipeline.side_effect = error
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(["--run", "--config", str(path)]), expected)
                pipeline.assert_called_once()

    def test_no_arguments_only_shows_help(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main([]), 0)
        self.assertIn("--ping", output.getvalue())

    def test_ping_requires_port(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(["--ping"])
        self.assertEqual(caught.exception.code, 2)

    @patch("conveyor.communication.serial_link.UartLink")
    @patch("conveyor.communication.protocol.UartProtocol")
    def test_ping_success_closes_transport(self, protocol, link):
        protocol.return_value.exchange.return_value = Response(0, Status.PONG)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            with patch.dict("sys.modules", {"ultralytics": None, "torch": None, "numpy": None}):
                self.assertEqual(main(["--ping", "--port", "test-port"]), 0)
        link.assert_called_once_with(port="test-port")
        protocol.assert_called_once_with(link.return_value.__enter__.return_value)
        protocol.return_value.exchange.assert_called_once_with(Command.PING)
        link.return_value.__exit__.assert_called_once()
        self.assertIn("PONG", output.getvalue())

    @patch("conveyor.communication.serial_link.UartLink")
    @patch("conveyor.communication.protocol.UartProtocol")
    def test_start_requires_ack(self, protocol, link):
        for status, expected in ((Status.ACK, 0), (Status.NOT_READY, 1)):
            with self.subTest(status=status):
                protocol.reset_mock()
                protocol.return_value.exchange.return_value = Response(0, status)
                with contextlib.redirect_stdout(io.StringIO()):
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(main(["--start", "--port", "test-port"]), expected)
                protocol.return_value.exchange.assert_called_once_with(Command.START)

    def test_ping_and_start_are_mutually_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(["--ping", "--start", "--port", "test-port"])
        self.assertEqual(caught.exception.code, 2)

    @patch("conveyor.communication.serial_link.UartLink")
    def test_open_failure_returns_error(self, link):
        link.return_value.__enter__.side_effect = serial.SerialException("missing port")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--ping", "--port", "missing"]), 1)

    @patch("conveyor.communication.serial_link.UartLink")
    @patch("conveyor.communication.protocol.UartProtocol")
    def test_config_values_and_cli_port_override(self, protocol, link):
        example = Path(__file__).resolve().parents[1] / "config.example.toml"
        text = example.read_text(encoding="utf-8").replace(
            "transaction_timeout = 0.1", "transaction_timeout = 0.7"
        ).replace("max_attempts = 3", "max_attempts = 5")
        settings = tomllib.loads(text)["serial"]
        protocol.return_value.exchange.return_value = Response(0, Status.PONG)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(text, encoding="utf-8")
            for override in (None, "override-port"):
                with self.subTest(override=override):
                    link.reset_mock()
                    protocol.reset_mock()
                    argv = ["--ping", "--config", str(path)]
                    if override is not None:
                        argv += ["--port", override]
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(main(argv), 0)
                    link.assert_called_once_with(
                        port=override or settings["port"], baudrate=settings["baudrate"],
                        read_timeout=settings["read_timeout"], write_timeout=settings["write_timeout"],
                    )
                    protocol.assert_called_once_with(
                        link.return_value.__enter__.return_value,
                        **{field: settings[field] for field in (
                            "transaction_timeout", "frame_timeout", "max_attempts",
                            "retry_delay", "temporary_status_delay",
                        )},
                    )
                    link.return_value.__exit__.assert_called_once()

    @patch("conveyor.communication.serial_link.UartLink")
    def test_config_error_never_opens_uart(self, link):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            for text in (None, "[serial", "[serial]\nport = 123"):
                with self.subTest(text=text):
                    if text is not None:
                        path.write_text(text, encoding="utf-8")
                    with contextlib.redirect_stderr(io.StringIO()) as output:
                        self.assertEqual(main([
                            "--ping", "--config", str(path), "--port", "override",
                        ]), 1)
                    self.assertIn("Config error", output.getvalue())
                    link.assert_not_called()

    @patch("conveyor.communication.serial_link.UartLink")
    def test_help_never_opens_uart(self, link):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(["--help"])
        self.assertEqual(caught.exception.code, 0)
        link.assert_not_called()

    def test_blank_cli_port_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(["--ping", "--port", "   "])
        self.assertEqual(caught.exception.code, 2)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "config.example.toml"
        self.config = tomllib.loads(path.read_text(encoding="utf-8"))
        self.camera_class = MagicMock()
        self.camera = self.camera_class.return_value
        self.protocol = MagicMock()
        self.detector = MagicMock()
        self.link = MagicMock()
        self.enterContext(patch.dict("sys.modules", {
            "picamera2": types.SimpleNamespace(Picamera2=self.camera_class),
        }))
        self.enterContext(patch("conveyor.communication.protocol.UartProtocol",
                                 return_value=self.protocol))
        self.enterContext(patch("conveyor.communication.serial_link.UartLink", self.link))
        self.detector_class = self.enterContext(patch(
            "conveyor.vision.detector.Detector", return_value=self.detector))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def request(self, timestamp):
        request = MagicMock()
        request.get_metadata.return_value = {"SensorTimestamp": timestamp}
        request.make_array.return_value.copy.return_value.shape = (100, 100, 3)
        return request

    def run_pipeline(self):
        return run_pipeline(self.config, {"port": "test-port"}, {})

    def test_real_tracking_crossing_sender_for_three_labels(self):
        done = threading.Event()
        products = []
        def exchange(command):
            if command == Command.PING:
                return Response(0, Status.PONG)
            if command == Command.START:
                return Response(1, Status.ACK)
            products.append(command)
            if len(products) == 3:
                done.set()
            return Response(len(products) + 1, Status.ACK)
        self.protocol.exchange.side_effect = exchange
        requests = [self.request(t) for t in (1_000_000_000, 1_100_000_000, 1_200_000_000)]
        remaining = iter(requests)
        def capture():
            request = next(remaining, None)
            if request is not None:
                return request
            if not done.wait(2):
                raise AssertionError("Expected all three product commands")
            raise KeyboardInterrupt()
        self.camera.capture_request.side_effect = capture
        frames = [[]]  # Warmup không phát sự kiện.
        for x in (30, 60):
            detections = []
            for label, y in zip(("green", "riped", "damaged"), (15, 45, 75)):
                detections.append(Detection((x-5, y-5, x+5, y+5), 0, label, .9))
            frames.append(detections)
        self.detector.predict.side_effect = frames
        with self.assertRaises(KeyboardInterrupt):
            self.run_pipeline()
        self.assertEqual(products, [Command.UNRIPE, Command.RIPE, Command.SPOILED])
        self.assertEqual([call.args[0] for call in self.protocol.exchange.call_args_list[:2]],
                         [Command.PING, Command.START])
        self.assertTrue(all(call.kwargs == {"color_order": "BGR"}
                            for call in self.detector.predict.call_args_list))
        for request in requests:
            request.release.assert_called_once()
        self.camera.close.assert_called_once()
        self.link.return_value.__exit__.assert_called_once()

    def test_model_failure_never_opens_uart(self):
        self.detector_class.side_effect = FileNotFoundError("missing weights")
        with self.assertRaises(FileNotFoundError):
            self.run_pipeline()
        self.link.assert_not_called()

    def test_bad_timestamp_releases_request_and_never_starts_motor(self):
        self.protocol.exchange.return_value = Response(0, Status.PONG)
        request = self.request(0)
        self.camera.capture_request.return_value = request
        with self.assertRaises(ValueError):
            self.run_pipeline()
        self.protocol.exchange.assert_called_once_with(Command.PING)
        request.release.assert_called_once()
        self.camera.close.assert_called_once()

    def test_start_rejected_closes_camera_and_uart(self):
        self.protocol.exchange.side_effect = [Response(0, Status.PONG), Response(1, Status.NOT_READY)]
        self.camera.capture_request.return_value = self.request(1_000_000_000)
        with self.assertRaisesRegex(RuntimeError, "START"):
            self.run_pipeline()
        self.camera.close.assert_called_once()
        self.link.return_value.__exit__.assert_called_once()

    def test_sender_failure_stops_next_capture(self):
        self.protocol.exchange.side_effect = [Response(0, Status.PONG), Response(1, Status.ACK)]
        self.camera.capture_request.return_value = self.request(1_000_000_000)
        with patch("conveyor.communication.sender.Sender") as sender:
            sender.return_value.failure.is_set.return_value = True
            sender.return_value.pending_events = ()
            sender.return_value.error = RuntimeError("UART timeout")
            with self.assertRaisesRegex(RuntimeError, "UART timeout"):
                self.run_pipeline()
            sender.return_value.stop.assert_called_once()
        self.assertEqual(self.camera.capture_request.call_count, 1)
        self.camera.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

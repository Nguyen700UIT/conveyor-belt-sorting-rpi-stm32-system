import contextlib
import io
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

import serial

from conveyor.app import main
from conveyor.communication.protocol import Command, Response, Status


class AppTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

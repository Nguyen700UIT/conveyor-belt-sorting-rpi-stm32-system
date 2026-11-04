import contextlib
import io
import unittest
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
            self.assertEqual(main(["--ping", "--port", "test-port"]), 0)
        link.assert_called_once_with("test-port")
        protocol.return_value.exchange.assert_called_once_with(Command.PING)
        link.return_value.__exit__.assert_called_once()
        self.assertIn("PONG", output.getvalue())

    @patch("conveyor.communication.serial_link.UartLink")
    def test_open_failure_returns_error(self, link):
        link.return_value.__enter__.side_effect = serial.SerialException("missing port")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--ping", "--port", "missing"]), 1)


if __name__ == "__main__":
    unittest.main()

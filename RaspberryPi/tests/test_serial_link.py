import unittest
from unittest.mock import MagicMock, patch

from conveyor.communication.serial_link import UartLink


class SerialLinkTests(unittest.TestCase):
    @patch("conveyor.communication.serial_link.serial.Serial")
    def test_context_opens_8n1_and_closes_on_exception(self, factory):
        with self.assertRaises(RuntimeError):
            with UartLink("test-port") as uart:
                self.assertTrue(uart.is_open)
                raise RuntimeError("test shutdown")
        factory.assert_called_once_with(
            port="test-port", baudrate=115200, bytesize=8, parity="N", stopbits=1,
            timeout=0.1, write_timeout=1.0,
        )
        factory.return_value.close.assert_called_once()
        self.assertFalse(uart.is_open)

    def test_temporary_read_timeout_is_restored_even_on_error(self):
        uart = UartLink("test-port")
        uart._serial = MagicMock(is_open=True, timeout=0.1)
        uart._serial.read.side_effect = OSError("read failed")
        with self.assertRaises(OSError):
            uart.receive(timeout=0.02)
        self.assertEqual(uart._serial.timeout, 0.1)


if __name__ == "__main__":
    unittest.main()

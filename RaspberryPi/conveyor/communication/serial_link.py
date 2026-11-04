"""Byte-level serial I/O for Raspberry Pi UART adapters such as CP2102."""

import serial


class UartLink:
    def __init__(self, port, baudrate=115200, read_timeout=0.1, write_timeout=1.0):
        self.port = port
        self.baudrate = baudrate
        self.read_timeout = read_timeout
        self.write_timeout = write_timeout
        self._serial = None

    @property
    def is_open(self):
        return self._serial is not None and self._serial.is_open

    def open(self):
        if self.is_open:
            return

        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.read_timeout,
            write_timeout=self.write_timeout,
        )

    def close(self):
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def send(self, data):
        if not self.is_open:
            raise serial.PortNotOpenError()

        payload = bytes(data)
        if not payload:
            return 0

        written = self._serial.write(payload)
        self._serial.flush()
        return written

    def receive(self, max_length=1, timeout=None):
        if not self.is_open:
            raise serial.PortNotOpenError()
        if max_length <= 0:
            raise ValueError("max_length must be greater than zero")

        if timeout is None:
            return self._serial.read(max_length)
        if timeout < 0:
            raise ValueError("timeout must not be negative")
        if timeout == 0:
            return b""

        previous_timeout = self._serial.timeout
        try:
            self._serial.timeout = timeout
            return self._serial.read(max_length)
        finally:
            self._serial.timeout = previous_timeout

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

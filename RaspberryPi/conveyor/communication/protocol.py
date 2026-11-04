"""Pi-side framing, CRC, sequence handling, and stop-and-wait transactions."""

from dataclasses import dataclass
from enum import IntEnum
import threading
import time

import serial


SOF_REQUEST = 0xA5
SOF_RESPONSE = 0x5A
FRAME_SIZE = 4
CRC_POLYNOMIAL = 0x07


class Command(IntEnum):
    PING = 0x01
    UNRIPE = 0x02
    RIPE = 0x03
    SPOILED = 0x04


class Status(IntEnum):
    PONG = 0x00
    ACK = 0x01
    FULL = 0x02
    NOT_READY = 0x03
    BAD_CMD = 0x04


@dataclass(frozen=True)
class Response:
    sequence: int
    status: Status


class ProtocolError(Exception):
    """Base error for Pi-side protocol transactions."""


class TransportError(ProtocolError):
    """The serial device could not send or receive data."""


class TransactionTimeout(ProtocolError):
    """No valid response arrived after the configured transmission attempts."""


class UncertainTransaction(ProtocolError):
    """A previous transaction has an unknown result and blocks new commands."""


def crc8_atm(data):
    crc = 0x00
    for value in data:
        crc ^= value
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ CRC_POLYNOMIAL) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def build_request(sequence, command):
    if not 0 <= sequence <= 0xFF:
        raise ValueError("sequence must be in range 0..255")

    command = Command(command)
    frame = bytes((SOF_REQUEST, sequence, command))
    return frame + bytes((crc8_atm(frame),))


def decode_response(frame):
    frame = bytes(frame)
    if len(frame) != FRAME_SIZE:
        return None
    if frame[0] != SOF_RESPONSE or crc8_atm(frame[:3]) != frame[3]:
        return None

    try:
        status = Status(frame[2])
    except ValueError:
        return None

    return Response(sequence=frame[1], status=status)


class UartProtocol:
    """Protocol layer over conveyor.communication.serial_link's byte API."""

    def __init__(
        self,
        uart,
        initial_sequence=0,
        transaction_timeout=0.1,
        frame_timeout=0.02,
        max_attempts=3,
        retry_delay=0.02,
        temporary_status_delay=0.1,
    ):
        if not 0 <= initial_sequence <= 0xFF:
            raise ValueError("initial_sequence must be in range 0..255")
        if transaction_timeout <= 0 or frame_timeout <= 0 or max_attempts < 1:
            raise ValueError("timeouts and max_attempts must be positive")

        self.uart = uart
        self.sequence = initial_sequence
        self.transaction_timeout = transaction_timeout
        self.frame_timeout = frame_timeout
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        self.temporary_status_delay = temporary_status_delay
        self._uncertain_command = None
        self._transaction_lock = threading.Lock()

    def exchange(self, command):
        if not self._transaction_lock.acquire(blocking=False):
            raise ProtocolError("Only one UART transaction may be active at a time")

        try:
            return self._exchange(command)
        finally:
            self._transaction_lock.release()

    def _exchange(self, command):
        command = Command(command)

        if self._uncertain_command is not None:
            raise UncertainTransaction(
                "Previous transaction result is unknown; do not send a new command"
            )

        frame = build_request(self.sequence, command)
        last_response = None

        for attempt in range(self.max_attempts):
            try:
                written = self.uart.send(frame)
            except (serial.SerialException, OSError) as exc:
                self._uncertain_command = command
                raise TransportError("UART write failed; transaction result is unknown") from exc

            if written != FRAME_SIZE:
                self._uncertain_command = command
                raise TransportError("UART write was incomplete; transaction result is unknown")

            deadline = time.monotonic() + self.transaction_timeout
            try:
                response = self._read_response(deadline, command)
            except (serial.SerialException, OSError) as exc:
                self._uncertain_command = command
                raise TransportError("UART read failed; transaction result is unknown") from exc

            if response is None:
                if attempt + 1 < self.max_attempts:
                    time.sleep(self.retry_delay)
                    continue

                self._uncertain_command = command
                raise TransactionTimeout(
                    "No valid response after retries; transaction result is unknown"
                )

            last_response = response
            if response.status in (Status.ACK, Status.PONG, Status.BAD_CMD):
                if response.status in (Status.ACK, Status.PONG):
                    self.sequence = (self.sequence + 1) & 0xFF
                return response

            if attempt + 1 < self.max_attempts:
                time.sleep(self.temporary_status_delay)

        return last_response

    def _read_response(self, deadline, command):
        frame = bytearray()
        frame_deadline = None

        while True:
            now = time.monotonic()
            if now >= deadline:
                return None

            if frame and frame_deadline is not None and now >= frame_deadline:
                frame.clear()
                frame_deadline = None

            read_deadline = deadline
            if frame_deadline is not None:
                read_deadline = min(read_deadline, frame_deadline)
            read_timeout = min(self.uart.read_timeout, max(0.0, read_deadline - now))
            chunk = self.uart.receive(1, timeout=read_timeout)
            if not chunk:
                continue

            now = time.monotonic()
            if now >= deadline:
                return None
            if frame and frame_deadline is not None and now >= frame_deadline:
                frame.clear()
                frame_deadline = None

            value = chunk[0]
            frame.append(value)

            while frame:
                sof_index = frame.find(SOF_RESPONSE)
                if sof_index < 0:
                    frame.clear()
                    frame_deadline = None
                    break
                if sof_index > 0:
                    del frame[:sof_index]
                    frame_deadline = now + self.frame_timeout
                if len(frame) < FRAME_SIZE:
                    if frame_deadline is None:
                        frame_deadline = now + self.frame_timeout
                    break

                response = decode_response(frame[:FRAME_SIZE])
                if response is not None and response.sequence == self.sequence:
                    is_ping = command == Command.PING
                    status_matches_command = (
                        response.status in (Status.PONG, Status.BAD_CMD)
                        if is_ping
                        else response.status != Status.PONG
                    )
                    if status_matches_command:
                        return response

                del frame[0]
                frame_deadline = (
                    now + self.frame_timeout
                    if SOF_RESPONSE in frame
                    else None
                )

        return None

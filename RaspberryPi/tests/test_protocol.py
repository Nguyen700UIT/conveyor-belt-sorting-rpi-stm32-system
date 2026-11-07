"""Protocol regression checks using byte I/O, without a serial device."""

import unittest
from unittest.mock import patch

from conveyor.communication.protocol import (
    Command, Status, UartProtocol, TransactionTimeout, TransportError,
    UncertainTransaction, build_request, crc8_atm, decode_response,
)


def response(sequence, status):
    body = bytes((0x5A, sequence, status))
    return body + bytes((crc8_atm(body),))


class FakeUart:
    read_timeout = 0.1

    def __init__(self, replies):
        self.replies = iter(replies)
        self.incoming = bytearray()
        self.sent = []

    def send(self, data):
        self.sent.append(bytes(data))
        self.incoming.extend(next(self.replies, b""))
        return len(data)

    def receive(self, max_length=1, timeout=None):
        data = bytes(self.incoming[:max_length])
        del self.incoming[:max_length]
        return data


class ProtocolTests(unittest.TestCase):
    def test_crc_known_vector_and_request(self):
        self.assertEqual(crc8_atm(b"123456789"), 0xF4)
        self.assertEqual(build_request(0, Command.PING), bytes.fromhex("a5 00 01 8f"))
        for sequence in (-1, 256):
            with self.assertRaises(ValueError):
                build_request(sequence, Command.PING)
        with self.assertRaises(ValueError):
            build_request(0, 99)

    def test_decode_rejects_corrupt_and_unknown_status(self):
        valid = response(7, Status.ACK)
        self.assertEqual(decode_response(valid).sequence, 7)
        self.assertIsNone(decode_response(valid[:-1]))
        self.assertIsNone(decode_response(valid[:-1] + bytes((valid[-1] ^ 1,))))
        self.assertIsNone(decode_response(response(7, 99)))

    def test_ping_and_sequence_wrap(self):
        uart = FakeUart([response(255, Status.PONG)])
        protocol = UartProtocol(uart, initial_sequence=255)
        self.assertEqual(protocol.exchange(Command.PING).status, Status.PONG)
        self.assertEqual(protocol.sequence, 0)

    def test_start_retries_same_frame_and_accepts_ack(self):
        uart = FakeUart([response(0, Status.NOT_READY), response(0, Status.ACK)])
        protocol = UartProtocol(uart, temporary_status_delay=0)
        self.assertEqual(Command.START, 0x05)
        self.assertEqual(protocol.exchange(Command.START).status, Status.ACK)
        self.assertEqual(uart.sent, [build_request(0, Command.START)] * 2)
        self.assertEqual(protocol.sequence, 1)

    def test_parser_skips_noise_corruption_and_wrong_sequence(self):
        corrupt = bytearray(response(0, Status.ACK))
        corrupt[-1] ^= 1
        uart = FakeUart([b"noise" + corrupt + response(1, Status.ACK)
                         + response(0, Status.PONG) + response(0, Status.ACK)])
        protocol = UartProtocol(uart)
        self.assertEqual(protocol.exchange(Command.RIPE).status, Status.ACK)
        self.assertEqual(protocol.sequence, 1)

    def test_temporary_statuses_retry_identical_frame(self):
        uart = FakeUart([response(0, Status.FULL), response(0, Status.NOT_READY),
                         response(0, Status.ACK)])
        protocol = UartProtocol(uart, temporary_status_delay=0)
        self.assertEqual(protocol.exchange(Command.UNRIPE).status, Status.ACK)
        self.assertEqual(uart.sent, [build_request(0, Command.UNRIPE)] * 3)
        self.assertEqual(protocol.sequence, 1)

    def test_full_exhaustion_does_not_advance_sequence(self):
        uart = FakeUart([response(0, Status.FULL)] * 3)
        protocol = UartProtocol(uart, temporary_status_delay=0)
        self.assertEqual(protocol.exchange(Command.RIPE).status, Status.FULL)
        self.assertEqual(protocol.sequence, 0)

    def test_timeout_retries_then_blocks_new_command(self):
        uart = FakeUart([])
        protocol = UartProtocol(uart, retry_delay=0)
        # Deterministic deadline progression, without real sleeping or hardware.
        with patch("conveyor.communication.protocol.time.monotonic",
                   side_effect=(0, 1, 2, 3, 4, 5)):
            with self.assertRaises(TransactionTimeout):
                protocol.exchange(Command.SPOILED)
        self.assertEqual(uart.sent, [build_request(0, Command.SPOILED)] * 3)
        with self.assertRaises(UncertainTransaction):
            protocol.exchange(Command.RIPE)
        self.assertEqual(len(uart.sent), 3)

    def test_timeout_retry_can_receive_ack(self):
        uart = FakeUart([b"", response(0, Status.ACK)])
        protocol = UartProtocol(uart, retry_delay=0)
        with patch("conveyor.communication.protocol.time.monotonic") as clock:
            clock.side_effect = [0, 1, 2] + [2.01] * 8
            self.assertEqual(protocol.exchange(Command.RIPE).status, Status.ACK)
        self.assertEqual(uart.sent, [build_request(0, Command.RIPE)] * 2)

    def test_short_write_blocks_new_command(self):
        uart = FakeUart([])
        with patch.object(uart, "send", return_value=2):
            protocol = UartProtocol(uart)
            with self.assertRaises(TransportError):
                protocol.exchange(Command.RIPE)
            with self.assertRaises(UncertainTransaction):
                protocol.exchange(Command.RIPE)


if __name__ == "__main__":
    unittest.main()

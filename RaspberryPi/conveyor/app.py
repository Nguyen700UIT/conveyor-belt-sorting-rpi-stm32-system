"""Application entrypoint; currently provides a non-actuating UART check."""

import argparse
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Conveyor UART diagnostics. Vision pipeline is not implemented yet."
    )
    parser.add_argument("--ping", action="store_true", help="Check STM32 communication only")
    parser.add_argument("--port", help="Serial device, for example /dev/ttyUSB0")
    args = parser.parse_args(argv)
    if not args.ping:
        parser.print_help()
        return 0
    if not args.port:
        parser.error("--port is required with --ping")

    import serial
    from .communication.protocol import Command, ProtocolError, Status, UartProtocol
    from .communication.serial_link import UartLink

    try:
        with UartLink(args.port) as uart:
            response = UartProtocol(uart).exchange(Command.PING)
    except (ProtocolError, serial.SerialException, OSError) as exc:
        print(f"UART check failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130

    if response.status != Status.PONG:
        print(f"Unexpected STM32 status: {response.status.name}", file=sys.stderr)
        return 1
    print(f"STM32 PONG (sequence={response.sequence})")
    return 0

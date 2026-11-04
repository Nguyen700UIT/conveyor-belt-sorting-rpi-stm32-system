"""Application entrypoint; currently provides a non-actuating UART check."""

import argparse
import sys
from .config import load_config


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Conveyor UART diagnostics. Vision pipeline is not implemented yet."
    )
    parser.add_argument("--ping", action="store_true", help="Check STM32 communication only")
    parser.add_argument("--port", help="Serial device, for example /dev/ttyUSB0")
    parser.add_argument("--config", metavar="PATH", help="Path to the TOML configuration file")
    args = parser.parse_args(argv)

    if not args.ping:
        parser.print_help()
        return 0
    if args.port is None and args.config is None:
        parser.error("--config or --port is required with --ping")
    if args.port is not None and not args.port.strip():
        parser.error("--port must not be empty")

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

    import serial
    from .communication.protocol import Command, ProtocolError, Status, UartProtocol
    from .communication.serial_link import UartLink

    try:
        with UartLink(**serial_options) as uart:
            response = UartProtocol(uart, **protocol_options).exchange(Command.PING)
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

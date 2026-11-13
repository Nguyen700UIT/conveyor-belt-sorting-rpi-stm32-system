import tomllib
import math
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def load_config(path):
    with open(path, "rb") as file:
        config = tomllib.load(file)

    # Validate settings before the application opens devices or loads the model.
    serial_config = config.get("serial")
    if not isinstance(serial_config, dict):
        raise ValueError("serial must be a TOML table")

    port = serial_config.get("port")
    if not isinstance(port, str) or not port.strip():
        raise ValueError("serial.port must be a non-empty string")

    baudrate = serial_config.get("baudrate")
    if type(baudrate) is not int or baudrate != 115200:
        raise ValueError("serial.baudrate must be the integer 115200")

    max_attempts = serial_config.get("max_attempts")
    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError("serial.max_attempts must be a positive integer")

    for field in (
        "read_timeout", "write_timeout", "transaction_timeout", "frame_timeout",
        "retry_delay", "temporary_status_delay",
    ):
        value = serial_config.get(field)
        if type(value) not in (int, float) or (
            type(value) is float and not math.isfinite(value)
        ):
            raise ValueError(f"serial.{field} must be a finite number")
        if field in ("retry_delay", "temporary_status_delay"):
            if value < 0:
                raise ValueError(f"serial.{field} must be non-negative")
        elif value <= 0:
            raise ValueError(f"serial.{field} must be positive")

    camera_config = config.get("camera")
    if not isinstance(camera_config, dict):
        raise ValueError("camera must be a TOML table")

    for field in ("width", "height", "fps"):
        value = camera_config.get(field)
        if type(value) is not int:
            raise ValueError(f"camera.{field} must be an integer")
        if value <= 0:
            raise ValueError(f"camera.{field} must be positive")

    detector_config = config.get("detector")
    if not isinstance(detector_config, dict):
        raise ValueError("detector must be a TOML table")

    model = detector_config.get("model")
    if not isinstance(model, str):
        raise ValueError("detector.model must be a string")
    if not model.strip():
        raise ValueError("detector.model must not be empty")
    model_path = Path(model)
    if model_path.suffix.lower() != ".pt" and not model_path.name.endswith("_ncnn_model"):
        raise ValueError("detector.model must point to a local .pt file or *_ncnn_model directory")
    if not model_path.is_absolute():
        config_directory = Path(path).resolve().parent
        model_path = config_directory / model_path
    detector_config["model"] = str(model_path.resolve())

    imgsz = detector_config.get("imgsz")
    if type(imgsz) is not int or imgsz <= 0:
        raise ValueError("detector.imgsz must be a positive integer")

    confidence = detector_config.get("confidence")
    if type(confidence) not in (int, float):
        raise ValueError("detector.confidence must be a number")
    if type(confidence) is float:
        if not math.isfinite(confidence):
            raise ValueError("detector.confidence must be finite")
    if confidence <= 0 or confidence >= 1:
        raise ValueError("detector.confidence must be between 0 and 1, exclusive")

    configure_dashboard(config, path)
    return config


def configure_dashboard(config, path):
    """Giá trị mặc định giữ web tắt; mọi đường dẫn theo file TOML."""
    directory = Path(path).resolve().parent
    statistics = config.setdefault("statistics", {})
    dashboard = config.setdefault("dashboard", {})
    stream = config.setdefault("stream", {})
    for name, table in (("statistics", statistics), ("dashboard", dashboard), ("stream", stream)):
        if not isinstance(table, dict):
            raise ValueError(f"{name} must be a TOML table")
    statistics.setdefault("database", "runtime/statistics.sqlite3")
    statistics.setdefault("timezone", "Asia/Bangkok")
    dashboard.setdefault("enabled", False)
    dashboard.setdefault("host", "0.0.0.0")
    dashboard.setdefault("port", 8000)
    stream.setdefault("width", 640)
    stream.setdefault("fps", 5)
    stream.setdefault("quality", 70)
    stream.setdefault("font", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if type(dashboard["enabled"]) is not bool:
        raise ValueError("dashboard.enabled must be a boolean")
    if not isinstance(dashboard["host"], str) or not dashboard["host"].strip():
        raise ValueError("dashboard.host must not be empty")
    for name, table, field, lower, upper in (
        ("dashboard", dashboard, "port", 1, 65535),
        ("stream", stream, "width", 64, 1920),
        ("stream", stream, "fps", 1, 30),
        ("stream", stream, "quality", 1, 95),
    ):
        if type(table[field]) is not int or not lower <= table[field] <= upper:
            raise ValueError(f"{name}.{field} must be an integer from {lower} to {upper}")
    zone = statistics["timezone"]
    if not isinstance(zone, str):
        raise ValueError("statistics.timezone must be a timezone name")
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown statistics.timezone: {zone}; install tzdata") from exc
    for table, field in ((statistics, "database"), (stream, "font")):
        value = table[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty path")
        target = Path(value)
        if not target.is_absolute():
            target = directory / target
        table[field] = str(target.resolve())

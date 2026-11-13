# Raspberry Pi Application

`conveyor` connects Picamera2, YOLO detection, fruit tracking, line counting,
and UART sorting commands. SQLite stores production history. A FastAPI LAN
dashboard displays daily statistics and a shared MJPEG stream with detection
overlays. Camera streaming reuses the pipeline frames and encodes images
while viewers are connected.

## Installation

Use Raspberry Pi OS with Python 3.11+. Run these commands from `RaspberryPi`.

```sh
sudo apt update
sudo apt install python3-picamera2 python3-venv fonts-dejavu-core
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements-ncnn.txt -r requirements-dashboard.txt
cp config.example.toml config.toml
```

| Dependency file | Purpose |
| --- | --- |
| `requirements.txt` | UART and timezone support |
| `requirements-vision.txt` | PyTorch inference |
| `requirements-ncnn.txt` | NCNN inference with Ultralytics 8.4.194 |
| `requirements-dashboard.txt` | Dashboard and camera streaming |

Copy your model into `models/`. NCNN requires a folder named `*_ncnn_model`
containing one `.param` file, its matching `.bin`, and `metadata.yaml`.
The model must contain exactly `green`, `riped`, and `damaged` labels.

Edit these existing tables in `config.toml`, keeping the remaining settings
from the example file.

```toml
[detector]
model = "models/best_ncnn_model"
confidence = 0.4
imgsz = 640

[statistics]
database = "runtime/statistics.sqlite3"
timezone = "Asia/Bangkok"

[dashboard]
enabled = true
host = "0.0.0.0"
port = 8000
```

For PyTorch, set `model = "models/best.pt"`. NCNN requires `imgsz` to match
the square export size. Adjust the serial port, camera, tracker distance,
and counting-line direction for your hardware.

Model, database, and font paths are relative to the TOML file. With
`conveyor/config.toml`, use `../models/best_ncnn_model` and
`../runtime/statistics.sqlite3` instead.

Connect CP2102 TX to STM32 PA10, RX to PA9, and share GND. Set the serial device
to the connected adapter, usually `/dev/ttyUSB0`, at 115200 baud, 8N1.
Build and flash STM32 using the [project instructions](../README.md#stm32).

Verify the application installation with

```sh
.venv/bin/python -m conveyor --help
```

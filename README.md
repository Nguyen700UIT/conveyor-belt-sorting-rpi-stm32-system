# Conveyor Belt Fruit Sorting System

A kumquat sorting conveyor powered by Raspberry Pi 5 and STM32F103C8T6.
YOLO detects unripe, ripe, and damaged fruit. The Pi tracks each fruit and
sends its class over UART when it crosses a counting line.

STM32 controls two MG90S servos and a JGB37-545 motor through a BTS7960 driver.
Two E3F-DS30C4 infrared sensors detect fruit at the sorting positions.
A LAN dashboard shows daily counts, UART outcomes, and live camera overlays.
SQLite keeps production history. Local PyTorch and NCNN models are supported.

Model labels are `green`, `riped`, and `damaged`. Counts represent line crossings.
UART ACK confirms that STM32 accepted a command.

## Installation

Clone the repository on your development machine and Raspberry Pi.

```sh
git clone https://github.com/Nguyen700UIT/conveyor-belt-sorting-rpi-stm32-system.git
cd conveyor-belt-sorting-rpi-stm32-system
```

### STM32

Install CMake 3.22+, Ninja, ARM GNU Toolchain, and STM32CubeProgrammer.
Add `arm-none-eabi-gcc` to `PATH`, then build the firmware.

```sh
cd STM32Firmware
cmake --preset Debug
cmake --build --preset Debug
```

Flash `build-local/Debug/STM32Firmware.elf` using ST-Link over SWD.

### Raspberry Pi

Use Raspberry Pi OS with Python 3.11+. From the repository root, install
camera support and create a virtual environment with system packages.

```sh
cd RaspberryPi
sudo apt update
sudo apt install python3-picamera2 python3-venv fonts-dejavu-core
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements-ncnn.txt -r requirements-dashboard.txt
cp config.example.toml config.toml
```

Copy the complete `best_ncnn_model/` export into `RaspberryPi/models/`, including
its `.param`, matching `.bin`, and `metadata.yaml`. In `config.toml`, set
`detector.model = "models/best_ncnn_model"` and `dashboard.enabled = true`.
Match `detector.imgsz` to the export size, usually 640. For PyTorch, install
`requirements-vision.txt` and set the model path to `models/best.pt`.

Set the serial device, camera, tracker, and counting-line settings for your
conveyor. Connect CP2102 TX to STM32 PA10, RX to PA9, and share GND.
UART uses 115200 baud, 8N1, usually through `/dev/ttyUSB0` on the Pi.
Connect the camera with the Pi powered off and provide suitable external
power for the motor and servos.

See [Raspberry Pi installation](RaspberryPi/README.md) for configuration paths
and dependency options.

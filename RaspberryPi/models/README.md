# Local weights

Copy the trained Ultralytics detection weights here as `best.pt`.
The model must contain exactly `green`, `riped`, `damaged` labels; class ID order
does not matter. Weight files are ignored by Git.

Record the training Ultralytics version and use that version on the Pi first.
Verify the model on real images before freezing deployment dependencies.

## NCNN on Raspberry Pi

Extract `ce224_ncnn.zip` from the notebook and copy the entire
`best_ncnn_model/` directory here. Keep its `.param`, matching `.bin`, and
`metadata.yaml` files together; do not point the loader at the ZIP or `.bin`.

Install from the `RaspberryPi` directory:

```sh
python -m pip install -r requirements-ncnn.txt
```

For `conveyor/config.toml`, set:

```toml
[detector]
model = "../models/best_ncnn_model"
confidence = 0.4
imgsz = 640
```

For `RaspberryPi/config.toml`, use `models/best_ncnn_model` instead.
Paths are relative to the TOML file. Keep `imgsz` equal to the notebook export
size. NCNN runs on CPU with square letterboxing, preserving the camera aspect
ratio. The existing `.pt` configuration remains supported. No camera or model
is loaded by `--ping` or `--start`.

Check accuracy and inference time on the Pi before deploying the exported
model. The loader checks the class names from the export metadata; class IDs
are not hardcoded.

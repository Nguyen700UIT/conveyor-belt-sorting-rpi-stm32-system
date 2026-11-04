import tempfile
import tomllib
import unittest
from pathlib import Path

from conveyor.config import load_config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "config.toml"
        example = Path(__file__).resolve().parents[1] / "config.example.toml"
        self.text = example.read_text(encoding="utf-8")

    def load(self, text):
        self.path.write_text(text, encoding="utf-8")
        return load_config(self.path)

    def field_text(self, field, value):
        return "\n".join(f"{field} = {value}" if line.startswith(f"{field} =") else line
                         for line in self.text.splitlines())

    def test_example_preserves_all_sections(self):
        expected = tomllib.loads(self.text)
        expected["detector"]["model"] = str((self.path.parent / "models/best.pt").resolve())
        self.assertEqual(self.load(self.text), expected)

    def test_serial_table_required(self):
        for text in ("", 'serial = "invalid"'):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "serial"):
                self.load(text)

    def test_missing_fields(self):
        for field in tomllib.loads(self.text)["serial"]:
            text = "\n".join(line for line in self.text.splitlines()
                             if not line.startswith(f"{field} ="))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                self.load(text)

    def test_invalid_values(self):
        cases = {
            "port": ('""', '"   "', "42", "true"),
            "baudrate": ("9600", "115200.0", "true"),
            "max_attempts": ("0", "-1", "1.5", "true", '"3"'),
        }
        for field in ("read_timeout", "write_timeout", "transaction_timeout", "frame_timeout"):
            cases[field] = ("0", "-0.1", "nan", "inf", "-inf", "true", '"0.1"')
        for field in ("retry_delay", "temporary_status_delay"):
            cases[field] = ("-1", "nan", "inf", "true", '"0"')
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(ValueError, field):
                        self.load(self.field_text(field, value))

    def test_integer_timeouts_and_zero_delays(self):
        for field in ("read_timeout", "write_timeout", "transaction_timeout", "frame_timeout"):
            self.assertEqual(self.load(self.field_text(field, "1"))["serial"][field], 1)
        for field in ("retry_delay", "temporary_status_delay"):
            self.assertEqual(self.load(self.field_text(field, "0"))["serial"][field], 0)

    def test_file_and_parse_errors_propagate(self):
        with self.assertRaises(FileNotFoundError):
            load_config(self.path)
        with self.assertRaises(tomllib.TOMLDecodeError):
            self.load("[serial")

    def test_vision_tables_required(self):
        for table in ("camera", "detector"):
            for replacement in (f"[unused_{table}]", f"[[{table}]]"):
                text = self.text.replace(f"[{table}]", replacement)
                with self.subTest(table=table, replacement=replacement):
                    with self.assertRaisesRegex(ValueError, table):
                        self.load(text)

    def test_missing_vision_fields(self):
        for field in ("width", "height", "fps", "model", "confidence", "imgsz"):
            lines = []
            for line in self.text.splitlines():
                if not line.startswith(f"{field} ="):
                    lines.append(line)
            text = "\n".join(lines)
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field):
                    self.load(text)

    def test_camera_requires_positive_integers(self):
        for field in ("width", "height", "fps"):
            for value in ("0", "-1", "true", "1.5", '"720"'):
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(ValueError, f"camera\\.{field}"):
                        self.load(self.field_text(field, value))

    def test_model_requires_nonempty_string(self):
        for value in ('""', '"   "', "42", "true"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "detector\\.model"):
                    self.load(self.field_text("model", value))

    def test_confidence_requires_finite_number_inside_bounds(self):
        for value in ("0", "1", "-0.1", "1.1", "nan", "inf", "-inf", "true", '"0.4"'):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "detector\\.confidence"):
                    self.load(self.field_text("confidence", value))

    def test_valid_vision_values_are_preserved(self):
        text = self.field_text("fps", "1")
        text = text.replace("confidence = 0.4", "confidence = 0.99")
        result = self.load(text)
        self.assertEqual(result["camera"]["fps"], 1)
        self.assertEqual(result["detector"]["confidence"], 0.99)

    def test_model_path_is_relative_to_config_not_working_directory(self):
        result = self.load(self.field_text("model", '"../models/best.pt"'))
        expected = (self.path.parent / "../models/best.pt").resolve()
        self.assertEqual(result["detector"]["model"], str(expected))
        self.assertFalse(expected.exists())  # Config/PING need no weights yet.

    def test_absolute_model_path(self):
        model = (self.path.parent / "absolute.pt").resolve()
        text = self.field_text("model", '"' + model.as_posix() + '"')
        self.assertEqual(self.load(text)["detector"]["model"], str(model))

    def test_invalid_extension_and_imgsz(self):
        for model in ('"best.onnx"', '"best"', '"workspace/model"'):
            with self.subTest(model=model), self.assertRaisesRegex(ValueError, "detector.model"):
                self.load(self.field_text("model", model))
        for value in ("0", "-1", "true", "640.0", '"640"'):
            with self.subTest(imgsz=value), self.assertRaisesRegex(ValueError, "detector.imgsz"):
                self.load(self.field_text("imgsz", value))


if __name__ == "__main__":
    unittest.main()

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from conveyor.vision.detector import Detector

try:
    import numpy as np
except ImportError:
    np = None


class DetectorTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "best.pt"
        self.path.write_bytes(b"fake weights; model loading is mocked")
        self.yolo = MagicMock()
        self.model = self.yolo.return_value
        self.model.task = "detect"
        self.model.names = {0: "damaged", 1: "green", 2: "riped"}
        fake_module = types.ModuleType("ultralytics")
        fake_module.YOLO = self.yolo
        patcher = patch.dict(sys.modules, {"ultralytics": fake_module})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_file_never_calls_yolo(self):
        with self.assertRaises(FileNotFoundError):
            Detector(self.path.parent / "missing.pt")
        self.yolo.assert_not_called()

    def test_bad_extension_and_corrupt_weights(self):
        with self.assertRaises(ValueError):
            Detector(self.path.with_suffix(".onnx"))
        self.yolo.assert_not_called()
        self.yolo.side_effect = RuntimeError("bad weights")
        with self.assertRaisesRegex(ValueError, "Cannot load model weights"):
            Detector(self.path)
        self.yolo.assert_called_once_with(str(self.path.resolve()))

    def test_task_and_class_names_are_checked(self):
        self.model.task = "classify"
        with self.assertRaisesRegex(ValueError, "object detection"):
            Detector(self.path)
        self.model.task = "detect"
        self.model.names = {0: "green", 1: "ripe", 2: "damaged"}
        with self.assertRaisesRegex(ValueError, "exactly"):
            Detector(self.path)

    def test_class_id_order_is_not_assumed(self):
        detector = Detector(self.path)
        self.assertEqual(detector.names[0], "damaged")
        self.assertEqual(detector.names[1], "green")
        self.yolo.assert_called_once()

    @unittest.skipIf(np is None, "NumPy required for image tests")
    def test_rgb_conversion_predictions_and_load_once(self):
        import numpy as np

        box = MagicMock()
        box.xyxy = [[10.0, 20.0, 30.0, 40.0]]
        box.xyxy = np.array(box.xyxy)
        box.cls.item.return_value = 1
        box.conf.item.return_value = 0.9
        result = MagicMock()
        result.boxes = [box]
        self.model.predict.return_value = [result]
        detector = Detector(self.path, confidence=0.5, imgsz=320)
        frame = np.array([[[255, 0, 10]]], dtype=np.uint8)
        detections = detector.predict(frame, color_order="RGB")
        self.assertEqual(detections[0].label, "green")
        self.assertEqual(detections[0].xyxy, (10.0, 20.0, 30.0, 40.0))
        self.assertEqual(detections[0].confidence, 0.9)
        options = self.model.predict.call_args.kwargs
        np.testing.assert_array_equal(options["source"], [[[10, 0, 255]]])
        np.testing.assert_array_equal(frame, [[[255, 0, 10]]])
        self.assertEqual(options["device"], "cpu")
        self.assertEqual(options["conf"], 0.5)
        self.assertEqual(options["imgsz"], 320)
        result.boxes = []
        self.assertEqual(detector.predict(frame, color_order="BGR"), [])
        np.testing.assert_array_equal(self.model.predict.call_args.kwargs["source"], frame)
        self.yolo.assert_called_once()

    @unittest.skipIf(np is None, "NumPy required for image tests")
    def test_invalid_images_never_reach_predict(self):
        import numpy as np

        detector = Detector(self.path)
        for frame in (None, np.zeros((1, 1, 3)), np.zeros((1, 1), dtype=np.uint8),
                      np.zeros((0, 1, 3), dtype=np.uint8), np.zeros((1, 1, 4), dtype=np.uint8)):
            with self.subTest(frame=type(frame)), self.assertRaises(ValueError):
                detector.predict(frame, color_order="BGR")
        with self.assertRaises(ValueError):
            detector.predict(np.zeros((1, 1, 3), dtype=np.uint8), color_order="unknown")
        self.model.predict.assert_not_called()


if __name__ == "__main__":
    unittest.main()

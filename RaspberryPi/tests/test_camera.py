"""Kiểm tra quản lý buffer và vòng đời camera mà không cần phần cứng Pi."""

import types
import unittest
from unittest.mock import MagicMock, patch

from conveyor.vision.camera import Camera


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.picamera = MagicMock()
        self.device = self.picamera.return_value
        self.enterContext(patch.dict("sys.modules", {
            "picamera2": types.SimpleNamespace(Picamera2=self.picamera),
        }))
        self.camera = Camera(1280, 720, 10)
        self.addCleanup(self.camera.close)

    def test_frame_copied_before_request_release(self):
        self.camera.start()
        request = self.device.capture_request.return_value
        request.get_metadata.return_value = {"SensorTimestamp": 1_500_000_000}
        image = request.make_array.return_value
        def copy_image():
            request.release.assert_not_called()
            return image.copy.return_value
        image.copy.side_effect = copy_image
        frame, timestamp = self.camera.read()
        self.assertIs(frame, image.copy.return_value)
        self.assertEqual(timestamp, 1.5)
        self.assertEqual(self.camera.color_order, "BGR")
        request.release.assert_called_once()

    def test_invalid_timestamp_still_releases_request(self):
        self.camera.start()
        request = self.device.capture_request.return_value
        request.get_metadata.return_value = {}
        with self.assertRaises(ValueError):
            self.camera.read()
        request.release.assert_called_once()

    def test_start_failure_closes_device(self):
        self.device.start.side_effect = RuntimeError("camera unavailable")
        with self.assertRaises(RuntimeError):
            self.camera.start()
        self.device.close.assert_called_once()
        self.camera.close()
        self.device.close.assert_called_once()

    def test_close_is_idempotent_and_read_requires_start(self):
        with self.assertRaises(RuntimeError):
            self.camera.read()
        self.camera.start()
        with self.assertRaises(RuntimeError):
            self.camera.start()
        self.camera.close()
        self.camera.close()
        self.device.close.assert_called_once()
        with self.assertRaises(RuntimeError):
            self.camera.read()

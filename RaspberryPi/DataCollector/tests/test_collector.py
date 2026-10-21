import asyncio
import base64
import io
import json
import os
from pathlib import Path
import queue
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import capture_yolo_local as collector
import quality_mcp as quality


def jpeg(image):
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


class CollectorTests(unittest.TestCase):
    def test_remote_syntax(self):
        compile(collector.REMOTE_CODE, "REMOTE_CODE", "exec")

    def test_packet_keeps_latest_image_and_matching_metadata(self):
        wire = bytearray()
        for value in (1000, 2000):
            details = json.dumps({"ExposureTime": value}).encode()
            picture = jpeg(np.full((16, 16, 3), value // 10, np.uint8))
            wire.extend(struct.pack("!I", len(details)) + details)
            wire.extend(struct.pack("!I", len(picture)) + picture)
        frames, errors = queue.Queue(maxsize=1), queue.Queue()
        collector.receive_frames(io.BytesIO(wire), frames, errors)
        _, _, picture, metadata = frames.get_nowait()
        self.assertEqual(metadata["ExposureTime"], 2000)
        self.assertAlmostEqual(float(cv2.imdecode(np.frombuffer(picture, np.uint8), 0).mean()), 200, delta=2)
        self.assertIsInstance(errors.get_nowait(), EOFError)

    def test_metrics_detect_loss_of_detail_and_low_light(self):
        pattern = ((np.indices((128, 128)).sum(axis=0) // 8 % 2) * 255).astype(np.uint8)
        sharp = cv2.cvtColor(pattern, cv2.COLOR_GRAY2BGR)
        blurred = cv2.GaussianBlur(sharp, (15, 15), 4)
        a, _ = quality.analyse(jpeg(sharp))
        b, _ = quality.analyse(jpeg(blurred))
        dark, _ = quality.analyse(jpeg(np.zeros_like(sharp)))
        self.assertGreater(a["laplacian_variance"], b["laplacian_variance"])
        self.assertEqual(dark["dark_pixels_below_20_percent"], 100)
        with self.assertRaises(ValueError):
            quality.analyse(jpeg(sharp), [0, 0, 2, 1])

    def test_snapshot_and_path_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            picture = jpeg(np.full((32, 32, 3), 120, np.uint8))
            collector.publish_live(root, picture, time.time() - 10, {"LensPosition": 2}, {})
            with patch.object(quality, "LIVE_DIR", root), patch.object(quality, "IMAGES_DIR", root):
                result = quality.get_live_frame([0, 0, 0.5, 0.5])
                report = json.loads(result[0].text)
                self.assertTrue(report["stale"])
                self.assertEqual(base64.b64decode(result[1].data), picture)
                self.assertEqual(len(result), 3)
                for name in ("../outside.jpg", str(root.parent / "outside.jpg")):
                    with self.assertRaises(ValueError):
                        quality.saved_path(name)

    def test_stdio_mcp_connection_and_image_tools(self):
        async def run():
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                picture = jpeg(np.full((32, 32, 3), 130, np.uint8))
                collector.publish_live(root, picture, time.time(), {"ExposureTime": 1000}, {})
                (root / "sample.jpg").write_bytes(picture)
                params = StdioServerParameters(
                    command=sys.executable, args=[str(BASE / "quality_mcp.py")],
                    env={**os.environ, "COLLECTOR_LIVE_DIR": folder, "COLLECTOR_IMAGES_DIR": folder},
                )
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        available = await session.list_tools()
                        self.assertEqual(len(available.tools), 3)
                        result = await session.call_tool("get_live_frame", {"roi": [0, 0, 0.5, 0.5]})
                        self.assertFalse(result.isError)
                        self.assertTrue(any(c.type == "image" for c in result.content))
                        listing = await session.call_tool("list_recent_captures", {})
                        self.assertFalse(listing.isError)
                        result = await session.call_tool("inspect_saved_image", {"filename": "sample.jpg"})
                        self.assertFalse(result.isError)
                        blocked = await session.call_tool("inspect_saved_image", {"filename": "../outside.jpg"})
                        self.assertTrue(blocked.isError)
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

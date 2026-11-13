"""Vòng đời thống kê/web; không đặt logic phân loại trong HTTP handler."""

from contextlib import ExitStack
from pathlib import Path

from ..config import configure_dashboard
from ..statistics.store import Store
from .broadcast import Broadcast


class Runtime:
    def __init__(self, config, *, history_only=False):
        self.config = config
        self.history_only = history_only
        self.camera = None
        self.web = None
        self.updates = Broadcast()
        self._stack = ExitStack()

    def __enter__(self):
        try:
            # run_pipeline cũng được gọi trực tiếp trong test và chương trình khác.
            configure_dashboard(self.config, Path(__file__).parents[2] / "config.toml")
            settings = self.config["statistics"]
            self.store = Store(settings["database"], settings["timezone"], self.updates.notify)
            self._stack.callback(self.store.close)
            if self.history_only or self.config["dashboard"]["enabled"]:
                from .stream import CameraStream
                from .web import WebServer

                self.camera = CameraStream(self.config["stream"], self.updates.notify)
                self._stack.callback(self.camera.close)
                self.web = WebServer(self.store, self.updates, self.camera, self.config["dashboard"])
                self._stack.callback(self.web.close)
                self.web.start()
                print(f"Dashboard: http://<Pi-IP>:{self.config['dashboard']['port']}", flush=True)
            if not self.history_only:
                self.store.start_session()
                self._stack.callback(self.store.finish_session)
            return self
        except BaseException:
            self._stack.close()
            raise

    def __exit__(self, *args):
        self._stack.close()

    def camera_state(self, active, message):
        if self.camera is not None:
            self.camera.set_active(active, message)

    def frame(self, frame, detections, crossing, color_order):
        if self.camera is not None:
            self.camera.submit(frame, detections, crossing, color_order)

    def check(self):
        if self.web is not None and self.web.error is not None:
            raise RuntimeError(f"Dashboard failed: {self.web.error}")

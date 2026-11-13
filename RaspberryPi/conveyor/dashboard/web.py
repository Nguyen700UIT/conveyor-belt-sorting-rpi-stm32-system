"""HTTP chỉ đọc; SSE và MJPEG chờ notification thay vì polling."""

import asyncio
from contextlib import asynccontextmanager
from datetime import date as Date
import json
from pathlib import Path
import socket
import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import uvicorn


def create_app(store, updates, camera, ready=None):
    @asynccontextmanager
    async def lifespan(app):
        if ready is not None:
            ready.set()
        yield

    app = FastAPI(lifespan=lifespan)
    assets = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=assets), name="static")

    @app.get("/")
    def index():
        return FileResponse(assets / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/api/summary")
    def summary(date: Date):
        try:
            return store.summary(date)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/daily")
    def daily(start: Date, end: Date):
        try:
            return store.daily(start, end)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/events")
    async def events():
        async def generate():
            async with updates.subscribe() as queue:
                yield "data: " + json.dumps({"camera": camera.status(), "timezone": store.zone.key}) + "\n\n"
                while not updates.closed:
                    try:
                        await asyncio.wait_for(queue.get(), timeout=15)
                    except TimeoutError:
                        # Heartbeat giữ kết nối; không đọc database.
                        yield ": keep-alive\n\n"
                        continue
                    if not updates.closed:
                        yield "data: " + json.dumps({"camera": camera.status(), "timezone": store.zone.key}) + "\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/camera/stream")
    async def stream():
        if not camera.status()["active"]:
            raise HTTPException(503, camera.status()["message"])

        async def generate():
            async with camera.frames.subscribe() as queue:
                if not camera.add_viewer():
                    return
                last_version = -1
                try:
                    while not camera.frames.closed:
                        version, jpeg, active = camera.latest()
                        if not active:
                            return
                        if jpeg is not None and version != last_version:
                            yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                   + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
                            last_version = version
                        try:
                            await asyncio.wait_for(queue.get(), timeout=5)
                        except TimeoutError:
                            # Không phát lại ảnh cũ khi pipeline không còn cung cấp frame.
                            camera.mark_stalled()
                            return
                finally:
                    camera.remove_viewer()
        return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    return app


class WebServer:
    def __init__(self, store, updates, camera, settings):
        self.ready = threading.Event()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._socket.bind((settings["host"], settings["port"]))
            self._socket.listen(128)
        except BaseException:
            self._socket.close()
            raise
        self._updates = updates
        self._camera = camera
        app = create_app(store, updates, camera, self.ready)
        self._server = uvicorn.Server(uvicorn.Config(app, log_level="warning", workers=1,
                                                    timeout_graceful_shutdown=3))
        self._thread = threading.Thread(target=self._serve, name="dashboard-http", daemon=True)
        self.error = None

    def _serve(self):
        try:
            self._server.run(sockets=[self._socket])
        except BaseException as exc:
            self.error = exc
        finally:
            if self.error is None and not self._server.should_exit:
                self.error = RuntimeError("HTTP server exited unexpectedly")
            self.ready.set()

    def start(self):
        self._thread.start()
        if not self.ready.wait(10) or self.error is not None:
            self.close()
            raise RuntimeError(f"Dashboard could not start: {self.error}")

    def close(self):
        self._updates.close()
        self._camera.frames.close()
        self._server.should_exit = True
        if self._thread.ident is not None:
            self._thread.join(timeout=5)
        self._socket.close()

    def wait(self):
        self._thread.join()
        if self.error is not None:
            raise RuntimeError(f"Dashboard failed: {self.error}")

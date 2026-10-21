"""Run the selected Roboflow model on the Pi CSI camera; view MJPEG in a browser."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='tung-tran-s-workspace/ce224-project-1-yolo26n-t1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--confidence', type=float, default=0.4)
    args = parser.parse_args()
    if not 0 < args.confidence < 1 or not 1 <= args.port <= 65535:
        parser.error('Confidence must be in (0, 1); port must be 1..65535')

    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'))
    import cv2
    from inference_models import AutoModel
    from libcamera import controls
    from picamera2 import Picamera2
    import torch

    torch.set_num_threads(4)
    print(f'Loading {args.model}; first download/warmup can take a while.', flush=True)
    model = AutoModel.from_pretrained(args.model, backend='onnx', device='cpu',
                                      onnx_execution_providers=['CPUExecutionProvider'])
    print(f'Classes: {model.class_names}', flush=True)
    camera = Picamera2()
    condition = threading.Condition()
    state = {'jpeg': None, 'sequence': 0, 'clients': 0, 'stopped': False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path == '/':
                body = (b'<!doctype html><title>CE224 Camera</title>'
                        b'<style>body{background:#111;color:#eee;font-family:sans-serif;'
                        b'text-align:center}img{max-width:100%;height:auto}</style>'
                        b'<h2>CE224 - Pi camera detection</h2><img src="/stream.mjpg">'
                        b'<p>Close this page to pause inference.</p>')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path != '/stream.mjpg':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.connection.settimeout(10)
            with condition:
                state['clients'] += 1
                condition.notify_all()
            sequence = -1
            try:
                while True:
                    with condition:
                        condition.wait_for(lambda: state['stopped'] or (
                            state['jpeg'] is not None and state['sequence'] != sequence))
                        if state['stopped']:
                            return
                        jpeg, sequence = state['jpeg'], state['sequence']
                    self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '
                                     + str(len(jpeg)).encode() + b'\r\n\r\n' + jpeg + b'\r\n')
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
            finally:
                with condition:
                    state['clients'] -= 1
                    condition.notify_all()

    server = ThreadingHTTPServer(('0.0.0.0', args.port), Handler)
    server.daemon_threads = True
    try:
        camera.configure(camera.create_video_configuration(
            main={'size': (1280, 720), 'format': 'RGB888'},
            controls={'FrameRate': 10}, buffer_count=4))
        camera.start()
        time.sleep(2)
        if 'AfMode' in camera.camera_controls:
            camera.set_controls({'AfMode': controls.AfModeEnum.Auto})
            print('Autofocus: keep fruit still in the centre.', flush=True)
            if not camera.autofocus_cycle():
                raise RuntimeError('Autofocus failed; improve lighting and restart')
            position = camera.capture_metadata()['LensPosition']
            camera.set_controls({'AfMode': controls.AfModeEnum.Manual, 'LensPosition': position})
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f'Camera ready. Open http://<PI-IP>:{args.port}/ ; Ctrl+C stops.', flush=True)
        while True:
            with condition:
                condition.wait_for(lambda: state['clients'] > 0)
            started = time.monotonic()
            frame = camera.capture_array('main')
            detections = model(frame, confidence=args.confidence)[0].to_supervision()
            for box, confidence, class_id in zip(
                    detections.xyxy, detections.confidence, detections.class_id):
                x1, y1, x2, y2 = map(int, box)
                name = model.class_names[int(class_id)]
                color = {'green': (0, 220, 0), 'riped': (0, 180, 255),
                         'damaged': (0, 0, 255)}.get(name, (255, 200, 0))
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f'{name} {confidence:.0%}', (x1, max(22, y1 - 7)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
            fps = 1 / (time.monotonic() - started)
            cv2.putText(frame, f'Pi CPU | {fps:.1f} FPS | conf >= {args.confidence:.0%}',
                        (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                raise RuntimeError('JPEG encoding failed')
            with condition:
                state['jpeg'] = encoded.tobytes()
                state['sequence'] += 1
                condition.notify_all()
    except KeyboardInterrupt:
        pass
    finally:
        with condition:
            state['stopped'] = True
            condition.notify_all()
        server.server_close()
        camera.close()


if __name__ == '__main__':
    main()

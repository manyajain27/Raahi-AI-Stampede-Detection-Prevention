"""
Live Detection Server

Flask + SocketIO backend that streams webcam + YOLO person detection
to the web dashboard, with browser-based calibration.
"""

import os
import sys
import cv2
import numpy as np
import base64
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
import math

try:
    import serial
except ImportError:
    serial = None

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

# Add parent + local dir to path for crowd_simulation import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).parent.parent))

from crowd_simulation.venue import Venue

app = Flask(__name__)
app.config['SECRET_KEY'] = 'live-detect-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


# ─── Global State ───────────────────────────────────────────────────
class LiveDetectionManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

        # Venue
        self.venue = None
        self.base_map_img = None

        # Camera
        self.cap = None
        self.camera_source = 0

        # YOLO
        self.model = None

        # Calibration
        self.calibration_state = 'idle'  # idle | picking_map | picking_cam | done
        self.map_points = []
        self.cam_points = []
        self.H_matrix = None

        # Tracking
        self.track_history = defaultdict(lambda: deque(maxlen=30))  # map positions history per ID
        self.last_map_pos = {}
        self.person_count = 0

        # Fall detection
        self.prev_ids = set()           # IDs seen in the previous frame
        self.id_seen_count = defaultdict(int)  # how many frames each ID has been tracked
        self.fall_alerts = {}           # tid -> {'x': int, 'y': int, 'time': float}
        self.FALL_MIN_FRAMES = 5        # must be seen at least this many frames before counting as fall
        self.FALL_ALERT_DURATION = 6.0  # seconds to show the fall marker

        # ESP32 band integration (Serial)
        self.serial_port = None     # e.g. 'COM3'
        self.serial_conn = None     # pyserial connection
        self.max_capacity = 30      # max people before density = 1.0
        self.density = 0.0
        self.last_esp32_notify = 0
        self._esp32_notified_falls = set()  # fall tids already sent to ESP32

        # Collision detection
        self.collisions = []
        self._collision_history = {}   # key -> {'data': col_dict, 'time': float}
        self.COLLISION_PERSIST_DURATION = 3.0  # seconds to keep collision visible

    def load_venue(self, yaml_path: str):
        """Load venue YAML and draw the base map image."""
        with self.lock:
            self.venue = Venue.from_yaml(yaml_path)
            self.base_map_img = self._draw_venue_map()
        return True

    def _draw_venue_map(self):
        """Render venue as an OpenCV image."""
        venue = self.venue
        ppm = venue.pixels_per_meter

        all_x = []
        all_y = []
        for path in venue.pathways.values():
            for p in path.points:
                all_x.append(p.x * ppm)
                all_y.append(p.y * ppm)

        if not all_x:
            return np.zeros((600, 800, 3), dtype=np.uint8)

        w = int(max(all_x)) + 100
        h = int(max(all_y)) + 100
        map_img = np.zeros((h, w, 3), dtype=np.uint8)

        # Draw pathways
        for pathway in venue.pathways.values():
            pts = [(int(p.x * ppm), int(p.y * ppm)) for p in pathway.points]
            for i in range(len(pts) - 1):
                cv2.line(map_img, pts[i], pts[i + 1], (70, 70, 70),
                         max(2, int(pathway.width * ppm)))

        # Draw choke points
        for choke in venue.choke_points.values():
            cx, cy = int(choke.position.x * ppm), int(choke.position.y * ppm)
            cv2.circle(map_img, (cx, cy), int(choke.radius * ppm), (0, 0, 255), 2)
            cv2.putText(map_img, choke.name, (cx - 20, cy - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        # Draw entries
        for entry in venue.entries.values():
            ex, ey = int(entry.position.x * ppm), int(entry.position.y * ppm)
            cv2.circle(map_img, (ex, ey), 8, (0, 255, 200), -1)
            cv2.putText(map_img, entry.name, (ex + 10, ey),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 200), 1)

        # Draw exits
        for exit_pt in venue.exits.values():
            ex, ey = int(exit_pt.position.x * ppm), int(exit_pt.position.y * ppm)
            cv2.circle(map_img, (ex, ey), 8, (200, 0, 255), -1)
            cv2.putText(map_img, exit_pt.name, (ex + 10, ey),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 0, 255), 1)

        return map_img

    def load_model(self):
        """Load YOLO model."""
        from ultralytics import YOLO
        model_path = os.path.join(os.path.dirname(__file__), 'yolov8n.pt')
        if not os.path.exists(model_path):
            model_path = 'yolov8n.pt'  # will auto-download
        self.model = YOLO(model_path)
        return True

    def open_camera(self, source=0):
        """Open webcam."""
        with self.lock:
            if self.cap and self.cap.isOpened():
                self.cap.release()
            self.camera_source = source
            self.cap = cv2.VideoCapture(source)
            if not self.cap.isOpened():
                return False
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        return self.cap.isOpened()

    def start_calibration(self):
        """Begin calibration — first pick 4 points on the map."""
        with self.lock:
            self.map_points = []
            self.cam_points = []
            self.H_matrix = None
            self.calibration_state = 'picking_map'

    def add_map_point(self, x, y):
        """Add a calibration point on the floor plan."""
        with self.lock:
            if self.calibration_state != 'picking_map':
                return
            self.map_points.append((x, y))
            if len(self.map_points) >= 4:
                self.calibration_state = 'picking_cam'

    def add_cam_point(self, x, y):
        """Add a calibration point on the camera feed."""
        with self.lock:
            if self.calibration_state != 'picking_cam':
                return
            self.cam_points.append((x, y))
            if len(self.cam_points) >= 4:
                cam_pts = np.array(self.cam_points, dtype=np.float32)
                map_pts = np.array(self.map_points, dtype=np.float32)
                self.H_matrix, _ = cv2.findHomography(cam_pts, map_pts)
                self.calibration_state = 'done'

    def start_streaming(self):
        """Start the background frame-processing thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._stream_loop, daemon=True)
        self.thread.start()

    def stop_streaming(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)

    # ─── Vector-based Collision Detection ────────────────────────────

    def _compute_velocities(self):
        """Compute velocity vectors from position history."""
        velocities = {}
        for tid, history in self.track_history.items():
            if len(history) >= 4:
                old_x, old_y = history[-4]
                new_x, new_y = history[-1]
                vx = (new_x - old_x) / 4.0
                vy = (new_y - old_y) / 4.0
                if abs(vx) > 0.5 or abs(vy) > 0.5:
                    velocities[tid] = (vx, vy)
        return velocities

    def _detect_collisions(self, velocities):
        """
        Detect collision risks using vector dot product and cross product.

        For persons A and B with velocities Va, Vb at positions Pa, Pb:
          D   = Pb - Pa            (relative displacement)
          Vr  = Va - Vb            (relative velocity)
          dot(Vr, D) > 0           means approaching each other
          t   = dot(Vr, D)/|Vr|^2  time of closest approach (frames)
          cross(Va, Vb)            sign tells passing side
        """
        collisions = []
        tids = list(velocities.keys())

        for i in range(len(tids)):
            for j in range(i + 1, len(tids)):
                tid_a, tid_b = tids[i], tids[j]
                pos_a = self.last_map_pos.get(tid_a)
                pos_b = self.last_map_pos.get(tid_b)
                if not pos_a or not pos_b:
                    continue

                vel_a = velocities[tid_a]
                vel_b = velocities[tid_b]

                # Relative displacement D = B - A
                dx = pos_b[0] - pos_a[0]
                dy = pos_b[1] - pos_a[1]
                dist = math.hypot(dx, dy)
                if dist < 5 or dist > 200:
                    continue

                # Relative velocity Vr = Va - Vb
                vrx = vel_a[0] - vel_b[0]
                vry = vel_a[1] - vel_b[1]
                vr_sq = vrx * vrx + vry * vry
                if vr_sq < 1:
                    continue

                # Dot product: dot(Vr, D) — positive means approaching
                dot_val = vrx * dx + vry * dy
                if dot_val <= 0:
                    continue  # diverging

                # Time of closest approach (in frames)
                t_min = dot_val / vr_sq
                if t_min > 30:  # > ~1.5 s at 20 fps
                    continue

                # Min separation at closest approach
                cx = -dx + vrx * t_min
                cy = -dy + vry * t_min
                min_sep = math.hypot(cx, cy)
                if min_sep > 35:  # pixels
                    continue

                # 2-D cross product Va x Vb (scalar) — sign = passing side
                cross_val = vel_a[0] * vel_b[1] - vel_a[1] * vel_b[0]

                collisions.append({
                    'id_a': int(tid_a), 'id_b': int(tid_b),
                    'pos_a': pos_a, 'pos_b': pos_b,
                    'distance': round(dist, 1),
                    'time_frames': round(t_min, 1),
                    'min_sep': round(min_sep, 1),
                    'cross': round(cross_val, 2),
                })
        return collisions

    def _compute_density(self, person_count):
        """Crowd density as ratio of count to max capacity."""
        if self.max_capacity <= 0:
            return 0.0
        return min(person_count / self.max_capacity, 1.5)

    def connect_serial(self, port):
        """Open serial connection to ESP32 band."""
        if serial is None:
            raise RuntimeError('pyserial not installed — run: pip install pyserial')
        with self.lock:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
            self.serial_port = port
            self.serial_conn = serial.Serial(port, 115200, timeout=1)
            time.sleep(0.5)  # ESP32 reboot grace period
        return True

    def disconnect_serial(self):
        """Close serial connection."""
        with self.lock:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
            self.serial_conn = None
            self.serial_port = None

    def _notify_esp32(self, density, has_fall, has_collision):
        """Send value to ESP32 band over Serial.
        Protocol: send a line like '0.45\n' or '2\n' for fall."""
        if not self.serial_conn or not self.serial_conn.is_open:
            return
        try:
            if has_fall:
                self.serial_conn.write(b'2\n')
            else:
                # Clamp to 0.1-1.0 range that the ESP32 expects
                value = max(0.1, min(density, 1.0))
                if has_collision:
                    value = max(value, 0.8)  # bump to at least HIGH on collision
                self.serial_conn.write(f'{value:.2f}\n'.encode())
        except Exception:
            pass

    def _stream_loop(self):
        """Background loop: grab frames, detect, emit."""
        while self.running:
            if not self.cap or not self.cap.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            display_map = self.base_map_img.copy() if self.base_map_img is not None else None

            # Draw calibration points on map
            if self.calibration_state == 'picking_map' and display_map is not None:
                for pt in self.map_points:
                    cv2.circle(display_map, (int(pt[0]), int(pt[1])), 6, (0, 255, 0), -1)

            # Draw calibration points on camera
            if self.calibration_state == 'picking_cam':
                for pt in self.cam_points:
                    cv2.circle(frame, (int(pt[0]), int(pt[1])), 6, (0, 0, 255), -1)

            person_count = 0
            current_ids = set()
            fall_count = 0
            # Run YOLO + homography if calibrated
            if self.calibration_state == 'done' and self.model and self.H_matrix is not None:
                results = self.model.track(frame, classes=[0], persist=True, verbose=False)

                if results[0].boxes.id is not None:
                    boxes = results[0].boxes.xyxy.cpu().numpy()
                    track_ids = results[0].boxes.id.int().cpu().numpy()
                    person_count = len(track_ids)

                    for box, tid in zip(boxes, track_ids):
                        tid = int(tid)
                        current_ids.add(tid)
                        self.id_seen_count[tid] += 1

                        x1, y1, x2, y2 = box
                        feet_x = int((x1 + x2) / 2)
                        feet_y = int(y2)

                        # Draw bbox on camera
                        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)),
                                      (100, 200, 100), 1)

                        # Perspective transform feet → floor plan
                        cam_pt = np.array([[[feet_x, feet_y]]], dtype=np.float32)
                        floor_pt = cv2.perspectiveTransform(cam_pt, self.H_matrix)[0][0]
                        map_x, map_y = int(floor_pt[0]), int(floor_pt[1])

                        self.last_map_pos[tid] = (map_x, map_y)
                        self.track_history[tid].append((map_x, map_y))

                        if display_map is not None:
                            # Draw person dot
                            cv2.circle(display_map, (map_x, map_y), 6, (0, 255, 255), -1)

                            # Draw movement vector arrow
                            history = self.track_history[tid]
                            if len(history) >= 6:
                                old_x, old_y = history[-6]
                                dx = map_x - old_x
                                dy = map_y - old_y
                                if abs(dx) > 2 or abs(dy) > 2:
                                    arrow_end = (map_x + dx * 3, map_y + dy * 3)
                                    cv2.arrowedLine(display_map,
                                                    (map_x, map_y),
                                                    (int(arrow_end[0]), int(arrow_end[1])),
                                                    (0, 200, 255), 2, tipLength=0.35)

                # ── Fall detection: check for suddenly vanished IDs ──
                vanished = self.prev_ids - current_ids
                now = time.time()
                for tid in vanished:
                    if self.id_seen_count.get(tid, 0) >= self.FALL_MIN_FRAMES:
                        if tid in self.last_map_pos:
                            mx, my = self.last_map_pos[tid]
                            self.fall_alerts[tid] = {'x': mx, 'y': my, 'time': now}
                    # Clean up tracking data for vanished IDs
                    self.id_seen_count.pop(tid, None)
                    self.track_history.pop(tid, None)

                self.prev_ids = current_ids.copy()

                # ── Draw fall alerts on floor plan ──
                if display_map is not None:
                    expired = []
                    for tid, alert in self.fall_alerts.items():
                        elapsed = now - alert['time']
                        if elapsed > self.FALL_ALERT_DURATION:
                            expired.append(tid)
                            continue
                        ax, ay = alert['x'], alert['y']
                        # Pulsing red circle
                        pulse = int(12 + 6 * abs(np.sin(elapsed * 4)))
                        cv2.circle(display_map, (ax, ay), pulse, (0, 0, 255), 2)
                        cv2.circle(display_map, (ax, ay), 5, (0, 0, 255), -1)
                        cv2.putText(display_map, 'FALL',
                                    (ax + 12, ay - 8),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                    (0, 0, 255), 2)
                    for tid in expired:
                        self.fall_alerts.pop(tid, None)
                        self.last_map_pos.pop(tid, None)

                fall_count = len(self.fall_alerts)

                # ── Collision detection using vector dot/cross product ──
                velocities = self._compute_velocities()
                new_collisions = self._detect_collisions(velocities)

                # Merge into history with timestamp
                _col_now = time.time()
                for col in new_collisions:
                    key = (min(col['id_a'], col['id_b']), max(col['id_a'], col['id_b']))
                    self._collision_history[key] = {'data': col, 'time': _col_now}

                # Prune expired entries
                expired_keys = [k for k, v in self._collision_history.items()
                                if _col_now - v['time'] > self.COLLISION_PERSIST_DURATION]
                for k in expired_keys:
                    del self._collision_history[k]

                # Build full collision list from history
                self.collisions = [v['data'] for v in self._collision_history.values()]

                # Draw collision warnings on floor plan
                if display_map is not None:
                    for col in self.collisions:
                        pa = col['pos_a']
                        pb = col['pos_b']
                        mid = ((pa[0] + pb[0]) // 2, (pa[1] + pb[1]) // 2)
                        # Orange warning line between the pair
                        cv2.line(display_map, pa, pb, (0, 100, 255), 2, cv2.LINE_AA)
                        # Warning triangle at midpoint
                        sz = 10
                        tri = np.array([
                            [mid[0], mid[1] - sz],
                            [mid[0] - sz, mid[1] + sz],
                            [mid[0] + sz, mid[1] + sz]
                        ], dtype=np.int32)
                        cv2.fillPoly(display_map, [tri], (0, 100, 255))
                        cv2.putText(display_map, '!', (mid[0] - 3, mid[1] + 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

            self.person_count = person_count

            # Compute density and notify ESP32
            self.density = self._compute_density(person_count)
            # Only flag a NEW fall (not already sent to ESP32)
            new_falls = set(self.fall_alerts.keys()) - self._esp32_notified_falls
            has_new_fall = len(new_falls) > 0
            has_collision = len(self.collisions) > 0
            _now = time.time()
            if _now - self.last_esp32_notify > 1.0:
                self.last_esp32_notify = _now
                if has_new_fall:
                    self._esp32_notified_falls.update(new_falls)
                threading.Thread(
                    target=self._notify_esp32,
                    args=(self.density, has_new_fall, has_collision),
                    daemon=True
                ).start()
            # Clean up notified set when fall alerts expire
            self._esp32_notified_falls &= set(self.fall_alerts.keys())

            # Encode frames as JPEG → base64
            _, cam_buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            cam_b64 = base64.b64encode(cam_buf).decode('utf-8')

            map_b64 = None
            if display_map is not None:
                _, map_buf = cv2.imencode('.jpg', display_map, [cv2.IMWRITE_JPEG_QUALITY, 80])
                map_b64 = base64.b64encode(map_buf).decode('utf-8')

            socketio.emit('frame', {
                'camera': cam_b64,
                'floorplan': map_b64,
                'person_count': person_count,
                'fall_count': fall_count,
                'fall_alerts': [{'id': tid, 'x': a['x'], 'y': a['y']} for tid, a in self.fall_alerts.items()],
                'density': round(self.density, 3),
                'collision_count': len(self.collisions),
                'collisions': [{'id_a': c['id_a'], 'id_b': c['id_b'], 'dist': c['distance'], 'time': c['time_frames']} for c in self.collisions],
                'esp32_connected': self.serial_conn is not None and self.serial_conn.is_open,
                'calibration_state': self.calibration_state,
                'map_points_count': len(self.map_points),
                'cam_points_count': len(self.cam_points),
            })

            time.sleep(0.05)  # ~20 FPS

    def get_status(self):
        return {
            'venue_loaded': self.venue is not None,
            'model_loaded': self.model is not None,
            'camera_open': self.cap is not None and self.cap.isOpened(),
            'calibration_state': self.calibration_state,
            'streaming': self.running,
            'person_count': self.person_count,
            'density': round(self.density, 3),
            'collision_count': len(self.collisions),
            'serial_port': self.serial_port,
            'esp32_connected': self.serial_conn is not None and self.serial_conn.is_open,
            'max_capacity': self.max_capacity,
        }


manager = LiveDetectionManager()


# ─── Routes ─────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/api/status')
def status():
    return jsonify(manager.get_status())


@app.route('/api/venues', methods=['GET'])
def list_venues():
    """List available venue YAML files."""
    venues = []
    # Check project root
    project_root = Path(__file__).parent.parent
    for f in project_root.glob('*.yaml'):
        venues.append({'name': f.stem, 'path': str(f)})
    # Check live_detection dir
    local_dir = Path(__file__).parent
    for f in local_dir.glob('*.yaml'):
        venues.append({'name': f.stem, 'path': str(f)})
    return jsonify(venues)


# ─── SocketIO Events ────────────────────────────────────────────────

@socketio.on('connect')
def on_connect():
    emit('status', manager.get_status())


@socketio.on('load_venue')
def on_load_venue(data):
    path = data.get('path', '')
    if not path or not os.path.exists(path):
        emit('error', {'message': f'Venue file not found: {path}'})
        return
    try:
        manager.load_venue(path)
        emit('venue_loaded', {'success': True})
    except Exception as e:
        emit('error', {'message': str(e)})


@socketio.on('load_model')
def on_load_model():
    try:
        emit('status_msg', {'message': 'Loading YOLO model...'})
        manager.load_model()
        emit('model_loaded', {'success': True})
    except Exception as e:
        emit('error', {'message': str(e)})


@socketio.on('open_camera')
def on_open_camera(data):
    source = data.get('source', 0)
    ok = manager.open_camera(source)
    emit('camera_opened', {'success': ok})


@socketio.on('start_calibration')
def on_start_calibration():
    manager.start_calibration()
    emit('calibration_started', {})


@socketio.on('map_click')
def on_map_click(data):
    manager.add_map_point(data['x'], data['y'])
    emit('calibration_update', {
        'state': manager.calibration_state,
        'map_points': len(manager.map_points),
        'cam_points': len(manager.cam_points),
    })


@socketio.on('cam_click')
def on_cam_click(data):
    manager.add_cam_point(data['x'], data['y'])
    emit('calibration_update', {
        'state': manager.calibration_state,
        'map_points': len(manager.map_points),
        'cam_points': len(manager.cam_points),
    })


@socketio.on('start_stream')
def on_start_stream():
    manager.start_streaming()


@socketio.on('stop_stream')
def on_stop_stream():
    manager.stop_streaming()


@socketio.on('set_serial_port')
def on_set_serial_port(data):
    port = data.get('port', '').strip()
    if not port:
        manager.disconnect_serial()
        emit('esp32_config', {'port': None, 'connected': False})
        return
    try:
        manager.connect_serial(port)
        emit('esp32_config', {'port': port, 'connected': True})
    except Exception as e:
        emit('esp32_config', {'port': port, 'connected': False, 'error': str(e)})


@socketio.on('set_max_capacity')
def on_set_max_capacity(data):
    cap = data.get('capacity', 30)
    manager.max_capacity = max(1, int(cap))
    emit('capacity_config', {'max_capacity': manager.max_capacity})


if __name__ == '__main__':
    print("=" * 50)
    print("Live Detection Server")
    print("http://localhost:5002")
    print("=" * 50)
    socketio.run(app, host='0.0.0.0', port=5002, debug=False)

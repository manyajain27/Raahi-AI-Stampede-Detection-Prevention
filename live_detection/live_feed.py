import cv2
import numpy as np
from ultralytics import YOLO
from collections import defaultdict, deque
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crowd_simulation.venue import Venue

clicked_points = []


def click_event(event, x, y, flags, param):
    global clicked_points
    if event == cv2.EVENT_LBUTTONDOWN:
        clicked_points.append((x, y))


def draw_venue_map(venue):
    ppm = venue.pixels_per_meter
    max_x = max(p.x for path in venue.pathways.values() for p in path.points) * ppm
    max_y = max(p.y for path in venue.pathways.values() for p in path.points) * ppm

    map_img = np.zeros((int(max_y) + 100, int(max_x) + 100, 3), dtype=np.uint8)

    for pathway in venue.pathways.values():
        pts = [(int(p.x * ppm), int(p.y * ppm)) for p in pathway.points]
        for i in range(len(pts) - 1):
            cv2.line(map_img, pts[i], pts[i + 1], (70, 70, 70), int(pathway.width * ppm))

    for choke in venue.choke_points.values():
        cx, cy = int(choke.position.x * ppm), int(choke.position.y * ppm)
        cv2.circle(map_img, (cx, cy), int(choke.radius * ppm), (0, 0, 255), 2)
        cv2.putText(
            map_img,
            choke.name,
            (cx - 20, cy - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            1,
        )

    return map_img


class CameraNode:
    def __init__(self, name, source):
        self.name = name
        self.source = source
        self.cap = cv2.VideoCapture(source)

        self.H_matrix = None
        self.map_cam_pos = None
        self.map_fov_poly = None

        self.track_history = defaultdict(lambda: deque(maxlen=20))
        self.smoothed_map_pts = {}
        self.active_ids = set()

        self.last_cam_pos = {}
        self.last_map_pos = {}
        self.lost_frames = defaultdict(int)

        # Temporal confidence buffer for fall detection
        self.fall_history = defaultdict(lambda: deque(maxlen=15))
        self.fallen_alerts = {}

    def calibrate(self, base_map):
        global clicked_points
        print(f"\n--- CALIBRATING: {self.name} ---")

        clicked_points = []
        window_name = f"Calibration - {self.name}"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)
        cv2.setMouseCallback(window_name, click_event)

        while len(clicked_points) < 1:
            temp_map = base_map.copy()
            cv2.putText(
                temp_map,
                f"1. Click the physical location of {self.name} on this map.",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 0),
                2,
            )
            cv2.imshow(window_name, temp_map)
            cv2.waitKey(1)

        self.map_cam_pos = clicked_points[0]

        clicked_points = []
        while len(clicked_points) < 4:
            temp_map = base_map.copy()
            cv2.putText(
                temp_map,
                "2. Click 4 corners defining the VIEW AREA on the map.",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
            )
            cv2.circle(temp_map, self.map_cam_pos, 8, (255, 0, 0), -1)

            for pt in clicked_points:
                cv2.circle(temp_map, pt, 5, (0, 255, 0), -1)

            if len(clicked_points) > 1:
                cv2.polylines(
                    temp_map,
                    [np.array(clicked_points)],
                    isClosed=False,
                    color=(0, 255, 0),
                    thickness=2,
                )

            cv2.imshow(window_name, temp_map)
            cv2.waitKey(1)

        map_points = np.array(clicked_points, dtype=np.float32)
        self.map_fov_poly = np.array(clicked_points, np.int32)

        clicked_points = []
        while len(clicked_points) < 4:
            success, frame = self.cap.read()
            if not success:
                break

            cv2.putText(
                frame,
                "3. Click the 4 matching physical points in order.",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )

            for pt in clicked_points:
                cv2.circle(frame, pt, 5, (0, 0, 255), -1)

            if len(clicked_points) > 1:
                cv2.polylines(
                    frame,
                    [np.array(clicked_points)],
                    isClosed=False,
                    color=(0, 0, 255),
                    thickness=2,
                )

            cv2.imshow(window_name, frame)
            cv2.waitKey(1)

        cam_points = np.array(clicked_points, dtype=np.float32)
        cv2.destroyWindow(window_name)

        self.H_matrix, _ = cv2.findHomography(cam_points, map_points)
        print(f"{self.name} Calibrated Successfully!")

    def cleanup_id(self, tid):
        self.smoothed_map_pts.pop(tid, None)
        self.last_cam_pos.pop(tid, None)
        self.last_map_pos.pop(tid, None)
        self.lost_frames.pop(tid, None)
        self.fall_history.pop(tid, None)
        self.track_history.pop(tid, None)

    def process_frame(self, model, display_map):
        success, frame = self.cap.read()
        if not success:
            return None

        results = model.track(frame, classes=[0], persist=True, verbose=False)
        current_ids = set()

        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().numpy()
            current_ids = set(track_ids)

            for box, track_id in zip(boxes, track_ids):
                x1, y1, x2, y2 = box
                box_w = x2 - x1
                box_h = y2 - y1

                center_x = int(x1 + box_w / 2)
                feet_x, feet_y = center_x, int(y2)

                cam_pt = np.array([[[feet_x, feet_y]]], dtype=np.float32)
                floor_pt = cv2.perspectiveTransform(cam_pt, self.H_matrix)[0][0]
                map_x, map_y = int(floor_pt[0]), int(floor_pt[1])

                self.last_map_pos[track_id] = (map_x, map_y)
                cv2.circle(display_map, (map_x, map_y), 6, (0, 255, 255), -1)

        self.active_ids = current_ids
        cv2.putText(frame, self.name, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        return frame


def main():
    venue = Venue.from_yaml("crowd_simulation/venue.yaml")
    base_map_img = draw_venue_map(venue)
    model = YOLO("yolov8n.pt")

    cameras = [CameraNode(name="Main Camera", source=0)]

    for cam in cameras:
        if cam.cap.isOpened():
            cam.calibrate(base_map_img)

    cv2.namedWindow("Security Dashboard", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Security Dashboard", 1280, 720)

    print("\n--- LAUNCHING UNIFIED DASHBOARD ---")

    while True:
        display_map = base_map_img.copy()

        for cam in cameras:
            if cam.map_cam_pos and cam.map_fov_poly is not None:
                cv2.polylines(display_map, [cam.map_fov_poly], True, (100, 100, 100), 2)
                cv2.circle(display_map, cam.map_cam_pos, 10, (255, 100, 0), -1)

        for cam in cameras:
            if cam.cap.isOpened() and cam.H_matrix is not None:
                frame = cam.process_frame(model, display_map)
                if frame is not None:
                    cv2.imshow(cam.name, frame)

        cv2.imshow("Security Dashboard", display_map)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    for cam in cameras:
        cam.cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
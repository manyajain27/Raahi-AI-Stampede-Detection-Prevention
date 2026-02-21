# import cv2
# import numpy as np
# from ultralytics import YOLO
# from collections import defaultdict, deque
# import sys
# import os

# # Ensure the simulation module can be imported
# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# from crowd_simulation.venue import Venue

# # Global variables for calibration
# cam_points = []
# map_points = []
# calibration_done = False

# # Mouse callback for clicking on the camera feed
# def click_cam(event, x, y, flags, param):
#     if event == cv2.EVENT_LBUTTONDOWN and len(cam_points) < 4:
#         cam_points.append((x, y))

# # Mouse callback for clicking on the floor plan
# def click_map(event, x, y, flags, param):
#     if event == cv2.EVENT_LBUTTONDOWN and len(map_points) < 4:
#         map_points.append((x, y))

# # Function to render the venue.yaml as an image
# def draw_venue_map(venue):
#     # Create a blank black image (1200x1800 to fit the YAML coordinates)
#     map_img = np.zeros((1200, 1800, 3), dtype=np.uint8)
#     ppm = venue.pixels_per_meter

#     # Draw pathways
#     for pathway in venue.pathways.values():
#         pts = [(int(p.x * ppm), int(p.y * ppm)) for p in pathway.points]
#         for i in range(len(pts) - 1):
#             # Draw gray paths
#             cv2.line(map_img, pts[i], pts[i+1], (70, 70, 70), int(pathway.width * ppm))
    
#     # Draw Choke points in Red
#     for choke in venue.choke_points.values():
#         cx, cy = int(choke.position.x * ppm), int(choke.position.y * ppm)
#         cv2.circle(map_img, (cx, cy), int(choke.radius * ppm), (0, 0, 255), 2)
#         cv2.putText(map_img, choke.name, (cx - 20, cy - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

#     return map_img

# def main():
#     global calibration_done
    
#     # 1. Load the venue and create the base map image
#     venue = Venue.from_yaml("crowd_simulation/venue.yaml")
#     base_map_img = draw_venue_map(venue)
    
#     print("Loading YOLO model...")
#     model = YOLO('yolov8n.pt')
#     cap = cv2.VideoCapture(0)

#     # 2. Setup the windows and mouse click events
#     cv2.namedWindow("Camera")
#     cv2.setMouseCallback("Camera", click_cam)
    
#     cv2.namedWindow("Floor Plan")
#     cv2.setMouseCallback("Floor Plan", click_map)

#     track_history = defaultdict(lambda: deque(maxlen=10))
#     H_matrix = None

#     print("\n--- CALIBRATION PHASE ---")
#     print("1. Click 4 points on the 'Camera' window that form a square/rectangle on the physical floor.")
#     print("2. Click the 4 exact corresponding points on the 'Floor Plan' window.")

#     while cap.isOpened():
#         success, frame = cap.read()
#         if not success: 
#             break
        
#         # Fresh copy of the map every frame
#         display_map = base_map_img.copy()

#         # --- CALIBRATION LOGIC ---
#         if not calibration_done:
#             # Draw the points the user is clicking
#             for pt in cam_points: 
#                 cv2.circle(frame, pt, 5, (0, 0, 255), -1)
#             for pt in map_points: 
#                 cv2.circle(display_map, pt, 5, (0, 255, 0), -1)
            
#             # Once 4 points are clicked on both, calculate the Perspective Matrix!
#             if len(cam_points) == 4 and len(map_points) == 4:
#                 H_matrix, _ = cv2.findHomography(np.array(cam_points), np.array(map_points))
#                 calibration_done = True
#                 print("\nCalibration complete! Starting live tracking on the floor plan...")
        
#         # --- LIVE TRACKING LOGIC ---
#         else:
#             results = model.track(frame, classes=[0], persist=True, verbose=False)
#             if results[0].boxes.id is not None:
#                 boxes = results[0].boxes.xyxy.cpu().numpy()
#                 track_ids = results[0].boxes.id.int().cpu().numpy()

#                 for box, track_id in zip(boxes, track_ids):
#                     x1, y1, x2, y2 = box
#                     center_x, center_y = int((x1 + x2) / 2), int((y1 + y2) / 2)
#                     feet_x, feet_y = int((x1 + x2) / 2), int(y2)

#                     history = track_history[track_id]
#                     history.append((center_x, center_y))

#                     # 1. THIN BOUNDING BOX (Thickness = 1, dark gray)
#                     cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (100, 100, 100), 1)

#                     if len(history) >= 5:
#                         dx = center_x - history[-5][0]
#                         dy = center_y - history[-5][1]
#                         if abs(dx) > 2 or abs(dy) > 2:
#                             # Draw vector on camera feed
#                             cv2.arrowedLine(frame, (center_x, center_y), (int(center_x + dx*3), int(center_y + dy*3)), (0, 0, 255), 2, tipLength=0.3)

#                     # 2. THE MAGIC: PERSPECTIVE TRANSFORM (Map to Floor Plan)
#                     # We take the feet coordinates from the camera and warp them into floor plan coordinates
#                     cam_pt = np.array([[[feet_x, feet_y]]], dtype=np.float32)
#                     floor_pt = cv2.perspectiveTransform(cam_pt, H_matrix)[0][0]
#                     map_x, map_y = int(floor_pt[0]), int(floor_pt[1])

#                     # Draw the person as a yellow dot on the digital floor plan!
#                     cv2.circle(display_map, (map_x, map_y), 6, (0, 255, 255), -1)
                    
#                     # Optional: Draw their movement vector on the floor plan as well
#                     if len(history) >= 5:
#                         # Find where their feet were 5 frames ago and map that point too
#                         old_feet_cam_pt = np.array([[[history[-5][0], history[-5][1] + (y2-y1)/2]]], dtype=np.float32)
#                         old_floor_pt = cv2.perspectiveTransform(old_feet_cam_pt, H_matrix)[0][0]
#                         old_m_x, old_m_y = int(old_floor_pt[0]), int(old_floor_pt[1])
                        
#                         m_dx = map_x - old_m_x
#                         m_dy = map_y - old_m_y
                        
#                         if abs(m_dx) > 1 or abs(m_dy) > 1:
#                             cv2.arrowedLine(display_map, (map_x, map_y), (map_x + int(m_dx*3), map_y + int(m_dy*3)), (0, 255, 255), 2, tipLength=0.3)

#         cv2.imshow("Camera", frame)
#         cv2.imshow("Floor Plan", display_map)
        
#         if cv2.waitKey(1) & 0xFF == ord('q'): 
#             break
        
#     cap.release()
#     cv2.destroyAllWindows()

# if __name__ == "__main__":
#     main()

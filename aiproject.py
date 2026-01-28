import cv2
import numpy as np
import mediapipe as mp
import warnings
import pygame
import time

warnings.filterwarnings("ignore", category=UserWarning, module='google.protobuf')

pygame.mixer.init()
ALERT_PLAYING = False

def start_alert():
    global ALERT_PLAYING
    if not ALERT_PLAYING:
        try:
            pygame.mixer.music.load("alert.wav")
            pygame.mixer.music.play(-1)
            ALERT_PLAYING = True
        except Exception as e:
            print(f" Error playing sound: {e}")

def stop_alert():
    global ALERT_PLAYING
    if ALERT_PLAYING:
        pygame.mixer.music.stop()
        ALERT_PLAYING = False

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

def eye_aspect_ratio(eye_points):
    A = np.linalg.norm(eye_points[1] - eye_points[5])
    B = np.linalg.norm(eye_points[2] - eye_points[4])
    C = np.linalg.norm(eye_points[0] - eye_points[3])
    return (A + B) / (2.0 * C)

def mouth_aspect_ratio(mouth_points):
    A = np.linalg.norm(mouth_points[0] - mouth_points[1])
    B = np.linalg.norm(mouth_points[2] - mouth_points[3])
    C = np.linalg.norm(mouth_points[4] - mouth_points[5])
    return (A + B) / (2.0 * C)

EYE_AR_THRESH = 0.20
EYE_AR_CONSEC_FRAMES = 19

MOUTH_AR_THRESH = 0.55
MOUTH_AR_CONSEC_FRAMES = 5

HEAD_TILT_DROP = 0.12
HEAD_TILT_CONSEC_FRAMES = 20

COUNTER_EYE = 0
COUNTER_MOUTH = 0
COUNTER_HEAD = 0

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
MOUTH = [81, 311, 13, 14, 78, 308]
NOSE_TIP = 1

baseline_nose_rel = None
baseline_frames = 30
frame_count = 0

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Could not access camera.")
    exit()

print("Camera started. Press 'q' to quit.")
cv2.namedWindow("Drowsiness Detection", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Drowsiness Detection", 1280, 720)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print(" Failed to grab frame.")
        break

    frame = cv2.flip(frame, 1)
    h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    results = face_mesh.process(rgb)
    drowsy = False
    yawning = False
    head_down = False

    if not results.multi_face_landmarks:
        COUNTER_HEAD += 1
        if COUNTER_HEAD >= HEAD_TILT_CONSEC_FRAMES:
            head_down = True

        cv2.putText(frame, "FACE NOT CLEAR | HEAD DOWN ALERT!", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        start_alert()
        cv2.imshow("Drowsiness Detection", frame)
        continue

    for face_landmarks in results.multi_face_landmarks:

        xs = [lm.x * w for lm in face_landmarks.landmark]
        ys = [lm.y * h for lm in face_landmarks.landmark]

        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        face_height = max_y - min_y

        if face_height < 80:
            COUNTER_HEAD += 1
            if COUNTER_HEAD >= HEAD_TILT_CONSEC_FRAMES:
                head_down = True

            cv2.putText(frame, "FACE NOT CLEAR | HEAD DOWN ALERT!", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            start_alert()
            cv2.imshow("Drowsiness Detection", frame)
            continue

        cv2.rectangle(frame, (min_x, min_y), (max_x, max_y), (255, 0, 255), 2)

        nose_y = face_landmarks.landmark[NOSE_TIP].y * h
        nose_rel = (nose_y - min_y) / face_height

        if frame_count < baseline_frames:
            if baseline_nose_rel is None:
                baseline_nose_rel = 0
            baseline_nose_rel += nose_rel
            frame_count += 1

            if frame_count == baseline_frames:
                baseline_nose_rel /= baseline_frames
                print(" Head baseline stored.")
            continue

        if nose_rel > baseline_nose_rel + HEAD_TILT_DROP:
            COUNTER_HEAD += 1
            if COUNTER_HEAD >= HEAD_TILT_CONSEC_FRAMES:
                head_down = True
        else:
            COUNTER_HEAD = 0

        left_eye = np.array([(face_landmarks.landmark[i].x * w,
                              face_landmarks.landmark[i].y * h) for i in LEFT_EYE])
        right_eye = np.array([(face_landmarks.landmark[i].x * w,
                               face_landmarks.landmark[i].y * h) for i in RIGHT_EYE])

        leftEAR = eye_aspect_ratio(left_eye)
        rightEAR = eye_aspect_ratio(right_eye)
        ear = (leftEAR + rightEAR) / 2.0

        mouth_points = np.array([(face_landmarks.landmark[i].x * w,
                                  face_landmarks.landmark[i].y * h) for i in MOUTH])
        mar = mouth_aspect_ratio(mouth_points)

        cv2.polylines(frame, [left_eye.astype(np.int32)], True, (0, 255, 0), 1)
        cv2.polylines(frame, [right_eye.astype(np.int32)], True, (0, 255, 0), 1)
        cv2.polylines(frame, [mouth_points.astype(np.int32)], True, (255, 255, 0), 1)

        if ear < EYE_AR_THRESH:
            COUNTER_EYE += 1
            if COUNTER_EYE >= EYE_AR_CONSEC_FRAMES:
                drowsy = True
        else:
            COUNTER_EYE = 0

        if mar > MOUTH_AR_THRESH:
            COUNTER_MOUTH += 1
            if COUNTER_MOUTH >= MOUTH_AR_CONSEC_FRAMES:
                yawning = True
        else:
            COUNTER_MOUTH = 0

    alerts = []

    if drowsy: alerts.append("DROWSY")
    if yawning: alerts.append("YAWNING")
    if head_down: alerts.append("HEAD DOWN")

    if alerts:
        cv2.putText(frame, " | ".join(alerts) + " ALERT!", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        start_alert()
    else:
        cv2.putText(frame, "Awake", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        stop_alert()

    cv2.imshow("Drowsiness Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
stop_alert()
print("Closed.")
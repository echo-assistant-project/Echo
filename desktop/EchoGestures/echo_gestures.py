"""EchoGestures: control Echo with your hand (webcam + MediaPipe Hands, from the hand-tracking workshop).

Open palm = stop / interrupt Echo · two fingers (victory) = talk · fist = play/pause · thumbs up/down = volume ·
swipe left/right = previous/next track. Recognised gestures go to EchoDesktop on 127.0.0.1 (UDP 31418).
Video never leaves this PC and nothing is saved. Press Q in the window to quit.

Run:  powershell -ExecutionPolicy Bypass -File desktop\\EchoGestures\\Run-EchoGestures.ps1
"""
import sys
from pathlib import Path

import cv2
import mediapipe as mp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "EchoDesktop"))
from echo_desktop.gestures import ACTIONS, Smoother, send  # noqa: E402


def main(camera: int = 0) -> None:
    hands = mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)
    draw = mp.solutions.drawing_utils
    cap = cv2.VideoCapture(camera)
    smoother = Smoother()
    last = ""
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            print("Unable to access the webcam.")
            break
        frame = cv2.flip(frame, 1)                       # mirror view, as in the workshop
        results = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        landmarks = None
        if results.multi_hand_landmarks:
            hand = results.multi_hand_landmarks[0]
            draw.draw_landmarks(frame, hand, mp.solutions.hands.HAND_CONNECTIONS)
            landmarks = [(p.x, p.y) for p in hand.landmark]
        gesture = smoother.feed(landmarks)
        if gesture:
            send(gesture)
            last = f"{gesture} -> {ACTIONS[gesture]}"
        cv2.putText(frame, last or "Show your hand", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (66, 217, 255), 2)
        cv2.imshow("EchoGestures", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    hands.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 0)

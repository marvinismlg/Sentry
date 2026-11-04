import cv2, csv, datetime, sys, importlib
from pathlib import Path
import os
# system module and path import stuff

project_root = str(Path(__file__).resolve().parent)
original_path = sys.path.copy()
sys.path = [p for p in sys.path if Path(p or ".").resolve() != Path(project_root)]

# Error handling
try:
    face_recognition = importlib.import_module("face_recognition")
finally:
    sys.path = original_path
from pathlib import Path
from functools import lru_cache
import os

# I'll add error logging here as well, just in case.

Error_Logs = Path("error_logs.csv")

# Define the face that we'll be using for authentication
# Because were using windows, we need to create a virtual environment in the old python 3.11. for us to be able to run the pi scripts.
# Because of this we need to run the virtual environment instead of directly running the file
# Here is the terminal copy paste: .\.venv\Scripts\python.exe ..\camera.py

# Also, below is a hardcoded path that only works with my computer and with windows, when uploading to the Pi, we'll need to change it later

faces_folder = Path(__file__).resolve().parent / "faces"

faces_list = [
    image for image in faces_folder.iterdir()
    if image.suffix.lower() in (".png", ".jpg", ".jpeg")
]
# face_image = Path(r"C:\Users\marvi\PycharmProjects\Sentry\faces\marvin.png")
tolerance = 0.45


# Error logging flow just in case the recognition has any errors

errors = {
    "invalid_frame": {
        "Function Name": "scan_frame_for_faces",
        "Error Type": "Invalid Frame",
        "Message": "No valid frame was provided",
        "Severity": "Mid"},
    "frame_conversion": {
        "Function Name": "scan_frame_for_faces",
        "Error Type": "Image Conversion",
        "Message": "Failed to convert BGR frame to RGB",
        "Severity": "High"},
    "face_detection": {
        "Function Name": "scan_frame_for_faces",
        "Error Type": "Face Detection",
        "Message": "Facial recognition engine failed to process frame",
        "Severity": "High"},
    "reference_image": {
        "Function Name": "load_known_face",
        "Error Type": "Reference Image",
        "Message": "Reference image missing or does not contain exactly one face",
        "Severity": "High"},
    "recognition_failure": {
        "Function Name": "process_image_frame",
        "Error Type": "Face Verification",
        "Message": "Face verification failed",
        "Severity": "Mid"}}

# Error logging func
def error_logging(error_key, details=""):
    if error_key not in errors: return
    try:
        e = errors[error_key]
        new_file = not Error_Logs.exists() or Error_Logs.stat().st_size == 0
        with open(Error_Logs, "a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            if new_file: writer.writerow(["Timestamp", "Function Name", "Error Type", "Message", "Severity"])
            message = e["Message"] + (f" | {details}" if details else "")
            writer.writerow([datetime.datetime.now().strftime("%Y%m%d-%H%M%S"),
                             e["Function Name"], e["Error Type"], message, e["Severity"]])
    except OSError as e:
        print("Error logging failed:", e)

@lru_cache(maxsize=1)
# GOGGINS GOGGINS GOGGINS GOGGINS
# I'm changing this func so that it loops through the faces folder and compares each individual face with the face of the person trying to authenticate
# If any of the faces match, it authenticates the person, if none of them match, it still keeps the red flashing

# SON
def load_known_face():
    authorized_faces = {}
    for face_image in faces_list:
        try:
            image = face_recognition.load_image_file(str(face_image))
            encodings = face_recognition.face_encodings(image)
            if len(encodings) != 1:
                raise ValueError(f"{face_image.name} must contain exactly one face")
            authorized_faces[face_image.stem] = encodings[0]
        except Exception as e:
            error_logging("reference_image", str(e))
    if not authorized_faces:
        error_logging("reference_image", "No valid authorized faces found")
        raise ValueError("No valid authorized faces found")
    return authorized_faces

def scan_frame_for_faces(raw_bgr_frame):
    if raw_bgr_frame is None:
        error_logging("invalid_frame")
        print("No valid frame was provide.")
        return []
    # The face_recognition engine expects PNG images. Right now its hardcoded to just fit my face but we can allow it to fit other people in the future and we can store approved faces in an actual database
    try:
        rgb_frame = cv2.cvtColor(raw_bgr_frame, cv2.COLOR_BGR2RGB)
    except Exception as e:
        error_logging("frame_conversion", str(e))
        return []

    print("Scanning for facials (pause) goggins")

    try:
        face_locations = face_recognition.face_locations(rgb_frame)
    except Exception as e:
        error_logging("face_detection", str(e))
        return []

    if len(face_locations) == 0: print("No faces detected")
    else: print(f"Found {len(face_locations)} face(s) inside this frame.")
    return face_locations

# I lowk vibecoded ts, but I verified it to make sure all the code works
def process_image_frame(raw_bgr_frame):
    if raw_bgr_frame is None:
        error_logging("invalid_frame")
        return False
    try:
        known_faces = load_known_face()
        rgb = cv2.cvtColor(raw_bgr_frame, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb)
        if len(locations) != 1:
            error_logging("recognition_failure", f"Detected {len(locations)} faces")
            return False
        encodings = face_recognition.face_encodings(rgb, locations)
        if len(encodings) != 1:
            error_logging("recognition_failure", "Could not encode detected face")
            return False

        for name, known_encoding in known_faces.items():
            distance = face_recognition.face_distance([known_encoding], encodings[0])[0]
            if distance <= tolerance:
                print(f"Authenticated: {name} | Distance: {distance:.3f}")
                return True

        error_logging("recognition_failure", "No authorized faces matched")
        print("Access Denied: Face not recognized")
        return False
    except Exception as e:
        error_logging("face_detection", str(e))
        return False


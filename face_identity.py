"""SENTRY face identity engine (separate from the third-party face_recognition package)."""
from functools import lru_cache
from pathlib import Path

import cv2
import face_recognition as face_lib

FACES_DIR = Path(__file__).resolve().parent / "faces"
TOLERANCE = 0.45


@lru_cache(maxsize=1)
def load_known_face():
    """Return a mapping of enrolled names to 128-dimensional face encodings."""
    FACES_DIR.mkdir(parents=True, exist_ok=True)
    known = {}
    for path in sorted(FACES_DIR.iterdir()):
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        try:
            image = face_lib.load_image_file(str(path))
            encodings = face_lib.face_encodings(image)
            if len(encodings) == 1:
                known[path.stem] = encodings[0]
            else:
                print(f"Skipping {path.name}: expected exactly one face, found {len(encodings)}")
        except Exception as exc:
            print(f"Skipping {path.name}: {exc}")
    return known


def refresh_known_faces():
    load_known_face.cache_clear()
    return load_known_face()


def identify_face(raw_bgr_frame):
    """Return (matched_name_or_None, distance_or_None, status_message)."""
    if raw_bgr_frame is None:
        return None, None, "Camera frame unavailable"
    try:
        known = load_known_face()
        if not known:
            return None, None, "No enrolled faces found"
        rgb = cv2.cvtColor(raw_bgr_frame, cv2.COLOR_BGR2RGB)
        locations = face_lib.face_locations(rgb)
        if len(locations) != 1:
            return None, None, f"Expected one face, detected {len(locations)}"
        encodings = face_lib.face_encodings(rgb, locations)
        if len(encodings) != 1:
            return None, None, "Could not encode detected face"
        names = list(known)
        distances = face_lib.face_distance(list(known.values()), encodings[0])
        best = int(distances.argmin())
        distance = float(distances[best])
        if distance > TOLERANCE:
            return None, distance, "Face not recognized"
        return names[best], distance, f"Face recognized: {names[best]}"
    except Exception as exc:
        return None, None, f"Face recognition error: {exc}"


def process_image_frame(raw_bgr_frame):
    """Compatibility with callers expecting a boolean result."""
    name, _, _ = identify_face(raw_bgr_frame)
    return name is not None


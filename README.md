
# Sentry

**A Python-based biometric authentication prototype exploring facial recognition, speaker verification, and real-time camera/microphone interfaces.**

Sentry is an experimental cybersecurity project built to investigate how biometric signals could be used in access-control workflows. It includes a facial-recognition implementation on `windows-branch` and a voice-enrollment and speaker-verification implementation on `main`. These are **separate prototypes**, not yet a unified two-factor authentication system.

> **Project status:** Active prototype / proof of concept. Not intended for production authentication or physical-access enforcement.

## Highlights

- **Face verification (`windows-branch`):** Capture a camera frame, detect a face, compare its encoding with locally stored reference photos, and display an access-granted or access-denied result.
- **Voice enrollment (`main`):** Record eight 8-second audio samples per person and save them as WAV files in a local profile directory.
- **Speaker verification (`main`):** Compare a microphone recording against enrolled voice samples using SpeechBrain's pretrained ECAPA-TDNN model; reject low-confidence and ambiguous matches using preliminary thresholds.
- **Desktop interface:** Use CustomTkinter to display a camera feed, microphone activity, recognition status, and enrollment or verification controls.
- **Diagnostics (`windows-branch`):** Record categorized application errors, timestamps, and severity levels in CSV format.

## Technology

| Area | Tools and libraries |
| --- | --- |
| Language | Python |
| Desktop UI | CustomTkinter, Pillow |
| Computer vision | OpenCV, `face_recognition` (dlib-based) |
| Voice biometrics | SpeechBrain ECAPA-TDNN, PyTorch ecosystem |
| Audio capture | SoundDevice, NumPy, WAV files |
| Concurrency | `threading`, `queue` |
| Diagnostics | Python `csv`, `datetime` |

The `main` branch also includes a separate, earlier MFCC/cosine-similarity audio experiment in `Voice implementation`; it is not the active model used by `voice_recognition.py`.

## Repository layout

This project currently separates features across branches.

### `main`: Voice prototype

```text
README.md
Camera and Microphone UI.py   # Camera feed, microphone monitor, voice controls
voice_enrollment.py           # Voice profile enrollment interface
voice_recognition.py          # ECAPA-TDNN-based speaker comparison
Voice implementation          # Earlier standalone MFCC experiment
```

### `windows-branch`: Face prototype

```text
README.md
camera.py                     # Desktop interface and camera/microphone controls
face_recognition.py           # Authorized-face comparison logic
faces/                        # Local reference-image directory
faces_list/                   # Webcam screenshot output
error_logs.csv                # Application diagnostics
requirements.txt              # Windows prototype dependencies
requirements_for_pi.txt       # Raspberry Pi-oriented dependency list
```

**Privacy note:** The current Windows branch includes a sample face image in `faces_list/`. Any real biometric images, voice samples, or logs should be excluded from version control unless their publication is intentional and consented to.

## How the prototypes work

### Facial-recognition workflow (`windows-branch`)

1. Open the desktop application and capture a frame from the webcam.
2. Detect faces using the `face_recognition` library.
3. Require exactly one detected face in the verification frame.
4. Compare its face encoding against reference images in `faces/`.
5. Return a match when the face distance is at or below the configured tolerance (`0.45`), and update the interface.

The application uses a background thread for recognition, a queue to deliver the result to the UI, and CSV logging for selected failures. Its microphone-monitoring controls are gated by successful **face** verification; that is not equivalent to a second voice-authentication factor.

### Voice-recognition workflow (`main`)

1. Open the enrollment dialog and enter a name.
2. Record eight audio samples (eight seconds each) for the profile.
3. Save samples to `~/voice_profiles/<name>/sample_*.wav`.
4. Record an eight-second verification sample.
5. Compare the sample with enrolled recordings through the pretrained SpeechBrain speaker-verification model.
6. Rank profiles by average similarity, applying an initial match threshold (`0.25`) and minimum lead over the next-best profile (`0.05`).
7. Display a provisional speaker match or a rejection message.

The current thresholds are experimental and **have not been validated for security performance**. The code requires at least three stored samples per profile before comparing it.

## Local setup

A camera and microphone are needed to exercise the interactive prototypes. Python 3.11 is a reasonable starting point for the Windows branch, but platform-specific native dependencies (especially dlib) may require additional setup.

### Windows face prototype

```powershell
# From the repository root
git switch windows-branch
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\camera.py
```

Place an **authorized, consented-to** reference photo containing exactly one visible face in `faces/` before attempting face verification. Depending on the device, camera permissions or audio device selection may need adjustment.

### Voice prototype (`main`)

```powershell
# From the repository root
git switch main
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install customtkinter opencv-python sounddevice numpy Pillow speechbrain torch torchaudio
.\.venv\Scripts\python.exe '.\Camera and Microphone UI.py'
```

The SpeechBrain model is downloaded from `speechbrain/spkrec-ecapa-voxceleb` when first needed. The voice branch does **not** currently have a pinned dependency lockfile, and the commands above have not been validated end-to-end on every supported platform.

**Important:** Do not commit `.venv/`, `faces/.venv/`, model downloads, or private biometric recordings. Virtual environments are machine-specific and should be recreated locally.

## Engineering challenges and lessons

- **Hardware integration:** Coordinating webcam and microphone inputs inside a responsive desktop interface.
- **Separation of responsibilities:** Keeping the camera/UI path separate from image and voice verification logic.
- **Asynchronous work:** Running recognition outside the UI event loop and returning results through thread-safe queues.
- **Biometric comparison:** Exploring face embeddings and pretrained speaker embeddings, including threshold-based rejection and ambiguous-speaker handling.
- **Failure visibility:** Introducing structured CSV diagnostics for camera, audio, and recognition errors.

## Limitations and next steps

This repository is a development prototype. Before it could be described as a deployable authentication system, it would need:

1. **Unified verification:** Connect face and voice checks in one explicit policy that requires both factors to succeed.
2. **Security testing:** Add liveness/presentation-attack defenses, replay resistance, threshold calibration, and documented false-accept/false-reject measurements.
3. **Biometric data protection:** Define consent, secure storage, retention/deletion, and access controls for reference photos, recordings, and derived representations.
4. **Reproducibility:** Consolidate branch behavior, pin dependencies, add automated tests, and validate Windows/Raspberry Pi installation instructions.
5. **User experience:** Add screenshots or a short demo, clear device-error handling, and reproducible test cases.

No published biometric accuracy benchmarks, adversarial tests, or real-world deployment claims are provided by the current repository.

## Project context

Sentry is a personal engineering exploration of biometric access control, computer vision, audio processing, and desktop application design. The goal is to build hands-on understanding of the tradeoffs involved in converting sensor data into authentication decisions, and to progressively develop a reliable, testable implementation.

**Repository:** https://github.com/marvinismlg/Sentry

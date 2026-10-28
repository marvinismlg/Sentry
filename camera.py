import customtkinter as ctk
import cv2, sounddevice as sd, numpy as np, threading, csv, datetime
from queue import Queue, Empty
from PIL import Image
import importlib.util
from pathlib import Path
# Son
import os
import time

# Command to run the virtual environment
# First type "cd sentry" then copy and paste the command
# .\faces\.venv\Scripts\python.exe .\camera.py
# Were gonna have to use some extra libraries... I want to separate the recognition code from the webcam code just so we don't have files that are 400 lines long

path = Path(__file__).resolve().parent / "face_recognition.py"
spec = importlib.util.spec_from_file_location("recognition_service", path)
recognition_service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recognition_service)

# Since ts project has a lot of moving parts, I've decided to add some error logging just so we can track what actually goes wrong
# I've alr done it for a diff project so I'll just copy paste the code and change the variables

Error_Logs = Path("error_logs.csv")

# I'll probably just have AI scan the codebase, identify potential errors and I'll generatr the list and add all the errors to existing functions

errors = {
    "camera_initialization": {
        "Function Name": "camera",
        "Error Type": "Camera Initialization",
        "Message": "Camera device could not be opened",
        "Severity": "High"
    },
    "camera_capture": {
        "Function Name": "update_camera",
        "Error Type": "Frame Capture",
        "Message": "Camera failed to capture a frame",
        "Severity": "Mid"
    },
    "camera_conversion": {
        "Function Name": "update_camera",
        "Error Type": "Image Conversion",
        "Message": "Captured frame could not be converted",
        "Severity": "Mid"
    },
    "microphone_initialization": {
        "Function Name": "sd.Stream",
        "Error Type": "Microphone Initialization",
        "Message": "Audio stream failed to initialize",
        "Severity": "High"
    },
    "microphone_unavailable": {
        "Function Name": "toggle_mic",
        "Error Type": "Microphone Availability",
        "Message": "Microphone monitoring unavailable because audio stream is missing",
        "Severity": "Mid"
    },
    "audio_callback": {
        "Function Name": "audio_callback",
        "Error Type": "Audio Processing",
        "Message": "Audio callback reported an error or processing failure",
        "Severity": "High"
    },
    "recognition_unavailable": {
        "Function Name": "recognition_worker",
        "Error Type": "Recognition Service",
        "Message": "Recognition service could not be imported",
        "Severity": "High"
    },
    "recognition_failure": {
        "Function Name": "recognition_worker",
        "Error Type": "Facial Recognition",
        "Message": "Recognition service failed to process image",
        "Severity": "High"
    },
    "missing_frame": {
        "Function Name": "run_recognition",
        "Error Type": "Missing Camera Frame",
        "Message": "Facial recognition requested without an available frame",
        "Severity": "Mid"
    },
    "microphone_shutdown": {
        "Function Name": "close_app",
        "Error Type": "Audio Shutdown",
        "Message": "Failed to stop or close audio stream",
        "Severity": "Low"
    },
    "camera_shutdown": {
        "Function Name": "close_app",
        "Error Type": "Camera Shutdown",
        "Message": "Failed to release camera resource",
        "Severity": "Low"
    }
}

log_lock = threading.Lock()
logged_errors = set() # I'll add them all to a set before I actually send them to the csv

def error_logging(error_key, details="", once=False):
    if error_key not in errors: return
    try:
        with log_lock:
            if once and error_key in logged_errors: return
            e = errors[error_key]
            new_file = not Error_Logs.exists() or Error_Logs.stat().st_size == 0
            with open(Error_Logs, "a", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                if new_file: writer.writerow(["Timestamp", "Function Name", "Error Type", "Message", "Severity"])
                message = e["Message"] + (f" | {details}" if details else "")
                writer.writerow([datetime.datetime.now().strftime("%Y%m%d-%H%M%S"),
                                 e["Function Name"], e["Error Type"], message, e["Severity"]])
            if once: logged_errors.add(error_key)
    except OSError as e:
        print("Error logging failed:", e)
def reset_error(error_key):
    with log_lock: logged_errors.discard(error_key)

W, H, FPS, RATE, BLOCK = 640, 480, 20, 44100, 1024
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("Raspberry Pi 5 - Camera and Microphone")
app.geometry("1000x850")

frame = ctk.CTkFrame(app)
frame.pack(padx=20, pady=20, fill="both", expand=True)

ctk.CTkLabel(frame, text="Raspberry Pi 5 - Recognition System", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=15)
cam_label = ctk.CTkLabel(frame, text="Starting camera...", width=W, height=H)
cam_label.pack(pady=10)

def capture_webcam_screenshot():
    save_folder = "faces_list"
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return
    time.sleep(0.5)
    ret, frame = cap.read()
    if ret:
        filename = f"face_{int(time.time())}.jpg"
        filepath = os.path.join(save_folder, filename)
        cv2.imwrite(filepath, frame)
        print(f"Saved to: {filepath}")
    else:
        print("Cannot read ts")
    cap.release()

# Adding a webcam screenshot feature that automatically saves photos of your face to the "faces" folder
screenshot_button = ctk.CTkButton(master=frame, text="Take a webcam screenshot", font=("Arial Bold", 20), text_color="White", command=capture_webcam_screenshot)
screenshot_button.pack(pady=20)


# camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, W)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
camera.set(cv2.CAP_PROP_FPS, FPS)

frame_lock, audio_lock = threading.Lock(), threading.Lock()
raw_frame, cam_image, stream = None, None, None
running, monitoring, audio_level, busy = True, False, 0.0, False

# In order to get the code to work locally on my laptop, I had to refractor some of it so it would work on my laptop, I had AI do most of the refractoring but for the manual stuff, I'll just comment out the raspberry pi stuff
def update_camera():
    global raw_frame, cam_image
    if not running: return
    try:
        ok, img = camera.read()
        if ok:
            reset_error("camera_capture")
            with frame_lock: raw_frame = img.copy()
            try:
                rgb = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                if cam_image is None:
                    cam_image = ctk.CTkImage(light_image=rgb, dark_image=rgb, size=(W, H))
                    cam_label.configure(image=cam_image, text="")
                else: cam_image.configure(light_image=rgb, dark_image=rgb)
                reset_error("camera_conversion")
            except Exception as e:
                error_logging("camera_conversion", str(e), once=True)
        else:
            error_logging("camera_capture", once=True)
    except Exception as e:
        error_logging("camera_capture", str(e), once=True)
    app.after(50, update_camera)

# Just audio stuff, practically useless to us right now
def audio_callback(indata, outdata, frames, time_info, status):
    global audio_level
    if status: error_logging("audio_callback", str(status), once=True)
    try:
        level = float(np.sqrt(np.mean(indata.astype(np.float64)**2)))
        with audio_lock:
            audio_level = level
            enabled = monitoring
        if enabled: outdata[:] = indata
        else: outdata.fill(0)
        if not status: reset_error("audio_callback")
    except Exception as e:
        outdata.fill(0)
        error_logging("audio_callback", str(e), once=True)

audio_frame = ctk.CTkFrame(frame)
audio_frame.pack(pady=10, padx=20, fill="x")
mic_status = ctk.CTkLabel(audio_frame, text="Microphone: Initializing...", font=ctk.CTkFont(size=16))
mic_status.pack(pady=5)

def toggle_mic():
    global monitoring
    if not authenticated: return
    if stream is None:
        error_logging("microphone_unavailable")
        return
    with audio_lock:
        monitoring = not monitoring
        enabled = monitoring
    mic_button.configure(text="Disable Microphone Monitoring" if enabled else "Enable Microphone Monitoring",
                         fg_color="#b91c1c" if enabled else "#15803d",
                         hover_color="#991b1b" if enabled else "#166534")
    mic_status.configure(text=f"Microphone Monitoring: {'ON' if enabled else 'OFF'}")

authenticated = False
recognition_results = Queue()
original_color = frame.cget("fg_color")

def flash_screen(success):
    color = "#15803d" if success else "#b91c1c"
    frame.configure(fg_color=color)
    app.after(600, lambda: frame.configure(fg_color=original_color) if running else None)

def recognition_done(success=False, error=None):
    global busy, authenticated
    busy = False
    authenticated = bool(success)
    flash_screen(authenticated)
    rec_button.configure(state="normal", text="Run Facial Recognition")
    mic_button.configure(state="normal" if authenticated and stream is not None else "disabled")
    if authenticated:
        print("Granted: Face verified")
        mic_status.configure(text="Access Granted: Face Verified")
    else:
        print("Denied:", error or "External Error")
        mic_status.configure(text="Access Denied: Face Not Recognized")
        if error: error_logging("recognition_failure", error)

def recognition_worker(img):
    try:
        if recognition_service is None:
            error_logging("recognition_unavailable")
            raise RuntimeError("Recognition service unavailable")
        success = recognition_service.process_image_frame(img)
        recognition_results.put((success is True, None))
    except Exception as e:
        recognition_results.put((False, str(e)))

def check_recognition_results():
    if not running: return
    try:
        success, error = recognition_results.get_nowait()
        recognition_done(success, error)
    except Empty: pass
    app.after(50, check_recognition_results)

def run_recognition():
    global busy, authenticated, monitoring
    if busy or not running: return
    with frame_lock: img = None if raw_frame is None else raw_frame.copy()
    if img is None:
        error_logging("missing_frame")
        return
    authenticated = False
    with audio_lock: monitoring = False
    mic_button.configure(state="disabled", text="Enable Microphone Monitoring", fg_color="#15803d", hover_color="#166534")
    busy = True
    rec_button.configure(state="disabled", text="Scanning Face...")
    threading.Thread(target=recognition_worker, args=(img,), daemon=True).start()

check_recognition_results()
mic_button = ctk.CTkButton(audio_frame, text="Enable Microphone Monitoring", command=toggle_mic,
                           width=260, height=40, fg_color="#15803d", hover_color="#166534", state="disabled")
mic_button.pack(pady=8)
rec_button = ctk.CTkButton(audio_frame, text="Run Facial Recognition", command=run_recognition,
 width=260, height=40, fg_color="#1d4ed8", hover_color="#1e40af")
rec_button.pack(pady=8)

level_label = ctk.CTkLabel(audio_frame, text="Microphone Level: 0%")
level_label.pack(pady=3)
level_bar = ctk.CTkProgressBar(audio_frame, width=350)
level_bar.pack(pady=5)
level_bar.set(0)

def update_audio():
    if not running: return
    with audio_lock: level = audio_level
    value = min(level * 10, 1.0)
    level_bar.set(value)
    level_label.configure(text=f"Microphone Level: {value * 100:.0f}%")
    app.after(100, update_audio)

try:
    stream = sd.Stream(samplerate=RATE, blocksize=BLOCK, channels=1, dtype="float32",callback=audio_callback, latency="high")
    stream.start()
    mic_status.configure(text="Microphone Monitoring: OFF")
    # mic_button.configure(state="normal")
    mic_button.configure(state="normal" if authenticated else "disabled")
except Exception as e:
    error_logging("microphone_initialization", str(e))
    mic_status.configure(text="Microphone initialization failed")
    print("Audio error:", e)
    if stream: stream.close()
    stream = None

def close_app():
    global running, monitoring
    running = False
    with audio_lock: monitoring = False
    if stream:
        try:
            stream.stop()
            stream.close()
        except Exception as e: error_logging("microphone_shutdown", str(e))
    try: camera.release()
    except Exception as e: error_logging("camera_shutdown", str(e))
    app.destroy()

app.protocol("WM_DELETE_WINDOW", close_app)

if camera.isOpened(): update_camera()
else:
    error_logging("camera_initialization")
    cam_label.configure(text="ERROR: Webcam not found")

update_audio()
app.mainloop()

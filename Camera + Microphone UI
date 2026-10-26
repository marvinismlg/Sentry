import customtkinter as ctk
import cv2
import sounddevice as sd
import numpy as np
from PIL import Image
import threading

# -----------------------------------
# Settings
# -----------------------------------

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 20

AUDIO_RATE = 44100
AUDIO_BLOCK = 1024

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# -----------------------------------
# Initialize GUI
# -----------------------------------

user_interface = ctk.CTk()
user_interface.title("Raspberry Pi 5 - Camera and Microphone")
user_interface.geometry("1000x750")

frame1 = ctk.CTkFrame(
    master=user_interface
)
frame1.pack(
    padx=20,
    pady=20,
    fill="both",
    expand=True
)

title_label = ctk.CTkLabel(
    master=frame1,
    text="Raspberry Pi 5 - Recognition System",
    font=ctk.CTkFont(size=24, weight="bold")
)
title_label.pack(pady=15)

# -----------------------------------
# Webcam Display
# -----------------------------------

camera_label = ctk.CTkLabel(
    master=frame1,
    text="Starting camera...",
    width=CAMERA_WIDTH,
    height=CAMERA_HEIGHT
)
camera_label.pack(pady=10)

camera = cv2.VideoCapture(0, cv2.CAP_V4L2)

camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
camera.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

camera_image = None
running = True
camera_after_id = None

def update_camera():
    global camera_image, camera_after_id

    if not running:
        return

    success, frame = camera.read()

    if success:
        frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        pil_image = Image.fromarray(frame)

        # Reuse the image object to reduce overhead
        if camera_image is None:
            camera_image = ctk.CTkImage(
                light_image=pil_image,
                dark_image=pil_image,
                size=(CAMERA_WIDTH, CAMERA_HEIGHT)
            )
            camera_label.configure(
                image=camera_image,
                text=""
            )
        else:
            camera_image.configure(
                light_image=pil_image,
                dark_image=pil_image
            )

    if running:
        camera_after_id = user_interface.after(
            50, update_camera
        )

# -----------------------------------
# Microphone Audio System
# -----------------------------------

audio_stream = None
audio_lock = threading.Lock()

monitor_enabled = False
audio_level = 0.0

def audio_callback(indata, outdata, frames,
                   time_info, status):
    global audio_level

    # Measure microphone volume
    level = np.sqrt(
        np.mean(indata.astype(np.float64) ** 2)
    )

    with audio_lock:
        audio_level = float(level)
        enabled = monitor_enabled

    # Send microphone audio to output
    if enabled:
        outdata[:] = indata
    else:
        outdata.fill(0)

# -----------------------------------
# Audio Controls
# -----------------------------------

audio_frame = ctk.CTkFrame(
    master=frame1
)
audio_frame.pack(pady=10, padx=20, fill="x")

mic_status = ctk.CTkLabel(
    master=audio_frame,
    text="Microphone: Initializing...",
    font=ctk.CTkFont(size=16)
)
mic_status.pack(pady=5)

def toggle_microphone():
    global monitor_enabled

    if audio_stream is None:
        return

    with audio_lock:
        monitor_enabled = not monitor_enabled
        enabled = monitor_enabled

    if enabled:
        mic_button.configure(
            text="Disable Microphone Monitoring",
            fg_color="#b91c1c",
            hover_color="#991b1b"
        )
        mic_status.configure(
            text="Microphone Monitoring: ON"
        )
    else:
        mic_button.configure(
            text="Enable Microphone Monitoring",
            fg_color="#15803d",
            hover_color="#166534"
        )
        mic_status.configure(
            text="Microphone Monitoring: OFF"
        )

mic_button = ctk.CTkButton(
    master=audio_frame,
    text="Enable Microphone Monitoring",
    command=toggle_microphone,
    width=260,
    height=40,
    fg_color="#15803d",
    hover_color="#166534",
    state="disabled"
)
mic_button.pack(pady=8)

# -----------------------------------
# Microphone Level Indicator
# -----------------------------------

level_label = ctk.CTkLabel(
    master=audio_frame,
    text="Microphone Level: 0%"
)
level_label.pack(pady=3)

level_bar = ctk.CTkProgressBar(
    master=audio_frame,
    width=350
)
level_bar.pack(pady=5)
level_bar.set(0)

def update_audio_level():
    if not running:
        return

    with audio_lock:
        level = audio_level

    # Scale the RMS reading for a simple display
    display_level = min(level * 10, 1.0)

    level_bar.set(display_level)
    level_label.configure(
        text=f"Microphone Level: {display_level * 100:.0f}%"
    )

    user_interface.after(100, update_audio_level)

# -----------------------------------
# Initialize Audio
# -----------------------------------

try:
    # Uses default input and output devices.
    # They must support a common sample rate.
    audio_stream = sd.Stream(
        samplerate=AUDIO_RATE,
        blocksize=AUDIO_BLOCK,
        channels=1,
        dtype="float32",
        callback=audio_callback,
        latency="high"
    )

    audio_stream.start()

    mic_status.configure(
        text="Microphone Monitoring: OFF"
    )
    mic_button.configure(state="normal")

except Exception as error:
    mic_status.configure(
        text="Microphone initialization failed"
    )
    print("Audio error:", error)

# -----------------------------------
# Close Application
# -----------------------------------

def close_application():
    global running, monitor_enabled

    running = False

    with audio_lock:
        monitor_enabled = False

    if camera_after_id is not None:
        user_interface.after_cancel(camera_after_id)

    if audio_stream is not None:
        audio_stream.stop()
        audio_stream.close()

    camera.release()
    user_interface.destroy()

user_interface.protocol(
    "WM_DELETE_WINDOW",
    close_application
)

# -----------------------------------
# Start Application
# -----------------------------------

if camera.isOpened():
    update_camera()
else:
    camera_label.configure(
        text="ERROR: Webcam not found"
    )

update_audio_level()

user_interface.mainloop()



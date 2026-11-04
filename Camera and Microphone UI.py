import cv2
import customtkinter as ctk
import sounddevice as sd
import numpy as np

import threading
import queue

from PIL import Image
from PIL import ImageTk

from voice_recognition import verify_microphone
from voice_enrollment import VoiceEnrollmentWindow


# --------------------------------------------------
# APPLICATION SETTINGS
# --------------------------------------------------

CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 20

AUDIO_RATE = 44100
AUDIO_BLOCK = 1024

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# --------------------------------------------------
# GLOBAL VARIABLES
# --------------------------------------------------

running = True

camera = None
audio_stream = None

camera_after_id = None
audio_after_id = None

enrollment_window = None

audio_level_queue = queue.Queue(maxsize=1)
verification_queue = queue.Queue()

verification_running = False


# --------------------------------------------------
# MAIN WINDOW
# --------------------------------------------------

user_interface = ctk.CTk()

user_interface.title("Raspberry Pi 5 - Recognition System")
user_interface.geometry("1000x850")
user_interface.resizable(False, False)


# --------------------------------------------------
# TITLE
# --------------------------------------------------

title_label = ctk.CTkLabel(
    user_interface,
    text="Raspberry Pi 5 - Recognition System",
    font=("Arial", 28, "bold")
)

title_label.pack(pady=20)


# --------------------------------------------------
# CAMERA FRAME
# --------------------------------------------------

camera_frame = ctk.CTkFrame(
    user_interface,
    width=700,
    height=400
)

camera_frame.pack(pady=10)

camera_frame.pack_propagate(False)

camera_label = ctk.CTkLabel(
    camera_frame,
    text="Starting camera...",
    font=("Arial", 18)
)

camera_label.pack(expand=True)


# --------------------------------------------------
# MICROPHONE FRAME
# --------------------------------------------------

microphone_frame = ctk.CTkFrame(
    user_interface,
    width=700,
    height=130
)

microphone_frame.pack(pady=10)

microphone_frame.pack_propagate(False)

microphone_title = ctk.CTkLabel(
    microphone_frame,
    text="Microphone Monitor",
    font=("Arial", 20, "bold")
)

microphone_title.pack(pady=(12, 5))

microphone_status = ctk.CTkLabel(
    microphone_frame,
    text="Microphone initializing...",
    font=("Arial", 13)
)

microphone_status.pack(pady=3)

audio_level_bar = ctk.CTkProgressBar(
    microphone_frame,
    width=450
)

audio_level_bar.pack(pady=8)

audio_level_bar.set(0)


# --------------------------------------------------
# RECOGNITION STATUS
# --------------------------------------------------

status_frame = ctk.CTkFrame(
    user_interface,
    width=700,
    height=90
)

status_frame.pack(pady=10)

status_frame.pack_propagate(False)

recognition_status = ctk.CTkLabel(
    status_frame,
    text="System ready.",
    font=("Arial", 17, "bold")
)

recognition_status.pack(expand=True)


# --------------------------------------------------
# BUTTON FRAME
# --------------------------------------------------

button_frame = ctk.CTkFrame(
    user_interface,
    fg_color="transparent"
)

button_frame.pack(pady=15)


# --------------------------------------------------
# AUDIO CALLBACK
# --------------------------------------------------

def audio_callback(indata, frames, time_info, status):

    if status:
        print("Audio status:", status)

    volume = float(np.sqrt(np.mean(indata ** 2)))

    # Keep only the newest volume reading.
    try:
        audio_level_queue.put_nowait(volume)
    except queue.Full:
        try:
            audio_level_queue.get_nowait()
        except queue.Empty:
            pass

        try:
            audio_level_queue.put_nowait(volume)
        except queue.Full:
            pass


# --------------------------------------------------
# MICROPHONE CONTROL
# --------------------------------------------------

def start_microphone_monitor():

    global audio_stream

    if not running:
        return

    try:
        if audio_stream is not None:
            try:
                if audio_stream.active:
                    return
            except Exception:
                pass

            try:
                audio_stream.close()
            except Exception:
                pass

            audio_stream = None

        audio_stream = sd.InputStream(
            samplerate=AUDIO_RATE,
            channels=1,
            blocksize=AUDIO_BLOCK,
            dtype="float32",
            callback=audio_callback
        )

        audio_stream.start()

        microphone_status.configure(
            text="Microphone active",
            text_color="green"
        )

    except Exception as error:

        audio_stream = None

        microphone_status.configure(
            text=f"Microphone error: {error}",
            text_color="red"
        )

        print("Microphone error:", error)


def stop_microphone_monitor():

    global audio_stream

    if audio_stream is not None:

        try:
            if audio_stream.active:
                audio_stream.stop()

            audio_stream.close()

        except Exception as error:
            print("Microphone stop error:", error)

        audio_stream = None

    microphone_status.configure(
        text="Microphone paused",
        text_color="orange"
    )

def update_audio_level():

    if not running:
        return

    latest_volume = None

    try:
        while True:
            latest_volume = audio_level_queue.get_nowait()

    except queue.Empty:
        pass

    if latest_volume is not None:

        # Scale the RMS value for a visible progress bar.
        display_level = min(latest_volume * 8, 1.0)

        audio_level_bar.set(display_level)

    audio_after_id = user_interface.after(
        50,
        update_audio_level
    )


# --------------------------------------------------
# CAMERA CONTROL
# --------------------------------------------------

def start_camera():

    global camera

    print("Starting camera using V4L2...")

    camera = cv2.VideoCapture(
        CAMERA_INDEX,
        cv2.CAP_V4L2
    )

    if not camera.isOpened():

        print("V4L2 failed. Trying default backend...")

        camera.release()

        camera = cv2.VideoCapture(CAMERA_INDEX)

    if not camera.isOpened():

        camera_label.configure(
            text="Could not open camera."
        )

        print("Camera could not be opened.")
        return

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    camera.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

    print("Camera successfully opened!")

    update_camera()


def update_camera():

    global camera_after_id

    if not running:
        return

    if camera is None or not camera.isOpened():
        return

    success, frame = camera.read()

    if success:

        frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        image = Image.fromarray(frame)

        image.thumbnail((680, 380))

        camera_image = ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=image.size
        )

        camera_label.configure(
            image=camera_image,
            text=""
        )

        # Keep a reference so the image stays visible.
        camera_label.image = camera_image

    camera_after_id = user_interface.after(
        int(1000 / CAMERA_FPS),
        update_camera
    )


# --------------------------------------------------
# VOICE VERIFICATION
# --------------------------------------------------
def verification_worker():

    try:
        result = verify_microphone()

        print("Verification result:", result)

        verification_queue.put(("success", result))

    except Exception as e:

        print("Verification error:", e)

        verification_queue.put(("error", str(e)))
        


def verify_voice():

    global verification_running

    if verification_running:
        return

    verification_running = True

    verify_button.configure(
        state="disabled",
        text="Listening..."
    )

    enroll_button.configure(state="disabled")

    recognition_status.configure(
        text="Speak now! Recording your voice...",
        text_color="orange"
    )

    audio_level_bar.set(0)

    # Stop the microphone monitor first.
    stop_microphone_monitor()

    # Now update the status to reflect the actual recording.
    microphone_status.configure(
        text="Recording verification sample... SPEAK NOW!",
        text_color="orange"
    )

    threading.Thread(
        target=verification_worker,
        daemon=True
    ).start()

    check_verification_results()

def check_verification_results():

    global verification_running

    try:
        status, result = verification_queue.get_nowait()

    except queue.Empty:

        user_interface.after(
            100,
            check_verification_results
        )

        return

    if status == "success":

        name, score, message = result

        if name is not None:

            recognition_status.configure(
                text=f"Verified: {name} | Score: {score:.3f}",
                text_color="green"
            )

        else:

            recognition_status.configure(
                text=f"Access Denied: {message}",
                text_color="red"
            )

    else:

        recognition_status.configure(
            text=f"Verification Error: {result}",
            text_color="red"
        )

    # Re-enable the buttons.
    verification_running = False

    verify_button.configure(
        state="normal",
        text="Verify Voice"
    )

    enroll_button.configure(state="normal")

    # Restart microphone monitoring.
    start_microphone_monitor()


# --------------------------------------------------
# VOICE ENROLLMENT POPUP
# --------------------------------------------------

def open_voice_enrollment():

    global enrollment_window

    if verification_running:
        recognition_status.configure(
            text="Wait for voice verification to finish.",
            text_color="orange"
        )
        return

    if enrollment_window is not None:

        try:
            if enrollment_window.winfo_exists():
                enrollment_window.lift()
                return

        except Exception:
            enrollment_window = None

    # Stop microphone monitoring before opening enrollment.
    stop_microphone_monitor()

    def enrollment_closed():

        global enrollment_window

        enrollment_window = None

        if running:
            start_microphone_monitor()

    try:

        enrollment_window = VoiceEnrollmentWindow(
            user_interface,
            on_close=enrollment_closed
        )

    except Exception as error:

        enrollment_window = None

        recognition_status.configure(
            text=f"Could not open enrollment: {error}",
            text_color="red"
        )

        start_microphone_monitor()

        print("Enrollment error:", error)


# --------------------------------------------------
# BUTTONS
# --------------------------------------------------

verify_button = ctk.CTkButton(
    button_frame,
    text="Verify Voice",
    width=200,
    height=45,
    font=("Arial", 15, "bold"),
    command=verify_voice
)

verify_button.grid(
    row=0,
    column=0,
    padx=15
)


enroll_button = ctk.CTkButton(
    button_frame,
    text="Enroll New Voice",
    width=200,
    height=45,
    font=("Arial", 15, "bold"),
    command=open_voice_enrollment
)

enroll_button.grid(
    row=0,
    column=1,
    padx=15
)


# --------------------------------------------------
# APPLICATION SHUTDOWN
# --------------------------------------------------

def close_application():

    global running

    running = False

    if enrollment_window is not None:

        try:
            if enrollment_window.winfo_exists():
                enrollment_window.destroy()

        except Exception:
            pass

    if camera_after_id is not None:

        try:
            user_interface.after_cancel(camera_after_id)
        except Exception:
            pass

    if audio_after_id is not None:

        try:
            user_interface.after_cancel(audio_after_id)
        except Exception:
            pass

    stop_microphone_monitor()

    if camera is not None:
        camera.release()

    user_interface.destroy()


user_interface.protocol(
    "WM_DELETE_WINDOW",
    close_application
)


# --------------------------------------------------
# START APPLICATION
# --------------------------------------------------

start_camera()

start_microphone_monitor()

update_audio_level()

user_interface.mainloop()


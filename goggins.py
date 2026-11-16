"""SENTRY: Raspberry Pi face-first, voice-second local authentication UI."""
from pathlib import Path
import queue
import threading
import tkinter as tk
import time
from tkinter import messagebox, simpledialog

import cv2
import customtkinter as ctk
import numpy as np
import sounddevice as sd
from PIL import Image

from face_identity import identify_face, refresh_known_faces, FACES_DIR
from voice_recognition import verify_microphone
from voice_enrollment import VoiceEnrollmentWindow

CAMERA_INDEX = 0
CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS = 640, 480, 20
PREVIEW_WIDTH, PREVIEW_HEIGHT = 1000, 500
AUDIO_RATE, AUDIO_BLOCK = 44100, 1024
VOICE_RECORD_SECONDS = 5
SUCCESS_HOLD_MS = 3000
FAIL_HOLD_MS = 3000
BG, PANEL, BLUE = '#0b1220', '#172337', '#2563eb'
GREEN, RED, MUTED = '#15803d', '#b91c1c', '#9ca3af'

ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('blue')


class Sentinel(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_widget_scaling(1.2)
        self.title('SENTRY | Raspberry Pi Recognition')

        # Default window size when fullscreen is disabled
        self.geometry('1200x900')
        self.minsize(900, 780)

        # Start SENTINEL in fullscreen mode
        self.attributes('-fullscreen', True)

        self.configure(fg_color=BG)

        self.running = True
        self.busy = False
        self.enrollment = None
        self.camera = None
        self.current_frame = None
        self.preview_image = None
        self.events = queue.Queue()
        self.levels = queue.Queue(maxsize=1)
        self.audio_stream = None
        self.reset_after = None
        self.after_ids = set()
        self.face_identity = None
        self.voice_identity = None
        self.mic_status = 'Microphone initializing...'
        self.recording_active = False
        self.recording_started = 0.0

        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<F11>', self.toggle_fullscreen)
        self.bind('<Escape>', self.exit_fullscreen)
        self.build_ui()
        self.open_camera()
        self.start_monitor()
        self.schedule(50, self.update_camera)
        self.schedule(100, self.poll_events)
        self.schedule(100, self.update_level)

    def schedule(self, delay_ms, callback):
        if not self.running:
            return None
        holder = [None]

        def run():
            self.after_ids.discard(holder[0])
            if self.running:
                callback()

        holder[0] = self.after(delay_ms, run)
        self.after_ids.add(holder[0])
        return holder[0]

    def build_ui(self):
        ctk.CTkLabel(
            self,
            text='Sentry',
            font=ctk.CTkFont(size=42, weight='bold')
        ).pack(pady=(18, 0))        
        
        ctk.CTkLabel(self, text='DUAL BIOMETRIC RECOGNITION', text_color=MUTED,
                     font=ctk.CTkFont(size=12)).pack(pady=(0, 10))

        camera_panel = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14)
        camera_panel.pack(padx=28, fill='x')
        ctk.CTkLabel(camera_panel, text='LIVE CAMERA', font=ctk.CTkFont(size=13, weight='bold'),
                     anchor='w').pack(fill='x', padx=20, pady=(8, 0))
        self.camera_label = ctk.CTkLabel(camera_panel, text='Starting camera...',
                                         width=PREVIEW_WIDTH, height=PREVIEW_HEIGHT)
        self.camera_label.pack(pady=(2, 10))

        status_row = ctk.CTkFrame(self, fg_color='transparent')
        status_row.pack(padx=28, pady=(12, 8), fill='x')
        status_row.grid_columnconfigure((0, 1), weight=1)
        face_card = ctk.CTkFrame(status_row, fg_color=PANEL, corner_radius=12)
        voice_card = ctk.CTkFrame(status_row, fg_color=PANEL, corner_radius=12)
        face_card.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        voice_card.grid(row=0, column=1, sticky='nsew', padx=(6, 0))
        ctk.CTkLabel(face_card, text='FACE RECOGNITION', font=ctk.CTkFont(size=13, weight='bold')).pack(pady=(10, 0))
        self.face_label = ctk.CTkLabel(face_card, text='Waiting', text_color=MUTED,
                                        font=ctk.CTkFont(size=22))
        self.face_label.pack(pady=(0, 10))
        ctk.CTkLabel(voice_card, text='VOICE RECOGNITION', font=ctk.CTkFont(size=13, weight='bold')).pack(pady=(10, 0))
        self.voice_label = ctk.CTkLabel(voice_card, text='Locked until face passes',
                                         text_color=MUTED, font=ctk.CTkFont(size=22))
        self.voice_label.pack(pady=(0, 10))

        self.result_label = ctk.CTkLabel(self, text='READY FOR AUTHENTICATION',
                                         font=ctk.CTkFont(size=28, weight='bold'), text_color=MUTED)
        self.result_label.pack(pady=(10, 4))
        self.detail_label = ctk.CTkLabel(self, text='Press Authenticate to begin.', text_color=MUTED)
        self.detail_label.pack(pady=(0, 8))

        self.mic_label = ctk.CTkLabel(self, text=self.mic_status, text_color=MUTED)
        self.mic_label.pack(pady=(0, 2))
        self.mic_bar = ctk.CTkProgressBar(self, width=500, height=15)
        self.mic_bar.pack(pady=(0, 12))
        self.mic_bar.set(0)
        self.recording_label = ctk.CTkLabel(
            self,
            text="",
            text_color="#f87171",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.recording_label.pack(pady=(5, 2))

        self.recording_bar = ctk.CTkProgressBar(
            self,
            width=500,
            height=14,
            progress_color="#ef4444"
        )
        self.recording_bar.pack(pady=(0, 8))
        self.recording_bar.set(0)
        
        
        self.open_button = ctk.CTkButton(
            self,
            text="OPEN",
            command=self.open_access,
            width=280,
            height=60,
            fg_color=GREEN,
            hover_color="#166534",
            font=ctk.CTkFont(size=28, weight="bold")
        )

        # Hidden until authentication succeeds

        buttons = ctk.CTkFrame(self, fg_color='transparent')
        buttons.pack(pady=(4, 12))
        self.auth_button = ctk.CTkButton(buttons, text='AUTHENTICATE', command=self.authenticate,
                                          width=240, height=55, fg_color=BLUE)
        self.auth_button.grid(row=0, column=0, padx=6)
        self.face_button = ctk.CTkButton(buttons, text='Enroll Face', command=self.enroll_face,
                                          width=180, height=55)
        self.face_button.grid(row=0, column=1, padx=6)
        self.voice_button = ctk.CTkButton(buttons, text='Enroll Voice', command=self.enroll_voice,
                                           width=180, height=55)
        self.voice_button.grid(row=0, column=2, padx=6)

    def open_camera(self):
        # The preview owns the one and only camera capture object.
        self.camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
        if not self.camera.isOpened():
            self.camera.release()
            self.camera = cv2.VideoCapture(CAMERA_INDEX)
        if not self.camera.isOpened():
            self.camera.release()
            self.camera = None
            self.camera_label.configure(text='Camera unavailable')
            self.detail_label.configure(text='Check the USB camera and CAMERA_INDEX.')
            return
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        self.camera.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

    def update_camera(self):
        if self.camera is not None:
            ok, frame = self.camera.read()
            if ok and frame is not None:
                self.current_frame = frame
                h, w = frame.shape[:2]
                scale = min(PREVIEW_WIDTH / w, PREVIEW_HEIGHT / h)
                display = cv2.resize(frame, (int(w * scale), int(h * scale)))
                canvas = np.zeros((PREVIEW_HEIGHT, PREVIEW_WIDTH, 3), dtype=np.uint8)
                y = (PREVIEW_HEIGHT - display.shape[0]) // 2
                x = (PREVIEW_WIDTH - display.shape[1]) // 2
                canvas[y:y + display.shape[0], x:x + display.shape[1]] = display
                rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
                self.preview_image = ctk.CTkImage(light_image=Image.fromarray(rgb),
                                                    dark_image=Image.fromarray(rgb),
                                                    size=(PREVIEW_WIDTH, PREVIEW_HEIGHT))
                self.camera_label.configure(image=self.preview_image, text='')
        self.schedule(50, self.update_camera)

    def audio_callback(self, indata, frames, time_info, status):
        if not self.running:
            return
        level = float(np.sqrt(np.mean(np.square(indata.astype(np.float32)))))
        try:
            self.levels.put_nowait(min(1.0, level * 12.0))
        except queue.Full:
            pass

    def start_monitor(self):
        if not self.running or self.audio_stream is not None or self.busy or self.enrollment is not None:
            return
        try:
            self.audio_stream = sd.InputStream(samplerate=AUDIO_RATE, blocksize=AUDIO_BLOCK,
                                                channels=1, dtype='float32', callback=self.audio_callback)
            self.audio_stream.start()
            self.mic_status = 'Microphone ready'
        except Exception as exc:
            self.mic_status = f'Microphone monitor unavailable: {exc}'
            if self.audio_stream is not None:
                try:
                    self.audio_stream.close()
                except Exception:
                    pass
            self.audio_stream = None
        self.mic_label.configure(text=self.mic_status)

    def stop_monitor(self):
        stream = self.audio_stream
        self.audio_stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception as exc:
                print('Audio monitor shutdown:', exc)
        self.mic_bar.set(0)

    def update_level(self):
        try:
            while True:
                level = self.levels.get_nowait()
                if self.audio_stream is not None:
                    self.mic_bar.set(level)
        except queue.Empty:
            pass
        self.schedule(100, self.update_level)

    def authenticate(self):
        if self.busy or self.enrollment is not None:
            return
        if self.current_frame is None:
            messagebox.showerror('Camera', 'No camera frame available yet.')
            return
        if self.reset_after is not None:
            self.after_cancel(self.reset_after)
            self.reset_after = None
        self.busy = True
        self.face_identity = None
        self.voice_identity = None
        self.auth_button.configure(state='disabled')
        self.face_button.configure(state='disabled')
        self.voice_button.configure(state='disabled')
        self.face_label.configure(text='Checking face...', text_color=MUTED)
        self.voice_label.configure(text='Locked until face passes', text_color=MUTED)
        self.result_label.configure(text='AUTHENTICATING', text_color='white')
        self.detail_label.configure(text='Please face the camera.')
        snapshot = self.current_frame.copy()
        threading.Thread(target=self.authentication_worker, args=(snapshot,), daemon=True).start()
        
    def show_voice_popup(self, ready_event, response):
        popup = ctk.CTkToplevel(self)
        popup.title("Face Verified")
        popup.geometry("400x250")
        popup.resizable(False, False)
        popup.transient(self)
        popup.grab_set()

        ctk.CTkLabel(
            popup,
            text="FACE VERIFIED",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=GREEN
        ).pack(pady=(25, 10))

        ctk.CTkLabel(
            popup,
            text="Your identity has been confirmed.\n"
                 "Click below when you're ready to speak.",
            font=ctk.CTkFont(size=14)
        ).pack(pady=10)

        def finish(approved):
            response["approved"] = approved
            popup.grab_release()
            popup.destroy()
            ready_event.set()

        ctk.CTkButton(
            popup,
            text="START VOICE VERIFICATION",
            width=250,
            height=45,
            command=lambda: finish(True)
        ).pack(pady=(10, 5))

        ctk.CTkButton(
            popup,
            text="Cancel",
            width=250,
            fg_color=RED,
            command=lambda: finish(False)
        ).pack(pady=5)

        popup.protocol(
            "WM_DELETE_WINDOW",
            lambda: finish(False)
        )

    def request_voice_popup(self, ready_event, response):
        self.stop_monitor()
        self.mic_label.configure(
            text="Face verified. Waiting for voice verification."
        )
        self.show_voice_popup(ready_event, response)    

    def authentication_worker(self, frame):
        try:
            face_name, distance, message = identify_face(frame)
            self.events.put(('face', face_name, distance, message))
            if face_name is None:
                self.events.put(('result', False, message))
                return
            # Voice recording uses the same audio device as the monitor.
            # Request that the UI stop its monitor, then wait for confirmation.
            ready = threading.Event()
            response = {"approved": False}

            self.events.put(('voice_popup', ready, response))

            # Wait until the user clicks Start or Cancel.
            ready.wait()

            if not response["approved"]:
                self.events.put((
                    'result',
                    False,
                    'Voice verification cancelled.'
                ))
                return

            self.events.put(('recording_start',))

            self.events.put((
                'voice_status',
                'SPEAK NOW! Recording for 5 seconds...'
            ))

            voice_name, score, voice_message = verify_microphone(
                status_callback=lambda status: self.events.put(
                    ('recording_stop',)
                )
            )

            # Safety: ensure the animation stops after verification.
            self.events.put(('recording_stop',))
            
            
            self.events.put(('voice', voice_name, score, voice_message))
            if voice_name is None:
                self.events.put(('result', False, voice_message))
            elif voice_name != face_name:
                self.events.put(('result', False,
                                 f'Identity mismatch: face={face_name}, voice={voice_name}'))
            else:
                self.events.put(('result', True, f'Welcome, {face_name}!'))
        except Exception as exc:
            self.events.put(('result', False, f'Authentication error: {exc}'))


    def start_recording_animation(self):
        self.recording_active = True
        self.recording_started = time.monotonic()
        self.recording_bar.set(0)
        self.update_recording_animation()

    def stop_recording_animation(self):
        self.recording_active = False
        self.recording_bar.set(1)
        self.recording_label.configure(
            text="Recording complete. Verifying voice...",
            text_color=GREEN
        )

    def update_recording_animation(self):
        if not self.recording_active or not self.running:
            return

        elapsed = time.monotonic() - self.recording_started
        remaining = max(0.0, VOICE_RECORD_SECONDS - elapsed)
        progress = min(1.0, elapsed / VOICE_RECORD_SECONDS)

        self.recording_bar.set(progress)

        self.recording_label.configure(
            text=f"● RECORDING — {remaining:.1f}s remaining",
            text_color="#f87171"
        )

        if remaining > 0:
            self.schedule(50, self.update_recording_animation)


    
    def poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]

                if kind == 'recording_start':
                    self.start_recording_animation()

                elif kind == 'recording_stop':
                    self.stop_recording_animation()

                elif kind == 'face':
                    _, name, distance, message = event
                    self.face_identity = name
                    self.face_label.configure(
                        text=name or 'Denied',
                        text_color=GREEN if name else RED
                    )
                    self.detail_label.configure(text=message)

                elif kind == 'voice_popup':
                    _, ready_event, response = event
                    self.request_voice_popup(ready_event, response)

                elif kind == 'voice_status':
                    self.voice_label.configure(
                        text=event[1],
                        text_color='white'
                    )
                    self.detail_label.configure(text=event[1])

                elif kind == 'voice':
                    _, name, score, message = event
                    self.voice_identity = name
                    self.voice_label.configure(
                        text=f'{name} ({score:.3f})' if name else 'Denied',
                        text_color=GREEN if name else RED
                    )
                    self.detail_label.configure(text=message)

                elif kind == 'result':
                    _, allowed, message = event
                    self.show_result(allowed, message)

        except queue.Empty:
            pass

        self.schedule(100, self.poll_events)

        
    def open_access(self):
        # This currently acknowledges access and returns to standby.
        # A physical lock or door actuator can be integrated later.
        self.open_button.pack_forget()
        self.reset_state()
        
    def show_result(self, allowed, message):
        color = GREEN if allowed else RED

        self.result_label.configure(
            text='ACCESS GRANTED' if allowed else 'ACCESS DENIED',
            text_color=color
        )

        self.detail_label.configure(text=message)

        self.configure(
            fg_color='#0a2519' if allowed else '#2b1017'
        )

        if allowed:
            # Stay on the success screen until OPEN is clicked.
            self.open_button.pack(pady=(5, 10))

            self.detail_label.configure(
                text=f'{message} Click OPEN to continue.'
            )

        else:
            # Failed authentication still resets after 3 seconds.
            self.reset_after = self.schedule(
                FAIL_HOLD_MS,
                self.reset_state
            )

    def reset_state(self):
        self.recording_active = False
        self.recording_bar.set(0)
        self.recording_label.configure(text="")
        self.open_button.pack_forget()
        self.reset_after = None
        self.busy = False
        self.face_identity = None
        self.voice_identity = None
        self.configure(fg_color=BG)
        self.face_label.configure(text='Waiting', text_color=MUTED)
        self.voice_label.configure(text='Locked until face passes', text_color=MUTED)
        self.result_label.configure(text='READY FOR AUTHENTICATION', text_color=MUTED)
        self.detail_label.configure(text='Press Authenticate to begin.', text_color=MUTED)
        self.auth_button.configure(state='normal')
        self.face_button.configure(state='normal')
        self.voice_button.configure(state='normal')
        self.start_monitor()

    def enroll_face(self):
        if self.busy or self.enrollment is not None:
            return
        if self.current_frame is None:
            messagebox.showerror('Camera', 'No camera frame available.')
            return
        name = simpledialog.askstring('Enroll Face',
                                      'Enter a name exactly matching the voice profile folder:', parent=self)
        if name is None:
            return
        name = name.strip()
        if not name or name in ('.', '..') or '/' in name or '\\' in name:
            messagebox.showerror('Invalid name', 'Enter a valid name without slashes.')
            return
        frame = self.current_frame.copy()
        try:
            import face_recognition as face_lib
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            locations = face_lib.face_locations(rgb)
            if len(locations) != 1:
                messagebox.showerror('Enroll Face', f'Expected one face, found {len(locations)}.')
                return
            FACES_DIR.mkdir(parents=True, exist_ok=True)
            path = FACES_DIR / f'{name}.jpg'
            if path.exists() and not messagebox.askyesno('Replace Face', f'Replace existing photo for {name}?'):
                return
            if not cv2.imwrite(str(path), frame):
                raise OSError('Could not save camera image')
            refresh_known_faces()
            messagebox.showinfo('Face Enrolled', f'Saved {path.name}. Enroll a matching voice profile.')
        except Exception as exc:
            messagebox.showerror('Enroll Face', str(exc))

    def enroll_voice(self):
        if self.busy or self.enrollment is not None:
            return
        self.stop_monitor()
        self.mic_label.configure(text='Microphone reserved for enrollment')
        self.auth_button.configure(state='disabled')
        self.face_button.configure(state='disabled')
        self.voice_button.configure(state='disabled')
        try:
            self.enrollment = VoiceEnrollmentWindow(self, on_close=self.enrollment_closed)
        except Exception as exc:
            self.enrollment = None
            self.auth_button.configure(state='normal')
            self.face_button.configure(state='normal')
            self.voice_button.configure(state='normal')
            self.start_monitor()
            messagebox.showerror('Voice Enrollment', str(exc))

    def enrollment_closed(self):
        self.enrollment = None
        if not self.running:
            return
        self.auth_button.configure(state='normal')
        self.face_button.configure(state='normal')
        self.voice_button.configure(state='normal')
        self.start_monitor()

    def close(self):
        if not self.running:
            return
        if self.busy:
            messagebox.showinfo('SENTRY', 'Wait for authentication to finish before closing.')
            return
        if self.enrollment is not None:
            messagebox.showinfo('SENTRY', 'Close the enrollment window first.')
            return
        self.running = False
        for after_id in list(self.after_ids):
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        self.after_ids.clear()
        self.stop_monitor()
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        self.destroy()
    
    def toggle_fullscreen(self, event=None):
        current = self.attributes('-fullscreen')
        self.attributes('-fullscreen', not current)


    def exit_fullscreen(self, event=None):
        self.attributes('-fullscreen', False)


if __name__ == '__main__':
    app = Sentinel()
    app.mainloop()


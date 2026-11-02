import customtkinter as ctk
import sounddevice as sd
import numpy as np
import wave
import threading
import queue
import time

from pathlib import Path


VOICE_DIR = Path.home() / "voice_profiles"
SAMPLE_RATE = 16000
RECORD_SECONDS = 8
SAMPLES_PER_PERSON = 8


class VoiceEnrollmentWindow(ctk.CTkToplevel):

    def __init__(self, parent, on_close=None):
        super().__init__(parent)

        self.parent = parent
        self.on_close = on_close
        self.recording_window = None

        self.title("Voice Enrollment")
        self.geometry("500x500")
        self.resizable(False, False)

        self.protocol("WM_DELETE_WINDOW", self.close_window)

        VOICE_DIR.mkdir(parents=True, exist_ok=True)

        # Main title
        ctk.CTkLabel(
            self,
            text="Voice Enrollment",
            font=("Arial", 26, "bold")
        ).pack(pady=(25, 10))

        ctk.CTkLabel(
            self,
            text="Add a person to the voice recognition system.",
            font=("Arial", 14)
        ).pack(pady=5)

        # Name input
        self.name_entry = ctk.CTkEntry(
            self,
            placeholder_text="Enter person's name",
            width=300,
            height=40
        )
        self.name_entry.pack(pady=20)

        # Start button
        self.start_button = ctk.CTkButton(
            self,
            text="Start Enrollment",
            width=220,
            height=45,
            command=self.start_enrollment
        )
        self.start_button.pack(pady=10)

        # Existing profiles
        ctk.CTkLabel(
            self,
            text="Existing Voice Profiles",
            font=("Arial", 18, "bold")
        ).pack(pady=(25, 10))

        self.people_frame = ctk.CTkScrollableFrame(
            self,
            width=350,
            height=150
        )
        self.people_frame.pack(pady=5)

        self.status_label = ctk.CTkLabel(
            self,
            text="",
            text_color="gray"
        )
        self.status_label.pack(pady=10)

        self.refresh_profiles()

        self.transient(parent)
        self.grab_set()

    def refresh_profiles(self):
        for widget in self.people_frame.winfo_children():
            widget.destroy()

        profiles = [
            folder.name
            for folder in VOICE_DIR.iterdir()
            if folder.is_dir()
        ]

        if not profiles:
            ctk.CTkLabel(
                self.people_frame,
                text="No enrolled people yet."
            ).pack(pady=10)
            return

        for name in sorted(profiles):
            sample_count = len(
                list((VOICE_DIR / name).glob("sample_*.wav"))
            )

            ctk.CTkLabel(
                self.people_frame,
                text=f"{name}  —  {sample_count} samples"
            ).pack(pady=5)

    def start_enrollment(self):
        name = self.name_entry.get().strip()

        if not name:
            self.status_label.configure(
                text="Please enter a name.",
                text_color="red"
            )
            return

        # Prevent names that could create unintended paths.
        if name in (".", "..") or "/" in name or "\\" in name:
            self.status_label.configure(
                text="Please enter a valid name.",
                text_color="red"
            )
            return

        person_folder = VOICE_DIR / name
        person_folder.mkdir(parents=True, exist_ok=True)

        self.open_recording_window(name)

    def open_recording_window(self, name):
        self.recording_window = RecordingWindow(
            self,
            name,
            on_complete=self.enrollment_finished
        )

    def enrollment_finished(self):
        self.refresh_profiles()
        self.status_label.configure(
            text="Enrollment session finished.",
            text_color="green"
        )

    def close_window(self):
        if self.recording_window is not None:
            self.recording_window.cancel_recording()

        self.grab_release()
        self.destroy()

        if self.on_close:
            self.on_close()


class RecordingWindow(ctk.CTkToplevel):

    def __init__(self, parent, name, on_complete=None):
        super().__init__(parent)

        self.name = name
        self.on_complete = on_complete

        self.person_folder = VOICE_DIR / name
        self.person_folder.mkdir(parents=True, exist_ok=True)

        self.sample_number = 0
        self.cancelled = False
        self.recording = False
        self.event_queue = queue.Queue()
        self.record_thread = None
        self.timer_after_id = None
        self.poll_after_id = None
        self.sample_started_at = None

        self.title(f"Recording Voice - {name}")
        self.geometry("500x420")
        self.resizable(False, False)

        self.protocol("WM_DELETE_WINDOW", self.cancel_recording)

        ctk.CTkLabel(
            self,
            text=f"Enrolling: {name}",
            font=("Arial", 25, "bold")
        ).pack(pady=(25, 10))

        self.instruction_label = ctk.CTkLabel(
            self,
            text="Get ready for your first recording.",
            font=("Arial", 14)
        )
        self.instruction_label.pack(pady=10)

        self.sample_label = ctk.CTkLabel(
            self,
            text=f"Sample 0 of {SAMPLES_PER_PERSON}",
            font=("Arial", 20, "bold")
        )
        self.sample_label.pack(pady=15)

        self.progress_bar = ctk.CTkProgressBar(
            self,
            width=350
        )
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)

        self.countdown_label = ctk.CTkLabel(
            self,
            text="",
            font=("Arial", 32, "bold")
        )
        self.countdown_label.pack(pady=15)

        self.status_label = ctk.CTkLabel(
            self,
            text="Speak naturally when recording begins.",
            text_color="gray"
        )
        self.status_label.pack(pady=10)

        self.cancel_button = ctk.CTkButton(
            self,
            text="Cancel Enrollment",
            fg_color="#9b3030",
            hover_color="#762323",
            command=self.cancel_recording
        )
        self.cancel_button.pack(pady=15)

        self.transient(parent)
        self.grab_set()

        self.after(1000, self.start_next_sample)
        self.poll_queue()

    def get_next_filename(self):
        existing = list(self.person_folder.glob("sample_*.wav"))

        numbers = []
        for file in existing:
            try:
                numbers.append(int(file.stem.split("_")[-1]))
            except ValueError:
                pass

        next_number = max(numbers, default=0) + 1
        return self.person_folder / f"sample_{next_number}.wav"

    def start_next_sample(self):
        if self.cancelled:
            return

        if self.sample_number >= SAMPLES_PER_PERSON:
            self.finish_enrollment()
            return

        self.sample_number += 1

        self.sample_label.configure(
            text=f"Sample {self.sample_number} of {SAMPLES_PER_PERSON}"
        )

        self.instruction_label.configure(
            text="Recording now — speak naturally."
        )

        self.status_label.configure(
            text="Please speak for the full recording.",
            text_color="gray"
        )

        self.recording = True
        self.sample_started_at = time.monotonic()

        self.record_thread = threading.Thread(
            target=self.record_sample,
            daemon=True
        )
        self.record_thread.start()

        self.update_countdown()

    def record_sample(self):
        try:
            audio = sd.rec(
                int(RECORD_SECONDS * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16"
            )

            sd.wait()

            if self.cancelled:
                return

            audio = np.asarray(audio, dtype=np.int16)
            filename = self.get_next_filename()

            with wave.open(str(filename), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.writeframes(audio.tobytes())

            self.event_queue.put(("success", filename.name))

        except Exception as error:
            self.event_queue.put(("error", str(error)))

    def update_countdown(self):
        if self.cancelled or not self.recording:
            return

        elapsed = time.monotonic() - self.sample_started_at
        remaining = max(0, RECORD_SECONDS - int(elapsed))

        self.countdown_label.configure(
            text=f"{remaining} seconds"
        )

        self.progress_bar.set(
            min(1, elapsed / RECORD_SECONDS)
        )

        if remaining > 0:
            self.timer_after_id = self.after(
                200,
                self.update_countdown
            )

    def poll_queue(self):
        if self.cancelled:
            return

        try:
            while True:
                event, message = self.event_queue.get_nowait()

                if event == "success":
                    self.recording = False

                    self.progress_bar.set(
                        self.sample_number / SAMPLES_PER_PERSON
                    )

                    self.status_label.configure(
                        text=f"Saved {message}",
                        text_color="green"
                    )

                    self.countdown_label.configure(text="Saved!")

                    self.after(1000, self.start_next_sample)

                elif event == "error":
                    self.recording = False
                    self.status_label.configure(
                        text=f"Recording error: {message}",
                        text_color="red"
                    )
                    self.instruction_label.configure(
                        text="Recording stopped. Please cancel and try again."
                    )
                    self.cancel_button.configure(
                        text="Close Window"
                    )

        except queue.Empty:
            pass

        self.poll_after_id = self.after(100, self.poll_queue)

    def finish_enrollment(self):
        self.recording = False

        self.instruction_label.configure(
            text="All recordings have been saved!"
        )
        self.sample_label.configure(
            text="Enrollment Complete"
        )
        self.countdown_label.configure(text="Done!")
        self.progress_bar.set(1)
        self.status_label.configure(
            text=f"{SAMPLES_PER_PERSON} new samples saved for {self.name}.",
            text_color="green"
        )
        self.cancel_button.configure(
            text="Close",
            fg_color="#1f6aa5",
            hover_color="#144870",
            command=self.close_complete
        )

    def close_complete(self):
        if self.on_complete:
            self.on_complete()

        self.destroy()

    def cancel_recording(self):
        if self.cancelled:
            return

        self.cancelled = True
        self.recording = False

        if self.timer_after_id:
            self.after_cancel(self.timer_after_id)

        if self.poll_after_id:
            self.after_cancel(self.poll_after_id)

        sd.stop()

        self.destroy()


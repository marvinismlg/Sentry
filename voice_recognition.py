from pathlib import Path
import tempfile
import wave

import numpy as np
import sounddevice as sd

from speechbrain.inference.speaker import SpeakerRecognition


# -----------------------------------
# Settings
# -----------------------------------

VOICE_DIR = Path.home() / "voice_profiles"

MODEL_DIR = str(
    Path.home() / "speechbrain_models/ecapa_voxceleb"
)

SAMPLE_RATE = 16000
RECORD_SECONDS = 8

# Initial testing values, NOT security-certified thresholds.
MATCH_THRESHOLD = 0.25
MIN_MARGIN = 0.05

_model = None


# -----------------------------------
# Load ECAPA-TDNN
# -----------------------------------

def get_model():

    global _model

    if _model is None:

        print("Loading ECAPA-TDNN...")

        _model = SpeakerRecognition.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=MODEL_DIR,
            run_opts={"device": "cpu"}
        )

        print("ECAPA-TDNN loaded!")

    return _model


# -----------------------------------
# Record Authentication Audio
# -----------------------------------

def record_audio():

    print("\n========== VOICE VERIFICATION ==========")
    print("Selected input device:", sd.default.device)
    print("Input device information:", sd.query_devices(kind="input"))
    print(f"Recording for {RECORD_SECONDS} seconds...")
    print("SPEAK NOW!")

    audio = sd.rec(
        int(SAMPLE_RATE * RECORD_SECONDS),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16"
    )

    sd.wait()

    print("Recording finished.")
    print("Audio shape:", audio.shape)

    volume = np.sqrt(
        np.mean(audio.astype(np.float32) ** 2)
    )

    print("Recorded audio volume (RMS):", volume)

    if volume < 100:
        raise ValueError(
            "Microphone recording was too quiet."
        )

    temp_file = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False
    )

    path = Path(temp_file.name)
    temp_file.close()

    try:
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(audio.tobytes())

        print("Authentication recording saved.")
        print("========================================\n")

        return path

    except Exception:
        path.unlink(missing_ok=True)
        raise


# -----------------------------------
# Identify Speaker
# -----------------------------------

def identify_speaker(test_path):

    if not VOICE_DIR.exists():
        return None, 0.0, "No enrolled profiles"

    model = get_model()

    results = []

    for person_dir in sorted(VOICE_DIR.iterdir()):

        if not person_dir.is_dir():
            continue

        samples = sorted(
            person_dir.glob("sample_*.wav")
        )

        # Require at least three samples per person.
        if len(samples) < 3:
            continue

        scores = []

        for sample in samples:

            try:

                score, prediction = model.verify_files(
                    str(test_path),
                    str(sample)
                )

                score_value = float(
                    score.squeeze().item()
                )

                if not np.isfinite(score_value):
                    raise ValueError("Invalid model score")

                scores.append(score_value)

            except Exception as error:

                print(
                    f"Comparison failed for {sample}: {error}"
                )

                return None, 0.0, "Profile comparison failed"

        if scores:

            average_score = float(np.mean(scores))

            results.append(
                (person_dir.name, average_score)
            )

    if not results:
        return None, 0.0, "No complete voice profiles"

    # Highest similarity score first.
    results.sort(
        key=lambda item: item[1],
        reverse=True
    )

    best_name, best_score = results[0]

    print("\nVoice comparison results:")

    for name, score in results:
        print(f"{name}: {score:.3f}")

    # Reject scores below the threshold.
    if best_score < MATCH_THRESHOLD:
        return None, best_score, "Unknown speaker"

    # Reject ambiguous matches.
    if len(results) > 1:

        second_score = results[1][1]

        if best_score - second_score < MIN_MARGIN:
            return None, best_score, "Ambiguous speaker"

    return best_name, best_score, "Provisional match"


# -----------------------------------
# Main Verification Function
# -----------------------------------

def verify_microphone():

    path = None

    try:
        print("Listening for verification voice...")

        path = record_audio()

        print("Recording complete. Identifying speaker...")

        result = identify_speaker(path)

        return result

    finally:
        if path is not None:
            path.unlink(missing_ok=True)


# -----------------------------------
# Testing
# -----------------------------------

if __name__ == "__main__":

    print("Voice recognition module ready.")

    print("Voice profiles:", VOICE_DIR)

    print("Model directory:", MODEL_DIR)


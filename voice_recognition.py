from pathlib import Path
import tempfile
import wave
import time

import numpy as np
import sounddevice as sd
import torch
import torch.nn.functional as F

from speechbrain.inference.speaker import SpeakerRecognition


# -----------------------------------
# Settings
# -----------------------------------

VOICE_DIR = Path.home() / "voice_profiles"

MODEL_DIR = str(
    Path.home() / "speechbrain_models/ecapa_voxceleb"
)

SAMPLE_RATE = 16000
RECORD_SECONDS = 5

MATCH_THRESHOLD = 0.45
MIN_MARGIN = 0.05

CACHE_FILENAME = "embeddings.pt"
CACHE_VERSION = 1

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
# Extract Speaker Embedding
# -----------------------------------

def extract_embedding(audio_path, model):

    waveform = model.load_audio(str(audio_path))

    batch = waveform.unsqueeze(0)

    relative_length = torch.tensor([1.0])

    with torch.inference_mode():

        embedding = model.encode_batch(
            batch,
            relative_length,
            normalize=False
        )

    return embedding.reshape(-1).detach().cpu().float()


# -----------------------------------
# Enrollment Cache
# -----------------------------------

def get_sample_manifest(samples):

    manifest = []

    for sample in samples:

        stat = sample.stat()

        manifest.append({
            "name": sample.name,
            "modified": stat.st_mtime_ns,
            "size": stat.st_size
        })

    return manifest


def load_or_create_profile_embeddings(person_dir, model):

    samples = sorted(person_dir.glob("sample_*.wav"))

    if len(samples) < 3:
        return None

    cache_path = person_dir / CACHE_FILENAME

    manifest = get_sample_manifest(samples)

    # Check whether a valid cache already exists.
    if cache_path.exists():

        try:

            cached = torch.load(
                cache_path,
                map_location="cpu",
                weights_only=True
            )

            if (
                cached["version"] == CACHE_VERSION
                and cached["manifest"] == manifest
                and cached["embeddings"].shape[0] == len(samples)
            ):

                print(f"Using cached embeddings: {person_dir.name}")

                return cached["embeddings"].float()

        except Exception as error:

            print(
                f"Cache needs rebuilding for {person_dir.name}: {error}"
            )

    # Generate embeddings if the cache is missing or outdated.
    print(f"Generating embeddings for {person_dir.name}...")

    embeddings = []

    for sample in samples:

        embedding = extract_embedding(sample, model)

        embeddings.append(embedding)

    embeddings = torch.stack(embeddings)

    cache_data = {
        "version": CACHE_VERSION,
        "manifest": manifest,
        "embeddings": embeddings
    }

    temporary_path = person_dir / "embeddings.tmp"

    torch.save(cache_data, temporary_path)

    temporary_path.replace(cache_path)

    print(
        f"Saved {len(samples)} embeddings for {person_dir.name}"
    )

    return embeddings


# -----------------------------------
# Build All Existing Profiles
# -----------------------------------

def build_all_profile_embeddings():

    if not VOICE_DIR.exists():
        print("No voice profiles found.")
        return

    model = get_model()

    for person_dir in sorted(VOICE_DIR.iterdir()):

        if not person_dir.is_dir():
            continue

        samples = sorted(person_dir.glob("sample_*.wav"))

        if len(samples) < 3:
            print(f"Skipping incomplete profile: {person_dir.name}")
            continue

        try:

            load_or_create_profile_embeddings(
                person_dir,
                model
            )

        except Exception as error:

            print(
                f"Could not build profile {person_dir.name}: {error}"
            )

    print("\nAll existing profile caches processed!")


# -----------------------------------
# Generate Embeddings After Enrollment
# -----------------------------------

def build_profile_embeddings(person_dir):

    person_dir = Path(person_dir)

    model = get_model()

    embeddings = load_or_create_profile_embeddings(
        person_dir,
        model
    )

    if embeddings is None:
        raise ValueError("Not enough enrollment samples.")

    return len(embeddings)


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

    volume = np.sqrt(
        np.mean(audio.astype(np.float32) ** 2)
    )

    print("Recorded audio volume (RMS):", volume)

    if volume < 100:
        raise ValueError("Microphone recording was too quiet.")

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

        return path

    except Exception:

        path.unlink(missing_ok=True)
        raise


# -----------------------------------
# Identify Speaker
# -----------------------------------

def identify_speaker(test_path):

    total_start = time.perf_counter()

    if not VOICE_DIR.exists():
        return None, 0.0, "No enrolled profiles"

    model = get_model()

    # Extract the test embedding just once.
    print("Extracting verification embedding...")

    test_embedding = extract_embedding(
        test_path,
        model
    )

    print(
        f"Test embedding generated in "
        f"{time.perf_counter() - total_start:.2f}s"
    )

    results = []

    for person_dir in sorted(VOICE_DIR.iterdir()):

        if not person_dir.is_dir():
            continue

        samples = sorted(person_dir.glob("sample_*.wav"))

        if len(samples) < 3:
            continue

        try:

            enrolled_embeddings = load_or_create_profile_embeddings(
                person_dir,
                model
            )

            # Compare against all cached samples.
            scores = F.cosine_similarity(
                test_embedding.unsqueeze(0),
                enrolled_embeddings,
                dim=1
            )

            average_score = float(scores.mean().item())

            if not np.isfinite(average_score):
                raise ValueError("Invalid model score")

            results.append(
                (person_dir.name, average_score)
            )

        except Exception as error:

            print(
                f"Comparison failed for {person_dir.name}: {error}"
            )

            return None, 0.0, "Profile comparison failed"

    if not results:
        return None, 0.0, "No complete voice profiles"

    results.sort(
        key=lambda item: item[1],
        reverse=True
    )

    best_name, best_score = results[0]

    print("\n========== AUTHENTICATION RESULTS ==========")

    for name, score in results:
        print(f"{name}: {score:.4f}")

    print(f"\nBest match: {best_name}")
    print(f"Best score: {best_score:.4f}")
    print(f"Required score: {MATCH_THRESHOLD:.4f}")

    if best_score < MATCH_THRESHOLD:

        print("ACCESS DENIED: Score below threshold.")

        return None, best_score, "Score below authentication threshold"

    if len(results) > 1:

        second_score = results[1][1]

        margin = best_score - second_score

        print(f"Score margin: {margin:.4f}")
        print(f"Required margin: {MIN_MARGIN:.4f}")

        if margin < MIN_MARGIN:

            print("ACCESS DENIED: Ambiguous speaker.")

            return None, best_score, "Ambiguous speaker"

    elapsed = time.perf_counter() - total_start

    print(f"Identification time: {elapsed:.2f}s")
    print(f"ACCESS GRANTED: {best_name}")

    return best_name, best_score, "Access granted"


# -----------------------------------
# Main Verification Function
# -----------------------------------

def verify_microphone(status_callback=None):

    path = None

    try:

        print("Listening for verification voice...")

        path = record_audio()

        print("Recording complete. Identifying speaker...")

        if status_callback:

            status_callback(
                "Stop speaking. Verifying speaker..."
            )

        result = identify_speaker(path)

        return result

    finally:

        if path is not None:
            path.unlink(missing_ok=True)


# -----------------------------------
# Testing / Cache Preparation
# -----------------------------------

if __name__ == "__main__":

    print("Voice recognition module ready.")

    print("Voice profiles:", VOICE_DIR)

    print("Model directory:", MODEL_DIR)

    print("\nPreparing existing voice profiles...")

    build_all_profile_embeddings()


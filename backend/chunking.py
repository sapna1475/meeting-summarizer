"""
Splits long audio files into chunks that fit within Groq's free-tier limits:
- Max file size: 25 MB per request
- Max audio: 7,200 seconds/hour, 28,800 seconds/day

We chunk by duration (default 10 minutes) rather than size, since duration
is what matters for rate limits and is predictable regardless of codec.
"""
import os
from pydub import AudioSegment

CHUNK_LENGTH_MS = 10 * 60 * 1000  # 10 minutes per chunk


def split_audio(file_path: str, output_dir: str) -> list[str]:
    """
    Splits an audio file into chunks of CHUNK_LENGTH_MS.
    Returns a list of file paths for each chunk, in order.
    If the file is already short enough, returns a single-item list
    with the original file path (no re-encoding, saves time).
    """
    os.makedirs(output_dir, exist_ok=True)

    audio = AudioSegment.from_file(file_path)
    duration_ms = len(audio)

    if duration_ms <= CHUNK_LENGTH_MS:
        return [file_path]

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    chunk_paths = []

    for i, start in enumerate(range(0, duration_ms, CHUNK_LENGTH_MS)):
        end = min(start + CHUNK_LENGTH_MS, duration_ms)
        chunk = audio[start:end]
        chunk_path = os.path.join(output_dir, f"{base_name}_chunk{i:03d}.wav")
        # Export as mono 16kHz WAV - smaller file size, works well with Whisper
        chunk = chunk.set_frame_rate(16000).set_channels(1)
        chunk.export(chunk_path, format="wav")
        chunk_paths.append(chunk_path)

    return chunk_paths

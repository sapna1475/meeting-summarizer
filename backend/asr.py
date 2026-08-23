"""
Transcription via Groq's free Whisper API (OpenAI-compatible).
Free tier (as of 2026): 2,000 requests/day, 28,800 audio seconds/day,
25 MB max file size per request. See chunking.py for how we stay under
the file size limit on long meetings.
"""
import os
from groq import Groq
from chunking import split_audio

GROQ_ASR_MODEL = os.getenv("GROQ_ASR_MODEL", "whisper-large-v3-turbo")

client = Groq(api_key=os.getenv("GROQ_API_KEY")) 


def transcribe_chunk(file_path: str) -> str:
    """Transcribes a single audio chunk and returns plain text."""
    with open(file_path, "rb") as f:
        result = client.audio.transcriptions.create(
            file=(os.path.basename(file_path), f.read()),
            model=GROQ_ASR_MODEL,
            response_format="json",
            temperature=0.0,
        )
    return result.text.strip()


def transcribe_audio(file_path: str, work_dir: str) -> str:
    """
    Transcribes a full meeting audio file, chunking it first if needed.
    Returns the stitched-together transcript.
    """
    chunk_paths = split_audio(file_path, output_dir=work_dir)

    transcripts = []
    for chunk_path in chunk_paths:
        text = transcribe_chunk(chunk_path)
        transcripts.append(text)

    # Clean up generated chunk files (but not the original upload)
    for chunk_path in chunk_paths:
        if chunk_path != file_path and os.path.exists(chunk_path):
            os.remove(chunk_path)

    return "\n\n".join(transcripts)

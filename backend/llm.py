"""
Summary generation via Groq's free LLM API (Llama 3.3 70B by default).
Uses a structured JSON prompt so the output maps directly onto the frontend.

For very long transcripts we do a simple map-reduce: split into ~6000-char
chunks, summarize each chunk into bullet notes, then produce a final
structured summary from the combined notes. This keeps us well within
context limits and avoids truncating important decisions made late in
a long meeting.
"""
import os
import json
from groq import Groq

GROQ_LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
CHUNK_CHAR_LIMIT = 6000

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are a precise meeting assistant. You read meeting \
transcripts and extract only what was actually said - never invent \
decisions, owners, or dates that aren't in the text. If information is \
unclear or missing (e.g. no due date given), say so explicitly rather \
than guessing."""

FINAL_SUMMARY_PROMPT = """Summarize this meeting transcript into a \
structured JSON object with exactly these keys:

- "overview": a 2-3 sentence plain-language summary of what the meeting was about
- "key_decisions": a list of decisions that were explicitly made (empty list if none)
- "action_items": a list of objects, each with "task", "owner" (or "unassigned" \
if not stated), and "due_date" (or "not specified" if not stated)
- "open_questions": a list of unresolved questions or topics flagged for follow-up

Return ONLY valid JSON, no markdown code fences, no preamble.

Transcript:
---
{transcript}
---
"""

CHUNK_NOTES_PROMPT = """Extract key notes from this portion of a meeting \
transcript. List any decisions made, tasks assigned (with owner if stated), \
and open questions. Be concise - plain bullet points, no JSON needed.

Transcript portion:
---
{chunk}
---
"""


def _call_llm(prompt: str, json_mode: bool = False) -> str:
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(
        model=GROQ_LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        **kwargs,
    )
    return response.choices[0].message.content.strip()


def _chunk_text(text: str, limit: int = CHUNK_CHAR_LIMIT) -> list[str]:
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def summarize_transcript(transcript: str) -> dict:
    """
    Returns a dict with keys: overview, key_decisions, action_items, open_questions.
    Falls back to map-reduce summarization for long transcripts.
    """
    if len(transcript) <= CHUNK_CHAR_LIMIT:
        source_text = transcript
    else:
        # Map step: condense each chunk into notes
        chunks = _chunk_text(transcript)
        notes = [_call_llm(CHUNK_NOTES_PROMPT.format(chunk=c)) for c in chunks]
        source_text = "\n\n".join(notes)

    # Reduce step: produce final structured JSON from (possibly condensed) text
    raw = _call_llm(FINAL_SUMMARY_PROMPT.format(transcript=source_text), json_mode=True)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Defensive fallback in case the model wraps output unexpectedly
        return {
            "overview": "Summary generation returned malformed JSON; raw output below.",
            "key_decisions": [],
            "action_items": [],
            "open_questions": [],
            "_raw_output": raw,
        }

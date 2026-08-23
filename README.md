# Meeting Summarizer

Transcribes meeting audio and generates structured, action-oriented summaries —
built entirely on free-tier APIs.


Demo - https://youtu.be/LOaLXffZ8Hk


## How it works

```
Audio file
   │
   ▼
[Chunking]  — splits long recordings into ≤10-min pieces (Groq's 25MB limit)
   │
   ▼
[ASR: Groq Whisper API]  — whisper-large-v3-turbo
   │
   ▼
Transcript (stitched from chunks)
   │
   ▼
[LLM: Groq Llama API]  — openai/gpt-oss-120b
   │  (map-reduce summarization for long transcripts)
   ▼
Structured JSON: overview, key_decisions, action_items, open_questions
   │
   ▼
[FastAPI backend] ── stores in SQLite ── [Streamlit frontend]
```

**Why Groq for both stages:** one free API key covers transcription and
summarization, avoiding the need to juggle multiple provider accounts.
Free tier limits (2026): 2,000 ASR requests/day, 28,800 audio-seconds/day,
25MB max file size, generous daily token limits on the LLM side.

## Setup

### 1. Get a free Groq API key
Sign up at [console.groq.com](https://console.groq.com) — no credit card required.

### 2. Install dependencies
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

You'll also need `ffmpeg` installed on your system (used by `pydub` for audio chunking):
```bash
# macOS
brew install ffmpeg
# Ubuntu/Debian
sudo apt install ffmpeg
```

### 3. Configure environment
```bash
cp .env.example .env
# edit .env and paste in your GROQ_API_KEY
```

### 4. Run the backend
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 5. Run the frontend (in a new terminal)
```bash
cd frontend
streamlit run app.py
```

Open the Streamlit URL shown in the terminal, upload a meeting recording,
and watch it move through transcribing → summarizing → done.

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/upload-audio` | POST | Upload an audio file, kicks off async processing |
| `/meetings/{id}` | GET | Poll status / get transcript + summary |
| `/meetings` | GET | List all past meetings |
| `/health` | GET | Health check |

## Project Structure

```
meeting-summarizer/
├── backend/
│   ├── main.py        # FastAPI app, endpoints, background processing
│   ├── asr.py          # Groq Whisper transcription
│   ├── llm.py           # Groq Llama summarization + prompts
│   ├── chunking.py     # Audio splitting for long files
│   ├── models.py       # SQLModel schema
│   └── storage.py      # DB engine/session
├── frontend/
│   └── app.py            # Streamlit UI
├── requirements.txt
├── .env.example
└── README.md
```

## LLM Prompt Design

The summarization prompt asks for structured JSON directly (`overview`,
`key_decisions`, `action_items`, `open_questions`) rather than free-form text,
which:
- Makes rendering in the frontend trivial (no post-processing/regex needed)
- Forces the model to be explicit about missing info (e.g. `"owner": "unassigned"`
  instead of silently omitting or hallucinating a name)
- Is easy to unit-test against expected keys

For transcripts longer than ~6,000 characters, we use a **map-reduce** approach:
each chunk is condensed into plain-text notes first, then a final pass turns
the combined notes into the structured JSON summary. This avoids truncation
issues and keeps context per-call small and cheap.

### Prompt iteration notes (for evaluation writeup)
- **v1** (`"Summarize this meeting"`) — vague, produced generic paragraph summaries with no actionable structure.
- **v2** (added explicit JSON schema) — much more usable output, but the model would sometimes invent due dates.
- **v3** (current — added explicit instruction *"never invent decisions, owners, or dates... say so explicitly"*) — model now correctly returns `"not specified"` instead of guessing.

## Known Limitations

- No speaker diarization yet (who said what) — Groq's Whisper endpoint doesn't
  return speaker labels. Could add via `pyannote.audio` (also free/open-source)
  as a future improvement.
- Background processing uses FastAPI `BackgroundTasks` (in-process), which is
  fine for a demo but should move to a real task queue (Celery/RQ) for
  production use with concurrent uploads.
- Free-tier rate limits mean very heavy usage (>8 hrs of audio/day) will need
  a paid tier or a local Whisper fallback.

## Future Improvements
- Speaker diarization
- Real-time streaming transcription for live meetings
- Export summary as PDF/Markdown
- Slack/email delivery of action items

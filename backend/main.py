import os
import json
import shutil
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from models import Meeting
from storage import init_db, get_session, engine
from asr import transcribe_audio
from llm import summarize_transcript

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Meeting Summarizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this for production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


def process_meeting(meeting_id: int, file_path: str):
    """Background job: transcribe then summarize. Updates DB status as it goes."""
    with Session(engine) as session:
        meeting = session.get(Meeting, meeting_id)
        try:
            meeting.status = "transcribing"
            session.add(meeting)
            session.commit()

            work_dir = os.path.join(UPLOAD_DIR, f"chunks_{meeting_id}")
            transcript = transcribe_audio(file_path, work_dir=work_dir)

            meeting.transcript = transcript
            meeting.status = "summarizing"
            session.add(meeting)
            session.commit()

            summary = summarize_transcript(transcript)

            meeting.summary_json = json.dumps(summary)
            meeting.status = "done"
            session.add(meeting)
            session.commit()

            if os.path.isdir(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)

        except Exception as e:
            meeting.status = "failed"
            meeting.error = str(e)
            session.add(meeting)
            session.commit()


@app.post("/upload-audio")
def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    allowed_ext = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".flac", ".ogg"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    meeting = Meeting(filename=file.filename, status="pending")
    session.add(meeting)
    session.commit()
    session.refresh(meeting)

    saved_path = os.path.join(UPLOAD_DIR, f"{meeting.id}_{file.filename}")
    with open(saved_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    background_tasks.add_task(process_meeting, meeting.id, saved_path)

    return {"id": meeting.id, "status": meeting.status}


@app.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: int, session: Session = Depends(get_session)):
    meeting = session.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")

    summary = json.loads(meeting.summary_json) if meeting.summary_json else None

    return {
        "id": meeting.id,
        "filename": meeting.filename,
        "status": meeting.status,
        "transcript": meeting.transcript,
        "summary": summary,
        "error": meeting.error,
        "created_at": meeting.created_at,
    }


@app.get("/meetings")
def list_meetings(session: Session = Depends(get_session)):
    meetings = session.exec(select(Meeting).order_by(Meeting.created_at.desc())).all()
    return [
        {"id": m.id, "filename": m.filename, "status": m.status, "created_at": m.created_at}
        for m in meetings
    ]


@app.get("/health")
def health():
    return {"status": "ok"}

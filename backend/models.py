from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Meeting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    status: str = Field(default="pending")  # pending -> transcribing -> summarizing -> done -> failed
    transcript: Optional[str] = None
    summary_json: Optional[str] = None  # stored as JSON string
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    token: Optional[str] = None
    session_id: Optional[str] = None
    userid: Optional[str] = None
    access_role: Optional[str] = None


class ChatResponse(BaseModel):
    status: str
    intent: dict
    response: dict
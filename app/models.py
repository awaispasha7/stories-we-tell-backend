from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

# User and Session Models
class User(BaseModel):
    user_id: UUID
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    password_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class UserCreate(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    password_hash: Optional[str] = None

class Session(BaseModel):
    session_id: UUID
    user_id: UUID
    project_id: UUID
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    is_active: bool = True

class SessionCreate(BaseModel):
    user_id: UUID
    project_id: UUID
    title: Optional[str] = None

class SessionSummary(BaseModel):
    session_id: UUID
    project_id: UUID
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None
    message_count: int = 0
    last_message_preview: Optional[str] = None
    project_title: Optional[str] = None
    project_logline: Optional[str] = None

# Chat Message Models
class ChatMessage(BaseModel):
    message_id: UUID
    session_id: UUID
    turn_id: Optional[UUID] = None
    role: str  # 'user', 'assistant', 'system'
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ChatMessageCreate(BaseModel):
    session_id: UUID
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    text: str
    session_id: Optional[UUID] = None  # If provided, continue existing session
    project_id: Optional[UUID] = None  # If provided, create new session

class ChatResponse(BaseModel):
    reply: str
    metadata_json: Dict[str, Any]  # The structured metadata JSON returned by the assistant
    session_id: UUID
    message_id: UUID

# Legacy Models (keeping for backward compatibility)
class SubmissionMetadata(BaseModel):
    turn_id: str
    project_id: str
    raw_text: str
    normalized: Dict[str, Any]

class SceneMetadata(BaseModel):
    scene_id: str
    description: Optional[str] = None
    interior_exterior: Optional[str] = None
    time_of_day: Optional[str] = None
    tone: Optional[str] = None

class Dossier(BaseModel):
    title: Optional[str] = None
    logline: Optional[str] = None
    genre: Optional[str] = None
    tone: Optional[str] = None
    scenes: List[SceneMetadata] = []

# User Project Association
class UserProject(BaseModel):
    user_id: UUID
    project_id: UUID
    created_at: Optional[datetime] = None

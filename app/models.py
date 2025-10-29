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
    user_id: Optional[str] = None  # Supabase auth user ID
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
    turn_id: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    text: str
    session_id: Optional[UUID] = None  # If provided, continue existing session
    project_id: Optional[UUID] = None  # If provided, create new session
    attached_files: Optional[List[Dict[str, Any]]] = None  # Attached files with metadata
    edit_from_message_id: Optional[UUID] = None  # If provided, delete this message and all subsequent messages before creating new message

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

class CharacterMetadata(BaseModel):
    character_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    role: Optional[str] = None

class Dossier(BaseModel):
    project_id: UUID
    user_id: UUID
    snapshot_json: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Convenience properties for accessing snapshot data
    @property
    def title(self) -> Optional[str]:
        if self.snapshot_json:
            return self.snapshot_json.get('title')
        return None
    
    @property
    def logline(self) -> Optional[str]:
        if self.snapshot_json:
            return self.snapshot_json.get('logline')
        return None
    
    @property
    def genre(self) -> Optional[str]:
        if self.snapshot_json:
            return self.snapshot_json.get('genre')
        return None
    
    @property
    def tone(self) -> Optional[str]:
        if self.snapshot_json:
            return self.snapshot_json.get('tone')
        return None
    
    @property
    def scenes(self) -> List[SceneMetadata]:
        if self.snapshot_json and 'scenes' in self.snapshot_json:
            return [SceneMetadata(**scene) for scene in self.snapshot_json['scenes']]
        return []
    
    @property
    def characters(self) -> List[CharacterMetadata]:
        if self.snapshot_json and 'characters' in self.snapshot_json:
            return [CharacterMetadata(**char) for char in self.snapshot_json['characters']]
        return []

class DossierCreate(BaseModel):
    project_id: UUID
    user_id: UUID
    snapshot_json: Optional[Dict[str, Any]] = None

class DossierUpdate(BaseModel):
    snapshot_json: Optional[Dict[str, Any]] = None

# User Project Association
class UserProject(BaseModel):
    user_id: UUID
    project_id: UUID
    created_at: Optional[datetime] = None

# Migration Request
class MigrationRequest(BaseModel):
    anonymous_session_id: str
    user_id: str

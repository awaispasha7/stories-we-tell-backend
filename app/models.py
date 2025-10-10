from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ChatRequest(BaseModel):
    text: str

class ChatResponse(BaseModel):
    reply: str
    metadata_json: Dict[str, Any]  # The structured metadata JSON returned by the assistant

# You can add more models here in the future, for example:

# Example of a model for handling submission metadata
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

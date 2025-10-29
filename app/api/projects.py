"""
Projects API
Handles project creation and management for authenticated users
Projects = Stories (user-created, can have multiple sessions)
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone
from pydantic import BaseModel

from ..database.supabase import get_supabase_client

router = APIRouter()

class ProjectCreate(BaseModel):
    name: str  # User-friendly project name (e.g., "Romantic Novel")
    description: Optional[str] = None

class ProjectResponse(BaseModel):
    project_id: UUID
    name: str
    description: Optional[str] = None
    user_id: UUID
    created_at: str
    updated_at: str
    session_count: int = 0

@router.post("/projects")
async def create_project(
    project_data: ProjectCreate,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Create a new project for authenticated user
    Project = Story container (can have multiple chat sessions)
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required - please authenticate")
    
    try:
        user_id = UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection unavailable")
    
    # Verify user exists
    user_result = supabase.table("users").select("*").eq("user_id", str(user_id)).execute()
    if not user_result.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create new project (dossier entry)
    project_id = uuid4()
    current_time = datetime.now(timezone.utc).isoformat()
    
    # Create dossier entry for the project
    dossier_data = {
        "project_id": str(project_id),
        "user_id": str(user_id),
        "snapshot_json": {
            "title": project_data.name,
            "logline": project_data.description or "",
            "genre": "",
            "tone": "",
            "characters": [],
            "scenes": [],
            "created_at": current_time
        },
        "created_at": current_time,
        "updated_at": current_time
    }
    
    try:
        supabase.table("dossier").insert(dossier_data).execute()
    except Exception as e:
        print(f"❌ Error creating dossier: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")
    
    # Associate user with project
    user_project_data = {
        "user_id": str(user_id),
        "project_id": str(project_id),
        "created_at": current_time
    }
    
    try:
        supabase.table("user_projects").insert(user_project_data).execute()
    except Exception as e:
        print(f"⚠️ Warning: Failed to create user_project association: {e}")
        # Don't fail - dossier is created, association is nice-to-have
    
    print(f"✅ Created project: {project_data.name} (ID: {project_id}) for user: {user_id}")
    
    return {
        "project_id": str(project_id),
        "name": project_data.name,
        "description": project_data.description,
        "user_id": str(user_id),
        "created_at": current_time,
        "updated_at": current_time,
        "session_count": 0
    }

@router.get("/projects")
async def get_user_projects(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Get all projects for authenticated user with session counts
    Returns projects in hierarchical structure
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required - please authenticate")
    
    try:
        user_id = UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection unavailable")
    
    # Get all projects (dossiers) for user
    dossier_result = supabase.table("dossier").select("*").eq("user_id", str(user_id)).order("updated_at", desc=True).execute()
    
    projects = []
    for dossier in dossier_result.data:
        project_id = dossier["project_id"]
        
        # Get session count for this project
        sessions_result = supabase.table("sessions").select("session_id").eq("project_id", project_id).execute()
        session_count = len(sessions_result.data) if sessions_result.data else 0
        
        # Get project name from dossier title
        project_name = dossier.get("snapshot_json", {}).get("title", "Untitled Project")
        
        projects.append({
            "project_id": project_id,
            "name": project_name,
            "description": dossier.get("snapshot_json", {}).get("logline", ""),
            "user_id": str(user_id),
            "created_at": dossier.get("created_at", ""),
            "updated_at": dossier.get("updated_at", ""),
            "session_count": session_count
        })
    
    return {
        "projects": projects,
        "count": len(projects)
    }

@router.get("/projects/{project_id}")
async def get_project(
    project_id: UUID,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Get specific project details with sessions
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required - please authenticate")
    
    try:
        user_id = UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection unavailable")
    
    # Get dossier (project)
    dossier_result = supabase.table("dossier").select("*").eq("project_id", str(project_id)).eq("user_id", str(user_id)).execute()
    
    if not dossier_result.data:
        raise HTTPException(status_code=404, detail="Project not found")
    
    dossier = dossier_result.data[0]
    
    # Get sessions for this project
    sessions_result = supabase.table("sessions").select("*").eq("project_id", str(project_id)).order("last_message_at", desc=True).execute()
    
    sessions = []
    if sessions_result.data:
        for session in sessions_result.data:
            sessions.append({
                "session_id": session["session_id"],
                "title": session.get("title", "New Chat"),
                "created_at": session.get("created_at", ""),
                "last_message_at": session.get("last_message_at", ""),
                "is_active": session.get("is_active", True)
            })
    
    project_name = dossier.get("snapshot_json", {}).get("title", "Untitled Project")
    
    return {
        "project_id": str(project_id),
        "name": project_name,
        "description": dossier.get("snapshot_json", {}).get("logline", ""),
        "user_id": str(user_id),
        "created_at": dossier.get("created_at", ""),
        "updated_at": dossier.get("updated_at", ""),
        "session_count": len(sessions),
        "sessions": sessions
    }

@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: UUID,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Delete a project and all its related data (cascade delete manually)
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User ID required - please authenticate")
    
    try:
        user_id = UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(status_code=500, detail="Database connection unavailable")
    
    # Verify ownership
    dossier_result = supabase.table("dossier").select("*").eq("project_id", str(project_id)).eq("user_id", str(user_id)).execute()
    if not dossier_result.data:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_id_str = str(project_id)
    
    try:
        # Delete in order (respecting foreign key constraints):
        # 1. Delete message embeddings (references project_id)
        supabase.table("message_embeddings").delete().eq("project_id", project_id_str).execute()
        print(f"🗑️ Deleted message embeddings for project: {project_id}")
        
        # 2. Delete document embeddings (references project_id)
        supabase.table("document_embeddings").delete().eq("project_id", project_id_str).execute()
        print(f"🗑️ Deleted document embeddings for project: {project_id}")
        
        # 3. Delete embedding queue entries (references project_id)
        supabase.table("embedding_queue").delete().eq("project_id", project_id_str).execute()
        print(f"🗑️ Deleted embedding queue entries for project: {project_id}")
        
        # 4. Get all sessions for this project first
        sessions_result = supabase.table("sessions").select("session_id").eq("project_id", project_id_str).execute()
        session_ids = [session["session_id"] for session in sessions_result.data] if sessions_result.data else []
        
        # 5. Delete chat messages for all sessions (references session_id)
        for session_id in session_ids:
            supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
        print(f"🗑️ Deleted chat messages for {len(session_ids)} sessions")
        
        # 6. Delete turns for all sessions (references session_id)
        for session_id in session_ids:
            supabase.table("turns").delete().eq("session_id", session_id).execute()
        print(f"🗑️ Deleted turns for {len(session_ids)} sessions")
        
        # 7. Delete sessions (references project_id)
        supabase.table("sessions").delete().eq("project_id", project_id_str).execute()
        print(f"🗑️ Deleted {len(session_ids)} sessions for project: {project_id}")
        
        # 8. Delete assets (references project_id)
        supabase.table("assets").delete().eq("project_id", project_id_str).execute()
        print(f"🗑️ Deleted assets for project: {project_id}")
        
        # 9. Delete user_projects junction table entry (references project_id)
        supabase.table("user_projects").delete().eq("project_id", project_id_str).eq("user_id", str(user_id)).execute()
        print(f"🗑️ Deleted user_projects entry for project: {project_id}")
        
        # 10. Finally, delete the dossier (project) itself
        supabase.table("dossier").delete().eq("project_id", project_id_str).eq("user_id", str(user_id)).execute()
        print(f"✅ Deleted project: {project_id} for user: {user_id}")
        
        return {"message": "Project deleted successfully", "sessions_deleted": len(session_ids)}
    except Exception as e:
        print(f"❌ Error deleting project: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")


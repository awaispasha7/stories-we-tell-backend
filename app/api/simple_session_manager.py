"""
Simplified Session Manager
Clean, single-system approach for session management
"""

from fastapi import APIRouter, HTTPException, Header, Body, Query
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
import time

from ..database.supabase import get_supabase_client

router = APIRouter()

# Session timeout for anonymous users (24 hours)
ANONYMOUS_SESSION_TIMEOUT = 24 * 60 * 60  # 24 hours in seconds

class SimpleSessionManager:
    """Simplified session manager - one system for all users"""
    
    @staticmethod
    async def get_or_create_session(
        session_id: Optional[str] = None,
        user_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get or create a session. Works for both authenticated and anonymous users.
        
        Flow:
        1. If user_id provided (authenticated) -> use that user
        2. If session_id provided -> check if session exists and is valid
        3. If no session_id -> create new anonymous session with temporary user
        """
        supabase = get_supabase_client()
        
        # Case 1: Authenticated user
        if user_id:
            return await SimpleSessionManager._handle_authenticated_user(
                user_id, session_id, project_id
            )
        
        # Case 2: Anonymous user with existing session
        if session_id:
            return await SimpleSessionManager._handle_existing_anonymous_session(
                session_id, project_id
            )
        
        # Case 3: New anonymous user - create everything
        return await SimpleSessionManager._create_new_anonymous_session(project_id)
    
    @staticmethod
    async def _handle_authenticated_user(
        user_id: UUID, 
        session_id: Optional[str], 
        project_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Handle authenticated user session"""
        supabase = get_supabase_client()
        
        # Verify user exists
        user_result = supabase.table("users").select("*").eq("user_id", str(user_id)).execute()
        if not user_result.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = user_result.data[0]
        
        # Get or create session
        if session_id:
            # Check if session exists and belongs to user
            session_result = supabase.table("sessions").select("*").eq("session_id", session_id).eq("user_id", str(user_id)).execute()
            if session_result.data:
                session = session_result.data[0]
                return {
                    "session_id": session["session_id"],
                    "user_id": str(user_id),
                    "project_id": str(session["project_id"]) if session["project_id"] else None,
                    "is_authenticated": True,
                    "user": user
                }
        
        # Create new session for authenticated user
        # IMPORTANT: For authenticated users, project_id is REQUIRED (no auto-creation)
        # Users must create projects explicitly via the projects API
        if not project_id:
            raise HTTPException(
                status_code=400, 
                detail="Project ID required for authenticated users. Please create a project first via /api/v1/projects"
            )
        
        # Verify project exists and belongs to user
        dossier_result = supabase.table("dossier").select("*").eq("project_id", str(project_id)).eq("user_id", str(user_id)).execute()
        if not dossier_result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Project not found or you don't have access to it. Please create a project first via /api/v1/projects"
            )
        
        new_session_id = str(uuid4())
        new_project_id = project_id  # Use provided project_id (required)
        
        # For authenticated users, dossier MUST already exist (created via projects API)
        # Don't auto-create it - if it doesn't exist, that's an error
        dossier_check = supabase.table("dossier").select("*").eq("project_id", str(new_project_id)).execute()
        if not dossier_check.data:
            raise HTTPException(
                status_code=404,
                detail=f"Project dossier not found. Project must be created via /api/v1/projects first."
            )
        
        session_data = {
            "session_id": new_session_id,
            "user_id": str(user_id),
            "project_id": str(new_project_id),
            "title": "New Chat",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_message_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True
        }
        
        supabase.table("sessions").insert(session_data).execute()
        
        return {
            "session_id": new_session_id,
            "user_id": str(user_id),
            "project_id": str(new_project_id),
            "is_authenticated": True,
            "user": user
        }
    
    @staticmethod
    async def _handle_existing_anonymous_session(
        session_id: str, 
        project_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Handle existing anonymous session"""
        supabase = get_supabase_client()
        
        # Check if session exists
        session_result = supabase.table("sessions").select("*").eq("session_id", session_id).execute()
        if not session_result.data:
            # Session doesn't exist, create new one
            return await SimpleSessionManager._create_new_anonymous_session(project_id)
        
        session = session_result.data[0]
        user_id = session["user_id"]
        
        # Check if user still exists and is anonymous
        user_result = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if not user_result.data:
            # User was deleted, create new session
            return await SimpleSessionManager._create_new_anonymous_session(project_id)
        
        user = user_result.data[0]
        
        # Check if session is expired (for anonymous users)
        if user["email"].startswith("anonymous_"):
            session_created = datetime.fromisoformat(session["created_at"].replace('Z', '+00:00'))
            if datetime.now(timezone.utc) - session_created > timedelta(seconds=ANONYMOUS_SESSION_TIMEOUT):
                # Session expired, create new one
                return await SimpleSessionManager._create_new_anonymous_session(project_id)
        
        # For anonymous users, ensure dossier exists (can auto-create with proper title)
        # For authenticated users, dossier should already exist
        if user["email"].startswith("anonymous_"):
            dossier_check = supabase.table("dossier").select("*").eq("project_id", str(session["project_id"])).execute()
            if not dossier_check.data:
                dossier_data = {
                    "project_id": str(session["project_id"]),
                    "user_id": user_id,
                    "snapshot_json": {
                        "title": "Demo Story",
                        "logline": "",
                        "genre": "",
                        "tone": "",
                        # Story Frame
                        "story_timeframe": "",
                        "story_location": "",
                        "story_world_type": "",
                        "writer_connection_place_time": "",
                        "season_time_of_year": "",
                        "environmental_details": "",
                        # Character (Legacy)
                        "subject_exists_real_world": "unknown",
                        "subject_full_name": "",
                        "subject_relationship_to_writer": "",
                        "subject_brief_description": "",
                        # Heroes (Primary Characters - NEW)
                        "heroes": [],
                        # Supporting Characters (Secondary Characters - NEW)
                        "supporting_characters": [],
                        # Story Craft
                        "problem_statement": "",
                        "actions_taken": "",
                        "outcome": "",
                        "likes_in_story": "",
                        # Story Type & Style (NEW)
                        "story_type": "other",
                        "audience": {
                            "who_will_see_first": "",
                            "desired_feeling": ""
                        },
                        "perspective": "narrator_voice",
                        # Technical
                        "runtime": "3-5 minutes",
                        # Legacy Characters (for backward compatibility)
                        "characters": [],
                        # Scenes
                        "scenes": [],
                        # Future Phase 2 fields (placeholders)
                        "synopsis": "",
                        "full_script": "",
                        "dialogue": [],
                        "voiceover_script": {},
                        "shot_list": {},
                        "camera_logic": {},
                        "scene_math": {},
                        "micro_prompts": [],
                        "created_at": datetime.now(timezone.utc).isoformat()
                    },
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                supabase.table("dossier").insert(dossier_data).execute()
                print(f"Created dossier for anonymous project {session['project_id']}")
        
        return {
            "session_id": session_id,
            "user_id": str(user_id),
            "project_id": str(session["project_id"]) if session["project_id"] else None,
            "is_authenticated": not user["email"].startswith("anonymous_"),
            "user": user
        }
    
    @staticmethod
    async def _create_new_anonymous_session(project_id: Optional[UUID]) -> Dict[str, Any]:
        """Create new anonymous session with temporary user"""
        supabase = get_supabase_client()
        
        # Create temporary user
        temp_user_id = str(uuid4())
        temp_email = f"anonymous_{temp_user_id}@temp.local"
        
        user_data = {
            "user_id": temp_user_id,
            "email": temp_email,
            "display_name": f"Anonymous User {temp_user_id[:8]}",
            "avatar_url": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        supabase.table("users").insert(user_data).execute()
        
        # Create session
        session_id = str(uuid4())
        new_project_id = project_id or uuid4()
        
        # For anonymous users, ensure dossier exists with enhanced structure
        dossier_check = supabase.table("dossier").select("*").eq("project_id", str(new_project_id)).execute()
        if not dossier_check.data:
            dossier_data = {
                "project_id": str(new_project_id),
                "user_id": str(temp_user_id),
                "snapshot_json": {
                    "title": "Demo Story",
                    "logline": "",
                    "genre": "",
                    "tone": "",
                    # Story Frame
                    "story_timeframe": "",
                    "story_location": "",
                    "story_world_type": "",
                    "writer_connection_place_time": "",
                    "season_time_of_year": "",
                    "environmental_details": "",
                    # Character (Legacy)
                    "subject_exists_real_world": "unknown",
                    "subject_full_name": "",
                    "subject_relationship_to_writer": "",
                    "subject_brief_description": "",
                    # Heroes (Primary Characters - NEW)
                    "heroes": [],
                    # Supporting Characters (Secondary Characters - NEW)
                    "supporting_characters": [],
                    # Story Craft
                    "problem_statement": "",
                    "actions_taken": "",
                    "outcome": "",
                    "likes_in_story": "",
                    # Story Type & Style (NEW)
                    "story_type": "other",
                    "audience": {
                        "who_will_see_first": "",
                        "desired_feeling": ""
                    },
                    "perspective": "narrator_voice",
                    # Technical
                    "runtime": "3-5 minutes",
                    # Legacy Characters (for backward compatibility)
                    "characters": [],
                    # Scenes
                    "scenes": [],
                    # Future Phase 2 fields (placeholders)
                    "synopsis": "",
                    "full_script": "",
                    "dialogue": [],
                    "voiceover_script": {},
                    "shot_list": {},
                    "camera_logic": {},
                    "scene_math": {},
                    "micro_prompts": [],
                    "created_at": datetime.now(timezone.utc).isoformat()
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            supabase.table("dossier").insert(dossier_data).execute()
            print(f"Created dossier for anonymous project {new_project_id}")
        
        session_data = {
            "session_id": session_id,
            "user_id": str(temp_user_id),
            "project_id": str(new_project_id),
            "title": "New Chat",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_message_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True
        }
        
        supabase.table("sessions").insert(session_data).execute()
        
        return {
            "session_id": session_id,
            "user_id": str(temp_user_id),
            "project_id": str(new_project_id),
            "is_authenticated": False,
            "user": user_data
        }
    
    @staticmethod
    async def migrate_anonymous_to_authenticated(
        anonymous_user_id: str,
        authenticated_user_id: UUID
    ) -> Dict[str, Any]:
        """Migrate anonymous user's sessions to authenticated user"""
        supabase = get_supabase_client()
        
        # Get all sessions for anonymous user
        sessions_result = supabase.table("sessions").select("*").eq("user_id", anonymous_user_id).execute()
        
        if not sessions_result.data:
            return {"message": "No sessions to migrate"}
        
        # Update all sessions to use authenticated user
        for session in sessions_result.data:
            supabase.table("sessions").update({
                "user_id": str(authenticated_user_id),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("session_id", session["session_id"]).execute()
        
        # Update all chat messages
        supabase.table("chat_messages").update({
            "user_id": str(authenticated_user_id)
        }).eq("user_id", anonymous_user_id).execute()
        
        # Update all turns
        supabase.table("turns").update({
            "user_id": str(authenticated_user_id)
        }).eq("user_id", anonymous_user_id).execute()
        
        # Update dossier
        supabase.table("dossier").update({
            "user_id": str(authenticated_user_id)
        }).eq("user_id", anonymous_user_id).execute()
        
        # Update user_projects
        supabase.table("user_projects").update({
            "user_id": str(authenticated_user_id)
        }).eq("user_id", anonymous_user_id).execute()
        
        # Delete anonymous user
        supabase.table("users").delete().eq("user_id", anonymous_user_id).execute()
        
        return {
            "message": f"Successfully migrated {len(sessions_result.data)} sessions to authenticated user",
            "migrated_sessions": len(sessions_result.data)
        }
    
    @staticmethod
    async def cleanup_expired_anonymous_sessions():
        """Clean up expired anonymous sessions and users"""
        supabase = get_supabase_client()
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=ANONYMOUS_SESSION_TIMEOUT)
        
        # Get expired anonymous users
        expired_users_result = supabase.table("users").select("user_id, email").like("email", "anonymous_%@temp.local").lt("created_at", cutoff_time.isoformat()).execute()
        
        if not expired_users_result.data:
            return {"cleaned": 0}
        
        cleaned_count = 0
        for user in expired_users_result.data:
            user_id = user["user_id"]
            
            try:
                # Anonymize chat messages (set user_id to NULL)
                supabase.table("chat_messages").update({"user_id": None}).eq("user_id", user_id).execute()
                
                # Anonymize turns (set user_id to NULL)
                supabase.table("turns").update({"user_id": None}).eq("user_id", user_id).execute()
                
                # Delete dossier
                supabase.table("dossier").delete().eq("user_id", user_id).execute()
                
                # Delete user_projects
                supabase.table("user_projects").delete().eq("user_id", user_id).execute()
                
                # Delete sessions
                supabase.table("sessions").delete().eq("user_id", user_id).execute()
                
                # Delete user
                supabase.table("users").delete().eq("user_id", user_id).execute()
                
                cleaned_count += 1
                print(f"Cleaned up expired anonymous user: {user['email']}")
                
            except Exception as e:
                print(f"Error cleaning up user {user_id}: {e}")
                continue
        
        return {"cleaned": cleaned_count}
    
    @staticmethod
    async def _ensure_dossier_exists(project_id: UUID, user_id: str):
        """
        DEPRECATED: This method should not be used for authenticated users.
        For authenticated users, projects MUST be created via /api/v1/projects.
        This method only exists for backward compatibility with anonymous users.
        """
        supabase = get_supabase_client()
        
        # Check if dossier already exists
        dossier_result = supabase.table("dossier").select("*").eq("project_id", str(project_id)).execute()
        
        if not dossier_result.data:
            # Only create for anonymous users - authenticated users must use projects API
            # Note: This should rarely be called now as we handle dossier creation explicitly
            print(f"⚠️ WARNING: _ensure_dossier_exists called - this should not create projects for authenticated users")
            dossier_data = {
                "project_id": str(project_id),
                "user_id": str(user_id),
                "snapshot_json": {
                    "title": "Demo Story",
                    "logline": "",
                    "genre": "",
                    "tone": "",
                    "characters": [],
                    "scenes": [],
                    "created_at": datetime.now(timezone.utc).isoformat()
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            supabase.table("dossier").insert(dossier_data).execute()
            print(f"Created dossier for project {project_id} and user {user_id}")

# API Endpoints
@router.post("/session")
async def get_or_create_session(
    session_id: Optional[str] = Body(None),
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
    project_id: Optional[str] = Body(None)
):
    """Get or create a session - works for both authenticated and anonymous users"""
    try:
        parsed_user_id = None
        if user_id:
            try:
                parsed_user_id = UUID(user_id)
            except (ValueError, TypeError) as e:
                print(f"Invalid user_id format: {user_id} - {e}")
                raise HTTPException(status_code=400, detail=f"Invalid user_id format: {user_id}")
        
        parsed_project_id = None
        if project_id:
            try:
                parsed_project_id = UUID(project_id)
            except (ValueError, TypeError) as e:
                print(f"Invalid project_id format: {project_id} - {e}")
                raise HTTPException(status_code=400, detail=f"Invalid project_id format: {project_id}")
        
        result = await SimpleSessionManager.get_or_create_session(
            session_id=session_id,
            user_id=parsed_user_id,
            project_id=parsed_project_id
        )
        
        # Ensure all UUID objects are converted to strings for JSON serialization
        response_data = {
            "success": True,
            "session_id": str(result["session_id"]),
            "user_id": str(result["user_id"]),
            "project_id": str(result["project_id"]) if result["project_id"] else None,
            "is_authenticated": result["is_authenticated"],
            "user": result["user"]
        }
        
        return response_data
        
    except HTTPException:
        # Re-raise HTTPExceptions (400, 404, etc.)
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Error in get_or_create_session: {e}")
        print(f"❌ Traceback: {error_trace}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@router.post("/migrate-session")
async def migrate_anonymous_session(
    anonymous_user_id: str,
    authenticated_user_id: str
):
    """Migrate anonymous user's sessions to authenticated user"""
    try:
        result = await SimpleSessionManager.migrate_anonymous_to_authenticated(
            anonymous_user_id,
            UUID(authenticated_user_id)
        )
        return {"success": True, **result}
    except Exception as e:
        print(f"Error migrating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup-expired")
async def cleanup_expired_sessions():
    """Clean up expired anonymous sessions"""
    try:
        result = await SimpleSessionManager.cleanup_expired_anonymous_sessions()
        return {"success": True, **result}
    except Exception as e:
        print(f"Error cleaning up sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions")
async def get_user_sessions(
    limit: int = 10,
    user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Get user sessions"""
    try:
        print(f"🔍 Sessions API called - user_id: {user_id}")
        print(f"🔍 Sessions API called - limit: {limit}")
        
        if not user_id:
            print("❌ No user_id provided to sessions API")
            return {"success": True, "sessions": []}
        
        supabase = get_supabase_client()
        result = supabase.table("sessions").select("*").eq("user_id", user_id).order("updated_at", desc=True).limit(limit).execute()
        
        print(f"🔍 Found {len(result.data or [])} sessions for user {user_id}")
        
        return {
            "success": True,
            "sessions": result.data or []
        }
    except Exception as e:
        print(f"Error getting user sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = Query(500, ge=1, le=10000),  # Allow up to 10000 messages, default 500
    offset: int = Query(0, ge=0),  # Support pagination
    user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Get messages for a specific session"""
    try:
        print(f"🔍 Session messages API called - session_id: {session_id}, user_id: {user_id}")
        supabase = get_supabase_client()
        
        # Verify session exists and user has access
        session_result = supabase.table("sessions").select("*").eq("session_id", session_id).execute()
        if not session_result.data:
            print(f"❌ Session not found: {session_id}")
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = session_result.data[0]
        print(f"🔍 Session found - session_user_id: {session['user_id']}, request_user_id: {user_id}")
        
        if user_id and session["user_id"] != user_id:
            print(f"❌ Access denied - session belongs to {session['user_id']}, but user is {user_id}")
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get messages with limit and offset support
        # Supabase uses range() for offset + limit: range(offset, offset + limit - 1)
        # For example: range(0, 49) gets first 50 messages, range(50, 99) gets next 50
        messages_result = supabase.table("chat_messages")\
            .select("*")\
            .eq("session_id", session_id)\
            .order("created_at", desc=False)\
            .range(offset, offset + limit - 1)\
            .execute()
        
        print(f"📋 [MESSAGES] Fetched {len(messages_result.data) if messages_result.data else 0} messages (limit={limit}, offset={offset})")
        
        # Check PROJECT completion status (not just session) - if ANY session in project is completed, lock ALL sessions
        story_completed = False
        project_id = session.get("project_id")
        
        try:
            # First check if this specific session is completed
            session_completed = session.get("story_completed", False)
            story_completed = bool(session_completed) if session_completed is not None else False
            print(f"🔍 [COMPLETION CHECK] Session {session_id} completion status: {session_completed} (bool: {story_completed})")
            
            # CRITICAL: Check if ANY session in the project is completed
            # If so, lock ALL sessions in that project
            # BUT ONLY if project_id exists - don't lock if project_id is None!
            if project_id:
                print(f"🔍 [COMPLETION CHECK] Checking project {project_id} for completed sessions...")
                project_result = supabase.table("sessions").select("story_completed, session_id").eq("project_id", str(project_id)).eq("story_completed", True).limit(1).execute()
                print(f"🔍 [COMPLETION CHECK] Project query result: {len(project_result.data) if project_result.data else 0} completed sessions found")
                if project_result.data and len(project_result.data) > 0:
                    story_completed = True
                    print(f"🔒 [COMPLETION] Project {project_id} has completed sessions - locking all sessions in project")
                    print(f"🔒 [COMPLETION] Completed session found: {project_result.data[0].get('session_id')}")
                else:
                    print(f"✅ [COMPLETION] Project {project_id} has NO completed sessions - allowing messages")
            else:
                print(f"⚠️ [COMPLETION CHECK] No project_id for session {session_id} - only checking session-level completion")
                # If no project_id, only check session-level completion (already done above)
        except Exception as e:
            print(f"⚠️ Error checking completion status: {e}")
            import traceback
            print(f"⚠️ Traceback: {traceback.format_exc()}")
            # On error, default to NOT completed (safer)
            story_completed = False
        
        # Ensure story_completed is always a boolean, never None/undefined
        final_story_completed = bool(story_completed) if story_completed is not None else False
        final_project_id = str(project_id) if project_id else None
        
        print(f"📤 [COMPLETION] Returning story_completed={final_story_completed} (type: {type(final_story_completed).__name__}) for session {session_id}, project {final_project_id}")
        print(f"📤 [COMPLETION] Response will include: success=True, session_id={session_id}, messages_count={len(messages_result.data) if messages_result.data else 0}, is_authenticated={bool(user_id)}, story_completed={final_story_completed}, project_id={final_project_id}")
        
        response = {
            "success": True,
            "session_id": session_id,
            "messages": messages_result.data or [],
            "is_authenticated": bool(user_id),
            "story_completed": final_story_completed,  # Always a boolean, never None
            "project_id": final_project_id
        }
        
        print(f"📤 [COMPLETION] Final response keys: {list(response.keys())}")
        print(f"📤 [COMPLETION] Final response story_completed value: {response.get('story_completed')} (type: {type(response.get('story_completed')).__name__})")
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting session messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/message-count")
async def get_session_message_count(
    session_id: str,
    user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Get the exact message count for a session without fetching all messages"""
    try:
        supabase = get_supabase_client()
        
        # Verify session exists and user has access
        session_result = supabase.table("sessions").select("*").eq("session_id", session_id).execute()
        if not session_result.data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = session_result.data[0]
        
        if user_id and session["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get message count efficiently by selecting only message_id with a high limit
        # This is more efficient than fetching all message content
        messages_result = supabase.table("chat_messages")\
            .select("message_id")\
            .eq("session_id", session_id)\
            .limit(10000)\
            .execute()
        
        # Count the results (up to 10000 limit)
        message_count = len(messages_result.data) if messages_result.data else 0
        
        print(f"📊 Message count for session {session_id}: {message_count}")
        
        return {
            "success": True,
            "session_id": session_id,
            "message_count": message_count
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting session message count: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all its messages"""
    try:
        print(f"🔍 Delete session API called - session_id: {session_id}")
        supabase = get_supabase_client()
        
        # Delete all messages for this session first
        supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
        
        # Delete the session
        result = supabase.table("sessions").delete().eq("session_id", session_id).execute()
        
        print(f"✅ Deleted session {session_id}")
        return {"success": True, "message": "Session deleted successfully"}
    except Exception as e:
        print(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions")
async def delete_all_sessions(
    user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Delete all sessions for a user"""
    try:
        print(f"🔍 Delete all sessions API called - user_id: {user_id}")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID required")
        
        supabase = get_supabase_client()
        
        # Get all sessions for the user
        sessions_result = supabase.table("sessions").select("session_id").eq("user_id", user_id).execute()
        
        if not sessions_result.data:
            return {"success": True, "message": "No sessions to delete", "deleted_count": 0}
        
        session_ids = [session["session_id"] for session in sessions_result.data]
        print(f"🔍 Found {len(session_ids)} sessions to delete for user {user_id}")
        
        # Delete all messages for these sessions
        for session_id in session_ids:
            supabase.table("chat_messages").delete().eq("session_id", session_id).execute()
        
        # Delete all sessions for the user
        result = supabase.table("sessions").delete().eq("user_id", user_id).execute()
        
        deleted_count = len(session_ids)
        print(f"✅ Deleted {deleted_count} sessions for user {user_id}")
        
        return {
            "success": True, 
            "message": f"Deleted {deleted_count} sessions successfully",
            "deleted_count": deleted_count
        }
    except Exception as e:
        print(f"Error deleting all sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

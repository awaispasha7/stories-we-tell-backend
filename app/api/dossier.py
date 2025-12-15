"""
Dossier API
Handles user dossier/project management
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from ..models import Dossier, DossierCreate, DossierUpdate
from ..database.session_service_supabase import session_service

router = APIRouter()

def get_user_id_only(x_user_id: Optional[str] = Header(None, alias="X-User-ID")) -> UUID:
    """Get user ID from header, with fallback to default user"""
    if x_user_id:
        try:
            return UUID(x_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    # Fallback to default user - use a hardcoded user ID for now
    # This should be the same user ID that's being used in the frontend
    return UUID("6b7088ad-e032-44ac-8561-11a9abd80000")

async def get_or_create_default_user() -> UUID:
    """Get the first available user or create a default one"""
    try:
        # Try to get the first user from the database
        users = session_service.get_all_users()
        if users and len(users) > 0:
            user_id = users[0].user_id
            print(f"✅ Using existing user: {user_id}")
            return user_id
    except Exception as e:
        print(f"⚠️ Could not fetch users: {e}")
    
    # If no users exist, create a default one
    try:
        user_data = {
            "email": "default@example.com",
            "display_name": "Default User"
        }
        user = session_service.create_user(user_data)
        print(f"✅ Created default user: {user.user_id}")
        return user.user_id
    except Exception as e:
        print(f"❌ Failed to create default user: {e}")
        raise HTTPException(status_code=500, detail="No users available and cannot create default user")

def get_current_user_id(x_user_id: Optional[str] = Header(None, alias="X-User-ID")) -> UUID:
    """Get current user ID from header"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="User authentication required")
    
    try:
        return UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

@router.get("/dossiers", response_model=List[Dossier])
async def get_user_dossiers(user_id: UUID = Depends(get_user_id_only)):
    """Get all dossiers for the current user"""
    # Use the existing user from your database (Awais Pasha)
    print(f"✅ Using user: {user_id}")
    
    try:
        dossiers = session_service.get_user_dossiers(user_id)
        return dossiers
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dossiers: {str(e)}")

@router.get("/dossiers/{project_id}", response_model=Dossier)
async def get_dossier(
    project_id: UUID, 
    user_id: UUID = Depends(get_user_id_only)
):
    """Get a specific dossier for the current user"""
    print(f"🔍 [DOSSIER] get_dossier called - project_id: {project_id}, user_id: {user_id}")
    try:
        dossier = session_service.get_dossier(project_id, user_id)
        print(f"🔍 [DOSSIER] Result from session_service.get_dossier: {dossier}")
        if not dossier:
            print(f"❌ [DOSSIER] Dossier not found for project_id: {project_id}, user_id: {user_id}")
            raise HTTPException(status_code=404, detail="Dossier not found")
        print(f"✅ [DOSSIER] Returning dossier: {dossier.project_id if hasattr(dossier, 'project_id') else 'unknown'}")
        return dossier
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [DOSSIER] Exception in get_dossier: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch dossier: {str(e)}")

@router.post("/dossiers", response_model=Dossier)
async def create_dossier(
    dossier_data: DossierCreate,
    user_id: UUID = Depends(get_user_id_only)
):
    """Create a new dossier for the current user"""
    try:
        # Ensure the user_id matches the authenticated user
        dossier_data.user_id = user_id
        
        dossier = session_service.create_dossier(dossier_data)
        return dossier
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create dossier: {str(e)}")

@router.put("/dossiers/{project_id}", response_model=Dossier)
async def update_dossier(
    project_id: UUID,
    dossier_data: DossierUpdate,
    user_id: UUID = Depends(get_user_id_only)
):
    """Update a dossier for the current user"""
    try:
        dossier = session_service.update_dossier(project_id, user_id, dossier_data)
        if not dossier:
            raise HTTPException(status_code=404, detail="Dossier not found")
        return dossier
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update dossier: {str(e)}")

@router.delete("/dossiers/{project_id}")
async def delete_dossier(
    project_id: UUID,
    user_id: UUID = Depends(get_user_id_only)
):
    """Delete a dossier for the current user"""
    try:
        success = session_service.delete_dossier(project_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Dossier not found")
        return {"message": "Dossier deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete dossier: {str(e)}")

@router.post("/dossiers/{project_id}/initialize")
async def initialize_dossier(
    project_id: UUID,
    user_id: UUID = Depends(get_user_id_only)
):
    """Initialize a new dossier with default structure"""
    try:
        # Check if dossier already exists
        existing_dossier = session_service.get_dossier(project_id, user_id)
        if existing_dossier:
            return existing_dossier
        
        # Create new dossier with enhanced default structure
        from datetime import datetime, timezone
        current_time = datetime.now(timezone.utc).isoformat()
        
        dossier_data = DossierCreate(
            project_id=project_id,
            user_id=user_id,
            snapshot_json={
                "title": "New Project",
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
                "created_at": current_time
            }
        )
        
        dossier = session_service.create_dossier(dossier_data)
        return dossier
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize dossier: {str(e)}")

@router.post("/dossiers/{project_id}/dev/refresh")
async def refresh_dossier_dev(
    project_id: UUID,
    user_id: UUID = Depends(get_current_user_id)
):
    """
    DEV ENDPOINT: Manually refresh/update dossier by re-extracting from entire conversation history.
    
    This endpoint:
    1. Loads ALL messages from ALL sessions in the project
    2. Calls dossier extractor to extract metadata
    3. Updates the dossier with the extracted metadata
    
    Useful for testing dossier extraction updates or refreshing existing dossiers.
    """
    try:
        # Import necessary functions and services
        from .simple_chat import _get_project_conversation_history
        from ..ai.dossier_extractor import dossier_extractor
        
        print(f"🔄 [DEV] Refreshing dossier for project_id: {project_id}, user_id: {user_id}")
        
        # Step 1: Get all conversation history from all sessions in the project
        print(f"📚 [DEV] Loading conversation history for project {project_id}...")
        conversation_history = await _get_project_conversation_history(
            str(project_id), 
            str(user_id), 
            limit=None  # Get ALL messages
        )
        
        if not conversation_history or len(conversation_history) < 2:
            raise HTTPException(
                status_code=400, 
                detail=f"Not enough conversation history to extract dossier. Found {len(conversation_history) if conversation_history else 0} messages. Need at least 2 messages."
            )
        
        print(f"📚 [DEV] Loaded {len(conversation_history)} messages from project {project_id}")
        
        # Step 2: Extract metadata using dossier extractor
        print(f"🔍 [DEV] Extracting metadata from conversation history...")
        extracted_metadata = await dossier_extractor.extract_metadata(conversation_history)
        
        if not extracted_metadata:
            raise HTTPException(
                status_code=500,
                detail="Failed to extract metadata from conversation history"
            )
        
        print(f"✅ [DEV] Extracted metadata: {len(extracted_metadata.get('characters', []))} characters, {len(extracted_metadata.get('heroes', []))} heroes, {len(extracted_metadata.get('scenes', []))} scenes")
        
        # Step 3: Get existing dossier to merge with (preserve existing data where appropriate)
        existing_dossier = session_service.get_dossier(project_id, user_id)
        existing_snapshot = existing_dossier.snapshot_json if existing_dossier else {}
        
        # Step 4: Merge extracted metadata with existing dossier
        # Preserve title and logline if they exist and are meaningful
        final_metadata = extracted_metadata.copy()
        
        # Merge characters, heroes, and supporting_characters (deduplicate by name)
        if existing_snapshot:
            # Merge legacy characters
            existing_characters = existing_snapshot.get('characters', []) or []
            extracted_characters = extracted_metadata.get('characters', []) or []
            
            by_name = {}
            for char in existing_characters + extracted_characters:
                key = (char.get('name') or '').strip().lower()
                if key and key != 'unknown':
                    if key not in by_name:
                        by_name[key] = char
                    else:
                        # Merge: prefer non-empty values from extracted
                        merged = {**by_name[key], **{k: v for k, v in char.items() if v}}
                        by_name[key] = merged
            
            # Merge heroes
            existing_heroes = existing_snapshot.get('heroes', []) or []
            extracted_heroes = extracted_metadata.get('heroes', []) or []
            
            heroes_by_name = {}
            for hero in existing_heroes + extracted_heroes:
                key = (hero.get('name') or '').strip().lower()
                if key and key != 'unknown':
                    if key not in heroes_by_name:
                        heroes_by_name[key] = hero
                    else:
                        # Merge: prefer non-empty values from extracted
                        merged = {**heroes_by_name[key], **{k: v for k, v in hero.items() if v}}
                        heroes_by_name[key] = merged
            
            # Merge supporting characters
            existing_supporting = existing_snapshot.get('supporting_characters', []) or []
            extracted_supporting = extracted_metadata.get('supporting_characters', []) or []
            
            supporting_by_name = {}
            for s in existing_supporting + extracted_supporting:
                key = (s.get('name') or '').strip().lower()
                if key and key != 'unknown':
                    if key not in supporting_by_name:
                        supporting_by_name[key] = s
                    else:
                        # Merge: prefer non-empty values from extracted
                        merged = {**supporting_by_name[key], **{k: v for k, v in s.items() if v}}
                        supporting_by_name[key] = merged
            
            final_metadata['characters'] = list(by_name.values())
            final_metadata['heroes'] = list(heroes_by_name.values())
            final_metadata['supporting_characters'] = list(supporting_by_name.values())
            
            # Preserve title and logline if they exist and extracted ones are empty
            if existing_snapshot.get('title') and not final_metadata.get('title'):
                final_metadata['title'] = existing_snapshot.get('title')
            if existing_snapshot.get('logline') and not final_metadata.get('logline'):
                final_metadata['logline'] = existing_snapshot.get('logline')
        
        # Step 5: Update dossier
        print(f"💾 [DEV] Updating dossier with extracted metadata...")
        dossier_update = DossierUpdate(snapshot_json=final_metadata)
        updated_dossier = session_service.update_dossier(
            project_id,
            user_id,
            dossier_update
        )
        
        if not updated_dossier:
            raise HTTPException(
                status_code=500,
                detail="Failed to update dossier"
            )
        
        print(f"✅ [DEV] Dossier refreshed successfully for project {project_id}")
        
        return {
            "success": True,
            "message": f"Dossier refreshed successfully. Extracted {len(conversation_history)} messages.",
            "dossier": updated_dossier,
            "extraction_stats": {
                "total_messages": len(conversation_history),
                "characters": len(final_metadata.get('characters', [])),
                "heroes": len(final_metadata.get('heroes', [])),
                "supporting_characters": len(final_metadata.get('supporting_characters', [])),
                "scenes": len(final_metadata.get('scenes', [])),
                "has_story_type": bool(final_metadata.get('story_type')),
                "has_perspective": bool(final_metadata.get('perspective')),
                "has_audience": bool(final_metadata.get('audience'))
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ [DEV] Error refreshing dossier: {e}")
        print(f"❌ [DEV] Traceback: {error_trace}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to refresh dossier: {str(e)}"
        )

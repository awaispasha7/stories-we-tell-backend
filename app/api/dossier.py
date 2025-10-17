"""
Dossier API
Handles user dossier/project management
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List
from uuid import UUID, uuid4

from ..models import Dossier, DossierCreate, DossierUpdate
from ..database.session_service_supabase import session_service

router = APIRouter()

def get_current_user_id(x_user_id: Optional[str] = Header(None)) -> UUID:
    """Get current user ID from header (temporary implementation)"""
    if not x_user_id:
        # Default to demo user for now
        return UUID("550e8400-e29b-41d4-a716-446655440000")
    
    try:
        return UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

@router.get("/dossiers", response_model=List[Dossier])
async def get_user_dossiers(user_id: UUID = Depends(get_current_user_id)):
    """Get all dossiers for the current user"""
    try:
        dossiers = session_service.get_user_dossiers(user_id)
        return dossiers
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dossiers: {str(e)}")

@router.get("/dossiers/{project_id}", response_model=Dossier)
async def get_dossier(
    project_id: UUID, 
    user_id: UUID = Depends(get_current_user_id)
):
    """Get a specific dossier for the current user"""
    try:
        dossier = session_service.get_dossier(project_id, user_id)
        if not dossier:
            raise HTTPException(status_code=404, detail="Dossier not found")
        return dossier
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dossier: {str(e)}")

@router.post("/dossiers", response_model=Dossier)
async def create_dossier(
    dossier_data: DossierCreate,
    user_id: UUID = Depends(get_current_user_id)
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
    user_id: UUID = Depends(get_current_user_id)
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
    user_id: UUID = Depends(get_current_user_id)
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
    user_id: UUID = Depends(get_current_user_id)
):
    """Initialize a new dossier with default structure"""
    try:
        # Check if dossier already exists
        existing_dossier = session_service.get_dossier(project_id, user_id)
        if existing_dossier:
            return existing_dossier
        
        # Create new dossier with default structure
        dossier_data = DossierCreate(
            project_id=project_id,
            user_id=user_id,
            snapshot_json={
                "title": "New Project",
                "logline": "",
                "genre": "",
                "tone": "",
                "characters": [],
                "scenes": [],
                "created_at": "2025-01-17T00:00:00Z"
            }
        )
        
        dossier = session_service.create_dossier(dossier_data)
        return dossier
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize dossier: {str(e)}")

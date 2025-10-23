"""
Simplified User Management API
Clean user management using the simplified session manager
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional, Dict, Any
from uuid import UUID

from ..database.supabase import get_supabase_client

router = APIRouter()

@router.post("/users")
async def create_user(user_data: Dict[str, Any]):
    """Create a new user"""
    try:
        supabase = get_supabase_client()
        
        # Check if user already exists
        if user_data.get("email"):
            existing_user = supabase.table("users").select("*").eq("email", user_data["email"]).execute()
            if existing_user.data:
                return {
                    "message": "User already exists",
                    "user": existing_user.data[0]
                }
        
        # Create user
        result = supabase.table("users").insert(user_data).execute()
        
        if result.data:
            return {
                "success": True,
                "user": result.data[0]
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create user")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/me")
async def get_current_user(user_id: Optional[str] = Header(None, alias="X-User-ID")):
    """Get current user information"""
    try:
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID required")
        
        supabase = get_supabase_client()
        result = supabase.table("users").select("*").eq("user_id", user_id).execute()
        
        if result.data:
            return {
                "success": True,
                "user": result.data[0]
            }
        else:
            raise HTTPException(status_code=404, detail="User not found")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

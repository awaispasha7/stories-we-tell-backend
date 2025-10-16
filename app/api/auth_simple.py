"""
Simple authentication API endpoints for testing CORS
"""

from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class SignupRequest(BaseModel):
    email: str
    display_name: str
    password: str

@router.post("/signup")
async def signup(request: SignupRequest):
    """Simple signup endpoint for testing"""
    return {
        "message": "Signup endpoint working",
        "status": "success",
        "user": {
            "email": request.email,
            "display_name": request.display_name,
            "user_id": "test-user-id"
        },
        "access_token": "test-token",
        "token_type": "bearer",
        "timestamp": datetime.now().isoformat()
    }

@router.post("/login")
async def login(request: SignupRequest):
    """Simple login endpoint for testing"""
    return {
        "message": "Login endpoint working",
        "status": "success",
        "user": {
            "email": request.email,
            "display_name": request.display_name,
            "user_id": "test-user-id"
        },
        "access_token": "test-token",
        "token_type": "bearer",
        "timestamp": datetime.now().isoformat()
    }

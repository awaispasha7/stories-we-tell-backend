"""
Developer Test Endpoints
Convenient endpoints for testing functionality during development
"""

from fastapi import APIRouter, HTTPException, Body, Header
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel

from ..services.email_service import email_service
from ..database.session_service_supabase import session_service

router = APIRouter(prefix="/dev", tags=["dev"])


class TestEmailRequest(BaseModel):
    """Request model for testing email sending"""
    project_id: Optional[str] = None  # If provided, uses real dossier data
    user_email: str  # Email address to send test email to
    user_name: Optional[str] = "Test User"  # Optional user name
    story_data: Optional[Dict[str, Any]] = None  # Optional: override story data
    generated_script: Optional[str] = None  # Optional: override script (not used in client email anymore)


@router.post("/test-email")
async def test_story_captured_email(
    request: TestEmailRequest = Body(...),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    DEV ENDPOINT: Test the story captured email without going through full chat flow.
    
    This endpoint allows you to:
    1. Test email with real project data (provide project_id)
    2. Test email with custom data (provide story_data)
    3. Send to any email address for testing
    
    Usage examples:
    
    # Test with real project data:
    POST /api/v1/dev/test-email
    {
        "project_id": "37818fad-7260-437b-af74-71cf81fbe7fc",
        "user_email": "your-test@email.com",
        "user_name": "Test User"
    }
    
    # Test with custom data:
    POST /api/v1/dev/test-email
    {
        "user_email": "your-test@email.com",
        "user_name": "John Doe",
        "story_data": {
            "title": "My Test Story",
            "heroes": [{"name": "Alice", "age_at_story": 25}],
            "supporting_characters": [{"name": "Bob", "role": "friend"}]
        }
    }
    """
    try:
        # Get user_id (required for dossier lookup)
        user_id = None
        if x_user_id:
            try:
                user_id = UUID(x_user_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid user_id format")
        elif request.project_id:
            # If project_id provided but no user_id, try to get from dossier
            try:
                dossier = session_service.get_dossier(UUID(request.project_id), UUID("00000000-0000-0000-0000-000000000000"))
                if dossier:
                    # Use a default user_id if we can't determine it
                    user_id = UUID("00000000-0000-0000-0000-000000000000")
            except Exception:
                pass
        
        if not user_id:
            user_id = UUID("00000000-0000-0000-0000-000000000000")
        
        # Get story data
        story_data = request.story_data
        if request.project_id and not story_data:
            # Fetch real dossier data
            try:
                dossier = session_service.get_dossier(UUID(request.project_id), user_id)
                if dossier and dossier.snapshot_json:
                    story_data = dossier.snapshot_json
                    print(f"✅ Using real dossier data for project {request.project_id}")
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Dossier not found for project {request.project_id}"
                    )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid project_id format")
        elif not story_data:
            # Use default test data
            story_data = {
                "title": "Test Story",
                "logline": "This is a test story for email testing",
                "genre": "",
                "tone": "",
                "heroes": [
                    {
                        "name": "Test Hero",
                        "age_at_story": 25,
                        "relationship_to_user": "fictional character",
                        "physical_descriptors": "Test description",
                        "personality_traits": "Test traits"
                    }
                ],
                "supporting_characters": [],
                "story_location": "Test Location",
                "story_timeframe": "2024",
                "story_type": "other"
            }
            print("ℹ️ Using default test data")
        
        # Use provided script or empty string (not used in client email anymore)
        generated_script = request.generated_script or "Test script content (not shown in client email)"
        
        # Send test email
        print(f"📧 [DEV] Sending test email to {request.user_email}")
        success = await email_service.send_story_captured_email(
            user_email=request.user_email,
            user_name=request.user_name or "Test User",
            story_data=story_data,
            generated_script=generated_script,
            project_id=request.project_id or str(UUID("00000000-0000-0000-0000-000000000000")),
            client_emails=None
        )
        
        if success:
            return {
                "success": True,
                "message": f"Test email sent successfully to {request.user_email}",
                "email": request.user_email,
                "project_id": request.project_id,
                "used_real_data": bool(request.project_id and not request.story_data)
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send test email. Check email service configuration."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ [DEV] Error sending test email: {e}")
        print(f"❌ [DEV] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send test email: {str(e)}"
        )


@router.get("/test-email/health")
async def test_email_health():
    """
    DEV ENDPOINT: Check if email service is configured and available
    """
    return {
        "email_service_available": email_service.available,
        "email_provider": email_service.provider,
        "frontend_url": email_service.frontend_url,
        "smtp_configured": bool(email_service.smtp_user and email_service.smtp_password),
        "message": "Email service health check"
    }


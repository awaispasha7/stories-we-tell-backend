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
    frontend_url: Optional[str] = None  # Optional: override frontend URL for testing (defaults to FRONTEND_URL env var)


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
    
    # Test with production URL override:
    POST /api/v1/dev/test-email
    {
        "project_id": "37818fad-7260-437b-af74-71cf81fbe7fc",
        "user_email": "your-test@email.com",
        "frontend_url": "https://stories-we-tell.vercel.app"
    }
    
    Note: The frontend_url defaults to the FRONTEND_URL environment variable.
    Set FRONTEND_URL in your .env file or environment to configure the default.
    """
    try:
        # Get user_id (required for dossier lookup)
        user_id = None
        if x_user_id:
            try:
                user_id = UUID(x_user_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid user_id format")
        
        # Get story data
        story_data = request.story_data
        if request.project_id and not story_data:
            # Fetch real dossier data - need to find user_id from project first
            try:
                project_id_uuid = UUID(request.project_id)
                
                # If user_id not provided, try to get it from the dossier table
                if not user_id:
                    from ..database.supabase import get_supabase
                    supabase = get_supabase()
                    # Projects are stored in the dossier table
                    dossier_result = supabase.table("dossier").select("user_id").eq("project_id", str(project_id_uuid)).limit(1).execute()
                    
                    if dossier_result.data and len(dossier_result.data) > 0:
                        user_id = UUID(dossier_result.data[0]["user_id"])
                        print(f"✅ Found user_id {user_id} from dossier for project {request.project_id}")
                    else:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Project {request.project_id} not found in dossier. Please provide user_id in X-User-ID header, or make sure the project exists."
                        )
                
                # Now fetch dossier with both project_id and user_id
                dossier = session_service.get_dossier(project_id_uuid, user_id)
                if dossier and dossier.snapshot_json:
                    story_data = dossier.snapshot_json
                    print(f"✅ Using real dossier data for project {request.project_id}, user {user_id}")
                    print(f"📋 Story title: {story_data.get('title', 'Untitled')}")
                    print(f"📋 Heroes: {len(story_data.get('heroes', []))}")
                    print(f"📋 Supporting characters: {len(story_data.get('supporting_characters', []))}")
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Dossier not found for project {request.project_id} and user {user_id}. Make sure the story has been completed in the chat."
                    )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid project_id format: {str(e)}")
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
        
        # Override frontend_url if provided (for testing different environments)
        original_frontend_url = email_service.frontend_url
        if request.frontend_url:
            email_service.frontend_url = request.frontend_url
            print(f"🔧 [DEV] Overriding frontend_url to: {request.frontend_url}")
        
        try:
            # Send test email
            print(f"📧 [DEV] Sending test email to {request.user_email}")
            print(f"🌐 [DEV] Using frontend_url: {email_service.frontend_url}")
            success = await email_service.send_story_captured_email(
                user_email=request.user_email,
                user_name=request.user_name or "Test User",
                story_data=story_data,
                generated_script=generated_script,
                project_id=request.project_id or str(UUID("00000000-0000-0000-0000-000000000000")),
                client_emails=None
            )
        finally:
            # Restore original frontend_url
            if request.frontend_url:
                email_service.frontend_url = original_frontend_url
        
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
    
    Shows current configuration including frontend_url.
    The frontend_url is read from FRONTEND_URL environment variable.
    """
    import os
    return {
        "email_service_available": email_service.available,
        "email_provider": email_service.provider,
        "frontend_url": email_service.frontend_url,
        "frontend_url_env": os.getenv("FRONTEND_URL", "Not set (using default: https://stories-we-tell.vercel.app)"),
        "smtp_configured": bool(email_service.smtp_user and email_service.smtp_password),
        "message": "Email service health check",
        "note": "Set FRONTEND_URL environment variable to configure the frontend URL for email links. You can also override it per-request using the frontend_url field in the test-email endpoint."
    }


@router.get("/projects/{project_id}/dossier")
async def get_project_dossier(
    project_id: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    DEV ENDPOINT: Get dossier data for a project (useful for debugging)
    
    This helps you see what story data is stored for a project before testing the email.
    """
    try:
        project_id_uuid = UUID(project_id)
        
        # Get user_id
        user_id = None
        if x_user_id:
            try:
                user_id = UUID(x_user_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid user_id format")
        else:
            # Try to get user_id from dossier table (projects are stored as dossiers)
            from ..database.supabase import get_supabase
            supabase = get_supabase()
            dossier_result = supabase.table("dossier").select("user_id").eq("project_id", str(project_id_uuid)).limit(1).execute()
            
            if dossier_result.data and len(dossier_result.data) > 0:
                user_id = UUID(dossier_result.data[0]["user_id"])
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Project {project_id} not found in dossier. Please provide user_id in X-User-ID header."
                )
        
        # Get dossier
        dossier = session_service.get_dossier(project_id_uuid, user_id)
        if not dossier:
            raise HTTPException(
                status_code=404,
                detail=f"Dossier not found for project {project_id} and user {user_id}"
            )
        
        return {
            "project_id": str(dossier.project_id),
            "user_id": str(dossier.user_id),
            "title": dossier.title,
            "snapshot_json": dossier.snapshot_json,
            "created_at": dossier.created_at.isoformat() if dossier.created_at else None,
            "updated_at": dossier.updated_at.isoformat() if dossier.updated_at else None
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid project_id format: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ [DEV] Error getting dossier: {e}")
        print(f"❌ [DEV] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get dossier: {str(e)}"
        )


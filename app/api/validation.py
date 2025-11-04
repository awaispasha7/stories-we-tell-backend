"""
Validation API endpoints for Stories We Tell
Handles validation queue management for admin interface
"""

from fastapi import APIRouter, HTTPException, Query, Header, Body
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel
from ..services.validation_service import validation_service
from ..services.email_service import EmailService

router = APIRouter()


class ValidationApprovalRequest(BaseModel):
    reviewed_by: str
    review_notes: Optional[str] = None


class ValidationRejectionRequest(BaseModel):
    reviewed_by: str
    review_notes: str


class ValidationUpdateRequest(BaseModel):
    reviewed_by: str
    review_notes: Optional[str] = None
    updated_script: Optional[str] = None


@router.get("/validation/queue")
async def get_validation_queue(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: Optional[int] = Query(50, description="Limit results"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
) -> List[Dict[str, Any]]:
    """Get validation queue items, optionally filtered by status."""
    try:
        # Get validations based on status filter
        if status and status != "all":
            # Filter by specific status
            validations = await validation_service.get_validations_by_status(status)
        else:
            # Get all validations (not just pending) when status is "all" or not provided
            validations = await validation_service.get_pending_validations()  # This method actually returns ALL validations
        
        # Apply limit
        if limit and len(validations) > limit:
            validations = validations[:limit]
        
        print(f"📊 [API] Returning {len(validations)} validations (status filter: {status or 'all'})")
        
        # Return list directly (frontend expects array)
        return validations
        
    except Exception as e:
        print(f"❌ Error fetching validation queue: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch validation queue: {str(e)}")


@router.get("/validation/stats")
async def get_validation_stats() -> Dict[str, Any]:
    """Get validation queue statistics."""
    try:
        print(f"📊 [STATS API] Fetching validation stats...")
        stats = await validation_service.get_validation_stats()
        print(f"📊 [STATS API] Stats retrieved: {stats}")
        
        # Return stats directly (frontend expects the stats object)
        return stats
        
    except Exception as e:
        print(f"❌ [STATS API] Error fetching validation stats: {e}")
        import traceback
        print(f"❌ [STATS API] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch validation stats: {str(e)}")


@router.get("/validation/{validation_id}")
async def get_validation_request(validation_id: str) -> Dict[str, Any]:
    """Get a specific validation request by ID."""
    try:
        validation = await validation_service.get_validation_by_id(UUID(validation_id))
        
        if not validation:
            raise HTTPException(status_code=404, detail="Validation request not found")
        
        return {
            "success": True,
            "validation": validation
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid validation ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch validation request: {str(e)}")


@router.get("/validation/queue/{validation_id}")
async def get_validation_request_by_queue(validation_id: str) -> Dict[str, Any]:
    """Get a specific validation request by ID (frontend route)."""
    try:
        validation = await validation_service.get_validation_by_id(UUID(validation_id))
        
        if not validation:
            raise HTTPException(status_code=404, detail="Validation request not found")
        
        # Return directly as ValidationRequest (frontend expects this format)
        return validation
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid validation ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch validation request: {str(e)}")


@router.post("/validation/queue/{validation_id}/approve")
async def approve_validation_by_queue(
    validation_id: str,
    request: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """Approve a validation request (frontend route)."""
    try:
        # Extract reviewed_by from request or use default
        reviewed_by = request.get("reviewed_by", "admin")
        review_notes = request.get("notes") or request.get("review_notes")
        
        # Approve the validation
        validation = await validation_service.approve_and_send(
            validation_id=UUID(validation_id),
            reviewed_by=reviewed_by,
            review_notes=review_notes
        )
        
        if not validation:
            raise HTTPException(status_code=404, detail="Validation request not found")
        
        # Send to client using existing email service
        email_service = EmailService()
        if email_service.available and validation.get('client_email'):
            try:
                # Get dossier data for the project
                from ..database.session_service_supabase import session_service
                dossier = session_service.get_dossier(
                    UUID(validation['project_id']), 
                    UUID(validation['user_id'])
                )
                dossier_data = dossier.snapshot_json if dossier else {}
                
                success = await email_service.send_story_captured_email(
                    user_email=validation['client_email'],
                    user_name=validation['client_name'] or "Writer",
                    story_data=dossier_data,
                    generated_script=validation['generated_script'],
                    project_id=validation['project_id'],
                    client_emails=None
                )
                
                if success:
                    # Mark as sent to client
                    await validation_service.mark_sent_to_client(UUID(validation_id))
                    
                    return {
                        "success": True,
                        "message": "Validation approved and sent to client"
                    }
                else:
                    return {
                        "success": True,
                        "message": "Validation approved but email failed to send"
                    }
                    
            except Exception as e:
                print(f"❌ Error sending client email: {e}")
                return {
                    "success": True,
                    "message": "Validation approved but email failed to send"
                }
        else:
            return {
                "success": True,
                "message": "Validation approved (no client email to send)"
            }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid validation ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve validation: {str(e)}")


@router.post("/validation/{validation_id}/approve")
async def approve_validation(
    validation_id: str,
    request: ValidationApprovalRequest
) -> Dict[str, Any]:
    """Approve a validation request and send to client."""
    try:
        # Approve the validation
        validation = await validation_service.approve_and_send(
            validation_id=UUID(validation_id),
            reviewed_by=request.reviewed_by,
            review_notes=request.review_notes
        )
        
        if not validation:
            raise HTTPException(status_code=404, detail="Validation request not found")
        
        # Send to client using existing email service
        email_service = EmailService()
        if email_service.available and validation.get('client_email'):
            try:
                # Get dossier data for the project
                from ..database.session_service_supabase import session_service
                dossier = session_service.get_dossier(
                    UUID(validation['project_id']), 
                    UUID(validation['user_id'])
                )
                dossier_data = dossier.snapshot_json if dossier else {}
                
                success = await email_service.send_story_captured_email(
                    user_email=validation['client_email'],
                    user_name=validation['client_name'] or "Writer",
                    story_data=dossier_data,
                    generated_script=validation['generated_script'],
                    project_id=validation['project_id'],
                    client_emails=None
                )
                
                if success:
                    # Mark as sent to client
                    await validation_service.mark_sent_to_client(UUID(validation_id))
                    
                    return {
                        "success": True,
                        "message": "Validation approved and sent to client",
                        "validation": validation
                    }
                else:
                    return {
                        "success": True,
                        "message": "Validation approved but email failed to send",
                        "validation": validation,
                        "email_sent": False
                    }
                    
            except Exception as e:
                print(f"❌ Error sending client email: {e}")
                return {
                    "success": True,
                    "message": "Validation approved but email failed to send",
                    "validation": validation,
                    "email_error": str(e)
                }
        else:
            return {
                "success": True,
                "message": "Validation approved (no client email to send)",
                "validation": validation
            }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid validation ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve validation: {str(e)}")


@router.post("/validation/queue/{validation_id}/reject")
async def reject_validation_by_queue(
    validation_id: str,
    request: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """Reject a validation request (frontend route)."""
    try:
        # Extract notes from request
        notes = request.get("notes", "")
        if not notes:
            raise HTTPException(status_code=400, detail="Rejection notes are required")
        
        reviewed_by = request.get("reviewed_by", "admin")
        
        success = await validation_service.reject_validation(
            validation_id=UUID(validation_id),
            reviewed_by=reviewed_by,
            review_notes=notes
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Validation request not found")
        
        return {
            "success": True,
            "message": "Validation rejected"
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid validation ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reject validation: {str(e)}")


@router.post("/validation/{validation_id}/reject")
async def reject_validation(
    validation_id: str,
    request: ValidationRejectionRequest
) -> Dict[str, Any]:
    """Reject a validation request with notes."""
    try:
        success = await validation_service.reject_validation(
            validation_id=UUID(validation_id),
            reviewed_by=request.reviewed_by,
            review_notes=request.review_notes
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Validation request not found")
        
        return {
            "success": True,
            "message": "Validation rejected"
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid validation ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reject validation: {str(e)}")


@router.put("/validation/{validation_id}")
async def update_validation(
    validation_id: str,
    request: ValidationUpdateRequest
) -> Dict[str, Any]:
    """Update validation request (e.g., edit script)."""
    try:
        # Keep status as pending when script is updated (removed in_review status)
        success = await validation_service.update_validation_status(
            validation_id=UUID(validation_id),
            status='pending',  # Keep as pending - admin can view by opening
            reviewed_by=request.reviewed_by,
            review_notes=request.review_notes,
            updated_script=request.updated_script
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Validation request not found")
        
        # Get updated validation
        validation = await validation_service.get_validation_by_id(UUID(validation_id))
        
        return {
            "success": True,
            "message": "Validation updated",
            "validation": validation
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid validation ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update validation: {str(e)}")


class ScriptUpdateRequest(BaseModel):
    generated_script: str


@router.put("/validation/queue/{validation_id}/script")
async def update_validation_script(
    validation_id: str,
    request: ScriptUpdateRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
) -> Dict[str, Any]:
    """Update the generated script for a validation request (frontend route)."""
    try:
        # Update script using validation service
        success = await validation_service.update_validation_status(
            validation_id=UUID(validation_id),
            status='pending',  # Keep as pending - admin can view by opening (removed in_review status)
            reviewed_by=x_user_id or "admin",
            review_notes="Script updated",
            updated_script=request.generated_script
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Validation request not found")
        
        return {
            "success": True,
            "message": "Script updated successfully"
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid validation ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update script: {str(e)}")


@router.get("/validation/stats")
async def get_validation_stats() -> Dict[str, Any]:
    """Get validation queue statistics."""
    try:
        print(f"📊 [STATS API] Fetching validation stats...")
        stats = await validation_service.get_validation_stats()
        print(f"📊 [STATS API] Stats retrieved: {stats}")
        
        # Return stats directly (frontend expects the stats object)
        return stats
        
    except Exception as e:
        print(f"❌ [STATS API] Error fetching validation stats: {e}")
        import traceback
        print(f"❌ [STATS API] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch validation stats: {str(e)}")

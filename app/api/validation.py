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
        
        # Fetch dossier data for each validation
        from ..database.session_service_supabase import session_service
        validations_with_dossier = []
        for validation in validations:
            dossier_data = None
            try:
                dossier = session_service.get_dossier(
                    UUID(validation['project_id']),
                    UUID(validation['user_id'])
                )
                if dossier:
                    dossier_data = dossier.snapshot_json
            except Exception as dossier_error:
                print(f"⚠️ [VALIDATION] Could not fetch dossier data for project {validation.get('project_id')}: {dossier_error}")
                dossier_data = None
            
            validation_with_dossier = {**validation}
            if dossier_data:
                validation_with_dossier['dossier_data'] = dossier_data
            
            validations_with_dossier.append(validation_with_dossier)
        
        print(f"📊 [API] Returning {len(validations_with_dossier)} validations with dossier data (status filter: {status or 'all'})")
        
        # Return list directly (frontend expects array)
        return validations_with_dossier
        
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
    """Get a specific validation request by ID (frontend route) with dossier data."""
    try:
        validation = await validation_service.get_validation_by_id(UUID(validation_id))
        
        if not validation:
            raise HTTPException(status_code=404, detail="Validation request not found")
        
        # Fetch dossier data for review
        dossier_data = None
        try:
            from ..database.session_service_supabase import session_service
            dossier = session_service.get_dossier(
                UUID(validation['project_id']),
                UUID(validation['user_id'])
            )
            if dossier:
                dossier_data = dossier.snapshot_json
                print(f"📋 [VALIDATION] Fetched dossier data for project {validation['project_id']}")
        except Exception as dossier_error:
            print(f"⚠️ [VALIDATION] Could not fetch dossier data: {dossier_error}")
            dossier_data = None
        
        # Add dossier data to validation response
        validation_with_dossier = {**validation}
        if dossier_data:
            validation_with_dossier['dossier_data'] = dossier_data
        
        # Return directly as ValidationRequest (frontend expects this format)
        return validation_with_dossier
        
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


@router.post("/validation/queue/{validation_id}/send-review")
async def send_review(
    validation_id: str,
    request: Dict[str, Any] = Body(...),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
) -> Dict[str, Any]:
    """
    Send review with checklist and issues. This will:
    1. Store review_checklist and review_issues
    2. Set needs_revision=True if there are unchecked items or issues
    3. Reopen chat by setting story_completed=False for all sessions in project
    4. Send review email to all admins
    """
    try:
        from datetime import datetime, timezone
        
        # Get validation to access project_id and session_id
        validation = await validation_service.get_validation_by_id(UUID(validation_id))
        if not validation:
            raise HTTPException(status_code=404, detail="Validation request not found")
        
        project_id = validation.get('project_id')
        session_id = validation.get('session_id')
        user_id = validation.get('user_id')
        
        # Extract review data
        review_checklist = request.get('checklist', {})
        review_issues = request.get('issues', {})
        review_notes = request.get('notes', '')
        reviewed_by = x_user_id or request.get('reviewed_by', 'admin')
        
        # Determine if revision is needed (any unchecked items or flagged issues)
        unchecked_items = [
            key for key, checked in review_checklist.items() 
            if isinstance(checked, bool) and not checked
        ]
        has_issues = any(
            issues and len(issues) > 0 
            for issues in review_issues.values() 
            if isinstance(issues, list)
        )
        needs_revision = len(unchecked_items) > 0 or has_issues
        
        print(f"📋 [REVIEW] Sending review for validation {validation_id}")
        print(f"📋 [REVIEW] Unchecked items: {unchecked_items}")
        print(f"📋 [REVIEW] Has issues: {has_issues}")
        print(f"📋 [REVIEW] Needs revision: {needs_revision}")
        
        # Update validation with review data
        success = await validation_service.update_validation_status(
            validation_id=UUID(validation_id),
            status='pending',  # Keep as pending during review
            reviewed_by=reviewed_by,
            review_notes=review_notes,
            review_checklist=review_checklist,
            review_issues=review_issues,
            needs_revision=needs_revision
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update validation with review data")
        
        # If revision is needed, reopen the chat and auto-ask questions
        if needs_revision and project_id:
            try:
                from ..database.supabase import get_supabase_client
                from ..services.revision_prompt_library import get_user_friendly_question
                supabase = get_supabase_client()
                
                # Reopen ALL sessions in the project by setting story_completed=False and is_active=True
                reopen_result = supabase.table("sessions").update({
                    "story_completed": False,
                    "is_active": True,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }).eq("project_id", str(project_id)).execute()
                
                print(f"✅ [REVIEW] Reopened {len(reopen_result.data) if reopen_result.data else 0} sessions in project {project_id}")
                
                # Get all reopened sessions to add auto-question
                reopened_sessions = reopen_result.data if reopen_result.data else []
                
                # Generate user-friendly question from revision data
                unchecked_items = [
                    key for key, checked in review_checklist.items() 
                    if isinstance(checked, bool) and not checked
                ]
                flagged_issues = {}
                if review_issues:
                    for issue_type in ["missing_info", "conflicts", "factual_gaps"]:
                        issues = review_issues.get(issue_type, [])
                        if issues and len(issues) > 0:
                            flagged_issues[issue_type] = issues
                
                auto_question = get_user_friendly_question(unchecked_items, flagged_issues if flagged_issues else None)
                
                # Add auto-question as assistant message to the most recent active session
                if reopened_sessions and auto_question:
                    # Get the most recent session (or first one if we can't determine)
                    latest_session = reopened_sessions[0]
                    session_id = latest_session.get("session_id")
                    session_user_id = latest_session.get("user_id")
                    
                    if session_id and session_user_id:
                        try:
                            # Create assistant message with the auto-question
                            from uuid import uuid4
                            message_id = str(uuid4())
                            message_data = {
                                "message_id": message_id,
                                "session_id": session_id,
                                "role": "assistant",
                                "content": auto_question,
                                "metadata": {
                                    "auto_generated": True,
                                    "revision_question": True,
                                    "revision_items": unchecked_items
                                },
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                                "user_id": session_user_id
                            }
                            
                            supabase.table("chat_messages").insert(message_data).execute()
                            print(f"✅ [REVIEW] Auto-generated revision question in session {session_id}")
                        except Exception as msg_error:
                            print(f"⚠️ [REVIEW] Error creating auto-question message: {msg_error}")
                            # Don't fail if message creation fails
                
            except Exception as reopen_error:
                print(f"⚠️ [REVIEW] Error reopening chat: {reopen_error}")
                import traceback
                print(f"⚠️ [REVIEW] Traceback: {traceback.format_exc()}")
                # Don't fail the whole request if reopening fails
        
        # Send review email to all admins
        email_sent = False
        email_error = None
        try:
            from ..services.email_service import EmailService
            email_service = EmailService()
            
            print(f"📧 [REVIEW] Email service available: {email_service.available}")
            print(f"📧 [REVIEW] Email provider: {email_service.provider}")
            
            if email_service.available:
                # Get dossier data for email
                from ..database.session_service_supabase import session_service
                dossier = session_service.get_dossier(UUID(project_id), UUID(user_id))
                dossier_data = dossier.snapshot_json if dossier else {}
                
                # Get internal team emails
                import os
                internal_emails_str = os.getenv("CLIENT_EMAIL", "")
                internal_emails = [email.strip() for email in internal_emails_str.split(",") if email.strip()]
                
                print(f"📧 [REVIEW] Internal emails configured: {len(internal_emails)} recipients")
                
                if internal_emails:
                    # Send review notification email
                    email_sent = await email_service.send_review_notification(
                        internal_emails=internal_emails,
                        project_id=project_id,
                        validation_id=validation_id,
                        story_data=dossier_data,
                        review_checklist=review_checklist,
                        review_issues=review_issues,
                        needs_revision=needs_revision
                    )
                    if email_sent:
                        print(f"✅ [REVIEW] Review notification email sent successfully to {len(internal_emails)} admins")
                    else:
                        print(f"⚠️ [REVIEW] Review notification email failed to send")
                else:
                    print(f"⚠️ [REVIEW] No internal emails configured (CLIENT_EMAIL env var is empty)")
        except Exception as e:
            email_error = str(e)
            print(f"❌ [REVIEW] Error sending review email: {email_error}")
            import traceback
            print(f"❌ [REVIEW] Traceback: {traceback.format_exc()}")
            # Don't fail the whole request if email fails
        
        return {
            "success": True,
            "message": "Review sent successfully",
            "needs_revision": needs_revision,
            "unchecked_items": unchecked_items,
            "email_sent": email_sent,
            "email_error": email_error
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid validation ID format")
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [REVIEW] Error sending review: {e}")
        import traceback
        print(f"❌ [REVIEW] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to send review: {str(e)}")


@router.post("/validation/queue/{validation_id}/generate-synopsis")
async def generate_synopsis(
    validation_id: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
) -> Dict[str, Any]:
    """
    Generate synopsis for a validation request (Step 10).
    This is triggered after Step 9 (Dossier Review) is approved.
    """
    try:
        from ..services.validation_service import validation_service
        from ..services.synopsis_generator import synopsis_generator
        from ..database.session_service_supabase import session_service
        
        # Get validation request
        validation = await validation_service.get_validation_by_id(UUID(validation_id))
        if not validation:
            raise HTTPException(status_code=404, detail="Validation request not found")
        
        project_id = validation.get('project_id')
        user_id = validation.get('user_id')
        
        if not project_id or not user_id:
            raise HTTPException(status_code=400, detail="Missing project_id or user_id")
        
        # Get dossier data
        dossier = session_service.get_dossier(UUID(project_id), UUID(user_id))
        if not dossier:
            raise HTTPException(status_code=404, detail="Dossier not found")
        
        dossier_data = dossier.snapshot_json
        
        # Generate synopsis
        print(f"📝 [SYNOPSIS] Generating synopsis for validation {validation_id}")
        synopsis = await synopsis_generator.generate_synopsis(dossier_data, project_id)
        
        if not synopsis:
            raise HTTPException(status_code=500, detail="Failed to generate synopsis")
        
        # Update validation with synopsis and move to synopsis_review step
        success = await validation_service.update_validation_status(
            validation_id=UUID(validation_id),
            status='pending',  # Keep as pending during synopsis review
            workflow_step='synopsis_review',
            synopsis=synopsis
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save synopsis")
        
        print(f"✅ [SYNOPSIS] Synopsis generated and saved for validation {validation_id}")
        
        return {
            "success": True,
            "message": "Synopsis generated successfully",
            "synopsis": synopsis,
            "word_count": len(synopsis.split())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generating synopsis: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate synopsis: {str(e)}")


@router.post("/validation/queue/{validation_id}/approve-synopsis")
async def approve_synopsis(
    validation_id: str,
    request: Dict[str, Any] = Body(...),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
) -> Dict[str, Any]:
    """
    Approve synopsis (Step 11).
    This moves the workflow to script generation (Step 12).
    """
    try:
        from ..services.validation_service import validation_service
        from ..services.email_service import email_service
        from ..database.session_service_supabase import session_service
        
        reviewed_by = x_user_id or request.get('reviewed_by', 'admin')
        review_notes = request.get('notes', '')
        checklist = request.get('checklist', {})
        
        # Get validation to access project_id, user_id, and synopsis
        validation = await validation_service.get_validation_by_id(UUID(validation_id))
        if not validation:
            raise HTTPException(status_code=404, detail="Validation request not found")
        
        project_id = validation.get('project_id')
        user_id = validation.get('user_id')
        synopsis = validation.get('synopsis')
        client_email = validation.get('client_email')
        client_name = validation.get('client_name')
        
        if not project_id or not user_id:
            raise HTTPException(status_code=400, detail="Missing project_id or user_id")
        
        # Update validation with synopsis approval and checklist
        success = await validation_service.update_validation_status(
            validation_id=UUID(validation_id),
            status='pending',  # Keep as pending during script generation
            workflow_step='script_generation',
            reviewed_by=reviewed_by,
            synopsis_approved=True,
            synopsis_review_notes=review_notes,
            synopsis_checklist=checklist
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to approve synopsis")
        
        # Send email to client with synopsis
        email_sent = False
        email_error = None
        if client_email and synopsis:
            try:
                # Get dossier data for email context
                dossier = session_service.get_dossier(UUID(project_id), UUID(user_id))
                dossier_data = dossier.snapshot_json if dossier else {}
                
                email_sent = await email_service.send_synopsis_approval(
                    client_email=client_email,
                    client_name=client_name,
                    project_id=str(project_id),
                    validation_id=validation_id,
                    synopsis=synopsis,
                    dossier_data=dossier_data,
                    checklist=checklist,
                    review_notes=review_notes
                )
                if not email_sent:
                    email_error = "Email service returned False"
            except Exception as e:
                print(f"❌ [SYNOPSIS] Error sending synopsis approval email: {e}")
                import traceback
                print(f"❌ [SYNOPSIS] Traceback: {traceback.format_exc()}")
                email_error = str(e)
        
        print(f"✅ [SYNOPSIS] Synopsis approved for validation {validation_id}, moving to script generation")
        
        return {
            "success": True,
            "message": "Synopsis approved successfully. Ready for script generation.",
            "email_sent": email_sent,
            "email_error": email_error
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error approving synopsis: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to approve synopsis: {str(e)}")


@router.post("/validation/queue/{validation_id}/reject-synopsis")
async def reject_synopsis(
    validation_id: str,
    request: Dict[str, Any] = Body(...),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
) -> Dict[str, Any]:
    """
    Reject synopsis (Step 11).
    This requires revision and regenerates synopsis.
    """
    try:
        from ..services.validation_service import validation_service
        from ..services.synopsis_generator import synopsis_generator
        from ..database.session_service_supabase import session_service
        
        reviewed_by = x_user_id or request.get('reviewed_by', 'admin')
        review_notes = request.get('notes', '')
        special_instructions = request.get('special_instructions', '')
        
        if not review_notes:
            raise HTTPException(status_code=400, detail="Review notes are required for rejection")
        
        # Get validation to access project_id and user_id
        validation = await validation_service.get_validation_by_id(UUID(validation_id))
        if not validation:
            raise HTTPException(status_code=404, detail="Validation request not found")
        
        project_id = validation.get('project_id')
        user_id = validation.get('user_id')
        
        if not project_id or not user_id:
            raise HTTPException(status_code=400, detail="Missing project_id or user_id")
        
        # Regenerate synopsis
        dossier = session_service.get_dossier(UUID(project_id), UUID(user_id))
        if not dossier:
            raise HTTPException(status_code=404, detail="Dossier not found")
        
        dossier_data = dossier.snapshot_json
        
        print(f"📝 [SYNOPSIS] Regenerating synopsis for validation {validation_id}")
        if special_instructions:
            print(f"📝 [SYNOPSIS] Special instructions provided: {special_instructions[:100]}...")
        new_synopsis = await synopsis_generator.generate_synopsis(
            dossier_data, 
            project_id,
            special_instructions=special_instructions if special_instructions else None
        )
        
        if not new_synopsis:
            raise HTTPException(status_code=500, detail="Failed to regenerate synopsis")
        
        # Update validation with rejection notes and new synopsis
        success = await validation_service.update_validation_status(
            validation_id=UUID(validation_id),
            status='pending',
            workflow_step='synopsis_review',
            reviewed_by=reviewed_by,
            synopsis_approved=False,
            synopsis_review_notes=review_notes,
            synopsis=new_synopsis
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update synopsis rejection")
        
        print(f"✅ [SYNOPSIS] Synopsis rejected and regenerated for validation {validation_id}")
        
        return {
            "success": True,
            "message": "Synopsis rejected. New synopsis generated for review.",
            "synopsis": new_synopsis
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error rejecting synopsis: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to reject synopsis: {str(e)}")


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

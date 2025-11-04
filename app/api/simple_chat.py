"""
Simplified Chat API
Clean chat implementation using the simplified session manager
"""

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict
from uuid import UUID, uuid4
import json
import asyncio
import os
from datetime import datetime, timezone
import re

from ..models import ChatRequest, DossierUpdate
from .simple_session_manager import SimpleSessionManager
from ..database.supabase import get_supabase_client

# Try to import AI components
try:
    from ..ai.models import ai_manager, TaskType
    from ..ai.rag_service import rag_service
    from ..ai.dossier_extractor import dossier_extractor
    AI_AVAILABLE = True
except Exception as e:
    print(f"Warning: AI components not available: {e}")
    AI_AVAILABLE = False
    ai_manager = None
    TaskType = None
    rag_service = None
    dossier_extractor = None

router = APIRouter()

# Placeholder event sender (no-op). Replace with real SSE/bus if needed.
async def send_event(_event: dict) -> None:
    return

def _is_story_completion_text(text: str) -> bool:
    """Heuristic to detect completion based on assistant text."""
    if not text:
        return False
    normalized = text.lower()
    completion_markers = [
        "the story is complete",
        "your story is complete",
        "story is complete",
        "story complete",
        "we've reached the end",
        "the end of the story",
        "conclusion of the story",
        "would you like to create another story",  # Matches: "Would you like to create another story?"
        "would you like to start another story",
        "would you like to begin another story",
        "new story",
        "start a new story",
        "create another story",
        "sign up to create unlimited",  # Matches: "Sign up to create unlimited stories..."
        "create unlimited stories",  # Additional variant
    ]
    result = any(marker in normalized for marker in completion_markers)
    if result:
        print(f"🎯 [COMPLETION] Detected completion marker in: {text[:200]}...")
    return result

async def _generate_conversation_transcript(conversation_history: List[Dict]) -> str:
    """Generate a formatted conversation transcript from chat history."""
    try:
        transcript_lines = ["# Conversation Transcript", ""]
        
        for i, message in enumerate(conversation_history):
            role = message.get("role", "unknown")
            content = message.get("content", "")
            timestamp = message.get("timestamp", "")
            
            # Format role
            if role == "user":
                speaker = "Client"
            elif role == "assistant":
                speaker = "Stories We Tell AI"
            else:
                speaker = role.title()
            
            # Add message to transcript
            transcript_lines.append(f"## {speaker}")
            if timestamp:
                transcript_lines.append(f"*{timestamp}*")
            transcript_lines.append("")
            transcript_lines.append(content)
            transcript_lines.append("")
            transcript_lines.append("---")
            transcript_lines.append("")
        
        return "\n".join(transcript_lines)
    except Exception as e:
        print(f"⚠️ Transcript generation failed: {e}")
        return f"Transcript generation failed: {str(e)}"


async def _queue_for_validation(
    user_email: Optional[str],
    user_name: Optional[str],
    project_id: str,
    dossier_snapshot: Optional[dict],
    conversation_transcript: str,
    generated_script: str,
    session_id: str,
    user_id: str,
) -> None:
    """Queue story completion for human validation before client delivery."""
    try:
        print(f"📋 [VALIDATION] Starting validation queue process...")
        print(f"📋 [VALIDATION] Project ID: {project_id}")
        print(f"📋 [VALIDATION] User ID: {user_id}")
        print(f"📋 [VALIDATION] Session ID: {session_id}")
        print(f"📋 [VALIDATION] User Email: {user_email}")
        print(f"📋 [VALIDATION] Transcript length: {len(conversation_transcript)} chars")
        print(f"📋 [VALIDATION] Script length: {len(generated_script)} chars")
        
        from ..services.email_service import EmailService  # type: ignore
        from ..services.validation_service import validation_service  # type: ignore
        
        # Store validation request in database
        print(f"📋 [VALIDATION] Creating validation request in database...")
        validation_request = await validation_service.create_validation_request(
            project_id=UUID(project_id),
            user_id=UUID(user_id),
            session_id=UUID(session_id),
            conversation_transcript=conversation_transcript,
            generated_script=generated_script,
            client_email=user_email,
            client_name=user_name
        )
        
        if not validation_request:
            print("⚠️ [VALIDATION] Failed to create validation request in database - falling back to direct client email")
            await _send_completion_email(user_email, user_name, project_id, dossier_snapshot, generated_script)
            return
        
        validation_id = validation_request['validation_id']
        print(f"✅ [VALIDATION] Validation request created in database: {validation_id}")
        
        # Send email notification to internal team
        service = EmailService()
        if not service.available:
            print("⚠️ EmailService unavailable - validation stored in database but no email sent")
            return
        
        # Get internal team emails from environment
        internal_emails_str = os.getenv("CLIENT_EMAIL", "team@storiesweetell.com")
        internal_emails = [email.strip() for email in internal_emails_str.split(",") if email.strip()]
        print(f"📧 Sending validation notification to internal team: {internal_emails}")
        
        story_data = dossier_snapshot or {}
        
        # Send to internal team for validation
        ok = await service.send_validation_request(
            internal_emails=internal_emails,
            project_id=project_id,
            story_data=story_data,
            transcript=conversation_transcript,
            generated_script=generated_script,
            client_email=user_email,
            client_name=user_name or "Anonymous",
            validation_id=validation_id
        )
        
        if ok:
            print("📧 Validation notification sent to internal team")
            # Update status to indicate email was sent
            await validation_service.update_validation_status(
                validation_id=UUID(validation_id),
                status='pending'  # Keep as pending but note email sent
            )
        else:
            print("⚠️ Validation notification failed but request is stored in database")
            
    except Exception as e:
        print(f"⚠️ Validation queue failed: {e}")
        print("🔄 Falling back to direct client email")
        await _send_completion_email(user_email, user_name, project_id, dossier_snapshot, generated_script)


async def _send_completion_email(
    user_email: Optional[str],
    user_name: Optional[str],
    project_id: str,
    dossier_snapshot: Optional[dict],
    generated_script: str
) -> None:
    """Send a completion email via existing EmailService (Resend-backed)."""
    try:
        from ..services.email_service import EmailService  # type: ignore
        service = EmailService()
        if not service.available:
            print("⚠️ EmailService unavailable - skipping completion email")
            return
        if not user_email:
            print("⚠️ Missing user_email - skipping completion email")
            return
        story_data = dossier_snapshot or {}
        ok = await service.send_story_captured_email(
            user_email=user_email,
            user_name=user_name or "Writer",
            story_data=story_data,
            generated_script=generated_script or "",
            project_id=project_id,
            client_emails=None,
        )
        if ok:
            print("📧 Completion email sent via EmailService")
    except Exception as e:
        print(f"⚠️ Failed to send completion email: {e}")

@router.post("/chat")
async def chat(
    chat_request: ChatRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    x_project_id: Optional[str] = Header(None, alias="X-Project-ID")
):
    """
    Simplified chat endpoint that works for both authenticated and anonymous users
    
    Flow:
    1. Get or create session using SimpleSessionManager
    2. Save user message to database
    3. Generate AI response
    4. Save AI response to database
    5. Stream response back to user
    """
    
    try:
        # Get or create session
        session_info = await SimpleSessionManager.get_or_create_session(
            session_id=x_session_id or chat_request.session_id,
            user_id=UUID(x_user_id) if x_user_id else None,
            project_id=UUID(x_project_id) if x_project_id else chat_request.project_id
        )
        
        session_id = session_info["session_id"]
        user_id = session_info["user_id"]
        project_id = session_info["project_id"]
        is_authenticated = session_info["is_authenticated"]
        
        print(f"Chat request - Session: {session_id}, User: {user_id}, Authenticated: {is_authenticated}")
        
        # Handle message editing: delete messages from edit point onwards
        if chat_request.edit_from_message_id:
            print(f"✏️ [EDIT] Deleting messages from {chat_request.edit_from_message_id} onwards")
            try:
                supabase = get_supabase_client()
                if supabase:
                    # Get the message to find its timestamp
                    message_result = supabase.table("chat_messages").select("created_at").eq("message_id", str(chat_request.edit_from_message_id)).eq("session_id", str(session_id)).execute()
                    
                    if message_result.data:
                        edit_message_time = message_result.data[0]["created_at"]
                        
                        # First, delete the exact message being edited
                        supabase.table("chat_messages").delete().eq("message_id", str(chat_request.edit_from_message_id)).eq("session_id", str(session_id)).execute()
                        print(f"✏️ [EDIT] Deleted message {chat_request.edit_from_message_id}")
                        
                        # Then, delete all messages created after this timestamp
                        messages_after = supabase.table("chat_messages").select("message_id").eq("session_id", str(session_id)).gt("created_at", edit_message_time).execute()
                        
                        if messages_after.data:
                            message_ids_after = [msg["message_id"] for msg in messages_after.data]
                            print(f"✏️ [EDIT] Found {len(message_ids_after)} subsequent messages to delete: {message_ids_after}")
                            
                            # Delete subsequent messages
                            supabase.table("chat_messages").delete().eq("session_id", str(session_id)).gt("created_at", edit_message_time).execute()
                            print(f"✏️ [EDIT] Deleted {len(message_ids_after)} subsequent messages")
                        else:
                            print(f"✏️ [EDIT] No subsequent messages found to delete")
                        
                        # TODO: Delete RAG embeddings for these messages (requires adding delete_message_embedding method to RAG service)
                    else:
                        print(f"⚠️ [EDIT] Message {chat_request.edit_from_message_id} not found in session {session_id}")
            except Exception as e:
                print(f"❌ [EDIT] Error deleting messages: {e}")
                import traceback
                print(traceback.format_exc())
                # Continue with creating new message even if deletion fails
        
        # Save user message
        user_message_id = await _save_message(
            session_id=str(session_id),
            user_id=str(user_id),
            role="user",
            content=chat_request.text,
            metadata={
                "is_authenticated": is_authenticated,
                "attached_files": chat_request.attached_files or []
            }
        )
        
        # Store user message embedding for RAG
        if rag_service and user_message_id:
            try:
                if is_authenticated:
                    # For authenticated users, use their actual user_id
                    rag_user_id = UUID(user_id)
                    print(f"📚 Using RAG user_id: {rag_user_id} (authenticated: {is_authenticated})")
                else:
                    # For anonymous users, use the special anonymous user ID
                    # This allows RAG to work while maintaining session isolation
                    rag_user_id = UUID("00000000-0000-0000-0000-000000000000")
                    print(f"📚 Using anonymous user_id for RAG: {rag_user_id} (session: {session_id})")
                
                await rag_service.embed_and_store_message(
                    message_id=UUID(user_message_id),
                    user_id=rag_user_id,
                    project_id=UUID(project_id) if project_id else None,
                    session_id=UUID(session_id),
                    content=chat_request.text,
                    role="user",
                    metadata={"is_authenticated": is_authenticated, "original_user_id": str(user_id), "session_id": str(session_id)}
                )
                print(f"📚 Stored user message embedding: {user_message_id}")
            except Exception as e:
                print(f"⚠️ Failed to store user message embedding: {e}")
        
        # Get conversation history for context (moved outside generate_stream to fix scope issue)
        # Fetch last 50 messages for RAG context (good balance between context and performance)
        conversation_history = await _get_conversation_history(str(session_id), str(user_id), limit=50)
        
        # Process attached image files for DIRECT sending to model (ChatGPT-style)
        image_data_list = []  # List of {"data": bytes, "mime_type": str, "filename": str}
        
        if chat_request.attached_files:
            print(f"🖼️ [IMAGE] Processing {len(chat_request.attached_files)} attached files for direct model sending")
            print(f"🖼️ [IMAGE] Attached files: {[{'name': f.get('name'), 'type': f.get('type'), 'url': f.get('url')[:50] + '...' if f.get('url') else None} for f in chat_request.attached_files]}")
            
            import requests
            
            for idx, attached_file in enumerate(chat_request.attached_files):
                file_type = attached_file.get("type", "unknown")
                file_name = attached_file.get("name", "unknown")
                file_url = attached_file.get("url", "")
                
                print(f"🖼️ [IMAGE] Processing file {idx + 1}/{len(chat_request.attached_files)}: {file_name} (type: {file_type})")
                
                # Check if it's an image file
                is_image = (
                    file_type == "image" or 
                    file_type.startswith("image/") or 
                    file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
                )
                
                if is_image:
                    print(f"🖼️ [IMAGE] Detected image file: {file_name}")
                    print(f"🖼️ [IMAGE] Image URL: {file_url[:100]}...")
                    
                    try:
                        print(f"🖼️ [IMAGE] Downloading image from URL...")
                        response = requests.get(file_url, timeout=30)
                        
                        print(f"🖼️ [IMAGE] Download response status: {response.status_code}")
                        print(f"🖼️ [IMAGE] Download response size: {len(response.content)} bytes")
                        
                        if response.status_code == 200:
                            image_bytes = response.content
                            
                            # Determine MIME type from file extension or Content-Type
                            mime_type = file_type if file_type.startswith("image/") else "image/png"
                            if file_name.lower().endswith('.jpg') or file_name.lower().endswith('.jpeg'):
                                mime_type = "image/jpeg"
                            elif file_name.lower().endswith('.png'):
                                mime_type = "image/png"
                            elif file_name.lower().endswith('.gif'):
                                mime_type = "image/gif"
                            elif file_name.lower().endswith('.webp'):
                                mime_type = "image/webp"
                            
                            image_data_list.append({
                                "data": image_bytes,
                                "mime_type": mime_type,
                                "filename": file_name
                            })
                            
                            print(f"✅ [IMAGE] Image downloaded and prepared for direct model sending: {file_name} ({len(image_bytes)} bytes, {mime_type})")
                        else:
                            print(f"❌ [IMAGE] Failed to download image {file_name}: HTTP {response.status_code}")
                    except Exception as e:
                        import traceback
                        print(f"❌ [IMAGE] Error downloading image {file_name}: {str(e)}")
                        print(f"❌ [IMAGE] Traceback: {traceback.format_exc()}")
                else:
                    print(f"⏭️ [IMAGE] Skipping non-image file: {file_name} (type: {file_type})")
            
            print(f"🖼️ [IMAGE] Prepared {len(image_data_list)} image(s) for direct model sending")
        else:
            print(f"ℹ️ [IMAGE] No attached files in request")
        
        # Prepare image-to-asset mapping for later storage
        # attached_files should have asset_id if the file was uploaded through our system
        image_asset_mapping = {}  # {filename: asset_id}
        if chat_request.attached_files:
            for attached_file in chat_request.attached_files:
                asset_id = attached_file.get("asset_id")
                filename = attached_file.get("name", "unknown")
                if asset_id:
                    image_asset_mapping[filename] = asset_id
                    print(f"📎 [ASSET] Mapping image {filename} to asset {asset_id}")
        
        # Prepare attachment metadata for post-processing
        # We'll extract analysis from the model's response (single call approach)
        attachment_metadata = {}  # {filename: {"file_type": str, "asset_id": str}}
        
        if chat_request.attached_files:
            for attached_file in chat_request.attached_files:
                filename = attached_file.get("name", "unknown")
                file_type = attached_file.get("type", "unknown")
                asset_id = image_asset_mapping.get(filename)
                
                # Check if it's an image
                img_data = next((img for img in image_data_list if img.get("filename") == filename), None)
                
                if img_data and img_data.get("data"):
                    attachment_metadata[filename] = {
                        "file_type": "image",
                        "asset_id": asset_id
                    }
                elif file_type and ("document" in file_type.lower() or filename.lower().endswith(('.pdf', '.docx', '.txt', '.doc'))):
                    attachment_metadata[filename] = {
                        "file_type": "document",
                        "asset_id": asset_id
                    }
                    print(f"ℹ️ [ATTACHMENT] Document {filename} already processed during upload")
                else:
                    attachment_metadata[filename] = {
                        "file_type": file_type,
                        "asset_id": asset_id
                    }
        
        # Generate and stream AI response
        async def generate_stream():
            try:
                # Generate AI response
                if AI_AVAILABLE and ai_manager:
                    # Get or create dossier for this project
                    dossier_context = None
                    if dossier_extractor and project_id:
                        try:
                            from ..database.session_service_supabase import session_service
                            # Get existing dossier
                            dossier = session_service.get_dossier(UUID(project_id), UUID(user_id))
                            if dossier and dossier.snapshot_json:
                                dossier_context = dossier.snapshot_json
                                print(f"📋 Using existing dossier: {dossier.title}")
                            else:
                                print(f"📋 No existing dossier found for project {project_id}")
                        except Exception as e:
                            print(f"⚠️ Dossier retrieval error: {e}")
                    
                    # Get RAG context from uploaded documents
                    # IMPORTANT: Use project_id to limit search to current project only
                    # Each project = separate story with isolated context
                    # Stories should be isolated - no cross-project character references
                    rag_context = None
                    if rag_service:
                        try:
                            if is_authenticated:
                                # For authenticated users, use their actual user_id
                                rag_user_id = UUID(user_id)
                                print(f"🔍 Getting RAG context for user: {rag_user_id}, project: {project_id} (project-level isolation)")
                            else:
                                # For anonymous users, use the special anonymous user ID
                                rag_user_id = UUID("00000000-0000-0000-0000-000000000000")
                                print(f"🔍 Getting RAG context for anonymous user: {rag_user_id}, project: {project_id} (project-level isolation)")
                            
                            # Pass project_id to limit search to current project only
                            # This ensures each story/project is isolated and independent
                            rag_context = await rag_service.get_rag_context(
                                user_message=chat_request.text,
                                user_id=rag_user_id,
                                project_id=UUID(project_id) if project_id else None,  # Limit to current project
                                conversation_history=conversation_history
                            )
                            print(f"📚 RAG context retrieved: {rag_context.get('user_context_count', 0)} user messages, {rag_context.get('document_context_count', 0)} document chunks")
                        except Exception as e:
                            print(f"⚠️ RAG context error: {e}")
                            rag_context = None
                    
                    # Enhance user prompt when images are present to ensure detailed analysis
                    # Model will see images + conversation history + RAG context in single call
                    enhanced_prompt = chat_request.text
                    
                    if image_data_list:
                        # Add guidance to ensure detailed visual analysis while staying conversational
                        if enhanced_prompt:
                            # User provided context - model should analyze according to their guidance
                            enhanced_prompt = f"{enhanced_prompt}\n\n[Note: Please provide detailed visual analysis of the attached image(s) in your response, describing all relevant visual elements, appearance, and details that relate to the story.]"
                        else:
                            # No user text - request comprehensive analysis
                            enhanced_prompt = "Please analyze the attached image(s) in detail and provide comprehensive information about all visual elements relevant to storytelling and story development."
                    
                    print(f"📝 [PROMPT] Enhanced prompt (length: {len(enhanced_prompt)} chars)")
                    if image_data_list:
                        print(f"🖼️ [PROMPT] Images included in single model call with full context")
                    
                    # Use AI manager for response generation with RAG and dossier context
                    # SINGLE CALL: Images + conversation history + RAG context all together
                    ai_response = await ai_manager.generate_response(
                        task_type=TaskType.CHAT,
                        prompt=enhanced_prompt,
                        conversation_history=conversation_history,  # Full conversation history
                        user_id=user_id,
                        project_id=project_id,
                        rag_context=rag_context,  # RAG context from documents
                        dossier_context=dossier_context,
                        image_data=image_data_list  # Images sent directly (ChatGPT-style)
                    )
                    
                    # Get the response content
                    full_response = ai_response.get("response", "I'm sorry, I couldn't generate a response.")
                    
                    # Stream the response word by word for better UX
                    words = full_response.split()
                    chunk_count = 0
                    
                    for i, word in enumerate(words):
                        chunk_count += 1
                        chunk_data = {
                            "type": "content",
                            "content": word + (" " if i < len(words) - 1 else ""),
                            "chunk": chunk_count,
                            "done": i == len(words) - 1
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                        await asyncio.sleep(0.1)  # Small delay for streaming effect
                    
                    # Save AI response
                    assistant_message_id = await _save_message(
                        session_id=str(session_id),
                        user_id=str(user_id),
                        role="assistant",
                        content=full_response,
                        metadata={"is_authenticated": is_authenticated}
                    )
                    
                    # Extract and store attachment analysis from model's response
                    # Model sees images directly + conversation history + RAG context in single call
                    # Extract image analysis from the natural response
                    if image_data_list and attachment_metadata:
                        await _extract_and_store_attachment_analysis_from_response(
                            full_response=full_response,
                            image_data_list=image_data_list,
                            attachment_metadata=attachment_metadata,
                            conversation_history=conversation_history,
                            rag_context=rag_context,
                            project_id=project_id,
                            user_id=user_id
                        )
                    
                    # Update dossier if needed (after both user and assistant messages are saved)
                    # IMPORTANT: re-fetch conversation history so it includes the assistant's reply we just saved
                    # Fetch ALL messages for dossier (no limit to get complete conversation)
                    updated_conversation_history = conversation_history
                    try:
                        updated_conversation_history = await _get_conversation_history(str(session_id), str(user_id), limit=None)
                        print(f"📋 [DOSSIER CHECK] Conversation history length: {len(updated_conversation_history)}")
                    except Exception as _history_e:
                        print(f"⚠️ Failed to refresh conversation history before dossier update: {_history_e}")

                    print(f"📋 [DOSSIER CHECK] Checking dossier update conditions:")
                    print(f"   - dossier_extractor available: {dossier_extractor is not None}")
                    print(f"   - project_id: {project_id}")
                    print(f"   - conversation history length: {len(updated_conversation_history)}")
                    print(f"   - All conditions met: {dossier_extractor and project_id and len(updated_conversation_history) >= 2}")

                    if dossier_extractor and project_id and len(updated_conversation_history) >= 2:
                        try:
                            # Force update every 2 user turns (more reliable than LLM decision)
                            user_turns = sum(1 for m in updated_conversation_history if m.get("role") == "user")
                            should_update = user_turns >= 2 and user_turns % 2 == 0
                            
                            print(f"📋 [DOSSIER] User turns: {user_turns}, Should update: {should_update}")
                            
                            if should_update:
                                print(f"📋 Updating dossier for project {project_id}")
                                print(f"📋 [EXTRACT] Calling dossier_extractor.extract_metadata with {len(updated_conversation_history)} messages")
                                print(f"📋 [EXTRACT] First 2 messages: {updated_conversation_history[:2] if len(updated_conversation_history) >= 2 else updated_conversation_history}")
                                new_metadata = await dossier_extractor.extract_metadata(updated_conversation_history)
                                print(f"📋 [EXTRACT] Extraction complete. Metadata keys: {list(new_metadata.keys())}")
                                print(f"📋 [EXTRACT] Characters: {len(new_metadata.get('characters', []))}, Scenes: {len(new_metadata.get('scenes', []))}")

                                # Fetch existing dossier FIRST to merge characters/scenes and preserve title
                                existing_snapshot = {}
                                current_title = None
                                try:
                                    from ..database.session_service_supabase import session_service
                                    existing_dossier = session_service.get_dossier(UUID(project_id), UUID(user_id))
                                    if existing_dossier:
                                        existing_snapshot = existing_dossier.snapshot_json or {}
                                        current_title = existing_snapshot.get("title")
                                        print(f"📋 Fetched existing dossier: {current_title}")
                                        print(f"📋 Existing characters: {len(existing_snapshot.get('characters', []))}")
                                        print(f"📋 Existing scenes: {len(existing_snapshot.get('scenes', []))}")
                                except Exception as _e:
                                    print(f"⚠️ Could not fetch existing dossier: {_e}")

                                # Merge characters by name (case-insensitive)
                                try:
                                    existing_chars = existing_snapshot.get("characters", []) or []
                                    new_chars = new_metadata.get("characters", []) or []
                                    if new_chars:
                                        by_name = {}
                                        for c in existing_chars:
                                            key = (c.get("name") or "").strip().lower()
                                            by_name[key] = c
                                        for c in new_chars:
                                            key = (c.get("name") or "").strip().lower()
                                            if key in by_name:
                                                merged = {**by_name[key], **{k: v for k, v in c.items() if v}}
                                                by_name[key] = merged
                                            else:
                                                by_name[key] = c
                                        new_metadata["characters"] = list(by_name.values())
                                        print(f"📋 Merged characters: {len(new_metadata['characters'])}")
                                    elif existing_chars:
                                        new_metadata["characters"] = existing_chars
                                        print(f"📋 Preserved existing characters: {len(existing_chars)}")
                                except Exception as e:
                                    print(f"⚠️ Character merge failed: {e}")

                                # Merge scenes by one_liner
                                try:
                                    existing_scenes = existing_snapshot.get("scenes", []) or []
                                    new_scenes = new_metadata.get("scenes", []) or []
                                    if new_scenes:
                                        by_line = {}
                                        for s in existing_scenes:
                                            key = (s.get("one_liner") or "").strip().lower()
                                            by_line[key] = s
                                        for s in new_scenes:
                                            key = (s.get("one_liner") or "").strip().lower()
                                            if key in by_line:
                                                merged = {**by_line[key], **{k: v for k, v in s.items() if v}}
                                                by_line[key] = merged
                                            else:
                                                by_line[key] = s
                                        new_metadata["scenes"] = list(by_line.values())
                                        print(f"📋 Merged scenes: {len(new_metadata['scenes'])}")
                                    elif existing_scenes:
                                        new_metadata["scenes"] = existing_scenes
                                        print(f"📋 Preserved existing scenes: {len(existing_scenes)}")
                                except Exception as e:
                                    print(f"⚠️ Scene merge failed: {e}")

                                # Preserve user-entered project title
                                if current_title:
                                    new_metadata["title"] = current_title
                                    print(f"📋 Preserved project title: {current_title}")

                                # Update dossier in database
                                dossier_update = DossierUpdate(
                                    snapshot_json=new_metadata
                                )
                                updated_dossier = session_service.update_dossier(
                                    UUID(project_id),
                                    UUID(user_id),
                                    dossier_update
                                )
                                if updated_dossier:
                                    print(f"✅ Dossier updated: {updated_dossier.title}")
                                # Send updated dossier to the client for immediate refresh
                                await send_event({
                                    "type": "dossier_updated",
                                    "project_id": str(project_id),
                                    "dossier": new_metadata,
                                    "conversation_history": updated_conversation_history
                                })
                            else:
                                print(f"📋 Dossier update not needed for this turn (messages={len(updated_conversation_history)})")
                        except Exception as e:
                            print(f"⚠️ Failed to update dossier")
                            print(f"Error details: {e}")
                    
                    # Store message embeddings for RAG
                    if rag_service and assistant_message_id:
                        try:
                            if is_authenticated:
                                # For authenticated users, use their actual user_id
                                rag_user_id = UUID(user_id)
                            else:
                                # For anonymous users, use the special anonymous user ID
                                rag_user_id = UUID("00000000-0000-0000-0000-000000000000")
                            
                            await rag_service.embed_and_store_message(
                                message_id=UUID(assistant_message_id),
                                user_id=rag_user_id,
                                project_id=UUID(project_id) if project_id else None,
                                session_id=UUID(session_id),
                                content=full_response,
                                role="assistant",
                                metadata={"is_authenticated": is_authenticated, "original_user_id": str(user_id), "session_id": str(session_id)}
                            )
                            print(f"📚 Stored assistant message embedding: {assistant_message_id}")
                        except Exception as e:
                            print(f"⚠️ Failed to store assistant message embedding: {e}")

                    # Detect completion and handle wrap-up actions
                    try:
                        # Fetch all messages to accurately detect story completion
                        updated_history_for_completion = await _get_conversation_history(str(session_id), str(user_id), limit=None)
                        message_count = len(updated_history_for_completion) if updated_history_for_completion else 0
                        
                        # Only check for completion if we have enough conversation history
                        # This prevents false positives from first messages that might contain phrases like "new story"
                        MIN_MESSAGES_FOR_COMPLETION = 6  # At least 3 user + 3 assistant messages
                        
                        print(f"🔍 [COMPLETION CHECK] Checking story completion...")
                        print(f"🔍 [COMPLETION CHECK] Total messages in conversation: {message_count}")
                        print(f"🔍 [COMPLETION CHECK] Response length: {len(full_response)} chars")
                        print(f"🔍 [COMPLETION CHECK] Response preview: {full_response[:300]}...")
                        
                        is_complete = False
                        if message_count < MIN_MESSAGES_FOR_COMPLETION:
                            print(f"⏭️ [COMPLETION CHECK] Skipping completion check - only {message_count} messages (minimum {MIN_MESSAGES_FOR_COMPLETION} required)")
                        else:
                            is_complete = _is_story_completion_text(full_response)
                            print(f"🔍 [COMPLETION CHECK] Is complete: {is_complete}")
                        
                        if is_complete:
                            print("✅ Story completion detected. Generating script and transcript for validation.")
                            # fetch dossier snapshot if available
                            dossier_snapshot = None
                            try:
                                if project_id:
                                    from ..database.session_service_supabase import session_service
                                    d = session_service.get_dossier(UUID(project_id), UUID(user_id))
                                    dossier_snapshot = d.snapshot_json if d else None
                            except Exception as _e:
                                print(f"⚠️ Could not fetch dossier snapshot for email: {_e}")

                            # Generate conversation transcript
                            transcript = await _generate_conversation_transcript(updated_history_for_completion)
                            print(f"📋 Generated conversation transcript ({len(transcript)} chars)")

                            # Generate proper video script using AI
                            generated_script = ""
                            if ai_manager and dossier_snapshot:
                                try:
                                    print("🎬 Generating professional video script...")
                                    script_response = await ai_manager.generate_response(
                                        prompt="Generate script based on story data",
                                        task_type=TaskType.SCRIPT,
                                        dossier_context=dossier_snapshot
                                    )
                                    generated_script = script_response.get("response", "")
                                    print(f"✅ Generated script ({len(generated_script)} chars)")
                                except Exception as e:
                                    print(f"⚠️ Script generation failed: {e}")
                                    generated_script = f"Script generation failed. Chat response: {full_response}"
                            else:
                                print("⚠️ Using fallback - chat response as script")
                                generated_script = full_response

                            # try to get user email/name from users table if authenticated
                            user_email = None
                            user_name = None
                            if is_authenticated:
                                try:
                                    supabase = get_supabase_client()
                                    print(f"📧 [VALIDATION] Fetching user email for user_id: {user_id}")
                                    # Fix: Use 'user_id' not 'id' - matches schema
                                    res = supabase.table("users").select("email, display_name").eq("user_id", str(user_id)).limit(1).execute()
                                    if res.data and len(res.data) > 0:
                                        user_email = res.data[0].get("email")
                                        user_name = res.data[0].get("display_name")
                                        print(f"📧 [VALIDATION] Found user email: {user_email}, name: {user_name}")
                                    else:
                                        print(f"⚠️ [VALIDATION] No user found with user_id: {user_id}")
                                except Exception as e:
                                    print(f"❌ [VALIDATION] Error fetching user email: {e}")
                                    pass
                            
                            # Check if we can deliver the story
                            if not user_email:
                                if not is_authenticated:
                                    print("⚠️ Anonymous user - story will be validated but not delivered (no email available)")
                                else:
                                    print("⚠️ Authenticated user but no email found in database")
                                user_email = None

                            # Queue for human validation instead of direct client email
                            try:
                                await _queue_for_validation(
                                    user_email=user_email,
                                    user_name=user_name,
                                    project_id=str(project_id),
                                    dossier_snapshot=dossier_snapshot,
                                    conversation_transcript=transcript,
                                    generated_script=generated_script,
                                    session_id=str(session_id),
                                    user_id=str(user_id),
                                )
                                print("✅ [VALIDATION] Successfully queued story for validation")
                            except Exception as validation_error:
                                print(f"❌ [VALIDATION] CRITICAL ERROR queuing for validation: {validation_error}")
                                import traceback
                                print(f"❌ [VALIDATION] Traceback: {traceback.format_exc()}")

                            # mark session inactive
                            try:
                                supabase = get_supabase_client()
                                supabase.table("sessions").update({
                                    "is_active": False,
                                    "updated_at": datetime.now(timezone.utc).isoformat()
                                }).eq("session_id", str(session_id)).execute()
                            except Exception as _e:
                                print(f"⚠️ Failed to close session: {_e}")
                    except Exception as _e:
                        print(f"⚠️ Completion handling error: {_e}")
                    
                else:
                    # Fallback response if AI is not available
                    fallback_response = "Woops! Something went wrong. Please try again later."
                    
                    # Stream fallback response
                    words = fallback_response.split()
                    for i, word in enumerate(words):
                        chunk_data = {
                            "type": "content",
                            "content": word + (" " if i < len(words) - 1 else ""),
                            "chunk": i + 1,
                            "done": i == len(words) - 1
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                        await asyncio.sleep(0.1)
                    
                    # Save fallback response
                    fallback_message_id = await _save_message(
                        session_id=str(session_id),
                        user_id=str(user_id),
                        role="assistant",
                        content=fallback_response,
                        metadata={"is_authenticated": is_authenticated, "fallback": True}
                    )
                    
                    # Store fallback message embedding for RAG
                    if rag_service and fallback_message_id:
                        try:
                            # Use consistent user_id for RAG (same as storage)
                            rag_user_id = UUID(user_id) if is_authenticated else UUID(session_id)
                            await rag_service.embed_and_store_message(
                                message_id=UUID(fallback_message_id),
                                user_id=rag_user_id,
                                project_id=UUID(project_id) if project_id else None,
                                session_id=UUID(session_id),
                                content=fallback_response,
                                role="assistant",
                                metadata={"is_authenticated": is_authenticated, "fallback": True, "original_user_id": str(user_id)}
                            )
                            print(f"📚 Stored fallback message embedding: {fallback_message_id}")
                        except Exception as e:
                            print(f"⚠️ Failed to store fallback message embedding: {e}")
                
                # Update session last message time
                await _update_session_activity(str(session_id))
                
            except Exception as e:
                print(f"Error in chat generation: {e}")
                error_response = f"I apologize, but I'm having trouble generating a response right now. Please try again later."
                
                # Stream error response
                words = error_response.split()
                for i, word in enumerate(words):
                    chunk_data = {
                        "type": "content",
                        "content": word + (" " if i < len(words) - 1 else ""),
                        "chunk": i + 1,
                        "done": i == len(words) - 1,
                        "error": True
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                    await asyncio.sleep(0.1)
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "Access-Control-Allow-Origin": "*",
                "X-Session-ID": str(session_id),
                "X-User-ID": str(user_id)
            }
        )
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _extract_and_store_attachment_analysis_from_response(
    full_response: str,
    image_data_list: List[Dict],
    attachment_metadata: Dict[str, Dict[str, str]],  # {filename: {"file_type": str, "asset_id": str}}
    conversation_history: List[Dict],
    rag_context: Optional[Dict],
    project_id: str,
    user_id: str
):
    """
    Extract attachment analysis from model's single response.
    Model has full context: images + conversation history + RAG context.
    Extracts visual/attachment analysis and stores it for RAG.
    """
    try:
        supabase = get_supabase_client()
        if not supabase:
            print("⚠️ [ATTACHMENT ANALYSIS] Supabase not available, skipping storage")
            return
        
        # Build filename list to help section mapping
        filenames = [img.get("filename", "image.png") for img in image_data_list]
        
        # Try to split the assistant response into per-image sections using our enforced format
        # Sections like: "Image 1: <filename>" ... "Image 2: <filename>" ... followed by "Combined Summary"
        per_image_analysis: Dict[str, str] = {}
        try:
            import re
            # Create a pattern that finds "Image <index>: <anything>" headers
            header_regex = re.compile(r"(?i)(Image\s+(\d+)\s*:\s*(.*?))\n", re.M)
            matches = list(header_regex.finditer(full_response))
            if matches:
                # Append a sentinel end at end of text to slice last section
                spans = []
                for i, m in enumerate(matches):
                    start = m.start()
                    end = matches[i+1].start() if i+1 < len(matches) else len(full_response)
                    spans.append((m, start, end))
                for m, start, end in spans:
                    idx_str = m.group(2)
                    fname_header = m.group(3).strip()
                    section_text = full_response[start:end].strip()
                    try:
                        idx = int(idx_str) - 1
                        if 0 <= idx < len(filenames):
                            key = filenames[idx]
                            per_image_analysis[key] = section_text
                        else:
                            # Fallback: map by header filename if present
                            per_image_analysis[fname_header] = section_text
                    except:
                        per_image_analysis[fname_header] = section_text
        except Exception as e:
            print(f"⚠️ [ATTACHMENT ANALYSIS] Failed to split per-image sections: {e}")
        
        # For each image attachment, extract targeted analysis
        for img_data in image_data_list:
            filename = img_data.get("filename", "unknown")
            metadata = attachment_metadata.get(filename)
            
            file_type = (metadata or {}).get("file_type", "image")
            asset_id = (metadata or {}).get("asset_id")
            
            # Pick the most relevant analysis: dedicated section if available, otherwise full response
            analysis_text = per_image_analysis.get(filename) or full_response
            
            # Ensure we have an asset to tie analysis/embedding to
            if not asset_id:
                try:
                    from uuid import uuid4
                    new_asset_id = str(uuid4())
                    minimal_asset = {
                        "id": new_asset_id,
                        "project_id": str(project_id) if project_id else None,
                        "media_type": "image",
                        "uri": filename,
                        "processing_status": "processed",
                        "processing_metadata": {"source": "chat_inline", "filename": filename},
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                    supabase.table("assets").insert(minimal_asset).execute()
                    asset_id = new_asset_id
                    print(f"✅ [ATTACHMENT ANALYSIS] Created minimal asset {asset_id} for {filename}")
                except Exception as e:
                    print(f"⚠️ [ATTACHMENT ANALYSIS] Failed to create minimal asset for {filename}: {e}")
                    asset_id = None
            
            # Update asset analysis fields when we have an asset
            if asset_id:
                update_data = {
                    "analysis": analysis_text,
                    "analysis_type": file_type,
                    "analysis_data": {
                        "extracted_from": "gpt4o_analysis",
                        "filename": filename,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "file_type": file_type
                    }
                }
                try:
                    supabase.table("assets").update(update_data).eq("id", asset_id).execute()
                    print(f"✅ [ATTACHMENT ANALYSIS] Stored analysis for asset {asset_id} ({filename}, type: {file_type})")
                except Exception as e:
                    print(f"❌ [ATTACHMENT ANALYSIS] Failed to update asset {asset_id}: {e}")
            
            # Create an embedding for RAG storage regardless of asset update success
            try:
                from ..ai.embedding_service import get_embedding_service
                from ..ai.vector_storage import vector_storage

                embedding_text = f"Attachment Analysis ({filename}): {analysis_text}"
                embedding_service = get_embedding_service()
                if embedding_service:
                    embedding = await embedding_service.generate_query_embedding(embedding_text)
                    if embedding and asset_id:
                        await vector_storage.store_document_embedding(
                            asset_id=UUID(asset_id),
                            user_id=UUID(user_id),
                            project_id=UUID(project_id) if project_id else None,
                            document_type=file_type,
                            chunk_index=0,
                            chunk_text=embedding_text,
                            embedding=embedding,
                            metadata={
                                "filename": filename,
                                "file_type": file_type,
                                "embedding_model": "text-embedding-3-small",
                                "analysis": analysis_text
                            }
                        )
                        print(f"✅ [RAG] Created embedding for {file_type} analysis: {filename}")
                    elif not asset_id:
                        print(f"⚠️ [RAG] Skipped document_embedding due to missing asset_id (analysis still embedded via assistant message)")
                    else:
                        print(f"⚠️ [RAG] Failed to generate embedding for {filename}")
                else:
                    print(f"⚠️ [RAG] Embedding service not available")
            except Exception as e:
                print(f"⚠️ [RAG] Failed to create embedding for {filename}: {e}")
                import traceback
                print(traceback.format_exc())
    except Exception as e:
        print(f"❌ [ATTACHMENT ANALYSIS] Error in extract_and_store_attachment_analysis_from_response: {e}")
        import traceback
        print(traceback.format_exc())

async def _save_message(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict] = None
) -> str:
    """Save a message to the database"""
    supabase = get_supabase_client()
    
    message_id = str(uuid4())
    message_data = {
        "message_id": message_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id
    }
    
    supabase.table("chat_messages").insert(message_data).execute()
    return message_id

async def _get_conversation_history(session_id: str, user_id: str, limit: int = None) -> List[Dict]:
    """Get conversation history for context. If limit is None, fetches all messages."""
    supabase = get_supabase_client()
    
    # Build query
    query = supabase.table("chat_messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .eq("user_id", user_id)\
        .order("created_at", desc=False)
    
    # Only apply limit if specified
    if limit is not None:
        query = query.limit(limit)
    
    result = query.execute()
    
    if not result.data:
        return []
    
    # Convert to conversation format
    conversation = []
    for message in result.data:
        conversation.append({
            "role": message["role"],
            "content": message["content"],
            "timestamp": message["created_at"],
            "attached_files": message.get("metadata", {}).get("attached_files", [])
        })
    
    print(f"📚 Retrieved {len(conversation)} messages from conversation history for session {session_id}")
    return conversation

async def _update_session_activity(session_id: str):
    """Update session last message time"""
    supabase = get_supabase_client()
    
    supabase.table("sessions").update({
        "last_message_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("session_id", session_id).execute()

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Get messages for a specific session"""
    try:
        # Verify session exists and user has access
        session_info = await SimpleSessionManager.get_or_create_session(
            session_id=session_id,
            user_id=UUID(x_user_id) if x_user_id else None
        )
        
        messages = await _get_conversation_history(session_id, str(session_info["user_id"]), limit=50)
        
        return {
            "success": True,
            "session_id": session_id,
            "messages": messages,
            "is_authenticated": session_info["is_authenticated"]
        }
        
    except Exception as e:
        print(f"Error getting session messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

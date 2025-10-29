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

from ..models import ChatRequest
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
        conversation_history = await _get_conversation_history(str(session_id), str(user_id))
        
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
                    # IMPORTANT: Pass project_id=None to search across ALL user sessions
                    # This allows users to reference characters/stories from previous chats
                    # Story development benefits from cross-session context
                    rag_context = None
                    if rag_service:
                        try:
                            if is_authenticated:
                                # For authenticated users, use their actual user_id
                                rag_user_id = UUID(user_id)
                                print(f"🔍 Getting RAG context for user: {rag_user_id}, searching across ALL sessions (project_id=None)")
                            else:
                                # For anonymous users, use the special anonymous user ID
                                rag_user_id = UUID("00000000-0000-0000-0000-000000000000")
                                print(f"🔍 Getting RAG context for anonymous user: {rag_user_id}, searching across ALL sessions (project_id=None)")
                            
                            # Pass project_id=None to search across all user sessions
                            # This enables cross-session context for story development
                            rag_context = await rag_service.get_rag_context(
                                user_message=chat_request.text,
                                user_id=rag_user_id,
                                project_id=None,  # Search across ALL sessions, not just current project
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
                    if dossier_extractor and project_id and len(conversation_history) >= 2:
                        try:
                            # Check if we should update the dossier
                            should_update = await dossier_extractor.should_update_dossier(conversation_history)
                            if should_update:
                                print(f"📋 Updating dossier for project {project_id}")
                                # Extract new metadata from conversation
                                new_metadata = await dossier_extractor.extract_metadata(conversation_history)
                                
                                # Update dossier in database
                                from ..database.session_service_supabase import session_service
                                from ..models import DossierUpdate
                                
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
                                    
                                    # Check if story is complete and trigger script generation + email
                                    if ai_manager.is_story_complete(new_metadata):
                                        print(f"🎬 Story is complete! Generating script and sending email...")
                                        
                                        try:
                                            # Generate video script
                                            script_response = await ai_manager.generate_response(
                                                task_type=TaskType.SCRIPT,
                                                prompt="Generate video script",
                                                dossier_context=new_metadata
                                            )
                                            
                                            generated_script = script_response.get("response", "Script generation failed")
                                            print(f"✅ Script generated successfully")
                                            
                                            # Send email notification
                                            from ..services.email_service import email_service
                                            
                                            # Get user email and name from environment variables
                                            user_email = os.getenv("FROM_EMAIL", "user@example.com")
                                            user_name = os.getenv("USER_NAME", "Story Creator")
                                            
                                            # Get client emails (can be multiple, comma-separated)
                                            client_emails_str = os.getenv("CLIENT_EMAIL", "client@example.com")
                                            client_emails = [email.strip() for email in client_emails_str.split(",") if email.strip()]
                                            
                                            email_sent = await email_service.send_story_captured_email(
                                                user_email=user_email,
                                                user_name=user_name,
                                                story_data=new_metadata,
                                                generated_script=generated_script,
                                                project_id=str(project_id),
                                                client_emails=client_emails
                                            )
                                            
                                            if email_sent:
                                                print(f"✅ Email notification sent successfully")
                                            else:
                                                print(f"⚠️ Email notification failed")
                                                
                                        except Exception as e:
                                            print(f"⚠️ Script generation or email error: {e}")
                                    
                                else:
                                    print(f"⚠️ Failed to update dossier")
                        except Exception as e:
                            print(f"⚠️ Dossier update error: {e}")
                    
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
        
        # For each image attachment, extract analysis from the response
        for img_data in image_data_list:
            filename = img_data.get("filename", "unknown")
            metadata = attachment_metadata.get(filename)
            
            if not metadata:
                continue
            
            asset_id = metadata.get("asset_id")
            file_type = metadata.get("file_type", "image")
            
            if not asset_id:
                print(f"⚠️ [ATTACHMENT ANALYSIS] No asset_id found for {filename}, skipping")
                continue
            
            # Use the model's response as the analysis
            # The response contains visual details since model saw the image with full context
            # Combine response with conversation context for richer analysis
            analysis_text = full_response
            
            # Enhance analysis with context if available
            if conversation_history:
                recent_context = " | ".join([
                    f"{msg.get('role', 'unknown')}: {msg.get('content', '')[:50]}"
                    for msg in conversation_history[-3:]
                ])
                analysis_text = f"Context: {recent_context}\n\nAnalysis: {full_response}"
            
            if not analysis_text:
                print(f"⚠️ [ATTACHMENT ANALYSIS] Empty response for {filename}, skipping")
                continue
            
            # Store in assets table (generic for all file types)
            update_data = {
                "analysis": analysis_text,
                "analysis_type": file_type,  # Use file_type instead of hardcoded type
                "analysis_data": {
                    "extracted_from": "gpt4o_analysis" if file_type == "image" else "document_processor",
                    "filename": filename,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "file_type": file_type
                }
            }
            
            try:
                supabase.table("assets").update(update_data).eq("id", asset_id).execute()
                print(f"✅ [ATTACHMENT ANALYSIS] Stored analysis for asset {asset_id} ({filename}, type: {file_type})")
                
                # Create embedding for RAG storage (only for images - documents already embedded during upload)
                if file_type == "image":
                    try:
                        from ..ai.document_processor import document_processor
                        from ..ai.embedding_service import get_embedding_service
                        
                        if document_processor and hasattr(document_processor, 'vector_storage'):
                            # Use GPT-4o's analysis text for embedding
                            # This text contains rich semantic information guided by user's prompt
                            embedding_text = f"Attachment Analysis ({filename}): {analysis_text}"
                            
                            # Generate OpenAI text embedding from GPT-4o's analysis
                            embedding_service = get_embedding_service()
                            if embedding_service:
                                embedding = await embedding_service.generate_query_embedding(embedding_text)
                                
                                if embedding:
                                    # Store using document processor's vector storage
                                    await document_processor.vector_storage.store_document_embedding(
                                        asset_id=UUID(asset_id),
                                        user_id=UUID(user_id),
                                        project_id=UUID(project_id) if project_id else None,
                                        document_type=file_type,  # Generic: "image", "document", etc.
                                        chunk_index=0,
                                        chunk_text=embedding_text,
                                        embedding=embedding,  # OpenAI embedding (1536 dims)
                                        metadata={
                                            "filename": filename,
                                            "file_type": file_type,
                                            "embedding_model": "text-embedding-3-small",
                                            "analysis": analysis_text
                                        }
                                    )
                                    print(f"✅ [RAG] Created embedding for {file_type} analysis: {filename}")
                                else:
                                    print(f"⚠️ [RAG] Failed to generate embedding for {filename}")
                            else:
                                print(f"⚠️ [RAG] Embedding service not available")
                        else:
                            print(f"⚠️ [RAG] Document processor vector storage not available")
                    except Exception as e:
                        print(f"⚠️ [RAG] Failed to create embedding for {filename}: {e}")
                        import traceback
                        print(traceback.format_exc())
                else:
                    print(f"ℹ️ [RAG] Skipping embedding for {file_type} - already processed during upload")
                        
            except Exception as e:
                print(f"❌ [ATTACHMENT ANALYSIS] Failed to store analysis for {filename}: {e}")
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

async def _get_conversation_history(session_id: str, user_id: str, limit: int = 20) -> List[Dict]:
    """Get conversation history for context"""
    supabase = get_supabase_client()
    
    # Get more messages for better context and ensure user isolation
    result = supabase.table("chat_messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .eq("user_id", user_id)\
        .order("created_at", desc=False)\
        .limit(limit)\
        .execute()
    
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

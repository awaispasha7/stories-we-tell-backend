"""
Chat Sessions API
Handles user sessions, chat messages, and conversation persistence
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from typing import Optional, List
from uuid import UUID, uuid4
import json
import asyncio
from datetime import datetime

from ..models import (
    ChatRequest, ChatResponse, SessionSummary, ChatMessage,
    UserCreate, SessionCreate
)
from ..database.session_service_supabase import session_service

# Try to import AI components with error handling
try:
    from ..ai.models import ai_manager, TaskType
    from ..ai.dossier_extractor import dossier_extractor
    AI_AVAILABLE = True
    print("✅ AI components imported successfully")
except Exception as e:
    print(f"Warning: AI components not available: {e}")
    AI_AVAILABLE = False
    ai_manager = None
    TaskType = None
    dossier_extractor = None

router = APIRouter()

# Temporary user management (in production, use proper auth)
TEMP_USERS = {
    "demo-user": {
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "email": "demo@example.com",
        "display_name": "Demo User"
    }
}

def get_current_user_id(x_user_id: Optional[str] = Header(None)) -> UUID:
    """Get current user ID from header (temporary implementation)"""
    if not x_user_id:
        # Default to demo user for now
        return UUID("550e8400-e29b-41d4-a716-446655440000")
    
    try:
        return UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")


@router.post("/chat")
async def chat_with_session(
    chat_request: ChatRequest,
    user_id: UUID = Depends(get_current_user_id)
):
    """Chat endpoint with session support"""
    text = chat_request.text
    print(f"🔵 Received chat request from user {user_id}: '{text[:100]}...'")

    async def generate_stream():
        try:
            print(f"🟡 Starting response generation for: '{text[:50]}...'")

            # Get or create session
            session = await session_service.get_or_create_session(
                user_id=user_id,
                project_id=chat_request.project_id or uuid4(),
                session_id=chat_request.session_id,
                title=f"Chat Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            print(f"📋 Using session: {session.session_id}")

            # Get conversation history for context
            conversation_history = await session_service.get_session_context(
                session.session_id, user_id, context_limit=10
            )
            
            # Convert to the format expected by AI
            history_for_ai = [
                {"role": msg.role, "content": msg.content} 
                for msg in conversation_history
            ]
            
            print(f"📚 Conversation history length: {len(history_for_ai)} messages")

            # Store user message
            user_message = await session_service.create_message({
                "session_id": session.session_id,
                "role": "user",
                "content": text
            })

            # Check if AI is available
            if not AI_AVAILABLE or ai_manager is None or TaskType is None:
                print("⚠️ AI not available, using fallback response")
                reply = f"I received your message: '{text}'. I'm currently having trouble connecting to my AI backend, but I'm here to help with your story development! What kind of story are you working on?"
                model_used = "fallback"
                tokens_used = 0
            else:
                # Generate response using AI
                ai_response = await ai_manager.generate_response(
                    task_type=TaskType.CHAT,
                    prompt=text,
                    conversation_history=history_for_ai,
                    max_tokens=500,
                    temperature=0.7
                )

                print(f"🟢 AI Response received: {ai_response}")

                reply = ai_response.get("response", "Sorry, I couldn't generate a response.")
                model_used = ai_response.get("model_used", "unknown")
                tokens_used = ai_response.get("tokens_used", 0)

            print(f"📝 Reply content: '{reply[:100]}...'")
            print(f"🤖 Model used: {model_used}")
            print(f"🔢 Tokens used: {tokens_used}")

            # Stream the response word by word
            words = reply.split()
            print(f"📊 Streaming {len(words)} words")

            for i, word in enumerate(words):
                chunk = {
                    "type": "content",
                    "content": word + (" " if i < len(words) - 1 else ""),
                    "done": i == len(words) - 1
                }
                chunk_data = f"data: {json.dumps(chunk)}\n\n"
                print(f"📤 Sending chunk {i+1}/{len(words)}: '{word}'")
                yield chunk_data
                await asyncio.sleep(0.05)  # Slightly faster for better UX

            # Store assistant message
            assistant_message = await session_service.create_message({
                "session_id": session.session_id,
                "role": "assistant",
                "content": reply,
                "metadata": {
                    "model_used": model_used,
                    "tokens_used": tokens_used
                }
            })

            # Update dossier if needed (existing logic)
            if AI_AVAILABLE and dossier_extractor is not None:
                try:
                    should_update = await dossier_extractor.should_update_dossier(history_for_ai)
                    print(f"🔍 Should update dossier: {should_update}")
                    if should_update:
                        print("📊 Updating dossier using AI extractor...")
                        dossier_data = await dossier_extractor.extract_metadata(history_for_ai)
                        print(f"📊 Dossier data extracted: {dossier_data}")
                        
                        # Update dossier in database
                        # This would need to be implemented in the session service
                        # For now, we'll keep the existing Supabase logic
                except Exception as dossier_error:
                    print(f"⚠️ Dossier update error: {dossier_error}")

            # Send metadata chunk
            metadata = {
                "session_id": str(session.session_id),
                "message_id": str(assistant_message.message_id),
                "user_message_id": str(user_message.message_id),
                "project_id": str(session.project_id),
                "ai_model": model_used,
                "tokens_used": tokens_used
            }
            
            metadata_chunk = {
                "type": "metadata",
                "metadata": metadata
            }
            yield f"data: {json.dumps(metadata_chunk)}\n\n"

        except Exception as e:
            print(f"❌ Chat API error: {str(e)}")
            print(f"❌ Error type: {type(e).__name__}")
            import traceback
            print(f"❌ Full traceback: {traceback.format_exc()}")
            error_reply = f"I apologize, but I'm having trouble generating a response right now. Please try again later. Error: {str(e)}"

            # Stream error message
            words = error_reply.split()
            for i, word in enumerate(words):
                chunk = {
                    "type": "content",
                    "content": word + (" " if i < len(words) - 1 else ""),
                    "done": i == len(words) - 1
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.1)

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
        }
    )


@router.get("/sessions", response_model=List[SessionSummary])
async def get_user_sessions(
    limit: int = 10,
    user_id: UUID = Depends(get_current_user_id)
):
    """Get user's chat sessions"""
    try:
        sessions = await session_service.get_user_sessions(user_id, limit)
        return sessions
    except Exception as e:
        print(f"❌ Error fetching sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch sessions")


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessage])
async def get_session_messages(
    session_id: UUID,
    limit: int = 50,
    offset: int = 0,
    user_id: UUID = Depends(get_current_user_id)
):
    """Get messages for a specific session"""
    try:
        # Verify session ownership
        session = await session_service.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        messages = await session_service.get_session_messages(
            session_id, user_id, limit, offset
        )
        return messages
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch messages")


@router.put("/sessions/{session_id}/title")
async def update_session_title(
    session_id: UUID,
    title: str,
    user_id: UUID = Depends(get_current_user_id)
):
    """Update session title"""
    try:
        session = await session_service.update_session_title(session_id, user_id, title)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"message": "Session title updated successfully", "session": session}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating session title: {e}")
        raise HTTPException(status_code=500, detail="Failed to update session title")


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_id)
):
    """Delete (deactivate) a session"""
    try:
        success = await session_service.deactivate_session(session_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting session: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete session")


@router.post("/users", response_model=dict)
async def create_user(user_data: UserCreate):
    """Create a new user (temporary endpoint)"""
    try:
        user = await session_service.create_user(user_data)
        return {"message": "User created successfully", "user": user}
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user")


@router.get("/users/me", response_model=dict)
async def get_current_user(user_id: UUID = Depends(get_current_user_id)):
    """Get current user information"""
    try:
        user = await session_service.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching user: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user")

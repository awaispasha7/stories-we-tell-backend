"""
Chat Sessions API
Handles user sessions, chat messages, and conversation persistence
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict
from uuid import UUID, uuid4
import json
import asyncio
import time
from datetime import datetime, timedelta

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

# Anonymous session management
ANONYMOUS_SESSIONS: Dict[str, Dict] = {}
ANONYMOUS_SESSION_TIMEOUT = 30 * 60  # 30 minutes in seconds

async def ensure_anonymous_user_exists(session_id: str) -> str:
    """Create or get a temporary user for anonymous sessions"""
    try:
        # Check if we already have a user for this session
        result = supabase.table("users").select("user_id").eq("email", f"anonymous_{session_id}@temp.local").execute()
        
        if result.data:
            return result.data[0]["user_id"]
        
        # Create a new temporary user
        temp_user_data = {
            "email": f"anonymous_{session_id}@temp.local",
            "display_name": f"Anonymous User {session_id[:8]}",
            "avatar_url": None
        }
        
        result = supabase.table("users").insert(temp_user_data).execute()
        if result.data:
            user_id = result.data[0]["user_id"]
            print(f"🆕 Created temporary user for anonymous session: {user_id}")
            return user_id
        else:
            raise Exception("Failed to create temporary user")
            
    except Exception as e:
        print(f"❌ Error creating anonymous user: {e}")
        # Fallback to a generic anonymous user ID
        return "00000000-0000-0000-0000-000000000000"

class AnonymousSession:
    """Manages anonymous user sessions with timeout"""
    
    @staticmethod
    def create_session() -> str:
        """Create a new anonymous session"""
        session_id = str(uuid4())
        ANONYMOUS_SESSIONS[session_id] = {
            "created_at": time.time(),
            "last_activity": time.time(),
            "messages": [],
            "project_id": str(uuid4())
        }
        print(f"🆕 Created anonymous session: {session_id}")
        return session_id
    
    @staticmethod
    def get_session(session_id: str) -> Optional[Dict]:
        """Get anonymous session if it exists and hasn't expired"""
        if session_id not in ANONYMOUS_SESSIONS:
            return None
        
        session = ANONYMOUS_SESSIONS[session_id]
        current_time = time.time()
        
        # Check if session has expired
        if current_time - session["last_activity"] > ANONYMOUS_SESSION_TIMEOUT:
            print(f"⏰ Anonymous session expired: {session_id}")
            del ANONYMOUS_SESSIONS[session_id]
            return None
        
        # Update last activity
        session["last_activity"] = current_time
        return session
    
    @staticmethod
    def update_session(session_id: str, messages: List[Dict]) -> bool:
        """Update session messages"""
        session = AnonymousSession.get_session(session_id)
        if session:
            session["messages"] = messages
            return True
        return False
    
    @staticmethod
    def cleanup_expired_sessions():
        """Clean up expired anonymous sessions"""
        current_time = time.time()
        expired_sessions = [
            session_id for session_id, session in ANONYMOUS_SESSIONS.items()
            if current_time - session["last_activity"] > ANONYMOUS_SESSION_TIMEOUT
        ]
        
        for session_id in expired_sessions:
            del ANONYMOUS_SESSIONS[session_id]
            print(f"🧹 Cleaned up expired session: {session_id}")

# Temporary user management (in production, use proper auth)
TEMP_USERS = {
    "demo-user": {
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "email": "demo@example.com",
        "display_name": "Demo User"
    }
}

async def get_or_create_default_user() -> UUID:
    """Get the first available user or create a default one"""
    try:
        # Try to get the first user from the database
        users = session_service.get_all_users()
        if users and len(users) > 0:
            user_id = users[0].user_id
            print(f"✅ Using existing user: {user_id}")
            return user_id
    except Exception as e:
        print(f"⚠️ Could not fetch users: {e}")
    
    # If no users exist, create a default one
    try:
        user_data = {
            "email": "default@example.com",
            "display_name": "Default User"
        }
        user = session_service.create_user(user_data)
        print(f"✅ Created default user: {user.user_id}")
        return user.user_id
    except Exception as e:
        print(f"❌ Failed to create default user: {e}")
        raise HTTPException(status_code=500, detail="No users available and cannot create default user")

def get_current_user_id(x_user_id: Optional[str] = Header(None), x_session_id: Optional[str] = Header(None)) -> tuple[Optional[UUID], Optional[str]]:
    """Get current user ID and session ID from headers"""
    # If user is authenticated, use their user ID
    if x_user_id:
        try:
            return UUID(x_user_id), x_session_id
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    # If no user ID but has session ID, it's an anonymous session
    if x_session_id:
        return None, x_session_id
    
    # No user ID and no session ID - create new anonymous session
    return None, None


@router.post("/chat")
async def chat_with_session(
    chat_request: ChatRequest,
    user_session: tuple[Optional[UUID], Optional[str]] = Depends(get_current_user_id)
):
    """Chat endpoint with session support for both authenticated and anonymous users"""
    user_id, session_id = user_session
    
    # Handle anonymous sessions
    if user_id is None:
        if session_id is None:
            # Create new anonymous session
            session_id = AnonymousSession.create_session()
            print(f"🆕 Created new anonymous session: {session_id}")
        else:
            # Check if existing anonymous session is valid
            session = AnonymousSession.get_session(session_id)
            if session is None:
                # Session expired, create new one
                session_id = AnonymousSession.create_session()
                print(f"⏰ Session expired, created new anonymous session: {session_id}")
            else:
                print(f"✅ Using existing anonymous session: {session_id}")
    else:
        print(f"✅ Using authenticated user: {user_id}")
    
    text = chat_request.text
    print(f"🔵 Received chat request: '{text[:100]}...'")

    async def generate_stream():
        try:
            print(f"🟡 Starting response generation for: '{text[:50]}...'")

            # Handle session based on user type
            if user_id is not None:
                # Authenticated user - use database session
                session = session_service.get_or_create_session(
                    user_id=user_id,
                    project_id=chat_request.project_id or uuid4(),
                    session_id=chat_request.session_id,
                    title=f"Chat Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                print(f"📋 Using authenticated session: {session.session_id}")
                
                # Get conversation history for context
                conversation_history = session_service.get_session_context(
                    session.session_id, user_id, context_limit=10
                )
            else:
                # Anonymous user - use in-memory session AND create database session
                anonymous_session = AnonymousSession.get_session(session_id)
                if not anonymous_session:
                    raise HTTPException(status_code=410, detail="Anonymous session expired. Please sign in to continue.")
                
                print(f"📋 Using anonymous session: {session_id}")
                
                # Create temporary user for this anonymous session
                temp_user_id = await ensure_anonymous_user_exists(session_id)
                
                # Create database session for anonymous user
                session = session_service.get_or_create_session(
                    user_id=temp_user_id,
                    project_id=chat_request.project_id or uuid4(),
                    session_id=session_id,
                    title=f"Anonymous Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                
                # Get conversation history from anonymous session
                conversation_history = [
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in anonymous_session["messages"]
                ]
            
            # Convert to the format expected by AI
            if user_id is not None:
                # Authenticated user - convert from database objects
                history_for_ai = [
                    {"role": msg.role, "content": msg.content} 
                    for msg in conversation_history
                ]
            else:
                # Anonymous user - already in correct format
                history_for_ai = conversation_history
            
            print(f"📚 Conversation history length: {len(history_for_ai)} messages")
            if history_for_ai:
                print(f"📚 Last few messages in history:")
                for i, msg in enumerate(history_for_ai[-3:]):
                    print(f"  {i+1}. {msg['role']}: {msg['content'][:50]}...")

            # Store user message based on user type
            if user_id is not None:
                # Authenticated user - store in database
                user_message = session_service.create_message({
                    "session_id": session.session_id,
                    "role": "user",
                    "content": text
                })
            else:
                # Anonymous user - store in database (temp_user_id already created above)
                user_message = session_service.create_message({
                    "session_id": session.session_id,
                    "role": "user",
                    "content": text
                })
                
                # Also store in memory for immediate access
                anonymous_session["messages"].append({
                    "role": "user",
                    "content": text,
                    "timestamp": time.time()
                })
                
                # Update conversation history for anonymous users after storing the message
                conversation_history = [
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in anonymous_session["messages"]
                ]
                history_for_ai = conversation_history

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

            # Store assistant message based on user type
            if user_id is not None:
                # Authenticated user - store in database
                assistant_message = session_service.create_message({
                    "session_id": session.session_id,
                    "role": "assistant",
                    "content": reply,
                    "metadata": {
                        "model_used": model_used,
                        "tokens_used": tokens_used
                    }
                })
            else:
                # Anonymous user - store in database AND memory
                assistant_message = session_service.create_message({
                    "session_id": session.session_id,
                    "role": "assistant",
                    "content": reply,
                    "metadata": {
                        "model_used": model_used,
                        "tokens_used": tokens_used
                    }
                })
                
                # Also store in memory for immediate access
                anonymous_session["messages"].append({
                    "role": "assistant",
                    "content": reply,
                    "timestamp": time.time(),
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
            if user_id is not None:
                # Authenticated user metadata
                metadata = {
                    "session_id": str(session.session_id),
                    "message_id": str(assistant_message.message_id),
                    "user_message_id": str(user_message.message_id),
                    "project_id": str(session.project_id),
                    "ai_model": model_used,
                    "tokens_used": tokens_used,
                    "user_type": "authenticated"
                }
            else:
                # Anonymous user metadata
                metadata = {
                    "session_id": session_id,
                    "project_id": anonymous_session["project_id"],
                    "ai_model": model_used,
                    "tokens_used": tokens_used,
                    "user_type": "anonymous",
                    "session_expires_at": anonymous_session["last_activity"] + ANONYMOUS_SESSION_TIMEOUT
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
        sessions = session_service.get_user_sessions(user_id, limit)
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
        session = session_service.get_session(session_id, user_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        messages = session_service.get_session_messages(
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
        session = session_service.update_session_title(session_id, user_id, title)
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
        success = session_service.deactivate_session(session_id, user_id)
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
        # If user_id is provided, use the auth-specific method
        if hasattr(user_data, 'user_id') and user_data.user_id:
            user = session_service.create_user_from_auth(
                auth_user_id=user_data.user_id,
                email=user_data.email,
                display_name=user_data.display_name,
                avatar_url=user_data.avatar_url
            )
        else:
            user = session_service.create_user(user_data)
        return {"message": "User created successfully", "user": user}
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user")


@router.get("/users/me", response_model=dict)
async def get_current_user(user_id: UUID = Depends(get_current_user_id)):
    """Get current user information"""
    try:
        user = session_service.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching user: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user")


@router.post("/anonymous-session")
async def create_anonymous_session():
    """Create a new anonymous session for users who haven't signed in"""
    try:
        session_id = AnonymousSession.create_session()
        session = AnonymousSession.get_session(session_id)
        
        return {
            "session_id": session_id,
            "project_id": session["project_id"],
            "expires_at": session["last_activity"] + ANONYMOUS_SESSION_TIMEOUT,
            "message": "Anonymous session created. Sign in to save your chats permanently."
        }
    except Exception as e:
        print(f"❌ Error creating anonymous session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create anonymous session")


@router.get("/anonymous-session/{session_id}")
async def get_anonymous_session(session_id: str):
    """Get anonymous session details"""
    try:
        session = AnonymousSession.get_session(session_id)
        if not session:
            raise HTTPException(status_code=410, detail="Anonymous session expired. Please sign in to continue.")
        
        return {
            "session_id": session_id,
            "project_id": session["project_id"],
            "expires_at": session["last_activity"] + ANONYMOUS_SESSION_TIMEOUT,
            "messages_count": len(session["messages"]),
            "created_at": session["created_at"],
            "last_activity": session["last_activity"]
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting anonymous session: {e}")
        raise HTTPException(status_code=500, detail="Failed to get anonymous session")

@router.post("/migrate-anonymous-session")
async def migrate_anonymous_session(
    session_id: str,
    new_user_id: str
):
    """Migrate anonymous session data to a real user account"""
    try:
        # Get the temporary user ID for this session
        temp_user_result = supabase.table("users").select("user_id").eq("email", f"anonymous_{session_id}@temp.local").execute()
        
        if not temp_user_result.data:
            raise HTTPException(status_code=404, detail="Anonymous session not found")
        
        temp_user_id = temp_user_result.data[0]["user_id"]
        
        # Update all sessions to use the new user ID
        supabase.table("sessions").update({"user_id": new_user_id}).eq("user_id", temp_user_id).execute()
        
        # Update all messages to use the new user ID
        supabase.table("chat_messages").update({"user_id": new_user_id}).eq("user_id", temp_user_id).execute()
        
        # Update all turns to use the new user ID
        supabase.table("turns").update({"user_id": new_user_id}).eq("user_id", temp_user_id).execute()
        
        # Update all dossiers to use the new user ID
        supabase.table("dossier").update({"user_id": new_user_id}).eq("user_id", temp_user_id).execute()
        
        # Update all user_projects to use the new user ID
        supabase.table("user_projects").update({"user_id": new_user_id}).eq("user_id", temp_user_id).execute()
        
        # Delete the temporary user
        supabase.table("users").delete().eq("user_id", temp_user_id).execute()
        
        # Clean up the anonymous session from memory
        if session_id in ANONYMOUS_SESSIONS:
            del ANONYMOUS_SESSIONS[session_id]
        
        return {"message": "Anonymous session data migrated successfully"}
        
    except Exception as e:
        print(f"❌ Error migrating anonymous session: {e}")
        raise HTTPException(status_code=500, detail="Failed to migrate anonymous session data")

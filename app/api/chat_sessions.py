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
    UserCreate, SessionCreate, ChatMessageCreate, MigrationRequest
)
from ..database.session_service_supabase import session_service
from ..database.supabase import get_supabase_client

# Try to import AI components with error handling
try:
    from ..ai.models import ai_manager, TaskType
    from ..ai.dossier_extractor import dossier_extractor
    AI_AVAILABLE = True
    print(" AI components imported successfully")
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
CLEANUP_IN_PROGRESS = False  # Global lock to prevent concurrent cleanup

async def ensure_anonymous_user_exists(session_id: str) -> str:
    """Create or get a temporary user for anonymous sessions"""
    try:
        # Check if we already have a user for this session
        supabase = get_supabase_client()
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
        print(f"[DEBUG] User creation result: {result}")
        if result.data:
            user_id = result.data[0]["user_id"]
            print(f"[SUCCESS] Created temporary user for anonymous session: {user_id}")
            return user_id
        else:
            print(f"[ERROR] No data returned from user creation: {result}")
            raise Exception("Failed to create temporary user")
            
    except Exception as e:
        print(f"[ERROR] Error creating anonymous user: {e}")
        # Try to get any existing user as fallback
        try:
            fallback_result = supabase.table("users").select("user_id").limit(1).execute()
            if fallback_result.data:
                fallback_user_id = fallback_result.data[0]["user_id"]
                print(f"[FALLBACK] Using fallback user: {fallback_user_id}")
                return fallback_user_id
        except Exception as fallback_error:
            print(f"[ERROR] Fallback user lookup failed: {fallback_error}")
        
        # If all else fails, raise the error
        raise HTTPException(status_code=500, detail="Unable to create or find user for anonymous session")

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
        print(f" Created anonymous session: {session_id}")
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
            print(f" Anonymous session expired: {session_id}")
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
            print(f" Cleaned up expired session: {session_id}")
    
    @staticmethod
    async def cleanup_expired_anonymous_users():
        """Delete expired anonymous users and their associated data from Supabase"""
        global CLEANUP_IN_PROGRESS
        
        # Prevent concurrent cleanup operations
        if CLEANUP_IN_PROGRESS:
            print(" Cleanup already in progress, skipping...")
            return
        
        CLEANUP_IN_PROGRESS = True
        try:
            supabase = get_supabase_client()
            
            # Get all anonymous users (those with email pattern anonymous_*@temp.local)
            # Add a safety buffer - only clean up users that are significantly past timeout
            safety_buffer = 5 * 60  # 5 minutes safety buffer
            cutoff_time = datetime.now() - timedelta(seconds=ANONYMOUS_SESSION_TIMEOUT + safety_buffer)
            
            # Get users with their last activity from sessions table
            result = supabase.table("users").select("user_id, email, created_at").like("email", "anonymous_%@temp.local").execute()
            
            if not result.data:
                print("No anonymous users found for cleanup")
                return
            
            deleted_count = 0
            
            for user in result.data:
                user_id = user["user_id"]
                email = user["email"]
                created_at = datetime.fromisoformat(user["created_at"].replace('Z', '+00:00'))
                
                # Check if user has recent activity (last message or session activity)
                # Get the most recent activity for this user
                recent_activity = None
                
                # Check for recent chat messages
                messages_result = supabase.table("chat_messages").select("created_at").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
                if messages_result.data:
                    recent_activity = datetime.fromisoformat(messages_result.data[0]["created_at"].replace('Z', '+00:00'))
                
                # Check for recent session activity
                sessions_result = supabase.table("sessions").select("last_message_at, updated_at").eq("user_id", user_id).order("updated_at", desc=True).limit(1).execute()
                if sessions_result.data:
                    session_data = sessions_result.data[0]
                    session_activity = None
                    if session_data.get("last_message_at"):
                        session_activity = datetime.fromisoformat(session_data["last_message_at"].replace('Z', '+00:00'))
                    elif session_data.get("updated_at"):
                        session_activity = datetime.fromisoformat(session_data["updated_at"].replace('Z', '+00:00'))
                    
                    if session_activity and (not recent_activity or session_activity > recent_activity):
                        recent_activity = session_activity
                
                # Use the most recent activity or creation time if no activity found
                last_activity = recent_activity or created_at
                
                # Only clean up users that are significantly past timeout (with safety buffer)
                # AND have no recent activity
                if created_at < cutoff_time and last_activity < cutoff_time:
                    print(f" Cleaning up expired anonymous user: {email} (created: {created_at}, last activity: {last_activity})")
                    
                    try:
                        # Use a transaction-like approach with individual error handling
                        # Delete in order to respect foreign key constraints
                        # Keep chat messages and turns for data analysis - just anonymize them
                        
                        # 1. Anonymize chat messages (set user_id to NULL)
                        supabase.table("chat_messages").update({"user_id": None}).eq("user_id", user_id).execute()
                        print(f"   Anonymized chat messages for user {user_id}")
                        
                        # 2. Anonymize turns (set user_id to NULL)
                        supabase.table("turns").update({"user_id": None}).eq("user_id", user_id).execute()
                        print(f"   Anonymized turns for user {user_id}")
                        
                        # 3. Delete dossier (this is user-specific)
                        supabase.table("dossier").delete().eq("user_id", user_id).execute()
                        print(f"   Deleted dossier for user {user_id}")
                        
                        # 4. Delete user_projects
                        supabase.table("user_projects").delete().eq("user_id", user_id).execute()
                        print(f"   Deleted user_projects for user {user_id}")
                        
                        # 5. Delete sessions
                        supabase.table("sessions").delete().eq("user_id", user_id).execute()
                        print(f"   Deleted sessions for user {user_id}")
                        
                        # 6. Finally delete the user
                        supabase.table("users").delete().eq("user_id", user_id).execute()
                        print(f"   Deleted user {user_id}")
                        
                        deleted_count += 1
                        print(f" Successfully cleaned up anonymous user: {email} (messages preserved)")
                        
                    except Exception as user_cleanup_error:
                        print(f" Error cleaning up user {user_id}: {user_cleanup_error}")
                        continue
                else:
                    if created_at >= cutoff_time:
                        print(f" User {email} not yet eligible for cleanup (created: {created_at})")
                    elif last_activity >= cutoff_time:
                        print(f" User {email} has recent activity (last activity: {last_activity})")
                    else:
                        print(f" User {email} not eligible for cleanup (created: {created_at}, last activity: {last_activity})")
            
            print(f"Database cleanup completed: {deleted_count} expired anonymous users removed")
            
        except Exception as e:
            print(f"Error during database cleanup: {e}")
        finally:
            # Always release the lock
            CLEANUP_IN_PROGRESS = False

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
            print(f"Using existing user: {user_id}")
            return user_id
    except Exception as e:
        print(f"Could not fetch users: {e}")
    
    # If no users exist, create a default one
    try:
        user_data = {
            "email": "default@example.com",
            "display_name": "Default User"
        }
        user = session_service.create_user(user_data)
        print(f"Created default user: {user.user_id}")
        return user.user_id
    except Exception as e:
        print(f"Failed to create default user: {e}")
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

def get_user_id_only(x_user_id: Optional[str] = Header(None)) -> Optional[UUID]:
    """Get current user ID from headers (for endpoints that only need user ID)"""
    if x_user_id:
        try:
            return UUID(x_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
    return None


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
            print(f" Created new anonymous session: {session_id}")
        else:
            # Check if existing anonymous session is valid
            session = AnonymousSession.get_session(session_id)
            if session is None:
                # Session expired, create new one
                session_id = AnonymousSession.create_session()
                print(f" Session expired, created new anonymous session: {session_id}")
            else:
                print(f" Using existing anonymous session: {session_id}")
    else:
        print(f"Using authenticated user: {user_id}")
    
    text = chat_request.text
    print(f" Received chat request: '{text[:100]}...'")

    async def generate_stream():
        try:
            print(f"Starting response generation for: '{text[:50]}...'")

            # Initialize temp_user_id to None for authenticated users
            temp_user_id = None
            
            # Handle session based on user type
            if user_id is not None:
                # Authenticated user - use database session
                # Use first message as title, or default if no message yet
                session_title = text[:50] + "..." if len(text) > 50 else text
                session = session_service.get_or_create_session(
                    user_id=user_id,
                    project_id=chat_request.project_id or uuid4(),
                    session_id=chat_request.session_id,
                    title=session_title
                )
                print(f"Using authenticated session: {session.session_id}")
                
                # Get conversation history for context
                conversation_history = session_service.get_session_context(
                    session.session_id, user_id, context_limit=10
                )
            else:
                # Anonymous user - use in-memory session AND create database session
                anonymous_session = AnonymousSession.get_session(session_id)
                if not anonymous_session:
                    raise HTTPException(status_code=410, detail="Anonymous session expired. Please sign in to continue.")
                
                print(f"Using anonymous session: {session_id}")
                
                # Create temporary user for this anonymous session
                try:
                    temp_user_id = await ensure_anonymous_user_exists(session_id)
                    
                    # Create database session for anonymous user
                    print(f"[DEBUG] Creating session with user_id: {temp_user_id}, session_id: {session_id}")
                    # Use first message as title for anonymous sessions too
                    session_title = text[:50] + "..." if len(text) > 50 else text
                    session = session_service.get_or_create_session(
                        user_id=temp_user_id,
                        project_id=chat_request.project_id or uuid4(),
                        session_id=session_id,
                        title=session_title
                    )
                    print(f"[SUCCESS] Created database session for anonymous user: {temp_user_id}, session: {session.session_id}")
                    print(f"[DEBUG] Session object type: {type(session)}, has session_id attr: {hasattr(session, 'session_id')}")
                except Exception as session_error:
                    print(f"[ERROR] Failed to create database session for anonymous user: {session_error}")
                    # Create a minimal session object for compatibility
                    class MinimalSession:
                        def __init__(self, session_id):
                            self.session_id = session_id
                    session = MinimalSession(session_id)
                    print(f"[DEBUG] Created minimal session with ID: {session.session_id}")
                
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
            
            print(f" Conversation history length: {len(history_for_ai)} messages")
            if history_for_ai:
                print(f" Last few messages in history:")
                for i, msg in enumerate(history_for_ai[-3:]):
                    print(f"  {i+1}. {msg['role']}: {msg['content'][:50]}...")

            print(f"STARTING TURN CREATION PROCESS")
            # Create a turn ID for this user/assistant exchange before storing messages
            turn_id = uuid4()
            print(f"Generated turn_id: {turn_id}")

            # Create turn record FIRST before storing messages
            try:
                turn_record = {
                    "turn_id": str(turn_id),
                    "session_id": str(session.session_id),
                    "user_id": str(user_id) if user_id else str(temp_user_id),
                    "project_id": str(session.project_id),
                    "raw_text": text,
                    "normalized_json": {
                        "response_text": "",  # Will be updated after AI response
                        "ai_model": "",
                        "tokens_used": 0,
                        "timestamp": datetime.now().isoformat()
                    }
                }
                
                supabase = get_supabase_client()
                print(f"Creating turn record: {turn_record}")
                print(f"User ID: {user_id}, Temp User ID: {temp_user_id}")
                print(f"Session ID: {session.session_id}")
                
                turn_result = supabase.table("turns").insert([turn_record]).execute()
                print(f"Turn insert result: {turn_result}")
                
                if turn_result.data:
                    print(f"SUCCESS: Created turn record: {turn_id}")
                else:
                    print(f"WARNING: Failed to create turn record: {turn_result}")
                    if hasattr(turn_result, 'error') and turn_result.error:
                        print(f"WARNING: Turn result error: {turn_result.error}")
                    else:
                        print(f"WARNING: No error attribute in turn_result")
                    
                    # Try to create turn record without user_id if it's causing issues
                    if not user_id:
                        print(f"Retrying turn creation without user_id...")
                        turn_record_no_user = {**turn_record}
                        turn_record_no_user["user_id"] = None
                        retry_result = supabase.table("turns").insert([turn_record_no_user]).execute()
                        print(f"Retry result: {retry_result}")
                        if retry_result.data:
                            print(f"SUCCESS: Created turn record without user_id: {turn_id}")
                        else:
                            raise Exception(f"Failed to create turn record even without user_id: {retry_result}")
                    else:
                        raise Exception(f"Failed to create turn record: {turn_result}")
            except Exception as turn_error:
                print(f"ERROR: Failed to create turn record: {turn_error}")
                raise Exception(f"Could not create turn record: {turn_error}")

            # Store user message based on user type
            if user_id is not None:
                # Authenticated user - store in database
                print(f"Storing user message with turn_id: {turn_id}")
                print(f"About to create user message with session_id: {session.session_id}")
                user_message = session_service.create_message(ChatMessageCreate(
                    session_id=session.session_id,
                    turn_id=turn_id,
                    role="user",
                    content=text
                ))
                print(f" User message stored with turn_id: {turn_id}")
            else:
                # Anonymous user - store in database (temp_user_id already created above)
                try:
                    print(f"[DEBUG] Storing user message: session_id={session.session_id}, content='{text[:50]}...'")
                    print(f"[DEBUG] Session object before message storage: type={type(session)}, session_id={getattr(session, 'session_id', 'NO_ATTR')}")
                    user_message = session_service.create_message(ChatMessageCreate(
                        session_id=session.session_id,
                        turn_id=turn_id,
                        role="user",
                        content=text
                    ))
                    print(f"[SUCCESS] Stored user message in database for anonymous session: {user_message}")
                except Exception as db_error:
                    print(f"[ERROR] Failed to store user message in database: {db_error}")
                    # Continue with in-memory storage only
                
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
                print("AI not available, using fallback response")
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

                print(f" AI Response received: {ai_response}")

                reply = ai_response.get("response", "Sorry, I couldn't generate a response.")
                model_used = ai_response.get("model_used", "unknown")
                tokens_used = ai_response.get("tokens_used", 0)

            print(f" Reply content: '{reply[:100]}...'")
            print(f" Model used: {model_used}")
            print(f" Tokens used: {tokens_used}")

            # Stream the response word by word
            words = reply.split()
            print(f" Streaming {len(words)} words")

            for i, word in enumerate(words):
                chunk = {
                    "type": "content",
                    "content": word + (" " if i < len(words) - 1 else ""),
                    "done": i == len(words) - 1
                }
                chunk_data = f"data: {json.dumps(chunk)}\n\n"
                print(f" Sending chunk {i+1}/{len(words)}: '{word}'")
                yield chunk_data
                await asyncio.sleep(0.05)  # Slightly faster for better UX

            # Store assistant message based on user type
            if user_id is not None:
                # Authenticated user - store in database
                print(f" Storing assistant message with turn_id: {turn_id}")
                assistant_message = session_service.create_message(ChatMessageCreate(
                    session_id=session.session_id,
                    turn_id=turn_id,
                    role="assistant",
                    content=reply,
                    metadata={
                        "model_used": model_used,
                        "tokens_used": tokens_used
                    }
                ))
                print(f" Assistant message stored with turn_id: {turn_id}")
            else:
                # Anonymous user - store in database AND memory
                try:
                    assistant_message = session_service.create_message(ChatMessageCreate(
                        session_id=session.session_id,
                        turn_id=turn_id,
                        role="assistant",
                        content=reply,
                        metadata={
                            "model_used": model_used,
                            "tokens_used": tokens_used
                        }
                    ))
                    print(f" Stored assistant message in database for anonymous session")
                except Exception as db_error:
                    print(f" Failed to store assistant message in database: {db_error}")
                    # Continue with in-memory storage only
                
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

            # Update turn record with AI response data
            try:
                supabase = get_supabase_client()
                update_data = {
                    "normalized_json": {
                        "response_text": reply,
                        "ai_model": model_used,
                        "tokens_used": tokens_used,
                        "timestamp": datetime.now().isoformat()
                    }
                }
                print(f" Updating turn record with AI response: {turn_id}")
                update_result = supabase.table("turns").update(update_data).eq("turn_id", str(turn_id)).execute()
                if update_result.data:
                    print(f" Updated turn record with AI response: {turn_id}")
                else:
                    print(f" Failed to update turn record: {update_result}")
            except Exception as update_error:
                print(f" Failed to update turn record (non-critical): {update_error}")

            # Update dossier if needed (existing logic)
            if AI_AVAILABLE and dossier_extractor is not None:
                try:
                    should_update = await dossier_extractor.should_update_dossier(history_for_ai)
                    print(f" Should update dossier: {should_update}")
                    if should_update:
                        print(" Updating dossier using AI extractor...")
                        dossier_data = await dossier_extractor.extract_metadata(history_for_ai)
                        print(f" Dossier data extracted: {dossier_data}")
                        
                        # Update dossier in database
                        # This would need to be implemented in the session service
                        # For now, we'll keep the existing Supabase logic
                except Exception as dossier_error:
                    print(f" Dossier update error: {dossier_error}")

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
            print(f" Chat API error: {str(e)}")
            print(f" Error type: {type(e).__name__}")
            import traceback
            print(f" Full traceback: {traceback.format_exc()}")
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
    user_id: Optional[UUID] = Depends(get_user_id_only)
):
    """Get user's chat sessions"""
    try:
        if not user_id:
            raise HTTPException(status_code=401, detail="User authentication required")
        sessions = session_service.get_user_sessions(user_id, limit)
        return sessions
    except Exception as e:
        print(f" Error fetching sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch sessions")


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessage])
async def get_session_messages(
    session_id: UUID,
    limit: int = 50,
    offset: int = 0,
    user_id: Optional[UUID] = Depends(get_user_id_only)
):
    """Get messages for a specific session"""
    try:
        if not user_id:
            raise HTTPException(status_code=401, detail="User authentication required")
        
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
        print(f" Error fetching messages: {e}")
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
        print(f" Error updating session title: {e}")
        raise HTTPException(status_code=500, detail="Failed to update session title")


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: UUID,
    user_id: UUID = Depends(get_user_id_only)
):
    """Delete (deactivate) a session"""
    try:
        print(f" Attempting to delete session {session_id} for user {user_id}")
        success = session_service.deactivate_session(session_id, user_id)
        print(f" Deactivate session result: {success}")
        if not success:
            print(f" Session {session_id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Session not found")
        print(f" Session {session_id} deleted successfully")
        return {"message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f" Error deleting session {session_id}: {e}")
        print(f" Error type: {type(e)}")
        import traceback
        print(f" Traceback: {traceback.format_exc()}")
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
        print(f" Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user")


@router.get("/users/me", response_model=dict)
async def get_current_user(user_id: Optional[UUID] = Depends(get_user_id_only)):
    """Get current user information"""
    try:
        if not user_id:
            raise HTTPException(status_code=401, detail="User authentication required")
        user = session_service.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching user: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user")


@router.post("/anonymous-session")
async def create_anonymous_session():
    """Create a new anonymous session for users who haven't signed in"""
    try:
        # Clean up expired anonymous users from database
        await AnonymousSession.cleanup_expired_anonymous_users()
        
        # Clean up expired in-memory sessions
        AnonymousSession.cleanup_expired_sessions()
        
        session_id = AnonymousSession.create_session()
        session = AnonymousSession.get_session(session_id)
        
        return {
            "session_id": session_id,
            "project_id": session["project_id"],
            "expires_at": session["last_activity"] + ANONYMOUS_SESSION_TIMEOUT,
            "message": "Anonymous session created. Sign in to save your chats permanently."
        }
    except Exception as e:
        print(f" Error creating anonymous session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create anonymous session")

@router.post("/cleanup-expired-sessions")
async def cleanup_expired_sessions():
    """Manually trigger cleanup of expired anonymous sessions and users"""
    try:
        # Clean up in-memory sessions
        AnonymousSession.cleanup_expired_sessions()
        
        # Clean up database records
        await AnonymousSession.cleanup_expired_anonymous_users()
        
        return {"message": "Expired sessions and users cleaned up successfully"}
    except Exception as e:
        print(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup expired sessions")


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
        print(f" Error getting anonymous session: {e}")
        raise HTTPException(status_code=500, detail="Failed to get anonymous session")

@router.post("/migrate-anonymous-session")
async def migrate_anonymous_session(
    request: MigrationRequest
):
    """Migrate anonymous session data to a real user account"""
    global CLEANUP_IN_PROGRESS
    
    # Extract parameters from request body
    session_id = request.anonymous_session_id
    new_user_id = request.user_id
    
    # Prevent cleanup during migration
    if CLEANUP_IN_PROGRESS:
        print(" Migration blocked: cleanup in progress")
        raise HTTPException(status_code=409, detail="System maintenance in progress. Please try again in a moment.")
    
    try:
        # Get the temporary user ID for this session (if it exists in database)
        supabase = get_supabase_client()
        temp_user_result = supabase.table("users").select("user_id").eq("email", f"anonymous_{session_id}@temp.local").execute()
        
        temp_user_id = None
        if temp_user_result.data:
            temp_user_id = temp_user_result.data[0]["user_id"]
            
            # Update all sessions to use the new user ID
            supabase.table("sessions").update({"user_id": new_user_id}).eq("user_id", temp_user_id).execute()
            
            # Update all messages to use the new user ID
            supabase.table("chat_messages").update({"user_id": new_user_id}).eq("user_id", temp_user_id).execute()
            
            # Update all turns to use the new user ID
            supabase.table("turns").update({"user_id": new_user_id}).eq("user_id", temp_user_id).execute()
        
        # Only update database records if temp_user_id exists
        if temp_user_id:
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
        print(f" Error migrating anonymous session: {e}")
        raise HTTPException(status_code=500, detail="Failed to migrate anonymous session data")

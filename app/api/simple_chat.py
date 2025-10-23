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
        
        # Save user message
        user_message_id = await _save_message(
            session_id=str(session_id),
            user_id=str(user_id),
            role="user",
            content=chat_request.text,
            metadata={"is_authenticated": is_authenticated}
        )
        
        # Store user message embedding for RAG
        if rag_service and user_message_id:
            try:
                await rag_service.embed_and_store_message(
                    message_id=UUID(user_message_id),
                    user_id=UUID(user_id),
                    project_id=UUID(project_id) if project_id else None,
                    session_id=UUID(session_id),
                    content=chat_request.text,
                    role="user",
                    metadata={"is_authenticated": is_authenticated}
                )
                print(f"📚 Stored user message embedding: {user_message_id}")
            except Exception as e:
                print(f"⚠️ Failed to store user message embedding: {e}")
        
        # Generate and stream AI response
        async def generate_stream():
            try:
                # Get conversation history for context
                conversation_history = await _get_conversation_history(str(session_id), str(user_id))
                
                # Generate AI response
                if AI_AVAILABLE and ai_manager:
                    # Get RAG context from uploaded documents
                    rag_context = None
                    if rag_service:
                        try:
                            print(f"🔍 Getting RAG context for user: {user_id}, project: {project_id}")
                            rag_context = await rag_service.get_rag_context(
                                user_message=chat_request.text,
                                user_id=UUID(user_id),
                                project_id=UUID(project_id) if project_id else None,
                                conversation_history=conversation_history
                            )
                            print(f"📚 RAG context retrieved: {rag_context.get('document_context_count', 0)} document chunks")
                        except Exception as e:
                            print(f"⚠️ RAG context error: {e}")
                            rag_context = None
                    
                    # Use AI manager for response generation with RAG context
                    ai_response = await ai_manager.generate_response(
                        task_type=TaskType.CHAT,
                        prompt=chat_request.text,
                        conversation_history=conversation_history,
                        user_id=user_id,
                        project_id=project_id,
                        rag_context=rag_context
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
                    
                    # Store message embeddings for RAG
                    if rag_service and assistant_message_id:
                        try:
                            await rag_service.embed_and_store_message(
                                message_id=UUID(assistant_message_id),
                                user_id=UUID(user_id),
                                project_id=UUID(project_id) if project_id else None,
                                session_id=UUID(session_id),
                                content=full_response,
                                role="assistant",
                                metadata={"is_authenticated": is_authenticated}
                            )
                            print(f"📚 Stored assistant message embedding: {assistant_message_id}")
                        except Exception as e:
                            print(f"⚠️ Failed to store assistant message embedding: {e}")
                    
                else:
                    # Fallback response if AI is not available
                    fallback_response = "I'm here to help you develop your story! However, the AI system is currently unavailable. Please try again later."
                    
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
                            await rag_service.embed_and_store_message(
                                message_id=UUID(fallback_message_id),
                                user_id=UUID(user_id),
                                project_id=UUID(project_id) if project_id else None,
                                session_id=UUID(session_id),
                                content=fallback_response,
                                role="assistant",
                                metadata={"is_authenticated": is_authenticated, "fallback": True}
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
            "timestamp": message["created_at"]
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

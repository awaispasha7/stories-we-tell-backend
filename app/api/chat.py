from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models import ChatRequest, ChatResponse  # Import Pydantic models
from app.database.supabase import get_supabase_client
from app.ai.models import ai_manager, TaskType
from app.ai.dossier_extractor import dossier_extractor
import uuid
import os
import json
import asyncio
from dotenv import load_dotenv

router = APIRouter()
load_dotenv()

# In-memory conversation storage (in production, use Redis or database)
conversation_sessions = {}

@router.post("/chat")
async def rewrite_ask(chat_request: ChatRequest):
    text = chat_request.text
    print(f"🔵 Received chat request: '{text[:100]}...'")

    async def generate_stream():
        try:
            print(f"🟡 Starting AI response generation for: '{text[:50]}...'")
            
            # Get or create session
            session_id = "default_session"
            if session_id not in conversation_sessions:
                conversation_sessions[session_id] = {
                    "project_id": str(uuid.uuid4()),
                    "history": []
                }
            
            # Get conversation history for context
            conversation_history = conversation_sessions[session_id]["history"]
            print(f"📚 Conversation history length: {len(conversation_history)} messages")
            
            # Generate response using gpt-4o-mini for chat WITH CONTEXT
            ai_response = await ai_manager.generate_response(
                task_type=TaskType.CHAT,
                prompt=text,
                conversation_history=conversation_history,  # Pass history for context
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
                await asyncio.sleep(0.1)  # Slightly longer delay for typing effect

            # Send final metadata
            turn_id = str(uuid.uuid4())
            # Use session-based project_id (persist across requests)
            session_id = "default_session"  # In production, use user session/cookie
            if session_id not in conversation_sessions:
                conversation_sessions[session_id] = {
                    "project_id": str(uuid.uuid4()),
                    "history": []
                }
            
            project_id = conversation_sessions[session_id]["project_id"]
            
            # Add to conversation history
            conversation_sessions[session_id]["history"].extend([
                {"role": "user", "content": text},
                {"role": "assistant", "content": reply}
            ])
            
            # Metadata to send to frontend
    metadata = {
                "turn_id": turn_id,
                "project_id": project_id,
                "raw_text": text,
                "response_text": reply,
                "ai_model": model_used,
                "tokens_used": tokens_used
            }

            # Store the result in Supabase (matching actual schema)
            if "Error" not in reply:
                try:
                    supabase = get_supabase_client()
                    # Match the actual database schema: turn_id, project_id, raw_text, normalized_json
                    db_record = {
                        "turn_id": turn_id,
                        "project_id": project_id,
        "raw_text": text,
                        "normalized_json": {
                            "response_text": reply,
                            "ai_model": model_used,
                            "tokens_used": tokens_used,
                            "timestamp": str(uuid.uuid4())  # Can be replaced with actual timestamp if needed
                        }
                    }
                    response = supabase.table("turns").insert([db_record]).execute()
                    if not response.data:
                        print("Warning: Failed to store chat metadata in Supabase")
                    
                    # Update dossier if needed
                    conversation_history = conversation_sessions[session_id]["history"]
                    if dossier_extractor.should_update_dossier(conversation_history):
                        print("📊 Updating dossier...")
                        dossier_data = await dossier_extractor.extract_metadata(conversation_history)
                        
                        # Upsert dossier (insert or update)
                        dossier_record = {
                            "project_id": project_id,
                            "snapshot_json": dossier_data
                        }
                        
                        # Try to update first, then insert if not exists
                        existing = supabase.table("dossier").select("*").eq("project_id", project_id).execute()
                        
                        if existing.data and len(existing.data) > 0:
                            # Update existing
                            supabase.table("dossier").update(dossier_record).eq("project_id", project_id).execute()
                            print(f"✅ Updated dossier for project {project_id}")
                        else:
                            # Insert new
                            supabase.table("dossier").insert([dossier_record]).execute()
                            print(f"✅ Created dossier for project {project_id}")
                    
                except Exception as db_error:
                    print(f"Database error (non-critical): {str(db_error)}")

            # Send metadata chunk
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
            error_reply = f"I apologize, but I'm having trouble generating a response right now. Please make sure your OpenAI API key is properly configured. Error: {str(e)}"
            
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
        }
    )

@router.post("/generate-description")
async def generate_description(chat_request: ChatRequest):
    """Generate description using Gemini Pro"""
    text = chat_request.text
    
    ai_response = await ai_manager.generate_response(
        task_type=TaskType.DESCRIPTION,
        prompt=text,
        max_tokens=1000,
        temperature=0.7
    )
    
    return {
        "description": ai_response.get("response", "Could not generate description"),
        "model_used": ai_response.get("model_used", "unknown"),
        "tokens_used": ai_response.get("tokens_used", 0)
    }

@router.post("/generate-script")
async def generate_script(chat_request: ChatRequest):
    """Generate script using GPT-5"""
    text = chat_request.text
    
    ai_response = await ai_manager.generate_response(
        task_type=TaskType.SCRIPT,
        prompt=text,
        max_tokens=2000,
        temperature=0.8
    )
    
    return {
        "script": ai_response.get("response", "Could not generate script"),
        "model_used": ai_response.get("model_used", "unknown"),
        "tokens_used": ai_response.get("tokens_used", 0)
    }

@router.post("/generate-scene")
async def generate_scene(chat_request: ChatRequest):
    """Generate scene using Claude 3 Sonnet"""
    text = chat_request.text
    
    ai_response = await ai_manager.generate_response(
        task_type=TaskType.SCENE,
        prompt=text,
        max_tokens=2000,
        temperature=0.7
    )
    
    return {
        "scene": ai_response.get("response", "Could not generate scene"),
        "model_used": ai_response.get("model_used", "unknown"),
        "tokens_used": ai_response.get("tokens_used", 0)
    }

@router.get("/dossier")
async def get_dossier(project_id: str = None):
    """Get current story dossier data from Supabase"""
    try:
        supabase = get_supabase_client()
        
        # If no project_id provided, try to get the default session's project
        if not project_id:
            session_id = "default_session"
            if session_id in conversation_sessions:
                project_id = conversation_sessions[session_id]["project_id"]
        
        if project_id:
            # Fetch from database
            response = supabase.table("dossier").select("*").eq("project_id", project_id).execute()
            
            if response.data and len(response.data) > 0:
                dossier_data = response.data[0]["snapshot_json"]
                print(f"✅ Retrieved dossier for project {project_id}")
                return dossier_data
        
        # Return default data if no dossier found
        return {
            "title": "Untitled Story",
            "logline": "A compelling story waiting to be told...",
            "genre": "Unknown",
            "tone": "Unknown",
            "scenes": [],
            "characters": [],
            "locations": []
        }
        
    except Exception as e:
        print(f"❌ Error fetching dossier: {str(e)}")
        # Return default data on error
        return {
            "title": "Untitled Story",
            "logline": "A compelling story waiting to be told...",
            "genre": "Unknown",
            "tone": "Unknown",
            "scenes": [],
            "characters": [],
            "locations": []
        }

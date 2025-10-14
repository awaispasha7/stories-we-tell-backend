from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models import ChatRequest, ChatResponse  # Import Pydantic models
import uuid
import os
import json
import asyncio
from dotenv import load_dotenv

# Try to import Supabase client with error handling
try:
    from app.database.supabase import get_supabase_client
    SUPABASE_AVAILABLE = True
except Exception as e:
    print(f"Warning: Supabase not available: {e}")
    SUPABASE_AVAILABLE = False
    get_supabase_client = None

# Try to import AI components with error handling
try:
    from app.ai.models import ai_manager, TaskType
    from app.ai.dossier_extractor import dossier_extractor
    AI_AVAILABLE = True
    print("✅ AI components imported successfully")
except Exception as e:
    print(f"Warning: AI components not available: {e}")
    AI_AVAILABLE = False
    ai_manager = None
    TaskType = None
    dossier_extractor = None

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
            print(f"🟡 Starting response generation for: '{text[:50]}...'")

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
                    conversation_history=conversation_history,
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

            # Send final metadata
            turn_id = str(uuid.uuid4())
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

            # Store the result in Supabase (if available)
            if "Error" not in reply and SUPABASE_AVAILABLE and get_supabase_client is not None:
                try:
                    supabase = get_supabase_client()
                    db_record = {
                        "turn_id": turn_id,
                        "project_id": project_id,
                        "raw_text": text,
                        "normalized_json": {
                            "response_text": reply,
                            "ai_model": model_used,
                            "tokens_used": tokens_used,
                            "timestamp": str(uuid.uuid4())
                        }
                    }
                    response = supabase.table("turns").insert([db_record]).execute()
                    if not response.data:
                        print("Warning: Failed to store chat metadata in Supabase")

                    # Update dossier if needed
                    should_update = False
                    dossier_data = None
                    
                    print(f"🔍 AI_AVAILABLE: {AI_AVAILABLE}, dossier_extractor: {dossier_extractor is not None}")
                    
                    if AI_AVAILABLE and dossier_extractor is not None:
                        should_update = await dossier_extractor.should_update_dossier(conversation_history)
                        print(f"🔍 Should update dossier: {should_update}")
                        if should_update:
                            print("📊 Updating dossier using AI extractor...")
                            dossier_data = await dossier_extractor.extract_metadata(conversation_history)
                            print(f"📊 Dossier data extracted: {dossier_data}")
                        else:
                            print("🔍 Dossier update skipped - LLM decided not to update")
                    else:
                        print("🔍 Dossier update skipped - AI not available or dossier_extractor is None")

                    if should_update and dossier_data:
                        dossier_record = {
                            "project_id": project_id,
                            "snapshot_json": dossier_data
                        }

                        print(f"🔍 Checking existing dossier for project {project_id}")
                        existing = supabase.table("dossier").select("*").eq("project_id", project_id).execute()
                        print(f"🔍 Existing dossier data: {existing.data}")

                        if existing.data and len(existing.data) > 0:
                            print(f"🔍 Updating existing dossier record")
                            update_response = supabase.table("dossier").update(dossier_record).eq("project_id", project_id).execute()
                            print(f"✅ Updated dossier for project {project_id}: {update_response.data}")
                        else:
                            print(f"🔍 Creating new dossier record")
                            insert_response = supabase.table("dossier").insert([dossier_record]).execute()
                            print(f"✅ Created dossier for project {project_id}: {insert_response.data}")

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

# Additional endpoints temporarily disabled until AI components are properly configured
# These can be re-enabled when proper API keys and AI models are available

# @router.post("/generate-description")
# async def generate_description(chat_request: ChatRequest):
#     """Generate description using Gemini Pro"""
#     text = chat_request.text
#
#     if ai_manager is None or TaskType is None:
#         return {"error": "AI components not available"}
#
#     ai_response = await ai_manager.generate_response(
#         task_type=TaskType.DESCRIPTION,
#         prompt=text,
#         max_tokens=1000,
#         temperature=0.7
#     )
#
#     return {
#         "description": ai_response.get("response", "Could not generate description"),
#         "model_used": ai_response.get("model_used", "unknown"),
#         "tokens_used": ai_response.get("tokens_used", 0)
#     }

# @router.post("/generate-script")
# async def generate_script(chat_request: ChatRequest):
#     """Generate script using GPT-5"""
#     text = chat_request.text
#
#     if ai_manager is None or TaskType is None:
#         return {"error": "AI components not available"}
#
#     ai_response = await ai_manager.generate_response(
#         task_type=TaskType.SCRIPT,
#         prompt=text,
#         max_tokens=2000,
#         temperature=0.8
#     )
#
#     return {
#         "script": ai_response.get("response", "Could not generate script"),
#         "model_used": ai_response.get("model_used", "unknown"),
#         "tokens_used": ai_response.get("tokens_used", 0)
#     }

# @router.post("/generate-scene")
# async def generate_scene(chat_request: ChatRequest):
#     """Generate scene using Claude 3 Sonnet"""
#     text = chat_request.text
#
#     if ai_manager is None or TaskType is None:
#         return {"error": "AI components not available"}
#
#     ai_response = await ai_manager.generate_response(
#         task_type=TaskType.SCENE,
#         prompt=text,
#         max_tokens=2000,
#         temperature=0.7
#     )
#
#     return {
#         "scene": ai_response.get("response", "Could not generate scene"),
#         "model_used": ai_response.get("model_used", "unknown"),
#         "tokens_used": ai_response.get("tokens_used", 0)
#     }

@router.get("/dossier")
async def get_dossier(project_id: str = None):
    """Get current story dossier data from Supabase"""
    print(f"🔍 Fetching dossier for project_id: {project_id}")
    
    try:
        # Check if Supabase is available
        supabase_available = SUPABASE_AVAILABLE and get_supabase_client is not None
        print(f"🔍 Supabase available: {supabase_available}")
        
        if supabase_available:
            try:
                supabase = get_supabase_client()
                # If no project_id provided, try to get the default session's project
                if not project_id:
                    session_id = "default_session"
                    if session_id in conversation_sessions:
                        project_id = conversation_sessions[session_id]["project_id"]
                        print(f"🔍 Using project_id from session: {project_id}")
                    else:
                        print("🔍 No session found, creating default session")
                        # Create a default session with a proper UUID
                        import uuid
                        default_project_id = str(uuid.uuid4())
                        conversation_sessions[session_id] = {
                            "project_id": default_project_id,
                            "history": []
                        }
                        project_id = default_project_id
                        print(f"🔍 Created default session with project_id: {project_id}")
                
                if project_id:
                    print(f"🔍 Fetching dossier from database for project: {project_id}")
                    # Fetch from database
                    response = supabase.table("dossier").select("*").eq("project_id", project_id).execute()
                    
                    print(f"🔍 Database response: {response.data}")
                    
                    if response.data and len(response.data) > 0:
                        dossier_data = response.data[0]["snapshot_json"]
                        print(f"✅ Retrieved dossier for project {project_id}: {dossier_data}")
                        return dossier_data
                    else:
                        print(f"🔍 No dossier found for project {project_id}")
                else:
                    print("🔍 No project_id available")
                    
            except Exception as supabase_error:
                print(f"⚠️ Supabase error: {supabase_error}")
                # Don't immediately fall back - try to return cached data if available
                supabase_available = False
        
        # Only return default data if we truly have no data
        print("📝 No dossier data found, returning default structure")
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
        print(f"❌ Critical error fetching dossier: {str(e)}")
        # Return a more informative error structure
        return {
            "title": "Error Loading Dossier",
            "logline": "Unable to load story information",
            "genre": "Unknown",
            "tone": "Unknown",
            "scenes": [],
            "characters": [],
            "locations": []
        }

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models import ChatRequest, ChatResponse  # Import Pydantic models
from app.database.supabase import get_supabase_client
from app.ai.models import ai_manager, TaskType
import uuid
import os
import json
import asyncio
from dotenv import load_dotenv

router = APIRouter()
load_dotenv()

@router.post("/chat")
async def rewrite_ask(chat_request: ChatRequest):
    text = chat_request.text
    print(f"🔵 Received chat request: '{text[:100]}...'")

    async def generate_stream():
        try:
            print(f"🟡 Starting AI response generation for: '{text[:50]}...'")
            
            # Generate response using GPT-3.5-turbo for chat
            ai_response = await ai_manager.generate_response(
                task_type=TaskType.CHAT,
                prompt=text,
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
            project_id = str(uuid.uuid4())
            
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
async def get_dossier():
    """Get current story dossier data"""
    # For now, return mock data. In a real app, this would fetch from database
    return {
        "title": "Untitled Story",
        "logline": "A compelling story waiting to be told...",
        "genre": "Drama",
        "tone": "Intimate",
        "scenes": [
            {
                "scene_id": "1",
                "one_liner": "Opening scene - character introduction",
                "description": "The protagonist is introduced in their everyday world",
                "time_of_day": "Morning",
                "interior_exterior": "Interior",
                "tone": "Calm"
            },
            {
                "scene_id": "2", 
                "one_liner": "Inciting incident",
                "description": "Something happens that changes everything",
                "time_of_day": "Afternoon",
                "interior_exterior": "Exterior",
                "tone": "Tense"
            }
        ],
        "characters": [
            {
                "character_id": "1",
                "name": "Protagonist",
                "description": "Main character with a clear goal"
            }
        ],
        "locations": [
            {
                "location_id": "1",
                "name": "Home",
                "description": "The protagonist's starting point"
            }
        ]
    }

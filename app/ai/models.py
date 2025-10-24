"""
AI Model Management System
Handles multiple AI providers based on task type as specified by client requirements.
"""

import os
import openai
import google.generativeai as genai
import anthropic
from typing import Dict, Any, Optional
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

class TaskType(Enum):
    """Task types for AI model selection"""
    CHAT = "chat"
    DESCRIPTION = "description"
    SCRIPT = "script"
    SCENE = "scene"

class AIModelManager:
    """Manages AI model selection and execution based on task type"""
    
    def __init__(self):
        # Initialize OpenAI
        openai.api_key = os.getenv("OPENAI_API_KEY")

        # Check if other API keys are available and initialize if they are
        gemini_key = os.getenv("GEMINI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if gemini_key and gemini_key != "your_gemini_api_key_here":
            genai.configure(api_key=gemini_key)
            self.gemini_available = True
        else:
            self.gemini_available = False

        if anthropic_key and anthropic_key != "your_anthropic_api_key_here":
            self.claude_client = anthropic.Anthropic(api_key=anthropic_key)
            self.claude_available = True
        else:
            self.claude_available = False

        # Model selection mapping - using latest recommended models
        self.model_mapping = {
            TaskType.CHAT: "gpt-4.1-mini",  # Best price-to-quality for high-traffic chat
            TaskType.DESCRIPTION: "gemini-2.5-pro",  # Latest Pro tier for creative reasoning
            TaskType.SCRIPT: "claude-sonnet-4.5",  # SOTA for structured long-form writing
            TaskType.SCENE: "gpt-4.1",  # Flagship for deep text generation
        }
    
    def _build_conversation_context(self, conversation_history: list) -> str:
        """Build conversation context for the system prompt"""
        if not conversation_history:
            return "This is the start of our conversation."
        
        # Extract key information from conversation
        context_parts = []
        
        # Look for character names
        characters = set()
        for msg in conversation_history:
            content = msg.get('content', '').lower()
            # Simple character name detection (could be enhanced)
            if 'my character' in content or 'main character' in content:
                # Extract potential character names
                words = content.split()
                for i, word in enumerate(words):
                    if word in ['character', 'protagonist', 'main'] and i + 2 < len(words):
                        if words[i+1] == 'is' or words[i+1] == 'named':
                            characters.add(words[i+2].title())
        
        if characters:
            context_parts.append(f"Characters mentioned: {', '.join(characters)}")
        
        # Look for story elements
        story_elements = []
        for msg in conversation_history:
            content = msg.get('content', '').lower()
            if any(keyword in content for keyword in ['story', 'plot', 'setting', 'genre', 'time', 'place']):
                story_elements.append("Story details have been discussed")
                break
        
        if story_elements:
            context_parts.append("Story development is in progress")
        
        return " | ".join(context_parts) if context_parts else "Conversation in progress"

    def is_story_complete(self, dossier_context: dict) -> bool:
        """Check if story is complete based on filled slots"""
        if not dossier_context:
            return False
        
        # Required slots for story completion
        required_slots = [
            'story_timeframe',
            'story_location', 
            'story_world_type',
            'subject_full_name',
            'problem_statement',
            'actions_taken',
            'outcome'
        ]
        
        # Check if all required slots are filled (not "Unknown")
        filled_slots = 0
        for slot in required_slots:
            value = dossier_context.get(slot, 'Unknown')
            if value and value != 'Unknown' and value.strip():
                filled_slots += 1
        
        # Story is complete if 80% of required slots are filled
        completion_rate = filled_slots / len(required_slots)
        is_complete = completion_rate >= 0.8
        
        print(f"📊 Story completion check: {filled_slots}/{len(required_slots)} slots filled ({completion_rate:.1%}) - {'COMPLETE' if is_complete else 'INCOMPLETE'}")
        return is_complete

    async def generate_response(self, task_type: TaskType, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Generate response using the appropriate AI model for the task type
        
        Args:
            task_type: The type of task (determines which model to use)
            prompt: The input prompt
            **kwargs: Additional parameters for the specific model
            
        Returns:
            Dict containing the response and metadata
        """
        try:
            if task_type == TaskType.CHAT:
                return await self._generate_chat_response(prompt, **kwargs)
            elif task_type == TaskType.DESCRIPTION:
                return await self._generate_description_response(prompt, **kwargs)
            elif task_type == TaskType.SCRIPT:
                return await self._generate_script_response(prompt, **kwargs)
            elif task_type == TaskType.SCENE:
                return await self._generate_scene_response(prompt, **kwargs)
            else:
                raise ValueError(f"Unknown task type: {task_type}")
                
        except Exception as e:
            return {
                "response": f"Error generating response: {str(e)}",
                "model_used": self.model_mapping.get(task_type, "unknown"),
                "error": str(e)
            }
    
    async def _generate_chat_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate chat response using GPT-5 mini as specified by client"""
        try:
            print(f"🤖 Attempting to call OpenAI with model: gpt-4o-mini")
            print(f"🤖 Prompt: '{prompt[:100]}...'")
            
            # Check for RAG context from uploaded documents
            rag_context = kwargs.get("rag_context")
            document_context = ""
            if rag_context and rag_context.get("document_context"):
                document_chunks = rag_context["document_context"]
                if document_chunks:
                    document_context = "\n\nUPLOADED DOCUMENT CONTEXT:\n"
                    for i, chunk in enumerate(document_chunks[:3]):  # Limit to 3 chunks
                        document_context += f"--- Document Chunk {i+1} ---\n{chunk.get('chunk_text', '')}\n\n"
                    print(f"📄 Including {len(document_chunks)} document chunks in context")
            
            # Check for dossier context (existing story data) - Updated for client requirements
            dossier_context = kwargs.get("dossier_context")
            dossier_info = ""
            if dossier_context:
                dossier_info = "\n\nEXISTING STORY DATA (Slot-based):\n"
                
                # Story Frame
                if dossier_context.get('story_timeframe') and dossier_context.get('story_timeframe') != 'Unknown':
                    dossier_info += f"Time: {dossier_context['story_timeframe']}\n"
                if dossier_context.get('story_location') and dossier_context.get('story_location') != 'Unknown':
                    dossier_info += f"Location: {dossier_context['story_location']}\n"
                if dossier_context.get('story_world_type') and dossier_context.get('story_world_type') != 'Unknown':
                    dossier_info += f"World Type: {dossier_context['story_world_type']}\n"
                
                # Character (Subject)
                if dossier_context.get('subject_full_name') and dossier_context.get('subject_full_name') != 'Unknown':
                    dossier_info += f"Character: {dossier_context['subject_full_name']}\n"
                if dossier_context.get('subject_relationship_to_writer') and dossier_context.get('subject_relationship_to_writer') != 'Unknown':
                    dossier_info += f"Relationship: {dossier_context['subject_relationship_to_writer']}\n"
                
                # Story Craft
                if dossier_context.get('problem_statement') and dossier_context.get('problem_statement') != 'Unknown':
                    dossier_info += f"Problem: {dossier_context['problem_statement']}\n"
                if dossier_context.get('actions_taken') and dossier_context.get('actions_taken') != 'Unknown':
                    dossier_info += f"Actions: {dossier_context['actions_taken']}\n"
                if dossier_context.get('outcome') and dossier_context.get('outcome') != 'Unknown':
                    dossier_info += f"Outcome: {dossier_context['outcome']}\n"
                
                # Technical
                if dossier_context.get('title') and dossier_context.get('title') != 'Untitled Story':
                    dossier_info += f"Title: {dossier_context['title']}\n"
                
                print(f"📋 Including dossier context: {dossier_context.get('title', 'Untitled')} - {len([k for k, v in dossier_context.items() if v and v != 'Unknown'])} slots filled")
            
            # Enhanced story development system prompt based on client requirements
            system_prompt = f"""You are Ariel, a cinematic story development assistant for Stories We Tell. Your role is to help users develop compelling stories by following a structured, stateful conversation flow.

        CORE PRINCIPLES:
        1. FRAME-FIRST: Always collect time and location before characters
        2. STATEFUL MEMORY: Remember all previous answers and build on them
        3. PRONOUN RESOLUTION: Track character names and resolve pronouns (he/she = character name)
        4. STORY COMPLETION: Recognize when story is complete and transition appropriately
        5. PROGRESSIVE DISCLOSURE: Move from problem → actions → outcome

        CONVERSATION STRUCTURE (Slot-based, in order):
        1. STORY FRAME: story_timeframe → story_location → story_world_type → writer_connection_place_time
        2. CHARACTER: subject_exists_real_world → subject_full_name → subject_relationship_to_writer → subject_brief_description
        3. STORY CRAFT: problem_statement → actions_taken → outcome → likes_in_story
        4. TECHNICAL: runtime (3-5 minutes) → title
        5. COMPLETION: Recognize when story is complete

        MEMORY MANAGEMENT:
        - ALWAYS reference previous answers by name
        - NEVER re-ask questions already answered
        - Use character names consistently (never use pronouns without context)
        - Show you remember: "You mentioned [character name] earlier..."

        PRONOUN RESOLUTION:
        - When user says "he" or "she", always connect to the established character name
        - Example: "So [Character Name] faces this challenge. What does [Character Name] do to overcome it?"
        - NEVER ask "Who is he/she?" if character name is already established

        STORY COMPLETION DETECTION:
        - Look for phrases: "at the end", "finally", "in conclusion", "that's the story"
        - When story seems complete, acknowledge and move to next phase
        - Don't keep asking questions if story is finished

        RESPONSE GUIDELINES:
        1. Keep responses SHORT (1-2 sentences max)
        2. Ask ONE focused question at a time
        3. Always acknowledge what they've shared
        4. Use character names, not pronouns
        5. Be warm and encouraging
        6. Follow the structured flow above

        EXAMPLES (Slot-based):
        ❌ BAD: "What's your story about? Who are the characters?"
        ✅ GOOD: "I'd love to hear your story! When does it take place?" (story_timeframe)

        ❌ BAD: "What does he do?" (when character name is John)
        ✅ GOOD: "What does John do to face this challenge?" (actions_taken)

        ❌ BAD: Asking "Who is the main character?" when user already said "Sarah"
        ✅ GOOD: "You mentioned Sarah earlier. What's the main problem Sarah faces?" (problem_statement)

        ❌ BAD: Continuing to ask questions after user says "at the end of the story..."
        ✅ GOOD: "That's a beautiful story about [character name]! What makes this story special to you?" (likes_in_story)

        SLOT-BASED ROUTING:
        - If story_timeframe is Unknown → Ask "When does your story take place?"
        - If story_location is Unknown → Ask "Where does it take place?"
        - If subject_full_name is Unknown → Ask "What's your main character's name?"
        - If problem_statement is Unknown → Ask "What problem does [character] face?"
        - If actions_taken is Unknown → Ask "What does [character] do to solve this?"
        - If outcome is Unknown → Ask "How does the story end?"

        CONVERSATION CONTEXT:
        {self._build_conversation_context(conversation_history)}

        Be Ariel - warm, story-focused, and always building on what they share.{document_context}{dossier_info}"""

            # Build messages with conversation history for context
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history if provided
            conversation_history = kwargs.get("conversation_history", [])
            if conversation_history:
                # Limit to last 10 messages to avoid token limits
                recent_history = conversation_history[-10:]
                messages.extend(recent_history)
                print(f"📚 Using {len(recent_history)} messages from history for context")
            
            # Add current user message
            messages.append({"role": "user", "content": prompt})

            response = openai.chat.completions.create(
                model="gpt-4.1-mini",  # Best price-to-quality for high-traffic chat with ~1M token context
                messages=messages,
                max_completion_tokens=kwargs.get("max_tokens", 200),  # Optimized for chat responses
                temperature=0.7,
                top_p=1.0,  # Standard value for balanced creativity
                n=1,  # Single response
                stream=False,  # Non-streaming for API consistency
                presence_penalty=0.0,  # No penalty for topic repetition
                frequency_penalty=0.0  # No penalty for word repetition
            )
            
            print(f"✅ OpenAI response received: {response}")

            return {
                "response": response.choices[0].message.content,
                "model_used": "gpt-4.1-mini",
                "tokens_used": response.usage.total_tokens if response.usage else 0
            }
        except Exception as e:
            print(f"❌ OpenAI chat error: {str(e)}")
            print(f"❌ Error type: {type(e).__name__}")
            import traceback
            print(f"❌ Full traceback: {traceback.format_exc()}")
            raise Exception(f"OpenAI chat error: {str(e)}")
    
    async def _generate_description_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate description using Gemini 2.5 Pro (latest for creative reasoning) with fallback to 1.5 Pro"""
        try:
            if self.gemini_available:
                # Try Gemini 2.5 Pro first (latest for creative reasoning)
                try:
                    model = genai.GenerativeModel('gemini-2.5-pro')
                    response = model.generate_content(
                        f"Generate a detailed, vivid description for: {prompt}",
                        generation_config=genai.types.GenerationConfig(
                            max_output_tokens=kwargs.get("max_tokens", 2000),  # Increased for 2.5 Pro
                            temperature=kwargs.get("temperature", 0.8)  # Higher creativity for descriptions
                        )
                    )

                    return {
                        "response": response.text,
                        "model_used": "gemini-2.5-pro",
                        "tokens_used": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
                    }
                except Exception as e:
                    print(f"⚠️ Gemini 2.5 Pro failed, falling back to 1.5 Pro: {e}")
                    # Fallback to Gemini 1.5 Pro (stable, GA)
                    model = genai.GenerativeModel('gemini-1.5-pro')
                    response = model.generate_content(
                        f"Generate a detailed, vivid description for: {prompt}",
                        generation_config=genai.types.GenerationConfig(
                            max_output_tokens=kwargs.get("max_tokens", 1500),
                            temperature=kwargs.get("temperature", 0.8)
                        )
                    )

                    return {
                        "response": response.text,
                        "model_used": "gemini-1.5-pro",
                        "tokens_used": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
                    }
            else:
                # Fallback to GPT-4.1 (flagship for deep text generation)
                response = openai.chat.completions.create(
                    model="gpt-4.1",
                    messages=[
                        {"role": "system", "content": "You are a creative writing assistant specializing in vivid, detailed descriptions. Generate engaging, sensory-rich descriptions that bring scenes to life."},
                        {"role": "user", "content": f"Generate a detailed, vivid description for: {prompt}"}
                    ],
                    max_completion_tokens=kwargs.get("max_tokens", 2000),
                    temperature=kwargs.get("temperature", 0.8),
                    top_p=1.0,
                    n=1,
                    stream=False,
                    presence_penalty=0.0,
                    frequency_penalty=0.0
                )

                return {
                    "response": response.choices[0].message.content,
                    "model_used": "gpt-4.1",
                    "tokens_used": response.usage.total_tokens if response.usage else 0
                }
        except Exception as e:
            raise Exception(f"Description generation error: {str(e)}")
    
    async def _generate_script_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate video tutorial script from captured story data"""
        try:
            # Get dossier context for script generation
            dossier_context = kwargs.get("dossier_context", {})
            
            # Build comprehensive script prompt
            script_prompt = f"""You are a professional video scriptwriter for Stories We Tell. Create a compelling 3-5 minute video tutorial script based on the captured story data.

STORY DATA:
Time: {dossier_context.get('story_timeframe', 'Not specified')}
Location: {dossier_context.get('story_location', 'Not specified')}
World Type: {dossier_context.get('story_world_type', 'Not specified')}
Character: {dossier_context.get('subject_full_name', 'Not specified')}
Relationship: {dossier_context.get('subject_relationship_to_writer', 'Not specified')}
Problem: {dossier_context.get('problem_statement', 'Not specified')}
Actions: {dossier_context.get('actions_taken', 'Not specified')}
Outcome: {dossier_context.get('outcome', 'Not specified')}
Why This Story: {dossier_context.get('likes_in_story', 'Not specified')}

SCRIPT REQUIREMENTS:
1. Create a 3-5 minute video tutorial script
2. Use a warm, personal tone
3. Include visual cues and pacing notes
4. Structure: Introduction → Story Setup → Character Journey → Resolution → Call to Action
5. Make it engaging and emotionally resonant
6. Include specific details from the story data above

FORMAT:
[VIDEO SCRIPT FORMAT]
[SCENE 1: Introduction]
[Visual: Warm, inviting setting]
[Narrator]: "Today, I want to share a story about..."

[Continue with full script structure]

Generate a complete, production-ready video script."""

            # Use Claude Sonnet 4.5 for script generation (SOTA for structured long-form writing)
            if self.claude_available:
                response = self.claude_client.messages.create(
                    model="claude-sonnet-4.5",
                    max_tokens=kwargs.get("max_tokens", 8000),  # Claude 4.5 supports up to 64K tokens out
                    temperature=kwargs.get("temperature", 0.7),
                    messages=[
                        {"role": "user", "content": script_prompt}
                    ]
                )

                return {
                    "response": response.content[0].text,
                    "model_used": "claude-sonnet-4.5",
                    "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
                    "script_type": "video_tutorial",
                    "estimated_duration": "3-5 minutes"
                }
            else:
                # Fallback to GPT-4.1 (flagship for deep text generation)
                response = openai.chat.completions.create(
                    model="gpt-4.1",
                    messages=[
                        {"role": "system", "content": "You are a professional video scriptwriter specializing in personal storytelling and documentary-style content. Create engaging, emotionally resonant scripts that bring stories to life."},
                        {"role": "user", "content": script_prompt}
                    ],
                    max_completion_tokens=kwargs.get("max_tokens", 4000),
                    temperature=0.7,
                    top_p=1.0,
                    n=1,
                    stream=False,
                    presence_penalty=0.0,
                    frequency_penalty=0.0
                )

                return {
                    "response": response.choices[0].message.content,
                    "model_used": "gpt-4.1",
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                    "script_type": "video_tutorial",
                    "estimated_duration": "3-5 minutes"
                }
        except Exception as e:
            raise Exception(f"Script generation error: {str(e)}")
    
    async def _generate_scene_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate scene using GPT-4.1 (flagship for deep text generation) or fallback to Claude Sonnet 4.5"""
        try:
            # Use GPT-4.1 for scene generation (flagship for deep text generation with 1M token context)
            response = openai.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": "You are a professional screenwriter and scene director. Generate detailed, cinematic scenes with vivid descriptions, character actions, dialogue, and visual elements. Focus on creating immersive, emotionally engaging scenes with strong instruction-following and coherence over long passages."},
                    {"role": "user", "content": f"Generate a detailed, cinematic scene based on: {prompt}"}
                ],
                max_completion_tokens=kwargs.get("max_tokens", 3000),  # Increased for GPT-4.1
                temperature=kwargs.get("temperature", 0.8),  # Higher creativity for scenes
                top_p=1.0,
                n=1,
                stream=False,
                presence_penalty=0.0,
                frequency_penalty=0.0
            )

            return {
                "response": response.choices[0].message.content,
                "model_used": "gpt-4.1",
                "tokens_used": response.usage.total_tokens if response.usage else 0
            }
        except Exception as e:
            # Fallback to Claude Sonnet 4.5 if GPT-4.1 fails
            if self.claude_available:
                try:
                    response = self.claude_client.messages.create(
                        model="claude-sonnet-4.5",
                        max_tokens=kwargs.get("max_tokens", 3000),
                        temperature=kwargs.get("temperature", 0.8),
                        messages=[
                            {"role": "user", "content": f"Generate a detailed, cinematic scene based on: {prompt}"}
                        ]
                    )

                    return {
                        "response": response.content[0].text,
                        "model_used": "claude-sonnet-4.5",
                        "tokens_used": response.usage.input_tokens + response.usage.output_tokens
                    }
                except Exception as claude_error:
                    raise Exception(f"Both GPT-4.1 and Claude failed: GPT-4.1 error: {str(e)}, Claude error: {str(claude_error)}")
            else:
                raise Exception(f"GPT-4.1 scene generation error: {str(e)}")
    

# Global instance
ai_manager = AIModelManager()


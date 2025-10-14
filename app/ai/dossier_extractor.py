"""
Dossier Metadata Extractor
Extracts structured story metadata from chat conversations using AI
"""

import openai
import os
from dotenv import load_dotenv

load_dotenv()

class DossierExtractor:
    """Extract story metadata from conversations"""
    
    def __init__(self):
        self.api_key = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Lazy initialization to avoid import-time errors"""
        if not self._initialized:
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            self._initialized = True
    
    async def extract_metadata(self, conversation_history: list) -> dict:
        """
        Extract story metadata from conversation history
        
        Args:
            conversation_history: List of {"role": "user/assistant", "content": "text"}
        
        Returns:
            dict: Structured metadata with title, logline, genre, tone, characters, scenes
        """
        
        # Ensure we're initialized
        self._ensure_initialized()
        
        # Build conversation context
        context = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in conversation_history
        ])
        
        # Extraction prompt
        extraction_prompt = f"""Based on this conversation about a story, extract structured metadata.

Conversation:
{context}

Extract the following information (use "Unknown" if not mentioned):
1. Title: The story's working title
2. Logline: One-sentence story summary
3. Genre: Primary genre (e.g., Drama, Comedy, Thriller, Sci-Fi, Horror, Romance)
4. Tone: Overall tone (e.g., Dark, Light, Suspenseful, Intimate, Epic)
5. Characters: List of main characters with brief descriptions
6. Scenes: Key scenes or moments mentioned
7. Locations: Settings where the story takes place

Respond ONLY with valid JSON in this exact format:
{{
    "title": "string",
    "logline": "string",
    "genre": "string",
    "tone": "string",
    "characters": [
        {{
            "character_id": "char_1",
            "name": "Character Name",
            "description": "Brief description"
        }}
    ],
    "scenes": [
        {{
            "scene_id": "scene_1",
            "one_liner": "Brief scene description",
            "description": "Detailed description",
            "time_of_day": "Day/Night",
            "interior_exterior": "INT/EXT",
            "tone": "Scene tone"
        }}
    ],
    "locations": ["location1", "location2"]
}}"""

        try:
            # Call OpenAI to extract metadata
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a story analysis expert. Extract story metadata from conversations and respond ONLY with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": extraction_prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for consistent extraction
                max_completion_tokens=1000
            )
            
            # Parse the response
            metadata_text = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if metadata_text.startswith("```json"):
                metadata_text = metadata_text[7:]
            if metadata_text.startswith("```"):
                metadata_text = metadata_text[3:]
            if metadata_text.endswith("```"):
                metadata_text = metadata_text[:-3]
            
            metadata_text = metadata_text.strip()
            
            # Parse JSON
            import json
            metadata = json.loads(metadata_text)
            
            print(f"✅ Extracted metadata: {metadata}")
            
            return metadata
            
        except Exception as e:
            print(f"❌ Metadata extraction error: {str(e)}")
            # Return default structure on error
            return {
                "title": "Untitled Story",
                "logline": "A compelling story waiting to be told...",
                "genre": "Unknown",
                "tone": "Unknown",
                "characters": [],
                "scenes": [],
                "locations": []
            }
    
    async def should_update_dossier(self, conversation_history: list) -> bool:
        """
        Use LLM to intelligently determine if we should update the dossier based on conversation
        
        Args:
            conversation_history: List of messages
        
        Returns:
            bool: True if dossier should be updated
        """
        print(f"🔍 LLM checking if dossier should update. History length: {len(conversation_history)}")
        
        # Ensure we're initialized
        self._ensure_initialized()
        
        # Build conversation context
        context = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in conversation_history
        ])
        
        # LLM decision prompt
        decision_prompt = f"""You are analyzing a story development conversation to determine if the dossier should be updated.

Conversation:
{context}

Based on this conversation, should the story dossier be updated? Consider:
1. Did the user provide new story information (characters, plot, setting, genre, etc.)?
2. Did the user reveal important story details that should be captured?
3. Is there meaningful story content that wasn't in previous updates?

Respond with ONLY "YES" if the dossier should be updated, or "NO" if it shouldn't.

Decision:"""

        try:
            # Call OpenAI to make the decision
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a story analysis expert. Analyze conversations and decide if story information should be captured in a dossier. Respond with only YES or NO."
                    },
                    {
                        "role": "user",
                        "content": decision_prompt
                    }
                ],
                temperature=0.1,  # Very low temperature for consistent decisions
                max_completion_tokens=10
            )
            
            # Parse the response
            decision = response.choices[0].message.content.strip().upper()
            should_update = decision == "YES"
            
            print(f"🔍 LLM decision: {decision} -> Should update: {should_update}")
            return should_update
            
        except Exception as e:
            print(f"❌ Error in LLM dossier decision: {str(e)}")
            # Fallback: update if there are user messages with story content
            user_messages = [msg for msg in conversation_history if msg.get("role") == "user"]
            if user_messages:
                last_user_message = user_messages[-1].get("content", "").lower()
                story_keywords = ["character", "story", "plot", "main", "name", "called", "named", "wife", "husband"]
                has_story_content = any(keyword in last_user_message for keyword in story_keywords)
                print(f"🔍 Fallback decision: {has_story_content}")
                return has_story_content
            
            print(f"🔍 Fallback: Not updating dossier")
            return False


# Global instance - safe to create since we use lazy initialization
dossier_extractor = DossierExtractor()


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
        
        # Extraction prompt - Extended to include logline, characters[], scenes[]
        extraction_prompt = f"""Based on this conversation about a story, extract structured metadata following the client's slot-based framework.

Conversation:
{context}

Extract the following information (use "Unknown" if not mentioned). Always include all keys. If something is not present, use empty string for strings and [] for arrays.

STORY FRAME (Frame-first approach):
1. story_timeframe: When does the story take place?
2. story_location: Where does it take place?
3. story_world_type: Real/Invented-in-our-world/Invented-other-world
4. writer_connection_place_time: Connection to writer's time/place

CHARACTER (Subject):
5. subject_exists_real_world: boolean/unknown
6. subject_full_name: Character's name
7. subject_relationship_to_writer: Relationship to writer
8. subject_brief_description: Brief character description

STORY CRAFT:
9. problem_statement: What problem does the character face?
10. actions_taken: What actions does the character take?
11. outcome: What is the outcome?
12. likes_in_story: What does the writer like about this story?

TECHNICAL:
13. runtime: Estimated runtime (3-5 minutes)
14. title: Working title (if mentioned)
15. logline: Single-sentence premise (if implied)

CHARACTERS (array; include key even if empty):
- name, description, role (e.g., protagonist/mentor)

SCENES (array; include key even if empty):
- one_liner (short beat/scene summary)
- Optional: time_of_day, interior_exterior, tone

Respond ONLY with valid JSON in this exact format:
{{{{
    "story_timeframe": "string",
    "story_location": "string", 
    "story_world_type": "Real/Invented-in-our-world/Invented-other-world",
    "writer_connection_place_time": "string",
    "subject_exists_real_world": "boolean/unknown",
    "subject_full_name": "string",
    "subject_relationship_to_writer": "string",
    "subject_brief_description": "string",
    "problem_statement": "string",
    "actions_taken": "string", 
    "outcome": "string",
    "likes_in_story": "string",
    "runtime": "3-5 minutes",
    "title": "string",
    "logline": "string",
    "characters": [{{"name": "string", "description": "string", "role": "string"}}],
    "scenes": [{{"one_liner": "string", "time_of_day": "string", "interior_exterior": "string", "tone": "string"}}]
}}}}"""

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
            # Return default structure on error - matching client requirements
            return {
                "story_timeframe": "Unknown",
                "story_location": "Unknown", 
                "story_world_type": "Unknown",
                "writer_connection_place_time": "Unknown",
                "subject_exists_real_world": "unknown",
                "subject_full_name": "Unknown",
                "subject_relationship_to_writer": "Unknown",
                "subject_brief_description": "Unknown",
                "problem_statement": "Unknown",
                "actions_taken": "Unknown", 
                "outcome": "Unknown",
                "likes_in_story": "Unknown",
                "runtime": "3-5 minutes",
                "title": "Untitled Story",
                "logline": "",
                "characters": [],
                "scenes": []
            }


# Global instance - safe to create since we use lazy initialization
dossier_extractor = DossierExtractor()


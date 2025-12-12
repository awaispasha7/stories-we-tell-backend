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
        
        # Enhanced extraction prompt - Includes heroes, supporting characters, story type, perspective
        extraction_prompt = f"""Based on this ENTIRE conversation about a story, extract structured metadata following the client's comprehensive framework.

IMPORTANT: Read through the ENTIRE conversation from start to finish. Extract information mentioned at ANY point in the conversation, not just recent messages.

Conversation:
{context}

Extract the following information (use "Unknown" if not mentioned). Always include all keys. If something is not present, use empty string for strings and [] for arrays.

CRITICAL CHARACTER EXTRACTION RULES:
1. Extract ALL characters mentioned throughout the ENTIRE conversation, including:
   - All family members (mother, father, siblings, etc.)
   - All friends, partners, colleagues
   - All antagonists and supporting characters
   - Characters mentioned by relationship (e.g., "Cindy's mother", "her father") - extract them with proper names if given
2. If a character is mentioned as "Unknown" or "a third person" early but later identified by name, use the identified name and merge the information
3. If multiple references point to the same character (e.g., "Cindy's father" and "Robert"), merge them into one character entry
4. Do NOT create duplicate characters - if "Unknown" and "Robert" refer to the same person, only include "Robert" with all the information

STORY FRAME (Frame-first approach):
1. story_timeframe: When does the story take place? (e.g., "2017", "Winter 2018", "2039")
2. story_location: Where does it take place? (e.g., "Minnesota, US", "Oslo, Norway")
3. story_world_type: Real/Invented-in-our-world/Invented-other-world
4. writer_connection_place_time: Connection to writer's time/place
5. season_time_of_year: Season or time of year (if mentioned)
6. environmental_details: Any meaningful environmental details

CHARACTER (Subject - Legacy):
7. subject_exists_real_world: boolean/unknown
8. subject_full_name: Character's name
9. subject_relationship_to_writer: Relationship to writer
10. subject_brief_description: Brief character description

HEROES (array; up to 2 heroes - PRIMARY characters):
- name: Full name
- age_at_story: Age at time of story (number)
- relationship_to_user: Relationship to user/writer
- physical_descriptors: Physical appearance details
- personality_traits: Personality characteristics
- photo_url: URL if photo was uploaded (empty string if not)

SUPPORTING CHARACTERS (array; up to 2 - SECONDARY characters):
- name: Full name
- role: Role in story (e.g., "mentor", "antagonist", "friend")
- description: Brief description (light metadata)

STORY CRAFT:
11. problem_statement: What problem does the character face?
12. actions_taken: What actions does the character take?
13. outcome: What is the outcome?
14. likes_in_story: What does the writer like about this story?

STORY TYPE & STYLE:
15. story_type: One of: "romantic", "childhood_drama", "fantasy", "epic_legend", "adventure", "historic_action", "documentary_tone", "other"
16. audience: {{
    "who_will_see_first": "string",
    "desired_feeling": "string"
}}
17. perspective: One of: "first_person", "narrator_voice", "legend_myth_tone", "documentary_tone"

TECHNICAL:
18. runtime: Estimated runtime (3-5 minutes)
19. title: Working title (if mentioned)
20. logline: Single-sentence premise (if implied)

CHARACTERS (array; legacy format - include for backward compatibility):
- name, description, role (e.g., protagonist/mentor)
- IMPORTANT: Extract ALL characters mentioned throughout the ENTIRE conversation, not just the main ones
- If a character is mentioned as "Unknown" early but later identified by name, use the identified name
- Include ALL family members, friends, antagonists, and supporting characters mentioned
- If someone is mentioned (e.g., "Cindy's mother", "her father", "Robert"), extract them as separate characters with their proper names/relationships

SCENES (array; include key even if empty):
- one_liner (short beat/scene summary)
- Optional: time_of_day, interior_exterior, tone

Respond ONLY with valid JSON in this exact format:
{{{{
    "story_timeframe": "string",
    "story_location": "string", 
    "story_world_type": "Real/Invented-in-our-world/Invented-other-world",
    "writer_connection_place_time": "string",
    "season_time_of_year": "string",
    "environmental_details": "string",
    "subject_exists_real_world": "boolean/unknown",
    "subject_full_name": "string",
    "subject_relationship_to_writer": "string",
    "subject_brief_description": "string",
    "heroes": [{{"name": "string", "age_at_story": "number or string", "relationship_to_user": "string", "physical_descriptors": "string", "personality_traits": "string", "photo_url": "string"}}],
    "supporting_characters": [{{"name": "string", "role": "string", "description": "string", "photo_url": "string"}}],
    "problem_statement": "string",
    "actions_taken": "string", 
    "outcome": "string",
    "likes_in_story": "string",
    "story_type": "romantic|childhood_drama|fantasy|epic_legend|adventure|historic_action|documentary_tone|other",
    "audience": {{"who_will_see_first": "string", "desired_feeling": "string"}},
    "perspective": "first_person|narrator_voice|legend_myth_tone|documentary_tone",
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
                max_completion_tokens=2000  # Increased for more detailed extraction
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
                "season_time_of_year": "",
                "environmental_details": "",
                "subject_exists_real_world": "unknown",
                "subject_full_name": "Unknown",
                "subject_relationship_to_writer": "Unknown",
                "subject_brief_description": "Unknown",
                "heroes": [],
                "supporting_characters": [],
                "problem_statement": "Unknown",
                "actions_taken": "Unknown", 
                "outcome": "Unknown",
                "likes_in_story": "Unknown",
                "story_type": "other",
                "audience": {"who_will_see_first": "", "desired_feeling": ""},
                "perspective": "narrator_voice",
                "runtime": "3-5 minutes",
                "title": "Untitled Story",
                "logline": "",
                "characters": [],
                "scenes": []
            }


# Global instance - safe to create since we use lazy initialization
dossier_extractor = DossierExtractor()


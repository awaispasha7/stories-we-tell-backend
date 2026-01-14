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
        
        # Build conversation context - include attached files information
        context_parts = []
        photo_urls_by_character = {}  # Track photo URLs mentioned for characters
        
        for msg in conversation_history:
            role = msg.get('role', 'unknown').upper()
            content = msg.get('content', '')
            attached_files = msg.get('attached_files', []) or []
            
            # Build message line
            msg_line = f"{role}: {content}"
            
            # If there are attached files, include them in context
            if attached_files:
                file_info = []
                for file in attached_files:
                    file_name = file.get('name', 'unknown')
                    file_url = file.get('url', '')
                    file_type = file.get('type', 'unknown')
                    
                    if file_type == 'image' or file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        file_info.append(f"[IMAGE: {file_name} - URL: {file_url}]")
                        # Try to extract character name from the message content
                        # Look for patterns like "this is [name]", "this is my [character]", "[name]'s photo", etc.
                        import re
                        # Common patterns: "this is John", "this is my character John", "John's photo", "photo of Mary", "here's John"
                        char_patterns = [
                            r"this is (?:my )?(?:character )?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                            r"this is ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'s",
                            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'s photo",
                            r"photo of ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?) (?:is|looks like|appears as)",
                            r"here'?s ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?) (?:photo|picture|image)",
                            r"meet ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?) (?:here|attached)",
                        ]
                        for pattern in char_patterns:
                            match = re.search(pattern, content, re.IGNORECASE)
                            if match:
                                char_name = match.group(1).strip()
                                # Normalize name (capitalize first letter of each word)
                                char_name = ' '.join(word.capitalize() for word in char_name.split())
                                if char_name not in photo_urls_by_character:
                                    photo_urls_by_character[char_name] = []
                                photo_urls_by_character[char_name].append(file_url)
                                print(f"📸 [PHOTO ASSOCIATION] Found photo for character '{char_name}': {file_url[:50]}...")
                                break
                
                if file_info:
                    msg_line += " " + " ".join(file_info)
            
            context_parts.append(msg_line)
        
        context = "\n".join(context_parts)
        
        # Add photo URL mapping to the prompt for reference
        photo_context = ""
        if photo_urls_by_character:
            photo_context = "\n\nPHOTO URLS FOUND IN CONVERSATION:\n"
            for char_name, urls in photo_urls_by_character.items():
                photo_context += f"- {char_name}: {', '.join(urls)}\n"
            photo_context += "\nWhen extracting characters, use these photo URLs for the matching character names.\n"
        
        # Enhanced extraction prompt - Includes heroes, supporting characters, story type, perspective
        extraction_prompt = f"""Based on this ENTIRE conversation about a story, extract structured metadata following the client's comprehensive framework.

CRITICAL INSTRUCTIONS:
1. Read through the ENTIRE conversation from start to finish - do NOT skip any messages
2. Extract information mentioned at ANY point in the conversation, not just recent messages
3. Extract ALL scenes mentioned - do NOT limit the number of scenes. If the story has 30 scenes, extract all 30
4. Extract ALL characters mentioned - include every person, even minor ones
5. Do NOT truncate or summarize - extract complete information for every field
6. For problem_statement, actions_taken, and outcome: Read the ENTIRE story FIRST, then extract the ACTUAL/FINAL values based on the complete story arc, not just early mentions
7. The outcome MUST reflect how the story actually ends - read to the very end of the conversation to find the final resolution

Conversation:
{context}{photo_context}

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
  * CRITICAL: Look for photo URLs in the conversation history where the user mentions the character's name
  * If the user says "this is John" or "this is my character John" with an image attached, use that image URL for John's photo_url
  * Match photo URLs to character names based on the message context where the photo was shared

SUPPORTING CHARACTERS (array; up to 2 - SECONDARY characters):
- name: Full name
- role: Role in story (e.g., "mentor", "antagonist", "friend")
- description: Brief description (light metadata)
- photo_url: URL if photo was uploaded (empty string if not)
  * CRITICAL: Look for photo URLs in the conversation history where the user mentions the character's name
  * If the user says "this is Mary" or mentions a supporting character with an image attached, use that image URL
  * Match photo URLs to character names based on the message context where the photo was shared

STORY CRAFT (CRITICAL - Extract the ACTUAL/FINAL story elements, not just early mentions):
11. problem_statement: What is the ACTUAL/CORE problem the character faces in this story? 
    - Read the ENTIRE story to understand the full context
    - Extract the REAL problem that drives the story, not just what was mentioned in the beginning
    - If the problem evolves or becomes clearer later in the story, use the FINAL/ACTUAL problem
    - This should reflect the central conflict or challenge the character must overcome
    
12. actions_taken: What ACTIONS does the character take to address the problem or navigate the situation?
    - Extract the key actions taken throughout the ENTIRE story
    - Include actions mentioned at any point in the conversation
    - Focus on actions that are meaningful to the story's progression
    - If actions are described later in the story, include those as well
    
13. outcome: What is the FINAL outcome/resolution of the story?
    - This is CRITICAL: Extract the ACTUAL ending/outcome, not just what was mentioned early
    - Read to the very end of the conversation to find how the story actually concludes
    - If the story ends in confusion, uncertainty, or a specific way, capture that EXACT outcome
    - The outcome should reflect the final state of the story as described at the end
    - Examples: "Story ends in confusion and perplexion", "Character accepts the loss", "Story ends with sunset and reflection"
    
14. likes_in_story: What does the writer like about this story?
    - Extract what the writer explicitly says they like or find special about the story
    - Look for phrases like "I like the fact that...", "This story is special because...", "What makes this special..."

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

SCENES (array; CRITICAL - extract ALL scenes mentioned in the conversation):
- Extract EVERY scene, beat, or story moment mentioned throughout the ENTIRE conversation
- Do NOT limit the number of scenes - include ALL scenes, even if there are 20, 30, or more
- Read through the entire conversation chronologically and extract scenes in the order they appear in the story
- one_liner (short beat/scene summary)
- Optional: time_of_day, interior_exterior, tone
- IMPORTANT: If the conversation describes many scenes, extract ALL of them - completeness is more important than brevity
- IMPORTANT: Read through the entire conversation and extract scenes in chronological order as they appear in the story

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
                model="gpt-4o",  # Use GPT-4o for more accurate extraction of final story elements
                messages=[
                    {
                        "role": "system",
                        "content": "You are a story analysis expert. Read the ENTIRE conversation from start to finish before extracting metadata. Pay special attention to the FINAL problem, actions, and outcome as described at the end of the story, not just early mentions. Extract story metadata and respond ONLY with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": extraction_prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for consistent extraction
                max_completion_tokens=4000  # Increased significantly to allow for all scenes, characters, and details
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
            
            # Extract early genre hints using genre detector
            try:
                from ..services.genre_detector import genre_detector
                early_genre_hints = genre_detector.detect_early_hints(metadata)
                if early_genre_hints:
                    metadata["genre_predictions"] = early_genre_hints
                    print(f"🎭 [GENRE] Extracted {len(early_genre_hints)} early genre hints")
            except Exception as e:
                print(f"⚠️ [GENRE] Failed to extract early genre hints: {e}")
                # Continue without genre hints

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
                "scenes": [],
                "genre_predictions": []  # Empty early hints on error
            }


# Global instance - safe to create since we use lazy initialization
dossier_extractor = DossierExtractor()


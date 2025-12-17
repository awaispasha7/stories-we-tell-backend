"""
Synopsis Generator Service
Generates 500-800 word synopsis from clean dossier data (Step 10)
"""

from typing import Dict, Any, Optional
from ..ai.models import AIModelManager, TaskType


class SynopsisGenerator:
    """Service for generating story synopsis from dossier data"""
    
    def __init__(self):
        self.ai_manager = AIModelManager()
    
    async def generate_synopsis(
        self,
        dossier_data: Dict[str, Any],
        project_id: str
    ) -> Optional[str]:
        """
        Generate a 500-800 word synopsis from clean dossier data.
        
        Args:
            dossier_data: Clean dossier data with character profiles, story type, setting, etc.
            project_id: Project ID for reference
        
        Returns:
            Generated synopsis text (500-800 words), or None if generation fails
        """
        try:
            print(f"📝 [SYNOPSIS] Starting synopsis generation for project {project_id}")
            
            # Build synopsis prompt from dossier data
            synopsis_prompt = self._build_synopsis_prompt(dossier_data)
            
            # Use DESCRIPTION task type (Gemini 2.5 Pro) for creative narrative generation
            print(f"📝 [SYNOPSIS] Calling AI model for synopsis generation...")
            response = await self.ai_manager.generate_response(
                task_type=TaskType.DESCRIPTION,
                user_prompt=synopsis_prompt,
                conversation_history=[],
                project_id=project_id
            )
            
            if not response:
                print(f"❌ [SYNOPSIS] AI model returned empty response")
                return None
            
            synopsis = response.strip()
            word_count = len(synopsis.split())
            
            print(f"✅ [SYNOPSIS] Generated synopsis: {word_count} words")
            
            # Validate word count (should be 500-800 words)
            if word_count < 400:
                print(f"⚠️ [SYNOPSIS] Synopsis is shorter than expected ({word_count} words)")
            elif word_count > 1000:
                print(f"⚠️ [SYNOPSIS] Synopsis is longer than expected ({word_count} words)")
            
            return synopsis
            
        except Exception as e:
            print(f"❌ [SYNOPSIS] Error generating synopsis: {e}")
            import traceback
            print(f"❌ [SYNOPSIS] Traceback: {traceback.format_exc()}")
            return None
    
    def _build_synopsis_prompt(self, dossier_data: Dict[str, Any]) -> str:
        """Build the prompt for synopsis generation from dossier data"""
        
        # Extract key information
        title = dossier_data.get('title', 'Untitled Story')
        logline = dossier_data.get('logline', '')
        genre = dossier_data.get('genre', '')
        tone = dossier_data.get('tone', '')
        
        # Hero characters
        heroes = dossier_data.get('heroes', [])
        hero_info = []
        for idx, hero in enumerate(heroes, 1):
            hero_parts = []
            if hero.get('name'):
                hero_parts.append(f"Name: {hero['name']}")
            if hero.get('age_at_story'):
                hero_parts.append(f"Age: {hero['age_at_story']}")
            if hero.get('relationship_to_user'):
                hero_parts.append(f"Relationship: {hero['relationship_to_user']}")
            if hero.get('physical_descriptors'):
                hero_parts.append(f"Physical: {hero['physical_descriptors']}")
            if hero.get('personality_traits'):
                hero_parts.append(f"Personality: {hero['personality_traits']}")
            if hero_parts:
                hero_info.append(f"Hero {idx}: {' | '.join(hero_parts)}")
        
        # Supporting characters
        supporting = dossier_data.get('supporting_characters', [])
        supporting_info = []
        for idx, char in enumerate(supporting, 1):
            char_parts = []
            if char.get('name'):
                char_parts.append(f"Name: {char['name']}")
            if char.get('role'):
                char_parts.append(f"Role: {char['role']}")
            if char.get('description'):
                char_parts.append(f"Description: {char['description']}")
            if char_parts:
                supporting_info.append(f"Supporting {idx}: {' | '.join(char_parts)}")
        
        # Setting & Time
        setting_parts = []
        if dossier_data.get('story_location'):
            setting_parts.append(f"Location: {dossier_data['story_location']}")
        if dossier_data.get('story_timeframe'):
            setting_parts.append(f"Timeframe: {dossier_data['story_timeframe']}")
        if dossier_data.get('season_time_of_year'):
            setting_parts.append(f"Season: {dossier_data['season_time_of_year']}")
        if dossier_data.get('environmental_details'):
            setting_parts.append(f"Environmental: {dossier_data['environmental_details']}")
        
        # Story Type & Perspective
        story_type = dossier_data.get('story_type', '').replace('_', ' ').title() if dossier_data.get('story_type') else ''
        perspective = dossier_data.get('perspective', '').replace('_', ' ').title() if dossier_data.get('perspective') else ''
        audience = dossier_data.get('audience', {})
        who_will_see = audience.get('who_will_see_first', '') if isinstance(audience, dict) else ''
        desired_feeling = audience.get('desired_feeling', '') if isinstance(audience, dict) else ''
        
        # Build the prompt
        prompt = f"""Write a compelling 500-800 word synopsis for this story. The synopsis should be pure narrative, not technical. It should capture the emotional arc, character development, and story structure in a way that feels cinematic and engaging.

STORY FRAME:
Title: {title}
Logline: {logline}
Genre: {genre}
Tone: {tone}

CHARACTERS:
{chr(10).join(hero_info) if hero_info else 'No hero characters specified'}
{chr(10).join(supporting_info) if supporting_info else ''}

SETTING & TIME:
{chr(10).join(setting_parts) if setting_parts else 'Setting not specified'}

STORY TYPE & PERSPECTIVE:
Story Type: {story_type}
Perspective: {perspective}
Audience: {who_will_see}
Desired Feeling: {desired_feeling}

REQUIREMENTS:
1. Write a 500-800 word synopsis that tells the story in narrative form
2. Include the emotional arc - how the story progresses emotionally
3. Include brief character notes - who they are and their role in the story
4. Include brief setting notes - where and when the story takes place
5. Imply the story structure - beginning, middle, end, key moments
6. Make it pure narrative - no technical details, no shot descriptions, no camera language
7. Write in a cinematic, engaging style that captures the essence of the story
8. The synopsis should feel like reading a story, not a technical document

Write the synopsis now:"""
        
        return prompt


# Global instance
synopsis_generator = SynopsisGenerator()


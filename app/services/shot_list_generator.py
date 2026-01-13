"""
Shot List Generator Service
Generates structured shot list from script (Step 13)
"""

from typing import Dict, Any, Optional
import json
import os
from dotenv import load_dotenv

load_dotenv()

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class ShotListGenerator:
    """Service for generating shot list from script"""
    
    def __init__(self):
        if OPENAI_AVAILABLE:
            openai.api_key = os.getenv("OPENAI_API_KEY")
    
    async def generate_shot_list(
        self,
        script: str,
        dossier_data: Dict[str, Any],
        project_id: str,
        special_instructions: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a structured shot list from script.
        
        Args:
            script: Generated script text
            dossier_data: Dossier data for context (characters, setting, etc.)
            project_id: Project ID for reference
            special_instructions: Optional special instructions for shot list generation
        
        Returns:
            Generated shot list as JSON dict, or None if generation fails
        """
        try:
            print(f"📝 [SHOT_LIST] Starting shot list generation for project {project_id}")
            
            # Build shot list prompt from script and dossier data
            shot_list_prompt = self._build_shot_list_prompt(script, dossier_data, special_instructions)
            
            # Use GPT-4.1 for structured output
            print(f"📝 [SHOT_LIST] Calling AI model for shot list generation...")
            
            if not OPENAI_AVAILABLE:
                print(f"❌ [SHOT_LIST] OpenAI not available")
                return None
            
            response = openai.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional cinematographer and film director. Create detailed, structured shot lists that serve as blueprints for visual generation. Output valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": shot_list_prompt
                    }
                ],
                max_completion_tokens=8000,  # Shot lists can be lengthy
                temperature=0.7,
                top_p=1.0,
                n=1,
                stream=False,
                response_format={"type": "json_object"}  # Ensure JSON output
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                shot_list = json.loads(response_text)
                print(f"✅ [SHOT_LIST] Generated shot list with {len(shot_list.get('scenes', []))} scenes")
                return shot_list
            except json.JSONDecodeError as e:
                print(f"❌ [SHOT_LIST] Failed to parse JSON response: {e}")
                print(f"❌ [SHOT_LIST] Response: {response_text[:500]}...")
                return None
            
        except Exception as e:
            print(f"❌ [SHOT_LIST] Error generating shot list: {e}")
            import traceback
            print(f"❌ [SHOT_LIST] Traceback: {traceback.format_exc()}")
            return None
    
    def _build_shot_list_prompt(
        self,
        script: str,
        dossier_data: Dict[str, Any],
        special_instructions: Optional[str] = None
    ) -> str:
        """Build the prompt for shot list generation from script and dossier data"""
        
        # Extract character information for context
        heroes = dossier_data.get('heroes', [])
        hero_names = [hero.get('name', '') for hero in heroes if hero.get('name')]
        supporting = dossier_data.get('supporting_characters', [])
        supporting_names = [char.get('name', '') for char in supporting if char.get('name')]
        all_characters = hero_names + supporting_names
        
        # Build the prompt
        prompt = f"""Convert the following script into a detailed, structured shot list JSON format. The shot list serves as a blueprint for visual generation.

SCRIPT:
{script}

CHARACTERS IN STORY:
{', '.join(all_characters) if all_characters else 'No characters specified'}

REQUIREMENTS:
Create a comprehensive shot list with the following structure:

{{
  "scenes": [
    {{
      "scene_number": 1,
      "scene_description": "Brief description of the scene",
      "shots": [
        {{
          "shot_number": 1,
          "shot_type": "wide/medium/close-up/extreme close-up/etc",
          "description": "Visual description of the shot",
          "character_presence": ["character1", "character2"],
          "dialogue": "Any dialogue in this shot",
          "voice_over": "Any voice-over/narration text",
          "atmosphere": "Mood and atmosphere description",
          "environment": "Environment/setting details",
          "transitions": {{
            "from_previous": "transition type (cut/fade/dissolve/etc)",
            "to_next": "transition type"
          }},
          "timing": {{
            "estimated_duration_seconds": 5,
            "pacing": "fast/medium/slow",
            "emotional_beat": "Description of emotional moment"
          }}
        }}
      ],
      "overall_atmosphere": "Scene atmosphere",
      "environment_reference": "Environment details for the scene",
      "narrative_pacing": {{
        "pace": "fast/medium/slow",
        "emotional_arc": "Description of emotional progression",
        "key_moments": ["moment1", "moment2"]
      }}
    }}
  ],
  "overall_pacing_math": {{
    "total_estimated_duration_seconds": 180,
    "total_shots": 20,
    "average_shot_duration": 9,
    "transition_time_total": 10
  }}
}}

CRITICAL REQUIREMENTS:
1. Break down the script scene-by-scene
2. For each scene, create multiple shots (typically 3-8 shots per scene)
3. Specify character presence for each shot
4. Include dialogue and voice-over text from the script
5. Describe atmosphere, environment, and mood for each shot
6. Specify transitions between shots
7. Include timing estimates (duration, pacing, emotional beats)
8. Calculate overall pacing math (total duration, shot counts, etc.)
9. Ensure the shot list serves as a complete blueprint for visual generation
10. Output ONLY valid JSON - no additional text before or after

Generate the complete shot list now:"""
        
        # Add special instructions if provided
        if special_instructions and special_instructions.strip():
            prompt += f"""

ADMIN SPECIAL INSTRUCTIONS (CRITICAL - Follow these guidelines):
{special_instructions.strip()}

Please incorporate these instructions into your shot list generation."""
        
        return prompt


# Global instance
shot_list_generator = ShotListGenerator()


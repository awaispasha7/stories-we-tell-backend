"""
Script Generator Service
Generates 500-800 word full script from approved synopsis and dossier data (Step 12)
"""

from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv

load_dotenv()

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class ScriptGenerator:
    """Service for generating full script from synopsis and dossier data"""
    
    def __init__(self):
        if OPENAI_AVAILABLE:
            openai.api_key = os.getenv("OPENAI_API_KEY")
        if ANTHROPIC_AVAILABLE:
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            if anthropic_key and anthropic_key != "your_anthropic_api_key_here":
                self.claude_client = anthropic.Anthropic(api_key=anthropic_key)
                self.claude_available = True
            else:
                self.claude_available = False
        else:
            self.claude_available = False
    
    async def generate_script(
        self,
        synopsis: str,
        dossier_data: Dict[str, Any],
        project_id: str,
        special_instructions: Optional[str] = None,
        genre: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a 500-800 word full script from synopsis and dossier data.
        
        Args:
            synopsis: Approved synopsis text
            dossier_data: Clean dossier data with character profiles, story type, setting, etc.
            project_id: Project ID for reference
            special_instructions: Optional special instructions for script generation
        
        Returns:
            Generated script text (500-800 words), or None if generation fails
        """
        try:
            print(f"📝 [SCRIPT] Starting script generation for project {project_id}")
            
            # Build script prompt from synopsis and dossier data (with genre-specific agent)
            script_prompt = self._build_script_prompt(synopsis, dossier_data, special_instructions, genre)
            
            # Use GPT-4.1 as primary (flagship for deep text generation)
            # Pass max_tokens to ensure we get 500-800 words (approximately 2000-3200 tokens)
            print(f"📝 [SCRIPT] Calling AI model for script generation...")
            
            script = None
            
            # Get genre-specific system prompt if genre is provided
            system_prompt = self._get_system_prompt(genre)
            
            if OPENAI_AVAILABLE:
                try:
                    response = openai.chat.completions.create(
                        model="gpt-4.1",
                        messages=[
                            {
                                "role": "system",
                                "content": system_prompt
                            },
                            {
                                "role": "user",
                                "content": script_prompt
                            }
                        ],
                        max_completion_tokens=3200,  # Enough for 800 words
                        temperature=0.7,
                        top_p=1.0,
                        n=1,
                        stream=False,
                        presence_penalty=0.0,
                        frequency_penalty=0.0
                    )
                    
                    script = response.choices[0].message.content.strip()
                    print(f"📝 [SCRIPT] Generated with GPT-4.1")
                    
                except Exception as e:
                    print(f"⚠️ [SCRIPT] GPT-4.1 failed: {e}")
                    script = None
            
            # Fallback to Claude Sonnet 4.5 if GPT-4.1 failed or unavailable
            if not script and self.claude_available:
                try:
                    response = self.claude_client.messages.create(
                        model="claude-sonnet-4-5-20250929",
                        max_tokens=3200,
                        temperature=0.7,
                        messages=[
                            {"role": "user", "content": script_prompt}
                        ]
                    )
                    
                    script = response.content[0].text.strip()
                    print(f"📝 [SCRIPT] Generated with Claude Sonnet 4.5 (fallback)")
                    
                except Exception as e:
                    print(f"⚠️ [SCRIPT] Claude Sonnet 4.5 also failed: {e}")
                    return None
            
            if not script:
                print(f"❌ [SCRIPT] No AI models available or all failed")
                return None
            
            word_count = len(script.split())
            
            print(f"✅ [SCRIPT] Generated script: {word_count} words")
            print(f"📝 [SCRIPT] First 200 chars: {script[:200]}...")
            print(f"📝 [SCRIPT] Last 200 chars: ...{script[-200:]}")
            
            # Validate word count (should be 500-800 words)
            if word_count < 400:
                print(f"⚠️ [SCRIPT] WARNING: Script is much shorter than expected ({word_count} words)")
                print(f"⚠️ [SCRIPT] This might indicate the response was truncated")
                if script and not script.rstrip().endswith(('.', '!', '?', '"', "'")):
                    print(f"⚠️ [SCRIPT] Response appears to be cut off (doesn't end with punctuation)")
            elif word_count > 1000:
                print(f"⚠️ [SCRIPT] Script is longer than expected ({word_count} words)")
            
            return script
            
        except Exception as e:
            print(f"❌ [SCRIPT] Error generating script: {e}")
            import traceback
            print(f"❌ [SCRIPT] Traceback: {traceback.format_exc()}")
            return None
    
    def _get_system_prompt(self, genre: Optional[str] = None) -> str:
        """Get genre-specific system prompt"""
        if genre:
            try:
                from ..ai.genre_agents import genre_agents
                return genre_agents.get_system_prompt(genre)
            except Exception as e:
                print(f"⚠️ [SCRIPT] Failed to get genre-specific prompt: {e}")
        
        # Default system prompt
        return "You are a professional scriptwriter specializing in cinematic storytelling and video narration. Create engaging, emotionally resonant scripts that bring stories to life through narrative, dialogue, voice-over, and scene structure."
    
    def _build_script_prompt(
        self,
        synopsis: str,
        dossier_data: Dict[str, Any],
        special_instructions: Optional[str] = None,
        genre: Optional[str] = None
    ) -> str:
        """Build the prompt for script generation from synopsis and dossier data"""
        
        # Extract key information from dossier
        title = dossier_data.get('title', 'Untitled Story')
        logline = dossier_data.get('logline', '')
        dossier_genre = dossier_data.get('genre', '')
        # Use provided genre parameter if available, otherwise fall back to dossier genre
        final_genre = genre if genre else dossier_genre
        tone = dossier_data.get('tone', '')
        
        # Story Type & Perspective
        story_type = dossier_data.get('story_type', '').replace('_', ' ').title() if dossier_data.get('story_type') else ''
        perspective = dossier_data.get('perspective', '').replace('_', ' ').title() if dossier_data.get('perspective') else ''
        audience = dossier_data.get('audience', {})
        who_will_see = audience.get('who_will_see_first', '') if isinstance(audience, dict) else ''
        desired_feeling = audience.get('desired_feeling', '') if isinstance(audience, dict) else ''
        
        # Build the prompt
        prompt = f"""Expand the following synopsis into a complete, production-ready script for video narration. The script should be 500-800 words and designed for a 3-4 minute runtime.

SYNOPSIS:
{synopsis}

STORY CONTEXT:
Title: {title}
Logline: {logline}
Genre: {final_genre}
Tone: {tone}
Story Type: {story_type}
Perspective: {perspective}
Audience: {who_will_see}
Desired Feeling: {desired_feeling}

SCRIPT REQUIREMENTS:
1. CRITICAL: Write EXACTLY 500-800 words. Do not stop short. The script must be complete and comprehensive.
2. Include a structured narrative that flows scene-by-scene
3. Include dialogue (if applicable to the story type)
4. Include voice-over/narration text appropriate for video
5. Structure scenes clearly with scene breaks
6. Include emotional beats - moments of tension, release, connection, resolution
7. Maintain the tone and narrative POV specified
8. Ensure the script length translates to approximately 3-4 minutes of video runtime (approximately 150-200 words per minute)
9. Make it human quality, readable, and designed for video narration
10. The script should feel cinematic and engaging, bringing the synopsis to life

FORMAT:
Structure the script with clear scene breaks. For each scene, include:
- Scene description/action
- Dialogue (if applicable)
- Voice-over/narration text
- Emotional beats and pacing notes

Write the complete script now, ensuring you reach at least 500 words:"""
        
        # Add genre-specific guidance if genre is provided
        if final_genre:
            prompt += f"""

GENRE-SPECIFIC GUIDANCE:
This script should be written in the {final_genre} genre. Please ensure the script reflects the conventions, tone, and style appropriate for this genre."""
        
        # Add special instructions if provided
        if special_instructions and special_instructions.strip():
            prompt += f"""

ADMIN SPECIAL INSTRUCTIONS (CRITICAL - Follow these guidelines):
{special_instructions.strip()}

Please incorporate these instructions into your script generation."""
        
        return prompt


# Global instance
script_generator = ScriptGenerator()


"""
Genre Detection Service
Detects story genres at multiple stages (early hints from dossier, refined after synopsis)
"""

from typing import Dict, Any, List, Optional
import json
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


class GenreDetector:
    """Service for detecting story genres with confidence scores"""
    
    # Supported genres list
    SUPPORTED_GENRES = [
        "Historic Romance",
        "Family Saga",
        "Childhood Adventure",
        "Documentary",
        "Historical Epic",
        "Romantic",
        "Drama",
        "Comedy",
        "Thriller",
        "Action",
        "Adventure",
        "Fantasy",
        "Sci-Fi",
        "Horror",
        "Mystery",
        "Biographical",
        "Historical",
        "Coming of Age",
        "Family",
        "War",
        "Western",
        "Musical",
        "Animation",
        "Crime",
        "Noir",
        "Supernatural",
        "Epic",
        "Legend"
    ]
    
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
    
    def detect_early_hints(self, dossier_data: Dict[str, Any]) -> List[Dict[str, float]]:
        """
        Stage 1: Extract early genre hints from dossier metadata (low confidence)
        
        Args:
            dossier_data: Dossier data with story metadata
            
        Returns:
            List of genre predictions with confidence scores (0.0-1.0)
        """
        try:
            print(f"🎭 [GENRE] Starting early genre detection from dossier data")
            
            # Extract relevant metadata
            story_type = dossier_data.get('story_type', '').replace('_', ' ').title()
            tone = dossier_data.get('tone', '').lower()
            genre = dossier_data.get('genre', '').lower()
            
            # Map story_type to potential genres
            story_type_to_genres = {
                'romantic': ['Historic Romance', 'Romantic', 'Drama'],
                'childhood_drama': ['Childhood Adventure', 'Coming of Age', 'Drama'],
                'fantasy': ['Fantasy', 'Supernatural', 'Epic'],
                'epic_legend': ['Historical Epic', 'Epic', 'Legend'],
                'adventure': ['Adventure', 'Action', 'Childhood Adventure'],
                'historic_action': ['Historical Epic', 'Action', 'War'],
                'documentary_tone': ['Documentary', 'Biographical', 'Historical']
            }
            
            # Start with base predictions
            predictions = {}
            
            # If genre is already set, give it high confidence
            if genre:
                genre_normalized = genre.title()
                if genre_normalized in self.SUPPORTED_GENRES:
                    predictions[genre_normalized] = 0.6
            
            # Map story_type to genres
            if story_type.lower() in story_type_to_genres:
                for mapped_genre in story_type_to_genres[story_type.lower()]:
                    if mapped_genre in self.SUPPORTED_GENRES:
                        current_conf = predictions.get(mapped_genre, 0.0)
                        predictions[mapped_genre] = max(current_conf, 0.4)
            
            # Tone-based hints
            if 'romantic' in tone:
                predictions['Romantic'] = max(predictions.get('Romantic', 0.0), 0.3)
                predictions['Historic Romance'] = max(predictions.get('Historic Romance', 0.0), 0.25)
            if 'dramatic' in tone or 'drama' in tone:
                predictions['Drama'] = max(predictions.get('Drama', 0.0), 0.3)
            if 'adventure' in tone:
                predictions['Adventure'] = max(predictions.get('Adventure', 0.0), 0.3)
            
            # Convert to list format and normalize
            genre_list = [
                {"genre": genre, "confidence": min(conf, 0.5)}  # Cap at 0.5 for early detection
                for genre, conf in predictions.items()
            ]
            
            # Sort by confidence descending
            genre_list.sort(key=lambda x: x["confidence"], reverse=True)
            
            # Return top 5
            result = genre_list[:5]
            
            print(f"🎭 [GENRE] Early detection found {len(result)} genre hints")
            for pred in result:
                print(f"  - {pred['genre']}: {pred['confidence']:.2%}")
            
            return result
            
        except Exception as e:
            print(f"❌ [GENRE] Error in early genre detection: {e}")
            return []
    
    async def refine_from_synopsis(
        self,
        synopsis: str,
        dossier_data: Dict[str, Any],
        early_hints: Optional[List[Dict[str, float]]] = None
    ) -> List[Dict[str, float]]:
        """
        Stage 2: Refine genre predictions by analyzing synopsis text (high confidence)
        
        Args:
            synopsis: Generated synopsis text
            dossier_data: Dossier data for context
            early_hints: Optional early genre hints from Stage 1
            
        Returns:
            List of top 5 genre predictions with confidence scores (0.0-1.0)
        """
        try:
            print(f"🎭 [GENRE] Starting refined genre detection from synopsis")
            
            # Build prompt for genre detection
            prompt = self._build_genre_detection_prompt(synopsis, dossier_data, early_hints)
            
            # Use GPT-4.1 or Claude Sonnet 4.5 for genre detection
            predictions = None
            
            if OPENAI_AVAILABLE:
                try:
                    response = openai.chat.completions.create(
                        model="gpt-4.1",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a genre classification expert. Analyze story synopses and return genre predictions with confidence scores. Always return valid JSON."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        temperature=0.3,  # Lower temperature for consistent classification
                        max_completion_tokens=1000
                    )
                    
                    response_text = response.choices[0].message.content.strip()
                    predictions = self._parse_genre_response(response_text)
                    print(f"🎭 [GENRE] Generated with GPT-4.1")
                    
                except Exception as e:
                    print(f"⚠️ [GENRE] GPT-4.1 failed: {e}")
                    predictions = None
            
            # Fallback to Claude if GPT failed
            if not predictions and self.claude_available:
                try:
                    response = self.claude_client.messages.create(
                        model="claude-sonnet-4-5-20250929",
                        max_tokens=1000,
                        temperature=0.3,
                        messages=[
                            {"role": "user", "content": prompt}
                        ]
                    )
                    
                    response_text = response.content[0].text.strip()
                    predictions = self._parse_genre_response(response_text)
                    print(f"🎭 [GENRE] Generated with Claude Sonnet 4.5 (fallback)")
                    
                except Exception as e:
                    print(f"⚠️ [GENRE] Claude Sonnet 4.5 also failed: {e}")
                    return self._fallback_predictions(early_hints)
            
            if not predictions:
                print(f"⚠️ [GENRE] All AI models failed, using fallback")
                return self._fallback_predictions(early_hints)
            
            # Validate and normalize predictions
            validated = self._validate_predictions(predictions)
            
            # Return top 5
            result = validated[:5]
            
            print(f"✅ [GENRE] Refined detection found {len(result)} genres")
            for pred in result:
                print(f"  - {pred['genre']}: {pred['confidence']:.2%}")
            
            return result
            
        except Exception as e:
            print(f"❌ [GENRE] Error in refined genre detection: {e}")
            import traceback
            print(f"❌ [GENRE] Traceback: {traceback.format_exc()}")
            return self._fallback_predictions(early_hints)
    
    def _build_genre_detection_prompt(
        self,
        synopsis: str,
        dossier_data: Dict[str, Any],
        early_hints: Optional[List[Dict[str, float]]] = None
    ) -> str:
        """Build the prompt for genre detection"""
        
        # Extract context
        title = dossier_data.get('title', 'Untitled Story')
        story_type = dossier_data.get('story_type', '').replace('_', ' ').title()
        
        prompt = f"""Analyze the following story synopsis and predict the most likely genres with confidence scores.

STORY CONTEXT:
Title: {title}
Story Type: {story_type}

SYNOPSIS:
{synopsis}

AVAILABLE GENRES:
{', '.join(self.SUPPORTED_GENRES)}

INSTRUCTIONS:
1. Analyze the synopsis for genre indicators: themes, tone, narrative style, character types, setting, plot structure
2. Predict the top 5 most likely genres with confidence scores (0.0 to 1.0)
3. Confidence scores should sum to approximately 1.0 (they don't need to be mutually exclusive)
4. Consider primary genres like "Historic Romance", "Family Saga", "Childhood Adventure", "Documentary", "Historical Epic" as priority options
5. Also consider secondary genres if they strongly match

EARLY HINTS (from story metadata):
{json.dumps(early_hints, indent=2) if early_hints else 'None'}

Respond with ONLY valid JSON in this exact format:
{{
    "predictions": [
        {{"genre": "Genre Name", "confidence": 0.45}},
        {{"genre": "Genre Name", "confidence": 0.30}},
        ...
    ]
}}

Return exactly 5 predictions, sorted by confidence descending."""
        
        return prompt
    
    def _parse_genre_response(self, response_text: str) -> List[Dict[str, float]]:
        """Parse AI response into genre predictions"""
        try:
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Parse JSON
            data = json.loads(response_text)
            
            # Extract predictions
            if isinstance(data, dict) and "predictions" in data:
                return data["predictions"]
            elif isinstance(data, list):
                return data
            else:
                print(f"⚠️ [GENRE] Unexpected response format: {type(data)}")
                return []
                
        except json.JSONDecodeError as e:
            print(f"❌ [GENRE] Failed to parse JSON response: {e}")
            print(f"❌ [GENRE] Response text: {response_text[:500]}")
            return []
        except Exception as e:
            print(f"❌ [GENRE] Error parsing response: {e}")
            return []
    
    def _validate_predictions(self, predictions: List[Dict[str, float]]) -> List[Dict[str, float]]:
        """Validate and normalize genre predictions"""
        validated = []
        
        for pred in predictions:
            genre = pred.get("genre", "").strip()
            confidence = float(pred.get("confidence", 0.0))
            
            # Normalize genre name (title case)
            genre = genre.title()
            
            # Check if genre is supported
            if genre not in self.SUPPORTED_GENRES:
                # Try to find close match
                genre_lower = genre.lower()
                for supported in self.SUPPORTED_GENRES:
                    if supported.lower() == genre_lower:
                        genre = supported
                        break
                else:
                    # Skip unsupported genres
                    continue
            
            # Clamp confidence to 0.0-1.0
            confidence = max(0.0, min(1.0, confidence))
            
            if confidence > 0.0:
                validated.append({"genre": genre, "confidence": confidence})
        
        # Sort by confidence descending
        validated.sort(key=lambda x: x["confidence"], reverse=True)
        
        return validated
    
    def _fallback_predictions(self, early_hints: Optional[List[Dict[str, float]]] = None) -> List[Dict[str, float]]:
        """Fallback predictions if AI detection fails"""
        if early_hints:
            # Use early hints but boost confidence slightly
            return [
                {"genre": pred["genre"], "confidence": min(pred["confidence"] * 1.2, 0.6)}
                for pred in early_hints[:5]
            ]
        else:
            # Default fallback
            return [
                {"genre": "Drama", "confidence": 0.3},
                {"genre": "Documentary", "confidence": 0.25},
                {"genre": "Biographical", "confidence": 0.2},
                {"genre": "Historical", "confidence": 0.15},
                {"genre": "Family", "confidence": 0.1}
            ]


# Global instance
genre_detector = GenreDetector()


"""
Image Analysis Service
Handles image analysis and description extraction for chat integration
"""

import base64
import io
from typing import Optional, Dict, Any
from PIL import Image
import requests
import os
from dotenv import load_dotenv

load_dotenv()

class ImageAnalysisService:
    """Service for analyzing uploaded images and extracting descriptions"""
    
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            raise ValueError("OpenAI API key not found in environment variables")
    
    async def analyze_image(self, image_data: bytes, image_type: str = "character") -> Dict[str, Any]:
        """
        Analyze an uploaded image and extract relevant descriptions
        
        Args:
            image_data: Raw image bytes
            image_type: Type of image ("character", "location", "general")
            
        Returns:
            Dict containing analysis results
        """
        try:
            # Convert image to base64 for OpenAI API
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Determine image format for proper MIME type
            image_format = "jpeg"  # Default
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(image_data))
                if img.format:
                    image_format = img.format.lower()
            except:
                pass  # Use default if we can't determine format
            
            # Determine analysis prompt based on image type
            analysis_prompt = self._get_analysis_prompt(image_type)
            
            # Call OpenAI Vision API
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}"
            }
            
            payload = {
                "model": "gpt-4-vision-preview",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": analysis_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{image_format};base64,{image_base64}",
                                    "detail": "high"  # High detail for better analysis
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500,  # Increased for more detailed responses
                "temperature": 0.7  # Slightly creative for better descriptions
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                description = result['choices'][0]['message']['content']
                
                return {
                    "success": True,
                    "description": description,
                    "image_type": image_type,
                    "analysis": self._parse_analysis(description, image_type)
                }
            else:
                return {
                    "success": False,
                    "error": f"OpenAI API error: {response.status_code}",
                    "description": "Unable to analyze image"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "description": "Error analyzing image"
            }
    
    def _get_analysis_prompt(self, image_type: str) -> str:
        """Get appropriate analysis prompt based on image type"""
        
        prompts = {
            "character": """
            Look at this image and describe the character you see. Tell me about their appearance, what they're wearing, their age, and any personality traits you can infer from their expression or pose. Also describe the setting if it's visible. This will help me develop this character for a story.
            """,
            
            "location": """
            Examine this image and describe the location or setting. Tell me about the type of place, the atmosphere, the time period if you can determine it, and any distinctive features. This will help me set the scene for a story.
            """,
            
            "general": """
            Look at this image and describe what you see. Tell me about the main subjects, the setting, the mood, and any interesting details that could be useful for storytelling.
            """
        }
        
        return prompts.get(image_type, prompts["general"])
    
    def _parse_analysis(self, description: str, image_type: str) -> Dict[str, Any]:
        """Parse the analysis into structured data"""
        
        analysis = {
            "raw_description": description,
            "image_type": image_type,
            "extracted_elements": {}
        }
        
        # Extract specific elements based on image type
        if image_type == "character":
            analysis["extracted_elements"] = {
                "physical_description": description,
                "inferred_personality": self._extract_personality_traits(description),
                "setting_context": self._extract_setting_context(description)
            }
        elif image_type == "location":
            analysis["extracted_elements"] = {
                "location_description": description,
                "atmosphere": self._extract_atmosphere(description),
                "time_period": self._extract_time_period(description)
            }
        
        return analysis
    
    def _extract_personality_traits(self, description: str) -> str:
        """Extract personality traits from character description"""
        # Simple keyword extraction - could be enhanced with NLP
        personality_keywords = ["confident", "shy", "bold", "gentle", "serious", "playful", "mysterious", "friendly"]
        found_traits = [trait for trait in personality_keywords if trait in description.lower()]
        return ", ".join(found_traits) if found_traits else "Not specified"
    
    def _extract_setting_context(self, description: str) -> str:
        """Extract setting context from description"""
        setting_keywords = ["indoor", "outdoor", "urban", "rural", "modern", "historical", "fantasy", "sci-fi"]
        found_settings = [setting for setting in setting_keywords if setting in description.lower()]
        return ", ".join(found_settings) if found_settings else "Not specified"
    
    def _extract_atmosphere(self, description: str) -> str:
        """Extract atmosphere from location description"""
        atmosphere_keywords = ["dark", "bright", "mysterious", "peaceful", "tense", "romantic", "dramatic"]
        found_atmospheres = [atm for atm in atmosphere_keywords if atm in description.lower()]
        return ", ".join(found_atmospheres) if found_atmospheres else "Not specified"
    
    def _extract_time_period(self, description: str) -> str:
        """Extract time period from description"""
        time_keywords = ["modern", "historical", "medieval", "victorian", "futuristic", "contemporary"]
        found_periods = [period for period in time_keywords if period in description.lower()]
        return ", ".join(found_periods) if found_periods else "Not specified"

# Global instance
image_analysis_service = ImageAnalysisService()

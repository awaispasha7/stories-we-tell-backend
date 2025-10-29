"""
Image Analysis Service
Handles image analysis and description extraction for chat integration
"""

import base64
from typing import Optional, Dict, Any
import os
import requests
from dotenv import load_dotenv

# Try to import OpenAI SDK
try:
    from openai import OpenAI
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OPENAI_SDK_AVAILABLE = False

load_dotenv()

class ImageAnalysisService:
    """Service for analyzing uploaded images and extracting descriptions"""
    
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            raise ValueError("OpenAI API key not found in environment variables")
        
        # Initialize OpenAI client if SDK is available
        if OPENAI_SDK_AVAILABLE:
            self.client = OpenAI(api_key=self.openai_api_key)
            print(f"✅ [IMAGE ANALYSIS] Using OpenAI Python SDK")
        else:
            self.client = None
            print(f"⚠️ [IMAGE ANALYSIS] OpenAI SDK not available, falling back to requests")
    
    def _detect_image_format(self, image_data: bytes) -> str:
        """
        Detect image format from file signature (magic bytes) - lightweight alternative to Pillow
        Returns format string like 'jpeg', 'png', 'gif', 'webp', etc.
        """
        if not image_data:
            return "jpeg"
        
        # Check file signatures (magic bytes)
        if image_data.startswith(b'\xff\xd8\xff'):
            return "jpeg"
        elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
            return "png"
        elif image_data.startswith(b'GIF87a') or image_data.startswith(b'GIF89a'):
            return "gif"
        elif image_data.startswith(b'RIFF') and b'WEBP' in image_data[:20]:
            return "webp"
        elif image_data.startswith(b'BM'):
            return "bmp"
        elif image_data.startswith(b'\x00\x00\x01\x00') or image_data.startswith(b'\x00\x00\x02\x00'):
            return "ico"
        else:
            # Default to jpeg if format cannot be determined
            return "jpeg"
    
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
            
            # Determine image format using lightweight file signature detection
            image_format = self._detect_image_format(image_data)
            
            # Determine analysis prompt based on image type
            analysis_prompt = self._get_analysis_prompt(image_type)
            
            print(f"🖼️ [IMAGE ANALYSIS] Analyzing image with type: {image_type}")
            print(f"🖼️ [IMAGE ANALYSIS] Image format detected: {image_format}")
            print(f"🖼️ [IMAGE ANALYSIS] Image size: {len(image_data)} bytes, Base64 size: {len(image_base64)} chars")
            
            # Use OpenAI SDK if available (recommended)
            if OPENAI_SDK_AVAILABLE and self.client:
                print(f"🖼️ [IMAGE ANALYSIS] Using OpenAI Python SDK")
                
                try:
                    response = self.client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
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
                                            "detail": "high"
                                        }
                                    }
                                ]
                            }
                        ],
                        max_tokens=500,
                        temperature=0.7
                    )
                    
                    description = response.choices[0].message.content
                    
                    print(f"✅ [IMAGE ANALYSIS] Successfully analyzed image using SDK")
                    print(f"📝 [IMAGE ANALYSIS] Description length: {len(description)} chars")
                    print(f"📝 [IMAGE ANALYSIS] Description preview: {description[:200]}...")
                    
                    return {
                        "success": True,
                        "description": description,
                        "image_type": image_type,
                        "analysis": self._parse_analysis(description, image_type)
                    }
                    
                except Exception as sdk_error:
                    print(f"❌ [IMAGE ANALYSIS] SDK error: {str(sdk_error)}")
                    print(f"❌ [IMAGE ANALYSIS] Error type: {type(sdk_error).__name__}")
                    # Fall through to requests fallback
            
            # Fallback to requests if SDK not available or failed
            print(f"🖼️ [IMAGE ANALYSIS] Using requests fallback")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}"
            }
            
            payload = {
                "model": "gpt-4o",
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
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.7
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            print(f"🖼️ [IMAGE ANALYSIS] API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                description = result['choices'][0]['message']['content']
                
                print(f"✅ [IMAGE ANALYSIS] Successfully analyzed image using requests")
                print(f"📝 [IMAGE ANALYSIS] Description length: {len(description)} chars")
                print(f"📝 [IMAGE ANALYSIS] Description preview: {description[:200]}...")
                
                return {
                    "success": True,
                    "description": description,
                    "image_type": image_type,
                    "analysis": self._parse_analysis(description, image_type)
                }
            else:
                error_text = response.text
                print(f"❌ [IMAGE ANALYSIS] API error: {response.status_code}")
                print(f"❌ [IMAGE ANALYSIS] Error response: {error_text[:500]}")
                
                return {
                    "success": False,
                    "error": f"OpenAI API error: {response.status_code} - {error_text[:200]}",
                    "description": "Unable to analyze image"
                }
                
        except Exception as e:
            import traceback
            print(f"❌ [IMAGE ANALYSIS] Exception during image analysis: {str(e)}")
            print(f"❌ [IMAGE ANALYSIS] Traceback: {traceback.format_exc()}")
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

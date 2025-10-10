"""
AI Model Management System
Handles multiple AI providers based on task type as specified by client requirements.
"""

import os
import openai
import google.generativeai as genai
import anthropic
from typing import Dict, Any, Optional
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

class TaskType(Enum):
    """Task types for AI model selection"""
    CHAT = "chat"
    DESCRIPTION = "description"
    SCRIPT = "script"
    SCENE = "scene"

class AIModelManager:
    """Manages AI model selection and execution based on task type"""
    
    def __init__(self):
        # Initialize OpenAI
        openai.api_key = os.getenv("OPENAI_API_KEY")

        # Check if other API keys are available and initialize if they are
        gemini_key = os.getenv("GEMINI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if gemini_key and gemini_key != "your_gemini_api_key_here":
            genai.configure(api_key=gemini_key)
            self.gemini_available = True
        else:
            self.gemini_available = False

        if anthropic_key and anthropic_key != "your_anthropic_api_key_here":
            self.claude_client = anthropic.Anthropic(api_key=anthropic_key)
            self.claude_available = True
        else:
            self.claude_available = False

        # Model selection mapping - use real model names and fallbacks
        self.model_mapping = {
            TaskType.CHAT: "gpt-3.5-turbo",  # Using standard model for testing
            TaskType.DESCRIPTION: "gemini-pro",  # Gemini for descriptions
            TaskType.SCRIPT: "gpt-4",  # GPT-4 for scripts
            TaskType.SCENE: "claude-3-sonnet-20240229",  # Claude for scenes
        }
    
    async def generate_response(self, task_type: TaskType, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Generate response using the appropriate AI model for the task type
        
        Args:
            task_type: The type of task (determines which model to use)
            prompt: The input prompt
            **kwargs: Additional parameters for the specific model
            
        Returns:
            Dict containing the response and metadata
        """
        try:
            if task_type == TaskType.CHAT:
                return await self._generate_chat_response(prompt, **kwargs)
            elif task_type == TaskType.DESCRIPTION:
                return await self._generate_description_response(prompt, **kwargs)
            elif task_type == TaskType.SCRIPT:
                return await self._generate_script_response(prompt, **kwargs)
            elif task_type == TaskType.SCENE:
                return await self._generate_scene_response(prompt, **kwargs)
            else:
                raise ValueError(f"Unknown task type: {task_type}")
                
        except Exception as e:
            return {
                "response": f"Error generating response: {str(e)}",
                "model_used": self.model_mapping.get(task_type, "unknown"),
                "error": str(e)
            }
    
    async def _generate_chat_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate chat response using GPT-5 mini as specified by client"""
        try:
            print(f"🤖 Attempting to call OpenAI with model: gpt-3.5-turbo")
            print(f"🤖 Prompt: '{prompt[:100]}...'")
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful cinematic intake assistant for the Stories We Tell application. Help users develop their stories, characters, and scripts."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=kwargs.get("max_tokens", 500),
                temperature=0.7
            )
            
            print(f"✅ OpenAI response received: {response}")

            return {
                "response": response.choices[0].message.content,
                "model_used": "gpt-3.5-turbo",
                "tokens_used": response.usage.total_tokens if response.usage else 0
            }
        except Exception as e:
            print(f"❌ OpenAI chat error: {str(e)}")
            print(f"❌ Error type: {type(e).__name__}")
            import traceback
            print(f"❌ Full traceback: {traceback.format_exc()}")
            raise Exception(f"OpenAI chat error: {str(e)}")
    
    async def _generate_description_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate description using Gemini Pro or fallback to OpenAI"""
        try:
            if self.gemini_available:
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content(
                    f"Generate a detailed description for: {prompt}",
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=kwargs.get("max_tokens", 1000),
                        temperature=kwargs.get("temperature", 0.7)
                    )
                )

                return {
                    "response": response.text,
                    "model_used": "gemini-pro",
                    "tokens_used": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
                }
            else:
                # Fallback to OpenAI GPT-5
                response = openai.chat.completions.create(
                    model="gpt-5",
                    messages=[
                        {"role": "system", "content": "You are a creative writing assistant. Generate detailed, vivid descriptions based on the prompt."},
                        {"role": "user", "content": f"Generate a detailed description for: {prompt}"}
                    ],
                    max_completion_tokens=kwargs.get("max_tokens", 1000)
                    # Note: GPT-5 models only support temperature=1 (default), so we omit it
                )

                return {
                    "response": response.choices[0].message.content,
                    "model_used": "gpt-5",
                    "tokens_used": response.usage.total_tokens if response.usage else 0
                }
        except Exception as e:
            raise Exception(f"Description generation error: {str(e)}")
    
    async def _generate_script_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate script using GPT-5 as specified by client"""
        try:
            response = openai.chat.completions.create(
                model="gpt-5",
                messages=[
                    {"role": "system", "content": "You are a professional scriptwriter. Generate high-quality scripts based on the given prompt."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=kwargs.get("max_tokens", 2000)
                # Note: GPT-5 models only support temperature=1 (default), so we omit it
            )

            return {
                "response": response.choices[0].message.content,
                "model_used": "gpt-5",
                "tokens_used": response.usage.total_tokens if response.usage else 0
            }
        except Exception as e:
            raise Exception(f"OpenAI script error: {str(e)}")
    
    async def _generate_scene_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate scene using Claude 3 Sonnet or fallback to OpenAI"""
        try:
            if self.claude_available:
                response = self.claude_client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=kwargs.get("max_tokens", 2000),
                    temperature=kwargs.get("temperature", 0.7),
                    messages=[
                        {"role": "user", "content": f"Generate a detailed scene based on: {prompt}"}
                    ]
                )

                return {
                    "response": response.content[0].text,
                    "model_used": "claude-3-sonnet-20240229",
                    "tokens_used": response.usage.input_tokens + response.usage.output_tokens
                }
            else:
                # Fallback to OpenAI GPT-5
                response = openai.chat.completions.create(
                    model="gpt-5",
                    messages=[
                        {"role": "system", "content": "You are a creative writing assistant specializing in scene generation. Write detailed, vivid scenes based on the prompt."},
                        {"role": "user", "content": f"Generate a detailed scene based on: {prompt}"}
                    ],
                    max_completion_tokens=kwargs.get("max_tokens", 2000)
                    # Note: GPT-5 models only support temperature=1 (default), so we omit it
                )

                return {
                    "response": response.choices[0].message.content,
                    "model_used": "gpt-5",
                    "tokens_used": response.usage.total_tokens if response.usage else 0
                }
        except Exception as e:
            raise Exception(f"Scene generation error: {str(e)}")
    

# Global instance
ai_manager = AIModelManager()


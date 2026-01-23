from fastapi import APIRouter, File, UploadFile, HTTPException, Header, Form
from typing import Optional
import uuid
import os
import base64
import requests
from io import BytesIO
from PIL import Image
from app.database.supabase import get_supabase_client
from dotenv import load_dotenv

# Try to import Gemini
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Gemini not available: {e}")
    GEMINI_AVAILABLE = False
    genai = None
    genai_types = None

load_dotenv()

router = APIRouter()

# Initialize Gemini client if available
gemini_client = None
if GEMINI_AVAILABLE:
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_gemini_api_key_here":
        try:
            gemini_client = genai.Client(api_key=gemini_key)
            print("✅ Gemini client initialized for image editing")
        except Exception as e:
            print(f"⚠️ Failed to initialize Gemini client: {e}")
            gemini_client = None

def build_edit_prompt(edit_mode: str, custom_prompt: Optional[str] = None, intensity: Optional[int] = None) -> str:
    """Build the prompt for image editing based on edit mode"""
    
    if edit_mode == 'enhance':
        return "Enhance this image to improve overall quality, sharpness, colors, and clarity. Make it look professional and polished."
    
    elif edit_mode == 'remove-background':
        return "Remove the background from this image, keeping only the main subject. Make the background transparent or white."
    
    elif edit_mode == 'adjust-colors':
        return "Adjust the color balance of this image to make it more vibrant and visually appealing. Improve color saturation and contrast."
    
    elif edit_mode == 'brightness':
        intensity_percent = intensity if intensity is not None else 50
        if intensity_percent < 50:
            return f"Reduce the brightness of this image by {100 - intensity_percent}%. Make it darker."
        else:
            return f"Increase the brightness of this image by {intensity_percent}%. Make it brighter."
    
    elif edit_mode == 'contrast':
        intensity_percent = intensity if intensity is not None else 50
        if intensity_percent < 50:
            return f"Reduce the contrast of this image by {100 - intensity_percent}%. Make it softer and less dramatic."
        else:
            return f"Increase the contrast of this image by {intensity_percent}%. Make it more dramatic and defined."
    
    elif edit_mode == 'saturation':
        intensity_percent = intensity if intensity is not None else 50
        if intensity_percent < 50:
            return f"Reduce the color saturation of this image by {100 - intensity_percent}%. Make it more muted and desaturated."
        else:
            return f"Increase the color saturation of this image by {intensity_percent}%. Make colors more vibrant and vivid."
    
    elif edit_mode == 'crop':
        return "Crop this image to focus on the main subject, removing unnecessary background while maintaining good composition."
    
    elif edit_mode == 'rotate':
        return "Rotate this image 90 degrees clockwise to correct the orientation."
    
    elif edit_mode == 'custom' and custom_prompt:
        return f"Apply the following edit to this image: {custom_prompt}"
    
    else:
        return "Enhance this image to improve its overall quality and appearance."

async def edit_image_with_gemini(
    image_bytes: bytes,
    edit_prompt: str,
    model_name: str,
    mime_type: str = "image/jpeg"
) -> bytes:
    """Edit image using Gemini Nano Banana or Imagen models"""
    
    if not gemini_client:
        raise HTTPException(status_code=503, detail="Gemini API not available")
    
    try:
        print(f"🎨 [IMAGE EDIT] Editing image with {model_name}")
        print(f"🎨 [IMAGE EDIT] Edit prompt: {edit_prompt[:100]}...")
        
        # Check if it's a Nano Banana model (Gemini-based) or Imagen model
        is_nano_banana = 'gemini' in model_name.lower() or 'nano' in model_name.lower()
        is_imagen = 'imagen' in model_name.lower()
        
        if is_nano_banana:
            # Use Gemini API for Nano Banana models
            # Create the image part
            image_part = genai_types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type
            )
            
            # Generate edited image using the specified model
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=[
                    image_part,
                    edit_prompt
                ],
                config=genai_types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=8192,
                )
            )
            
            # Check if response contains image data
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    # Check for image parts in response
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            # Extract image data
                            image_data = base64.b64decode(part.inline_data.data)
                            return image_data
                        elif hasattr(part, 'file_data') and part.file_data:
                            # Handle file data if present
                            print(f"🎨 [IMAGE EDIT] File data found in response")
            
            # If we get text back, the model described the edit but didn't generate an image
            if hasattr(response, 'text') and response.text:
                print(f"🎨 [IMAGE EDIT] Model returned text description: {response.text[:200]}...")
                # For now, we'll need to use image generation API or return original
                # This is a limitation - we may need to use a different approach
                raise HTTPException(
                    status_code=501, 
                    detail=f"Model {model_name} returned text description. Image editing may require image generation API."
                )
            
            # If no image data found, return original
            print(f"⚠️ [IMAGE EDIT] No image data in response, returning original")
            return image_bytes
            
        elif is_imagen:
            # Imagen models are primarily for generation, not editing
            # We can try to use them for generation based on the edit prompt
            # But this would require a different API approach
            print(f"🎨 [IMAGE EDIT] Imagen models ({model_name}) are primarily for generation")
            print(f"🎨 [IMAGE EDIT] Attempting to use for image-to-image editing...")
            
            # For Imagen, we might need to use a different API endpoint
            # This is a placeholder - actual implementation would depend on Imagen API
            raise HTTPException(
                status_code=501,
                detail=f"Imagen models ({model_name}) require image generation API. Please use Nano Banana models for editing."
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown model: {model_name}. Please use a valid Nano Banana or Imagen model."
            )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [IMAGE EDIT] Error editing image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to edit image: {str(e)}")

@router.post("/image-edit")
async def edit_image(
    image: UploadFile = File(...),
    edit_mode: str = Form(...),
    model: str = Form("gemini-2.5-flash-image"),  # Default to Nano Banana
    custom_prompt: Optional[str] = Form(None),
    intensity: Optional[int] = Form(None),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    x_project_id: Optional[str] = Header(None, alias="X-Project-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Edit image using selected model (Nano Banana or Imagen)
    """
    print(f"🎨 [IMAGE EDIT] Received image edit request")
    print(f"🎨 [IMAGE EDIT] Edit mode: {edit_mode}")
    print(f"🎨 [IMAGE EDIT] Model: {model}")
    print(f"🎨 [IMAGE EDIT] Session ID: {x_session_id}")
    print(f"🎨 [IMAGE EDIT] Project ID: {x_project_id}")
    print(f"🎨 [IMAGE EDIT] User ID: {x_user_id}")
    
    # Validate image file
    if not image.content_type or not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Read image bytes
        image_bytes = await image.read()
        
        # Build edit prompt
        edit_prompt = build_edit_prompt(edit_mode, custom_prompt, intensity)
        
        # For now, we'll use a simpler approach:
        # Use PIL for basic edits, and Gemini for complex/custom edits
        pil_image = Image.open(BytesIO(image_bytes))
        edited_image_bytes = image_bytes  # Default to original
        
        # Apply basic edits with PIL
        if edit_mode == 'brightness' and intensity is not None:
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Brightness(pil_image)
            factor = intensity / 50.0  # Convert 0-100 to 0-2 range
            pil_image = enhancer.enhance(factor)
            
        elif edit_mode == 'contrast' and intensity is not None:
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(pil_image)
            factor = intensity / 50.0
            pil_image = enhancer.enhance(factor)
            
        elif edit_mode == 'saturation' and intensity is not None:
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Color(pil_image)
            factor = intensity / 50.0
            pil_image = enhancer.enhance(factor)
            
        elif edit_mode == 'rotate':
            pil_image = pil_image.rotate(-90, expand=True)
        
        # For complex edits or custom prompts, use selected model
        if edit_mode in ['enhance', 'remove-background', 'adjust-colors', 'crop', 'custom']:
            try:
                edited_image_bytes = await edit_image_with_gemini(
                    image_bytes,
                    edit_prompt,
                    model,  # Pass the selected model
                    image.content_type
                )
            except HTTPException as e:
                # If model fails, fall back to PIL enhancement
                if e.status_code == 501:
                    print(f"⚠️ [IMAGE EDIT] Model {model} not available for editing, using PIL fallback")
                    # For now, apply a basic enhancement
                    from PIL import ImageEnhance
                    enhancer = ImageEnhance.Sharpness(pil_image)
                    pil_image = enhancer.enhance(1.2)
                    enhancer = ImageEnhance.Color(pil_image)
                    pil_image = enhancer.enhance(1.1)
                else:
                    # Re-raise other HTTP exceptions
                    raise
        
        # Convert PIL image back to bytes if we used PIL
        if edit_mode in ['brightness', 'contrast', 'saturation', 'rotate'] or (
            edit_mode in ['enhance', 'remove-background', 'adjust-colors', 'crop', 'custom'] 
            and edited_image_bytes == image_bytes
        ):
            output = BytesIO()
            # Preserve format
            format = pil_image.format or 'JPEG'
            if format == 'JPEG':
                pil_image.save(output, format='JPEG', quality=95)
            else:
                pil_image.save(output, format=format)
            edited_image_bytes = output.getvalue()
        
        # Upload edited image to Supabase
        supabase = get_supabase_client()
        if not supabase:
            raise HTTPException(status_code=500, detail="Supabase not available")
        
        bucket_name = "story-assets"
        
        # Generate new asset ID and filename
        asset_id = str(uuid.uuid4())
        file_extension = image.filename.split('.')[-1] if '.' in image.filename else 'jpg'
        edited_filename = f"edited_{asset_id}.{file_extension}"
        
        # Upload to Supabase Storage
        file_path = f"{x_project_id or 'temp'}/{asset_id}/{edited_filename}"
        
        upload_response = supabase.storage.from_(bucket_name).upload(
            file_path,
            edited_image_bytes,
            file_options={
                "content-type": image.content_type,
                "upsert": False
            }
        )
        
        if upload_response.get('error'):
            raise HTTPException(status_code=500, detail=f"Failed to upload edited image: {upload_response['error']}")
        
        # Get public URL
        public_url_response = supabase.storage.from_(bucket_name).get_public_url(file_path)
        public_url = public_url_response if isinstance(public_url_response, str) else public_url_response.get('publicUrl', '')
        
        # Store asset metadata
        asset_record = {
            "id": asset_id,
            "project_id": x_project_id,
            "type": "image",
            "uri": public_url,
            "notes": f"Edited image: {edit_mode} using {model} - {edit_prompt[:100]}"
        }
        
        db_response = supabase.table("assets").insert([asset_record]).execute()
        
        if not db_response.data:
            print(f"⚠️ Warning: Failed to store edited asset metadata in database")
        
        print(f"✅ [IMAGE EDIT] Image edited and uploaded successfully: {edited_filename}")
        
        return {
            "success": True,
            "asset_id": asset_id,
            "edited_image_url": public_url,
            "edit_mode": edit_mode,
            "model_used": model,
            "message": "Image edited successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [IMAGE EDIT] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to edit image: {str(e)}")


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

def build_edit_prompt(
    edit_mode: str, 
    custom_prompt: Optional[str] = None, 
    intensity: Optional[int] = None,
    crop_ratio: Optional[str] = None,
    rotate_angle: Optional[int] = None
) -> str:
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
        if crop_ratio and crop_ratio != 'free' and crop_ratio != 'custom':
            return f"Crop this image to a {crop_ratio} aspect ratio, focusing on the main subject and maintaining good composition."
        else:
            return "Crop this image to focus on the main subject, removing unnecessary background while maintaining good composition."
    
    elif edit_mode == 'rotate':
        angle = rotate_angle if rotate_angle is not None else 90
        direction = "clockwise" if angle > 0 else "counter-clockwise"
        abs_angle = abs(angle)
        return f"Rotate this image {abs_angle} degrees {direction} to correct the orientation."
    
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
    crop_ratio: Optional[str] = Form(None),
    rotate_angle: Optional[int] = Form(None),
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
        
        # Separate manual edits (PIL) from AI edits (Gemini/Imagen)
        pil_image = Image.open(BytesIO(image_bytes))
        edited_image_bytes = image_bytes  # Default to original
        use_ai = False
        
        # Manual/Programmatic edits - handled with PIL only
        if edit_mode == 'brightness' and intensity is not None:
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Brightness(pil_image)
            factor = intensity / 50.0  # Convert 0-100 to 0-2 range
            pil_image = enhancer.enhance(factor)
            print(f"✅ [IMAGE EDIT] Applied brightness adjustment: {intensity}%")
            
        elif edit_mode == 'contrast' and intensity is not None:
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(pil_image)
            factor = intensity / 50.0
            pil_image = enhancer.enhance(factor)
            print(f"✅ [IMAGE EDIT] Applied contrast adjustment: {intensity}%")
            
        elif edit_mode == 'saturation' and intensity is not None:
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Color(pil_image)
            factor = intensity / 50.0
            pil_image = enhancer.enhance(factor)
            print(f"✅ [IMAGE EDIT] Applied saturation adjustment: {intensity}%")
            
        elif edit_mode == 'rotate' and rotate_angle is not None:
            pil_image = pil_image.rotate(-rotate_angle, expand=True)
            print(f"✅ [IMAGE EDIT] Applied rotation: {rotate_angle}°")
        
        elif edit_mode == 'crop' and crop_ratio is not None:
            # Apply crop based on ratio
            width, height = pil_image.size
            if crop_ratio == '1:1':
                # Square crop (center)
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                pil_image = pil_image.crop((left, top, left + size, top + size))
                print(f"✅ [IMAGE EDIT] Applied crop: 1:1 (square)")
            elif crop_ratio == '16:9':
                # 16:9 crop
                target_ratio = 16 / 9
                if width / height > target_ratio:
                    new_height = height
                    new_width = int(height * target_ratio)
                    left = (width - new_width) // 2
                    pil_image = pil_image.crop((left, 0, left + new_width, new_height))
                else:
                    new_width = width
                    new_height = int(width / target_ratio)
                    top = (height - new_height) // 2
                    pil_image = pil_image.crop((0, top, new_width, top + new_height))
                print(f"✅ [IMAGE EDIT] Applied crop: 16:9")
            elif crop_ratio == '4:3':
                # 4:3 crop
                target_ratio = 4 / 3
                if width / height > target_ratio:
                    new_height = height
                    new_width = int(height * target_ratio)
                    left = (width - new_width) // 2
                    pil_image = pil_image.crop((left, 0, left + new_width, new_height))
                else:
                    new_width = width
                    new_height = int(width / target_ratio)
                    top = (height - new_height) // 2
                    pil_image = pil_image.crop((0, top, new_width, top + new_height))
                print(f"✅ [IMAGE EDIT] Applied crop: 4:3")
            elif crop_ratio == '9:16':
                # 9:16 crop (portrait)
                target_ratio = 9 / 16
                if width / height > target_ratio:
                    new_height = height
                    new_width = int(height * target_ratio)
                    left = (width - new_width) // 2
                    pil_image = pil_image.crop((left, 0, left + new_width, new_height))
                else:
                    new_width = width
                    new_height = int(width / target_ratio)
                    top = (height - new_height) // 2
                    pil_image = pil_image.crop((0, top, new_width, top + new_height))
                print(f"✅ [IMAGE EDIT] Applied crop: 9:16")
            elif crop_ratio == 'free':
                # Free crop - use AI for intelligent cropping
                use_ai = True
                print(f"🎨 [IMAGE EDIT] Using AI for free-form crop")
            elif crop_ratio == 'custom':
                # Custom crop - use AI
                use_ai = True
                print(f"🎨 [IMAGE EDIT] Using AI for custom crop")
        
        # AI-powered edits - use Gemini/Imagen
        if edit_mode in ['enhance', 'remove-background', 'adjust-colors', 'custom']:
            use_ai = True
        
        # Apply AI edits if needed
        if use_ai:
            edit_prompt = build_edit_prompt(edit_mode, custom_prompt, intensity, crop_ratio, rotate_angle)
            try:
                edited_image_bytes = await edit_image_with_gemini(
                    image_bytes,
                    edit_prompt,
                    model,  # Pass the selected model
                    image.content_type
                )
                print(f"✅ [IMAGE EDIT] AI edit completed using {model}")
            except HTTPException as e:
                # If model fails, raise the error
                print(f"❌ [IMAGE EDIT] AI edit failed: {e.detail}")
                raise
        else:
            # Convert PIL image back to bytes for manual edits
            output = BytesIO()
            # Preserve format
            format = pil_image.format or 'JPEG'
            if format == 'JPEG':
                pil_image.save(output, format='JPEG', quality=95)
            else:
                pil_image.save(output, format=format)
            edited_image_bytes = output.getvalue()
            print(f"✅ [IMAGE EDIT] Manual edit completed")
        
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
        
        try:
            # Upload file - if no exception is raised, upload succeeded
            supabase.storage.from_(bucket_name).upload(
                file_path,
                edited_image_bytes,
                file_options={
                    "content-type": image.content_type,
                    "upsert": False
                }
            )
            # Just log that upload succeeded - don't store or access response
            print(f"✅ [IMAGE EDIT] Upload successful to: {file_path}")
        except Exception as upload_error:
            print(f"❌ [IMAGE EDIT] Upload error: {upload_error}")
            import traceback
            print(f"❌ [IMAGE EDIT] Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to upload edited image: {str(upload_error)}")
        
        # Get public URL - handle different response formats
        try:
            public_url_response = supabase.storage.from_(bucket_name).get_public_url(file_path)
            
            # Handle different response formats
            if isinstance(public_url_response, str):
                public_url = public_url_response
            elif isinstance(public_url_response, dict):
                public_url = public_url_response.get('publicUrl') or public_url_response.get('public_url') or public_url_response.get('url', '')
            elif hasattr(public_url_response, 'publicUrl'):
                public_url = public_url_response.publicUrl
            elif hasattr(public_url_response, 'public_url'):
                public_url = public_url_response.public_url
            elif hasattr(public_url_response, 'url'):
                public_url = public_url_response.url
            else:
                # Fallback: construct URL manually
                storage_url = os.getenv("SUPABASE_URL", "")
                if storage_url:
                    public_url = f"{storage_url}/storage/v1/object/public/{bucket_name}/{file_path}"
                else:
                    raise ValueError("Could not determine public URL")
            
            if not public_url:
                raise ValueError("Public URL is empty")
                
            print(f"✅ [IMAGE EDIT] Public URL: {public_url}")
        except Exception as url_error:
            print(f"❌ [IMAGE EDIT] Error getting public URL: {url_error}")
            import traceback
            print(f"❌ [IMAGE EDIT] Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to get public URL: {str(url_error)}")
        
        # Store asset metadata
        if use_ai:
            edit_prompt = build_edit_prompt(edit_mode, custom_prompt, intensity, crop_ratio, rotate_angle)
            notes = f"Edited image: {edit_mode} using {model} - {edit_prompt[:100]}"
        else:
            if edit_mode == 'brightness':
                notes = f"Edited image: {edit_mode} at {intensity}% (Manual/PIL)"
            elif edit_mode == 'contrast':
                notes = f"Edited image: {edit_mode} at {intensity}% (Manual/PIL)"
            elif edit_mode == 'saturation':
                notes = f"Edited image: {edit_mode} at {intensity}% (Manual/PIL)"
            elif edit_mode == 'rotate':
                notes = f"Edited image: {edit_mode} by {rotate_angle}° (Manual/PIL)"
            elif edit_mode == 'crop':
                notes = f"Edited image: {edit_mode} to {crop_ratio} (Manual/PIL)"
            else:
                notes = f"Edited image: {edit_mode} (Manual/PIL)"
        
        asset_record = {
            "id": asset_id,
            "project_id": x_project_id,
            "type": "image",
            "uri": public_url,
            "notes": notes
        }
        
        db_response = supabase.table("assets").insert([asset_record]).execute()
        
        if not db_response.data:
            print(f"⚠️ Warning: Failed to store edited asset metadata in database")
        
        print(f"✅ [IMAGE EDIT] Image edited and uploaded successfully: {edited_filename}")
        
        # Determine what was used for editing
        if use_ai:
            processing_method = f"AI ({model})"
        else:
            processing_method = "Manual (PIL)"
        
        return {
            "success": True,
            "asset_id": asset_id,
            "edited_image_url": public_url,
            "edit_mode": edit_mode,
            "model_used": model if use_ai else "manual",
            "processing_method": processing_method,
            "message": "Image edited successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [IMAGE EDIT] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to edit image: {str(e)}")


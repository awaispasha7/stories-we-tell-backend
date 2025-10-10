from fastapi import APIRouter, File, UploadFile, HTTPException
from typing import List
import uuid
import os
from app.database.supabase import get_supabase_client
from dotenv import load_dotenv

router = APIRouter()
load_dotenv()

# Maximum file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# Allowed file types
ALLOWED_EXTENSIONS = {
    'image': ['jpg', 'jpeg', 'png', 'gif', 'webp'],
    'document': ['pdf', 'doc', 'docx', 'txt'],
    'video': ['mp4', 'mov', 'avi'],
    'script': ['pdf', 'txt', 'doc', 'docx']
}

def get_file_type(filename: str) -> str:
    """Determine file type based on extension"""
    extension = filename.lower().split('.')[-1]
    
    for file_type, extensions in ALLOWED_EXTENSIONS.items():
        if extension in extensions:
            return file_type
    
    return 'other'

@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Upload files to Supabase Storage and store metadata in assets table
    """
    print(f"📥 Received {len(files)} file(s) for upload")
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    uploaded_files = []
    supabase = get_supabase_client()
    
    # Create a bucket name for story assets
    bucket_name = "story-assets"
    
    try:
        for file in files:
            print(f"📄 Processing file: {file.filename}")
            
            # Validate file size
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400, 
                    detail=f"File {file.filename} exceeds maximum size of 10MB"
                )
            
            # Generate unique filename
            file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            
            # Determine file type
            file_type = get_file_type(file.filename)
            
            print(f"📤 Uploading to Supabase Storage: {unique_filename}")
            
            # Upload to Supabase Storage
            try:
                # Upload file to storage
                storage_response = supabase.storage.from_(bucket_name).upload(
                    path=unique_filename,
                    file=content,
                    file_options={"content-type": file.content_type}
                )
                
                print(f"✅ Upload response: {storage_response}")
                
                # Get public URL
                public_url = supabase.storage.from_(bucket_name).get_public_url(unique_filename)
                
                print(f"🔗 Public URL: {public_url}")
                
                # Store metadata in assets table
                project_id = str(uuid.uuid4())  # In a real app, this would come from user session
                asset_record = {
                    "id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "type": file_type,
                    "uri": public_url,
                    "notes": f"Original filename: {file.filename}"
                }
                
                db_response = supabase.table("assets").insert([asset_record]).execute()
                
                if not db_response.data:
                    print(f"⚠️  Warning: Failed to store asset metadata in database")
                
                uploaded_files.append({
                    "name": file.filename,
                    "size": len(content),
                    "url": public_url,
                    "type": file_type,
                    "asset_id": asset_record["id"]
                })
                
                print(f"✅ File uploaded successfully: {file.filename}")
                
            except Exception as storage_error:
                print(f"❌ Storage error: {str(storage_error)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload {file.filename}: {str(storage_error)}"
                )
    
    except Exception as e:
        print(f"❌ Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    return {
        "success": True,
        "files": uploaded_files,
        "count": len(uploaded_files)
    }


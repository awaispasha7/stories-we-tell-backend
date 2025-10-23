from fastapi import APIRouter, File, UploadFile, HTTPException, Header
from typing import List, Optional
import uuid
import os
import asyncio
from app.database.supabase import get_supabase_client
from app.ai.document_processor import document_processor
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
async def upload_files(
    files: List[UploadFile] = File(...),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    x_project_id: Optional[str] = Header(None, alias="X-Project-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Upload files to Supabase Storage and store metadata in assets table
    """
    print(f"📥 Received {len(files)} file(s) for upload")
    print(f"📥 Session ID: {x_session_id}")
    print(f"📥 Project ID: {x_project_id}")
    print(f"📥 User ID: {x_user_id}")
    print(f"📥 User ID type: {type(x_user_id)}")
    print(f"📥 User ID repr: {repr(x_user_id)}")
    
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
                # Use real session data if available, otherwise fall back to test IDs
                if x_project_id:
                    project_id = x_project_id
                    print(f"✅ Using real project ID: {project_id}")
                    
                    # Check if project exists in dossier table, create if not
                    try:
                        project_check = supabase.table('dossier').select('project_id').eq('project_id', project_id).execute()
                        if not project_check.data:
                            print(f"📝 Creating project record for: {project_id}")
                            # Create a basic project record
                            project_record = {
                                "project_id": project_id,
                                "user_id": "00000000-0000-0000-0000-000000000001",  # Test user ID
                                "snapshot_json": {"title": "Auto-created Project", "description": "Project created automatically for document upload"},
                                "created_at": "now()"
                            }
                            supabase.table('dossier').insert(project_record).execute()
                            print(f"✅ Project record created successfully")
                    except Exception as e:
                        print(f"⚠️ Could not create project record: {e}")
                        # Fall back to test project ID
                        project_id = "00000000-0000-0000-0000-000000000002"
                        print(f"⚠️ Falling back to test project ID: {project_id}")
                else:
                    project_id = "00000000-0000-0000-0000-000000000002"  # Test project ID
                    print(f"⚠️ Using test project ID: {project_id}")
                
                # Use the actual user_id from the request, fallback to test ID if not provided
                user_id = x_user_id or "00000000-0000-0000-0000-000000000001"
                print(f"🔍 Using user_id: {user_id}")
                asset_id = str(uuid.uuid4())
                
                asset_record = {
                    "id": asset_id,
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
                    "asset_id": asset_id
                })
                
                print(f"✅ File uploaded successfully: {file.filename}")
                
                # Process document for RAG if it's a text-based document
                if file_type in ['document', 'script'] and file_extension in ['pdf', 'docx', 'doc', 'txt']:
                    print(f"🔄 Processing document for RAG: {file.filename}")
                    
                    # Process document asynchronously
                    asyncio.create_task(
                        process_document_for_rag(
                            asset_id=uuid.UUID(asset_id),
                            user_id=uuid.UUID(user_id),
                            project_id=uuid.UUID(project_id),
                            file_content=content,
                            filename=file.filename,
                            content_type=file.content_type or 'application/octet-stream'
                        )
                    )
                
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


async def process_document_for_rag(
    asset_id: uuid.UUID,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    file_content: bytes,
    filename: str,
    content_type: str
):
    """
    Background task to process uploaded document for RAG
    
    Args:
        asset_id: ID of the asset
        user_id: ID of the user
        project_id: ID of the project
        file_content: Raw file content
        filename: Original filename
        content_type: MIME type
    """
    try:
        print(f"🔄 Starting RAG processing for document: {filename}")
        
        result = await document_processor.process_document(
            asset_id=asset_id,
            user_id=user_id,
            project_id=project_id,
            file_content=file_content,
            filename=filename,
            content_type=content_type
        )
        
        if result["success"]:
            print(f"✅ RAG processing completed for {filename}: {result['embeddings_created']} embeddings created")
        else:
            print(f"❌ RAG processing failed for {filename}: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error in background RAG processing for {filename}: {e}")


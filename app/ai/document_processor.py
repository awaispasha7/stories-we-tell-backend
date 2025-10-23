"""
Document Processing Service
Handles text extraction and embedding generation for uploaded documents
"""

import os
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4
import PyPDF2
import docx
from io import BytesIO
import re
from .embedding_service import get_embedding_service
from .vector_storage import vector_storage
from ..database.supabase import get_supabase_client


class DocumentProcessor:
    """Service for processing uploaded documents and generating embeddings"""
    
    def __init__(self):
        self.embedding_service = None  # Lazy initialization
        self.supabase = get_supabase_client()
        
        # Configuration
        self.chunk_size = 1000  # Characters per chunk
        self.chunk_overlap = 200  # Overlap between chunks
        self.max_chunks_per_document = 50  # Limit chunks to prevent excessive embeddings
    
    def _get_embedding_service(self):
        """Lazy initialization of embedding service"""
        if self.embedding_service is None:
            self.embedding_service = get_embedding_service()
        return self.embedding_service
    
    async def process_document(
        self,
        asset_id: UUID,
        user_id: UUID,
        project_id: UUID,
        file_content: bytes,
        filename: str,
        content_type: str
    ) -> Dict[str, Any]:
        """
        Process an uploaded document and generate embeddings
        
        Args:
            asset_id: ID of the asset record
            user_id: ID of the user who uploaded the document
            project_id: ID of the project
            file_content: Raw file content
            filename: Original filename
            content_type: MIME type of the file
            
        Returns:
            Dict containing processing results
        """
        try:
            print(f"📄 Processing document: {filename} (type: {content_type})")
            
            # Step 1: Extract text based on file type
            text_content = await self._extract_text(file_content, filename, content_type)
            
            if not text_content or not text_content.strip():
                return {
                    "success": False,
                    "error": "No text content extracted from document",
                    "chunks_processed": 0
                }
            
            print(f"📝 Extracted {len(text_content)} characters of text")
            
            # Step 2: Split text into chunks
            chunks = self._split_text_into_chunks(text_content)
            
            if not chunks:
                return {
                    "success": False,
                    "error": "No text chunks created from document",
                    "chunks_processed": 0
                }
            
            print(f"📚 Created {len(chunks)} text chunks")
            
            # Step 3: Generate embeddings for each chunk
            chunks_processed = 0
            embeddings_created = 0
            
            for i, chunk in enumerate(chunks[:self.max_chunks_per_document]):
                try:
                    # Generate embedding for this chunk
                    embedding = await self._get_embedding_service().generate_embedding(chunk)
                    
                    # Store embedding in database
                    embedding_id = await vector_storage.store_document_embedding(
                        asset_id=asset_id,
                        user_id=user_id,
                        project_id=project_id,
                        document_type=self._get_document_type(filename),
                        chunk_index=i,
                        chunk_text=chunk,
                        embedding=embedding,
                        metadata={
                            "filename": filename,
                            "content_type": content_type,
                            "chunk_size": len(chunk),
                            "total_chunks": len(chunks)
                        }
                    )
                    
                    if embedding_id:
                        embeddings_created += 1
                        print(f"✅ Created embedding for chunk {i+1}/{len(chunks)}")
                    else:
                        print(f"❌ Failed to store embedding for chunk {i+1}")
                    
                    chunks_processed += 1
                    
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.1)
                    
                except Exception as chunk_error:
                    print(f"❌ Error processing chunk {i+1}: {chunk_error}")
                    continue
            
            # Step 4: Update asset record with processing status
            await self._update_asset_processing_status(
                asset_id, 
                "processed", 
                {
                    "chunks_processed": chunks_processed,
                    "embeddings_created": embeddings_created,
                    "total_text_length": len(text_content)
                }
            )
            
            return {
                "success": True,
                "chunks_processed": chunks_processed,
                "embeddings_created": embeddings_created,
                "total_text_length": len(text_content),
                "document_type": self._get_document_type(filename)
            }
            
        except Exception as e:
            print(f"❌ Error processing document {filename}: {e}")
            
            # Update asset record with error status
            await self._update_asset_processing_status(
                asset_id, 
                "failed", 
                {"error": str(e)}
            )
            
            return {
                "success": False,
                "error": str(e),
                "chunks_processed": 0
            }
    
    async def _extract_text(self, file_content: bytes, filename: str, content_type: str) -> str:
        """Extract text from various document formats"""
        try:
            file_extension = filename.lower().split('.')[-1] if '.' in filename else ''
            
            if file_extension == 'pdf' or content_type == 'application/pdf':
                return await self._extract_pdf_text(file_content)
            elif file_extension in ['docx', 'doc'] or 'word' in content_type:
                return await self._extract_docx_text(file_content)
            elif file_extension == 'txt' or content_type == 'text/plain':
                return file_content.decode('utf-8', errors='ignore')
            else:
                # Try to decode as text for unknown formats
                try:
                    return file_content.decode('utf-8', errors='ignore')
                except:
                    return ""
                    
        except Exception as e:
            print(f"❌ Error extracting text from {filename}: {e}")
            return ""
    
    async def _extract_pdf_text(self, file_content: bytes) -> str:
        """Extract text from PDF file"""
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
            text = ""
            
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
                except Exception as page_error:
                    print(f"⚠️ Error extracting page {page_num + 1}: {page_error}")
                    continue
            
            return text.strip()
            
        except Exception as e:
            print(f"❌ Error reading PDF: {e}")
            return ""
    
    async def _extract_docx_text(self, file_content: bytes) -> str:
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(BytesIO(file_content))
            text = ""
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text += paragraph.text + "\n"
            
            return text.strip()
            
        except Exception as e:
            print(f"❌ Error reading DOCX: {e}")
            return ""
    
    def _split_text_into_chunks(self, text: str) -> List[str]:
        """Split text into overlapping chunks for embedding"""
        if not text or not text.strip():
            return []
        
        # Clean and normalize text
        text = re.sub(r'\s+', ' ', text.strip())
        
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Find the end of the current chunk
            end = start + self.chunk_size
            
            if end >= len(text):
                # Last chunk
                chunks.append(text[start:])
                break
            
            # Try to break at a sentence boundary
            sentence_end = text.rfind('.', start, end)
            if sentence_end > start + self.chunk_size // 2:
                end = sentence_end + 1
            
            # If no sentence boundary, try word boundary
            else:
                word_end = text.rfind(' ', start, end)
                if word_end > start + self.chunk_size // 2:
                    end = word_end
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position with overlap
            start = end - self.chunk_overlap
            if start < 0:
                start = end
        
        return chunks
    
    def _get_document_type(self, filename: str) -> str:
        """Determine document type from filename"""
        extension = filename.lower().split('.')[-1] if '.' in filename else ''
        
        if extension in ['pdf']:
            return 'pdf'
        elif extension in ['docx', 'doc']:
            return 'docx'
        elif extension in ['txt']:
            return 'txt'
        else:
            return 'unknown'
    
    async def _update_asset_processing_status(
        self, 
        asset_id: UUID, 
        status: str, 
        metadata: Dict[str, Any]
    ):
        """Update asset record with processing status"""
        try:
            update_data = {
                "processing_status": status,
                "processing_metadata": metadata,
                "updated_at": "now()"
            }
            
            result = self.supabase.table("assets")\
                .update(update_data)\
                .eq("id", str(asset_id))\
                .execute()
            
            if result.data:
                print(f"✅ Updated asset {asset_id} with status: {status}")
            else:
                print(f"⚠️ Failed to update asset {asset_id} status")
                
        except Exception as e:
            print(f"❌ Error updating asset status: {e}")
    
    async def get_document_context(
        self,
        query_embedding: List[float],
        user_id: UUID,
        project_id: Optional[UUID] = None,
        match_count: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant document chunks for RAG context
        
        Args:
            query_embedding: Query embedding vector
            user_id: ID of the user
            project_id: Optional project ID to filter by
            match_count: Maximum number of chunks to retrieve
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of relevant document chunks
        """
        try:
            print(f"🔍 DocumentProcessor: Searching for document chunks")
            print(f"🔍 DocumentProcessor: user_id={user_id}, project_id={project_id}")
            print(f"🔍 DocumentProcessor: match_count={match_count}, similarity_threshold={similarity_threshold}")
            
            # Debug: Check embedding format
            print(f"🔍 DocumentProcessor: Query embedding type: {type(query_embedding)}, length: {len(query_embedding) if query_embedding else 'None'}")
            if query_embedding:
                print(f"🔍 DocumentProcessor: First few values: {query_embedding[:5]}")
            
            # Debug: Try a very simple query first to see if the function works at all
            print(f"🔍 DocumentProcessor: Testing RPC function with minimal parameters...")
            try:
                # Test with a very low threshold and high match count
                test_result = self.supabase.rpc(
                    'get_similar_document_chunks',
                    {
                        'query_embedding': query_embedding,
                        'query_user_id': str(user_id),
                        'query_project_id': str(project_id) if project_id else None,  # Only user's projects
                        'match_count': 10,  # Higher match count
                        'similarity_threshold': 0.01  # Very low threshold
                    }
                ).execute()
                print(f"🔍 DocumentProcessor: Test RPC result: {test_result}")
                print(f"🔍 DocumentProcessor: Test result data: {test_result.data}")
            except Exception as e:
                print(f"🔍 DocumentProcessor: Test RPC error: {e}")
            
            result = self.supabase.rpc(
                'get_similar_document_chunks',
                {
                    'query_embedding': query_embedding,
                    'query_user_id': str(user_id),
                    'query_project_id': str(project_id) if project_id else None,
                    'match_count': match_count,
                    'similarity_threshold': similarity_threshold
                }
            ).execute()
            
            print(f"🔍 DocumentProcessor: RPC result: {result}")
            print(f"🔍 DocumentProcessor: Result data: {result.data}")
            
            if result.data:
                print(f"📚 Found {len(result.data)} relevant document chunks")
                # Debug: Check user isolation
                for chunk in result.data:
                    chunk_user_id = chunk.get('user_id')
                    if chunk_user_id != str(user_id):
                        print(f"🚨 SECURITY WARNING: Found document chunk from different user! Expected: {user_id}, Found: {chunk_user_id}")
                return result.data
            else:
                print("📚 No relevant document chunks found")
                return []
                
        except Exception as e:
            print(f"❌ Error retrieving document context: {e}")
            return []


# Global singleton instance
document_processor = DocumentProcessor()

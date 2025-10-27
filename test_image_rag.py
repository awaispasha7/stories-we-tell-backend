#!/usr/bin/env python3
"""
Test script to verify image analysis RAG training
This script checks if image analysis data is being stored and retrieved from RAG
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

async def test_image_rag_training():
    """Test if image analysis is being stored in RAG"""
    
    try:
        # Import required modules
        from app.ai.vector_storage import vector_storage
        from app.database.supabase import get_supabase_client
        
        print("🧪 Testing Image Analysis RAG Training...")
        
        # Test 1: Check if we can store image analysis in RAG
        print("\n📚 Test 1: Storing image analysis in RAG...")
        
        test_image_analysis = {
            "content": "Image Analysis - Character: A confident young woman in her 20s, wearing a business suit, standing in a modern office setting. She has a determined expression and appears professional.",
            "metadata": {
                "type": "image_analysis",
                "image_type": "character",
                "asset_id": "test-asset-123",
                "filename": "test-character.jpg",
                "project_id": "test-project-456",
                "user_id": "test-user-789"
            }
        }
        
        # Store in RAG using the wrapper function
        from app.ai.vector_storage import store_global_knowledge
        
        await store_global_knowledge(
            content=test_image_analysis["content"],
            metadata=test_image_analysis["metadata"]
        )
        print("✅ Image analysis stored in RAG successfully")
        
        # Test 2: Check if we can retrieve image analysis from RAG
        print("\n🔍 Test 2: Retrieving image analysis from RAG...")
        
        # Search for character-related content
        from app.ai.embedding_service import get_embedding_service
        
        embedding_service = get_embedding_service()
        query_embedding = await embedding_service.generate_embedding("character business suit professional woman")
        
        search_results = await vector_storage.get_similar_global_knowledge(
            query_embedding=query_embedding,
            match_count=5
        )
        
        print(f"📊 Found {len(search_results)} relevant results:")
        for i, result in enumerate(search_results, 1):
            print(f"  {i}. Similarity: {result.get('similarity', 'N/A'):.3f}")
            print(f"     Content: {result.get('content', 'N/A')[:100]}...")
            print(f"     Metadata: {result.get('metadata', {})}")
            print()
        
        # Test 3: Check database for image analysis data
        print("\n🗄️ Test 3: Checking database for image analysis...")
        
        supabase = get_supabase_client()
        
        # Check if we have any assets with analysis data
        assets_response = supabase.table("assets").select("id, analysis, analysis_type, analysis_data").eq("type", "image").limit(5).execute()
        
        if assets_response.data:
            print(f"📸 Found {len(assets_response.data)} image assets with analysis:")
            for asset in assets_response.data:
                print(f"  - Asset ID: {asset.get('id', 'N/A')}")
                print(f"    Analysis Type: {asset.get('analysis_type', 'N/A')}")
                analysis = asset.get('analysis')
                print(f"    Analysis: {analysis[:100] if analysis else 'N/A'}...")
                print()
        else:
            print("⚠️ No image assets with analysis found in database")
        
        # Test 4: Check global knowledge table
        print("\n🌐 Test 4: Checking global knowledge table...")
        
        knowledge_response = supabase.table("global_knowledge").select("*").eq("category", "image_analysis").limit(5).execute()
        
        if knowledge_response.data:
            print(f"🧠 Found {len(knowledge_response.data)} image analysis entries in global knowledge:")
            for entry in knowledge_response.data:
                print(f"  - ID: {entry.get('knowledge_id', 'N/A')}")
                print(f"    Category: {entry.get('category', 'N/A')}")
                print(f"    Pattern Type: {entry.get('pattern_type', 'N/A')}")
                print(f"    Example Text: {entry.get('example_text', 'N/A')[:100]}...")
                print(f"    Description: {entry.get('description', 'N/A')}")
                print()
        else:
            print("⚠️ No image analysis entries found in global knowledge table")
        
        print("\n🎉 Image Analysis RAG Training Test Complete!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main test function"""
    print("🚀 Starting Image Analysis RAG Training Test...")
    await test_image_rag_training()

if __name__ == "__main__":
    asyncio.run(main())

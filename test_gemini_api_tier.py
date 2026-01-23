#!/usr/bin/env python3
"""
Test script to check if Gemini API key is free-tier or paid.
This will make a simple API call and analyze the response/quota behavior.
"""

import os
import sys

# Try to load .env file if dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, just use environment variables
    pass

# Try to import Gemini
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError as e:
    print(f"ERROR: Gemini SDK not available: {e}")
    print("   Install it with: pip install google-genai")
    sys.exit(1)

def test_gemini_api_tier():
    """Test Gemini API to determine if it's free-tier or paid"""
    
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not gemini_key or gemini_key == "your_gemini_api_key_here":
        print("ERROR: GEMINI_API_KEY not found in environment variables")
        print("   Make sure you have a .env file with GEMINI_API_KEY set")
        sys.exit(1)
    
    print(f"Found API key (length: {len(gemini_key)} characters)")
    print(f"Key starts with: {gemini_key[:10]}...")
    print()
    
    # Initialize client
    try:
        client = genai.Client(api_key=gemini_key)
        print("SUCCESS: Gemini client initialized successfully")
    except Exception as e:
        print(f"ERROR: Failed to initialize Gemini client: {e}")
        sys.exit(1)
    
    # Test models to check
    test_models = [
        "gemini-2.5-flash-image",
        "gemini-3-pro-image-preview",
        "gemini-2.0-flash-exp",
    ]
    
    print("\n" + "="*60)
    print("Testing API with simple text generation (no image)")
    print("="*60)
    
    # First, try a simple text-only request to see if API works at all
    try:
        print("\n📝 Test 1: Simple text generation (gemini-2.0-flash-exp)...")
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=["Say 'Hello, API test successful!' in one sentence."],
            config=genai_types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=50,
            )
        )
        
        if hasattr(response, 'text') and response.text:
            print(f"SUCCESS: Text generation works! Response: {response.text[:100]}")
        else:
            print("WARNING: Got response but no text content")
            
    except Exception as e:
        error_msg = str(e)
        print(f"ERROR: Text generation failed: {error_msg}")
        
        # Check for quota errors
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
            print("\n" + "="*60)
            print("QUOTA ANALYSIS")
            print("="*60)
            
            if "free_tier" in error_msg.lower() or "free-tier" in error_msg.lower():
                print("TIER DETECTED: FREE TIER (quota exhausted)")
                print("   - This API key is on the free tier")
                print("   - Free tier has limited requests per day/minute")
                print("   - You've hit the limit for this model")
            else:
                print("TIER DETECTED: UNKNOWN (quota exhausted)")
                print("   - Could be free tier or paid tier with quota limits")
            
            # Try to extract retry delay
            import re
            retry_match = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", error_msg, re.IGNORECASE)
            if retry_match:
                retry_seconds = float(retry_match.group(1))
                print(f"   - Retry after: {retry_seconds:.1f} seconds")
            
            print("\nSOLUTIONS:")
            print("   1. Wait for quota to reset (usually daily or per-minute)")
            print("   2. Check your quota at: https://ai.dev/rate-limit")
            print("   3. Enable billing in Google Cloud Console for higher limits")
            print("   4. Use a different API key/project with available quota")
            
            sys.exit(1)
        else:
            print(f"ERROR: Unexpected error (not quota-related): {error_msg}")
            sys.exit(1)
    
    # Now test image models
    print("\n" + "="*60)
    print("Testing Image Generation Models")
    print("="*60)
    
    for model_name in test_models:
        print(f"\n🖼️  Testing model: {model_name}")
        try:
            # Create a tiny test image (1x1 pixel PNG) to test image API
            import base64
            from io import BytesIO
            from PIL import Image
            
            # Create minimal test image
            img = Image.new('RGB', (10, 10), color='red')
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            img_bytes = buffer.getvalue()
            
            # Try to generate content with image
            image_part = genai_types.Part.from_bytes(
                data=img_bytes,
                mime_type="image/png"
            )
            
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    image_part,
                    "Describe this image in one word."
                ],
                config=genai_types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=10,
                )
            )
            
            print(f"   SUCCESS: {model_name}: API call succeeded")
            
            if hasattr(response, 'text') and response.text:
                print(f"   Response: {response.text[:50]}")
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print(f"   WARNING: {model_name}: Quota exceeded")
                if "free_tier" in error_msg.lower():
                    print(f"      -> FREE TIER detected for this model")
            elif "not found" in error_msg.lower() or "404" in error_msg:
                print(f"   WARNING: {model_name}: Model not available (might be preview/experimental)")
            else:
                print(f"   ERROR: {model_name}: Error - {error_msg[:100]}")
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("SUCCESS: API key is valid and working")
    print("To determine exact tier:")
    print("   1. Check https://ai.dev/rate-limit for your quota limits")
    print("   2. Free tier typically shows: 'free_tier' in error messages")
    print("   3. Paid tier usually has higher limits or no 'free_tier' mentions")
    print("   4. Check your Google Cloud Console billing status")
    print("\nIf you see 'free_tier' in quota errors, you're on free tier")
    print("If errors don't mention 'free_tier', you might be on paid tier with limits")

if __name__ == "__main__":
    test_gemini_api_tier()


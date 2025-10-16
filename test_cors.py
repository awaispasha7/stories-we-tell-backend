#!/usr/bin/env python3
"""
Simple script to test CORS configuration
"""

import requests
import json

def test_cors():
    """Test CORS configuration"""
    base_url = "https://stories-we-tell-backend.vercel.app"
    
    print("Testing CORS configuration...")
    
    # Test 1: Health check
    try:
        response = requests.get(f"{base_url}/health")
        print(f"✅ Health check: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
    
    # Test 2: CORS test endpoint
    try:
        response = requests.get(f"{base_url}/cors-test")
        print(f"✅ CORS test: {response.status_code}")
        print(f"   Response: {response.json()}")
        print(f"   CORS headers: {dict(response.headers)}")
    except Exception as e:
        print(f"❌ CORS test failed: {e}")
    
    # Test 3: OPTIONS preflight for signup
    try:
        headers = {
            "Origin": "https://stories-we-tell.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, Authorization"
        }
        response = requests.options(f"{base_url}/api/v1/auth/signup", headers=headers)
        print(f"✅ OPTIONS preflight: {response.status_code}")
        print(f"   CORS headers: {dict(response.headers)}")
    except Exception as e:
        print(f"❌ OPTIONS preflight failed: {e}")
    
    # Test 4: Simple auth test endpoint
    try:
        headers = {
            "Origin": "https://stories-we-tell.vercel.app",
            "Content-Type": "application/json"
        }
        response = requests.post(f"{base_url}/api/v1/auth/test", 
                               headers=headers)
        print(f"✅ Auth test request: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        else:
            print(f"   Error response: {response.text}")
    except Exception as e:
        print(f"❌ Auth test request failed: {e}")
    
    # Test 5: Actual signup request (should work with simple auth)
    try:
        headers = {
            "Origin": "https://stories-we-tell.vercel.app",
            "Content-Type": "application/json"
        }
        data = {
            "email": "test@example.com",
            "display_name": "Test User",
            "password": "testpassword123"
        }
        response = requests.post(f"{base_url}/api/v1/auth/signup", 
                               headers=headers, 
                               json=data)
        print(f"✅ Signup request: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        else:
            print(f"   Error response: {response.text}")
    except Exception as e:
        print(f"❌ Signup request failed: {e}")

if __name__ == "__main__":
    test_cors()

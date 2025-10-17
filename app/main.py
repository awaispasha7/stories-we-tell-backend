from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

# Import routes with error handling
try:
    from app.api import chat, transcribe, chat_sessions, auth
    ROUTES_AVAILABLE = True
    AUTH_AVAILABLE = True
except Exception as e:
    print(f"Warning: Some routes not available: {e}")
    ROUTES_AVAILABLE = False
    AUTH_AVAILABLE = False

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware with comprehensive configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now - can be restricted later
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all headers to the client
    max_age=3600,  # Cache preflight response for 1 hour
)

# Include routes with error handling
if ROUTES_AVAILABLE:
    try:
        # Include the chat route (legacy)
        app.include_router(chat.router)
        print("✅ Chat router included")
    except Exception as e:
        print(f"❌ Error including chat router: {e}")

    try:
        # Include the new chat sessions route
        app.include_router(chat_sessions.router, prefix="/api/v1", tags=["chat-sessions"])
        print("✅ Chat sessions router included")
    except Exception as e:
        print(f"❌ Error including chat sessions router: {e}")

    try:
        # Include the auth route
        app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
        print("✅ Auth router included")
    except Exception as e:
        print(f"❌ Error including auth router: {e}")

    try:
        # Include the transcribe route
        app.include_router(transcribe.router)
        print("✅ Transcribe router included")
    except Exception as e:
        print(f"❌ Error including transcribe router: {e}")
else:
    print("❌ Routes not available - running in minimal mode")

# Add root route to handle 404 errors
@app.get("/")
async def root():
    return {"message": "Stories We Tell Backend API", "status": "running"}

# Add health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "message": "Backend is running",
        "cors_enabled": True,
        "allowed_origins": ["*"],  # All origins allowed
        "endpoints": ["/chat", "/dossier", "/transcribe", "/upload", "/api/v1/chat", "/api/v1/sessions", "/api/v1/auth/login", "/api/v1/auth/signup"]
    }

# Add simple test endpoint
@app.get("/test")
async def test_endpoint():
    return {"message": "Test endpoint working", "status": "ok"}


# CORS is handled by the middleware above

@app.get("/cors-test")
async def cors_test():
    """Test endpoint to verify CORS is working"""
    return {
        "message": "CORS test successful",
        "timestamp": datetime.now().isoformat(),
        "cors_headers": "Should be set by middleware"
    }

# Add favicon routes to handle 404 errors
@app.get("/favicon.ico")
async def favicon():
    return {"message": "Favicon not found"}

@app.get("/favicon.png")
async def favicon_png():
    return {"message": "Favicon not found"}

@app.on_event("startup")
async def startup():
    """
    This function runs when the FastAPI application starts.
    """
    print("Starting up FastAPI application...")
    print("CORS middleware configured")
    print("Application ready to serve requests")

@app.on_event("shutdown")
async def shutdown():
    """
    This function runs when the FastAPI application shuts down.
    You can add cleanup tasks here if needed.
    """
    print("Shutting down FastAPI application...")


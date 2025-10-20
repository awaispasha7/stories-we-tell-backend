from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import asyncio

# Import routes with error handling
ROUTES_AVAILABLE = True
AUTH_AVAILABLE = True

# Import individual routes with error handling
chat = None
transcribe = None
chat_sessions = None
auth = None
dossier = None

# Old chat router removed - using new session-aware chat_sessions router instead
chat = None

try:
    from app.api import transcribe
    print("SUCCESS: Transcribe router imported")
except Exception as e:
    print(f"ERROR: Error importing transcribe router: {e}")
    transcribe = None

try:
    from app.api import chat_sessions
    print("SUCCESS: Chat sessions router imported")
except Exception as e:
    print(f"ERROR: Error importing chat_sessions router: {e}")
    chat_sessions = None

try:
    from app.api import auth
    print("SUCCESS: Auth router imported")
except Exception as e:
    print(f"ERROR: Error importing auth router: {e}")
    auth = None

try:
    from app.api import dossier
    print("SUCCESS: Dossier router imported")
except Exception as e:
    print(f"ERROR: Error importing dossier router: {e}")
    dossier = None

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

# Include routes with individual error handling
# Old chat router removed - using new session-aware chat_sessions router instead

if chat_sessions:
    try:
        app.include_router(chat_sessions.router, prefix="/api/v1", tags=["chat-sessions"])
        print("SUCCESS: Chat sessions router included")
    except Exception as e:
        print(f"ERROR: Error including chat sessions router: {e}")

if auth:
    try:
        app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
        print("SUCCESS: Auth router included")
    except Exception as e:
        print(f"ERROR: Error including auth router: {e}")

if transcribe:
    try:
        app.include_router(transcribe.router)
        print("SUCCESS: Transcribe router included")
    except Exception as e:
        print(f"ERROR: Error including transcribe router: {e}")

if dossier:
    try:
        app.include_router(dossier.router, prefix="/api/v1", tags=["dossier"])
        print("SUCCESS: Dossier router included")
    except Exception as e:
        print(f"ERROR: Error including dossier router: {e}")

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
        "endpoints": ["/dossier", "/transcribe", "/upload", "/api/v1/chat", "/api/v1/sessions", "/api/v1/auth/login", "/api/v1/auth/signup", "/api/v1/dossiers"],
        "routes_available": {
            "chat_sessions": chat_sessions is not None,
            "auth": auth is not None,
            "transcribe": transcribe is not None,
            "dossier": dossier is not None
        }
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

    # Start periodic cleanup of expired anonymous sessions/users
    try:
        from app.api.chat_sessions import AnonymousSession

        async def periodic_cleanup():
            while True:
                try:
                    # Lightweight session cleanup (in-memory)
                    AnonymousSession.cleanup_expired_sessions()
                    # Database cleanup (anonymize/delete)
                    await AnonymousSession.cleanup_expired_anonymous_users()
                except Exception as cleanup_error:
                    print(f"WARNING: Periodic cleanup error: {cleanup_error}")
                # Run every 15 minutes
                await asyncio.sleep(900)

        asyncio.create_task(periodic_cleanup())
        print("🧹 Started periodic anonymous cleanup task")
    except Exception as schedule_error:
        print(f"WARNING: Failed to start cleanup scheduler: {schedule_error}")

@app.on_event("shutdown")
async def shutdown():
    """
    This function runs when the FastAPI application shuts down.
    You can add cleanup tasks here if needed.
    """
    print("Shutting down FastAPI application...")


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
auth = None
dossier = None
upload = None

# Old chat router removed - using new simplified system

try:
    from app.api import transcribe
    print("SUCCESS: Transcribe router imported")
except Exception as e:
    print(f"ERROR: Error importing transcribe router: {e}")
    transcribe = None

# Using simplified session and chat system

try:
    from app.api import simple_session_manager
    print("SUCCESS: Simple session manager imported")
except Exception as e:
    print(f"ERROR: Error importing simple_session_manager: {e}")
    simple_session_manager = None

try:
    from app.api import simple_chat
    print("SUCCESS: Simple chat imported")
except Exception as e:
    print(f"ERROR: Error importing simple_chat: {e}")
    simple_chat = None

try:
    from app.api import simple_users
    print("SUCCESS: Simple users imported")
except Exception as e:
    print(f"ERROR: Error importing simple_users: {e}")
    simple_users = None

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

try:
    from app.api import projects
    print("SUCCESS: Projects router imported")
except Exception as e:
    print(f"ERROR: Error importing projects router: {e}")
    projects = None

try:
    from app.api import upload
    print("SUCCESS: Upload router imported")
except Exception as e:
    print(f"ERROR: Error importing upload router: {e}")
    upload = None

try:
    from app.api import validation
    print("SUCCESS: Validation router imported")
except Exception as e:
    print(f"ERROR: Error importing validation router: {e}")
    validation = None

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
# Using new simplified session and chat system

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

if projects:
    try:
        app.include_router(projects.router, prefix="/api/v1", tags=["projects"])
        print("SUCCESS: Projects router included")
    except Exception as e:
        print(f"ERROR: Error including projects router: {e}")

if upload:
    try:
        app.include_router(upload.router, prefix="/api/v1", tags=["upload"])
        print("SUCCESS: Upload router included")
    except Exception as e:
        print(f"ERROR: Error including upload router: {e}")

# Include new simplified routers
if simple_session_manager:
    try:
        app.include_router(simple_session_manager.router, prefix="/api/v1", tags=["session"])
        print("SUCCESS: Simple session manager router included")
    except Exception as e:
        print(f"ERROR: Error including simple session manager router: {e}")

if simple_chat:
    try:
        app.include_router(simple_chat.router, prefix="/api/v1", tags=["chat"])
        print("SUCCESS: Simple chat router included")
    except Exception as e:
        print(f"ERROR: Error including simple chat router: {e}")

if simple_users:
    try:
        app.include_router(simple_users.router, prefix="/api/v1", tags=["users"])
        print("SUCCESS: Simple users router included")
    except Exception as e:
        print(f"ERROR: Error including simple users router: {e}")

if validation:
    try:
        app.include_router(validation.router, prefix="/api/v1", tags=["validation"])
        print("SUCCESS: Validation router included")
    except Exception as e:
        print(f"ERROR: Error including validation router: {e}")

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
        "endpoints": ["/dossier", "/transcribe", "/upload", "/api/v1/chat", "/api/v1/sessions", "/api/v1/auth/login", "/api/v1/auth/signup", "/api/v1/dossiers", "/api/v1/validation/queue", "/api/v1/admin/extract-knowledge"],
        "routes_available": {
            "chat_sessions": False,  # Using simplified system
            "auth": auth is not None,
            "transcribe": transcribe is not None,
            "dossier": dossier is not None,
            "upload": upload is not None,
            "validation": validation is not None
        },
        "background_workers": {
            "periodic_cleanup": True,
            "knowledge_extraction": True
        }
    }

# Add simple test endpoint
@app.get("/test")
async def test_endpoint():
    return {"message": "Test endpoint working", "status": "ok"}

# Add manual knowledge extraction trigger endpoint
@app.post("/api/v1/admin/extract-knowledge")
async def trigger_knowledge_extraction():
    """Manually trigger knowledge extraction (admin endpoint)"""
    try:
        from app.workers.knowledge_extractor import knowledge_extractor
        
        # Run knowledge extraction
        await knowledge_extractor.extract_knowledge_from_conversations(limit=10)
        
        return {
            "success": True,
            "message": "Knowledge extraction completed successfully",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Knowledge extraction failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


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
        from app.api.simple_session_manager import SimpleSessionManager

        async def periodic_cleanup():
            while True:
                try:
                    # Database cleanup (anonymize/delete) - run every 30 minutes
                    await SimpleSessionManager.cleanup_expired_anonymous_sessions()
                except Exception as cleanup_error:
                    print(f"WARNING: Cleanup error: {cleanup_error}")
                
                # Run cleanup every 30 minutes
                await asyncio.sleep(1800)

        asyncio.create_task(periodic_cleanup())
        print("SUCCESS: Started periodic anonymous cleanup task")
    except Exception as schedule_error:
        print(f"WARNING: Failed to start cleanup scheduler: {schedule_error}")

    # Start knowledge extraction worker
    try:
        from app.workers.knowledge_extractor import knowledge_extractor

        async def knowledge_extraction_worker():
            while True:
                try:
                    # Run knowledge extraction every 2 hours
                    await knowledge_extractor.extract_knowledge_from_conversations(limit=5)
                    print("SUCCESS: Knowledge extraction completed")
                except Exception as extraction_error:
                    print(f"WARNING: Knowledge extraction error: {extraction_error}")
                
                # Run every 2 hours (7200 seconds)
                await asyncio.sleep(7200)

        asyncio.create_task(knowledge_extraction_worker())
        print("SUCCESS: Started knowledge extraction worker")
    except Exception as worker_error:
        print(f"WARNING: Failed to start knowledge extraction worker: {worker_error}")

@app.on_event("shutdown")
async def shutdown():
    """
    This function runs when the FastAPI application shuts down.
    You can add cleanup tasks here if needed.
    """
    print("Shutting down FastAPI application...")


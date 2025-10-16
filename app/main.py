from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import chat, transcribe, chat_sessions, auth  # Import the chat, transcribe, chat_sessions, and auth routes
# from app.api import upload  # Import the upload route
# Import the Supabase client (with error handling)
try:
    from app.database.supabase import get_supabase_client
    SUPABASE_AVAILABLE = True
except Exception as e:
    print(f"Warning: Supabase not available: {e}")
    SUPABASE_AVAILABLE = False

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "https://stories-we-tell.vercel.app",  # Production frontend URL
        "https://stories-we-tell-backend.vercel.app"  # Backend URL for testing
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicit methods
    allow_headers=["*"],  # Allow all headers
)

# Include the chat route (legacy)
app.include_router(chat.router)

# Include the new chat sessions route
app.include_router(chat_sessions.router, prefix="/api/v1", tags=["chat-sessions"])

# Include the auth route
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])

# Include the upload route
# app.include_router(upload.router)

# Include the transcribe route
app.include_router(transcribe.router)

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
        "endpoints": ["/chat", "/dossier", "/transcribe", "/upload", "/api/v1/chat", "/api/v1/sessions", "/api/v1/auth/login", "/api/v1/auth/signup"]
    }

# Add simple test endpoint
@app.get("/test")
async def test_endpoint():
    return {"message": "Test endpoint working", "status": "ok"}

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
    It's a good place to check the connection to the database.
    """
    try:
        print("Starting up FastAPI application...")
        if SUPABASE_AVAILABLE:
            # Try to get the Supabase client and check if the connection is successful
            supabase = get_supabase_client()
            print("Connected to Supabase!")
        else:
            print("Supabase not available - running without database")
    except Exception as e:
        print(f"Warning: Error connecting to Supabase: {e}")
        print("Application will continue to run without database connection")

@app.on_event("shutdown")
async def shutdown():
    """
    This function runs when the FastAPI application shuts down.
    You can add cleanup tasks here if needed.
    """
    print("Shutting down FastAPI application...")


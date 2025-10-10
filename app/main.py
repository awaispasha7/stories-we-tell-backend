from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import chat  # Import the chat routes
from app.database.supabase import get_supabase_client  # Import the Supabase client

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Include the chat route
app.include_router(chat.router)

@app.on_event("startup")
async def startup():
    """
    This function runs when the FastAPI application starts.
    It's a good place to check the connection to the database.
    """
    try:
        print("Starting up FastAPI application...")
        # Try to get the Supabase client and check if the connection is successful
        supabase = get_supabase_client()
        print("Connected to Supabase!")
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")

@app.on_event("shutdown")
async def shutdown():
    """
    This function runs when the FastAPI application shuts down.
    You can add cleanup tasks here if needed.
    """
    print("Shutting down FastAPI application...")


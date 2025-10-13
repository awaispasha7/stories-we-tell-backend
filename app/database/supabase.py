import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration for Supabase and other API keys
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Supabase client initialization
def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Supabase credentials are not set in the environment variables.")
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Optional: Check if the environment variables are loaded correctly
# Note: This check is moved to the get_supabase_client function to avoid startup failures

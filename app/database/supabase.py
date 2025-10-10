import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration for Supabase and other API keys
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Supabase client initialization
def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Supabase credentials are not set in the environment variables.")
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Optional: Check if the environment variables are loaded correctly
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Please make sure SUPABASE_URL and SUPABASE_KEY are set in the .env file.")

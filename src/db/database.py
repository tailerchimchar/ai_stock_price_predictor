import os
from functools import lru_cache
from supabase import create_client, Client
from dotenv import load_dotenv

# Load .env file
load_dotenv()

TABLE_NAME = "analysis_db"

DB = Client  # alias for type hints


@lru_cache(maxsize=1)
def get_db() -> DB:
    """Return a cached Supabase client using env vars SUPABASE_URL, SUPABASE_KEY."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)

def healthcheck() -> bool:
    """Return True if the table is reachable, else False."""
    try:
        get_db().table(TABLE_NAME).select("id").limit(1).execute()
        return True
    except Exception:
        return False

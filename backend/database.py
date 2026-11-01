"""Two Supabase connections.

Viva: supabase_public is for login only.
supabase_admin is for tables and rows, because those need the secret key.
"""

from supabase import create_client, Client

from config import get_settings

settings = get_settings()

supabase_admin: Client = create_client(settings.supabase_url, settings.supabase_secret_key)
supabase_public: Client = create_client(settings.supabase_url, settings.supabase_publishable_key)

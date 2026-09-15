from supabase import Client, create_client

from app.config import settings


def create_user_client(access_token: str) -> Client:
    """Create a Supabase client that is restricted by the user's RLS policies."""
    if not access_token.strip():
        raise ValueError("access_token must not be empty")

    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client


def create_service_role_client() -> Client:
    """Create a trusted Supabase client for server-side administrative work."""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


__all__ = ["create_service_role_client", "create_user_client"]
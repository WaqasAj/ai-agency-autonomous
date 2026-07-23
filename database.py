import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import requests

# Get connection string from environment (Streamlit secrets or env var)
DATABASE_URL = os.getenv("DATABASE_URL")

@contextmanager
def get_db_connection():
    """Get a database connection with automatic cleanup."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()

def get_all_pages():
    """Get all pages from the database."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM pages ORDER BY created_at DESC")
            return cur.fetchall()

def get_page(page_id):
    """Get a single page by ID."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM pages WHERE id = %s", (page_id,))
            return cur.fetchone()

def create_page(name, niche, description=""):
    """Create a new page."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pages (name, niche, description) VALUES (%s, %s, %s) RETURNING id",
                (name, niche, description)
            )
            page_id = cur.fetchone()["id"]
            conn.commit()
            return page_id

def update_page(page_id, name=None, niche=None, description=None, status=None):
    """Update a page."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            updates = []
            values = []
            if name is not None:
                updates.append("name = %s")
                values.append(name)
            if niche is not None:
                updates.append("niche = %s")
                values.append(niche)
            if description is not None:
                updates.append("description = %s")
                values.append(description)
            if status is not None:
                updates.append("status = %s")
                values.append(status)
            
            if updates:
                updates.append("updated_at = NOW()")
                values.append(page_id)
                cur.execute(f"UPDATE pages SET {', '.join(updates)} WHERE id = %s", values)
                conn.commit()

def delete_page(page_id):
    """Delete a page."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pages WHERE id = %s", (page_id,))
            conn.commit()

def save_token(page_id, platform, access_token, external_id=None, expires_at=None):
    """Save or update a token for a page."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Deactivate existing tokens for this page+platform
            cur.execute(
                "UPDATE tokens SET is_active = false WHERE page_id = %s AND platform = %s",
                (page_id, platform)
            )
            # Insert new token
            cur.execute(
                """INSERT INTO tokens (page_id, platform, access_token, external_id, expires_at)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (page_id, platform, access_token, external_id, expires_at)
            )
            token_id = cur.fetchone()["id"]
            conn.commit()
            return token_id

def get_tokens(page_id):
    """Get all active tokens for a page."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM tokens WHERE page_id = %s AND is_active = true",
                (page_id,)
            )
            return cur.fetchall()

def log_run(page_id, run_type, status, details=None, error_message=None):
    """Log a workflow run."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO run_history (page_id, run_type, status, details, error_message)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (page_id, run_type, status, details, error_message)
            )
            run_id = cur.fetchone()["id"]
            conn.commit()
            return run_id

def get_run_history(page_id=None, limit=20):
    """Get recent run history."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if page_id:
                cur.execute(
                    "SELECT * FROM run_history WHERE page_id = %s ORDER BY started_at DESC LIMIT %s",
                    (page_id, limit)
                )
            else:
                cur.execute(
                    "SELECT * FROM run_history ORDER BY started_at DESC LIMIT %s",
                    (limit,)
                )
            return cur.fetchall()

def test_facebook_connection(access_token, page_id):
    """Test if a Facebook Page token is valid."""
    try:
        url = f"https://graph.facebook.com/v19.0/{page_id}?fields=id,name&access_token={access_token}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "valid": True,
                "page_name": data.get("name"),
                "page_id": data.get("id")
            }
        else:
            error = response.json().get("error", {})
            return {
                "valid": False,
                "error": error.get("message", "Unknown error")
            }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }

def test_instagram_connection(access_token, ig_account_id):
    """Test if an Instagram Business token is valid."""
    try:
        url = f"https://graph.facebook.com/v19.0/{ig_account_id}?fields=id,username&access_token={access_token}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "valid": True,
                "username": data.get("username"),
                "ig_id": data.get("id")
            }
        else:
            error = response.json().get("error", {})
            return {
                "valid": False,
                "error": error.get("message", "Unknown error")
            }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }

def get_page_with_tokens(page_id):
    """Get a page with all its connected tokens."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get page
            cur.execute("SELECT * FROM pages WHERE id = %s", (page_id,))
            page = cur.fetchone()
            
            if not page:
                return None
            
            # Get tokens
            cur.execute(
                "SELECT * FROM tokens WHERE page_id = %s AND is_active = true",
                (page_id,)
            )
            tokens = cur.fetchall()
            
            page["tokens"] = tokens
            return page

import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

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

def trigger_github_workflow(page_id, github_token, repo_owner, repo_name, workflow_filename="daily-agents.yml"):
    """Trigger a GitHub Actions workflow for a specific page."""
    try:
        # Get page data with tokens
        page_data = get_page_with_tokens(page_id)
        if not page_data:
            return {"success": False, "error": "Page not found"}
        
        # Extract tokens
        fb_token = next((t for t in page_data["tokens"] if t["platform"] == "facebook"), None)
        ig_token = next((t for t in page_data["tokens"] if t["platform"] == "instagram"), None)
        
        # Build workflow inputs
        inputs = {
            "page_name": page_data["name"],
            "page_niche": page_data["niche"],
            "facebook_page_id": fb_token["external_id"] if fb_token else "",
            "facebook_access_token": fb_token["access_token"] if fb_token else "",
            "instagram_account_id": ig_token["external_id"] if ig_token else "",
        }
        
        # Trigger workflow via GitHub API
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/workflows/{workflow_filename}/dispatches"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        payload = {
            "ref": "main",
            "inputs": inputs
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 204:
            # Log the run
            run_id = log_run(page_id, "workflow_trigger", "triggered", details=inputs)
            return {"success": True, "run_id": run_id, "message": "Workflow triggered successfully"}
        else:
            error_msg = response.json().get("message", "Unknown error")
            return {"success": False, "error": error_msg}
    
    except Exception as e:
        return {"success": False, "error": str(e)}

def update_run_status(run_id, status, details=None, error_message=None):
    """Update the status of a workflow run."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE run_history 
                   SET status = %s, completed_at = NOW(), details = %s, error_message = %s
                   WHERE id = %s""",
                (status, details, error_message, run_id)
            )
            conn.commit()

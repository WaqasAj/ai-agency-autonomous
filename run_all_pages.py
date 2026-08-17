"""
Multi-Page Dispatcher
Queries the Neon database for all active pages and runs the agency for each one.
Used by the cron schedule to ensure ALL pages get content daily.
"""
import os
import subprocess
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")

def get_active_pages():
    """Fetch all active pages from the Neon database."""
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL not set. Running for default page only.")
        return [{"name": "Kahani AI", "niche": "parenting", "description": ""}]
    
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        cur.execute("SELECT name, niche, description FROM pages WHERE status = 'active'")
        pages = cur.fetchall()
        conn.close()
        
        if not pages:
            print("⚠️ No active pages found. Running for default page only.")
            return [{"name": "Kahani AI", "niche": "parenting", "description": ""}]
        
        return pages
    except Exception as e:
        print(f"⚠️ Database error: {e}. Running for default page only.")
        return [{"name": "Kahani AI", "niche": "parenting", "description": ""}]

def run_agency_for_page(page):
    """Run the agency for a specific page by setting env vars."""
    page_name = page["name"]
    page_niche = page.get("niche", "general")
    page_description = page.get("description", "")
    
    print(f"\n{'='*70}")
    print(f"🚀 DISPATCHER: Running agency for '{page_name}' ({page_niche})")
    print(f"   Description: {page_description[:100]}")
    print(f"{'='*70}\n")
    
    # Set environment variables for this specific page
    env = os.environ.copy()
    env["PAGE_NAME"] = page_name
    env["PAGE_NICHE"] = page_niche
    env["PAGE_DESCRIPTION"] = page_description
    
    # Run agents.py as a subprocess with the page-specific env vars
    result = subprocess.run(
        ["python", "agents.py"],
        env=env,
        capture_output=False
    )
    
    if result.returncode != 0:
        print(f"❌ Agency run failed for {page_name} (exit code: {result.returncode})")
    else:
        print(f"✅ Agency run completed for {page_name}")

if __name__ == "__main__":
    print("🔍 DISPATCHER: Fetching active pages from database...")
    pages = get_active_pages()
    print(f"📋 Found {len(pages)} active page(s): {[p['name'] for p in pages]}")
    
    for page in pages:
        run_agency_for_page(page)
    
    print(f"\n🎉 DISPATCHER: All pages processed!")

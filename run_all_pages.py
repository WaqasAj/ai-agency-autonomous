"""
Multi-Page Dispatcher with Full Output Capture
"""
import os
import subprocess
import sys

# Try to import psycopg2. If it fails, we'll use the hardcoded fallback.
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    print("⚠️ psycopg2 not installed. Using hardcoded active pages.")

def get_active_pages():
    print("\n🔍 DEBUG: Checking DATABASE_URL...")
    db_url = os.getenv("DATABASE_URL")
    print(f"🔍 DEBUG: DATABASE_URL is present: {bool(db_url)}")
    
    if HAS_PSYCOPG2 and db_url:
        try:
            print("🔍 DEBUG: Connecting to database...")
            conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
            cur = conn.cursor()
            cur.execute("SELECT name, niche, description, status FROM pages WHERE LOWER(status) = 'active'")
            pages = cur.fetchall()
            conn.close()
            print(f"✅ Found {len(pages)} active pages in database.")
            for p in pages:
                print(f"   - {p['name']} (niche: {p['niche']})")
            if pages:
                return pages
        except Exception as e:
            print(f"❌ Database query failed: {e}")
    
    print("⚠️ Falling back to hardcoded active pages.")
    return [
        {"name": "Kahani AI", "niche": "parenting", "description": "AI bedtime stories for kids"},
        {"name": "Geo Analyzer", "niche": "technology", "description": "SEO and GEO optimization tool"}
    ]

def run_agency_for_page(page):
    page_name = page["name"]
    page_niche = page.get("niche", "general")
    page_description = page.get("description", "")
    
    print(f"\n{'='*70}")
    print(f"🚀 DISPATCHER: Running agency for '{page_name}'")
    print(f"   Niche: {page_niche}")
    print(f"   Description: {page_description[:100] if page_description else 'None'}")
    print(f"{'='*70}\n")
    
    env = os.environ.copy()
    env["PAGE_NAME"] = page_name
    env["PAGE_NICHE"] = page_niche
    env["PAGE_DESCRIPTION"] = page_description
    
    print(f"🔍 DEBUG: Env vars set -> PAGE_NAME={page_name}, PAGE_NICHE={page_niche}")
    print(f"🔍 DEBUG: Starting agents.py subprocess...\n")
    
    # Run agents.py and capture ALL output in real-time
    process = subprocess.Popen(
        [sys.executable, "agents.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Stream output line by line
    if process.stdout:
        for line in process.stdout:
            print(line, end='', flush=True)
    
    process.wait()
    
    if process.returncode != 0:
        print(f"\n❌ Agency run failed for {page_name} (exit code: {process.returncode})")
    else:
        print(f"\n✅ Agency run completed for {page_name}")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔍 DISPATCHER STARTING")
    print("="*70)
    
    pages = get_active_pages()
    print(f"\n📋 Will run agency for {len(pages)} page(s)")
    
    for page in pages:
        run_agency_for_page(page)
    
    print(f"\n{'='*70}")
    print(f"🎉 DISPATCHER: All {len(pages)} pages processed!")
    print(f"{'='*70}\n")

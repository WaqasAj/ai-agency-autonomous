import os
import subprocess
import sys

print("\n" + "="*70)
print("🔍 DISPATCHER STARTING")
print("="*70)

# Hardcoded fallback to guarantee it runs
pages = [
    {"name": "Kahani AI", "niche": "parenting", "description": "AI bedtime stories for kids"},
    {"name": "Geo Analyzer", "niche": "technology", "description": "SEO and GEO optimization tool"}
]

print(f"\n📋 Will run agency for {len(pages)} page(s)")

for page in pages:
    page_name = page["name"]
    page_niche = page.get("niche", "general")
    page_description = page.get("description", "")
    
    print(f"\n{'='*70}")
    print(f"🚀 DISPATCHER: Running agency for '{page_name}'")
    print(f"   Niche: {page_niche}")
    print(f"{'='*70}\n")
    
    env = os.environ.copy()
    env["PAGE_NAME"] = page_name
    env["PAGE_NICHE"] = page_niche
    env["PAGE_DESCRIPTION"] = page_description
    
    print(f"🔍 Starting agents.py for {page_name}...\n")
    
    # Run and stream output in real-time
    process = subprocess.Popen(
        [sys.executable, "agents.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    if process.stdout:
        for line in process.stdout:
            print(line, end='', flush=True)
    
    process.wait()
    
    if process.returncode != 0:
        print(f"\n❌ Agency run FAILED for {page_name}")
    else:
        print(f"\n✅ Agency run completed for {page_name}")

print(f"\n{'='*70}")
print(f"🎉 DISPATCHER: All pages processed!")
print(f"{'='*70}\n")

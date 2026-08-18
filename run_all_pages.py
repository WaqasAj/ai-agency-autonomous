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
    
    # Run agents.py and capture ALL output
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
    output_lines = []
    if process.stdout:
        for line in process.stdout:
            print(line, end='', flush=True)
            output_lines.append(line)
    
    process.wait()
    
    # Check for errors
    if process.returncode != 0:
        print(f"\n❌ Agency run FAILED for {page_name}")
        print(f"   Exit code: {process.returncode}")
        print(f"   Last 10 lines of output:")
        for line in output_lines[-10:]:
            print(f"   {line}", end='')
    else:
        print(f"\n✅ Agency run completed for {page_name}")
        if not output_lines:
            print("   ⚠️ WARNING: No output was captured from agents.py")
            print("   This suggests the script may have crashed on import.")

import os
import requests
from crewai import Agent, Task, Crew, Process
from datetime import datetime

# Load secrets from GitHub Actions
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
NOTION_KEY = os.getenv("NOTION_API_KEY")
NOTION_DB_ID = os.getenv("NOTION_DATABASE_ID")

os.environ["GEMINI_API_KEY"] = GEMINI_KEY

# ============ FETCH BLOGS FROM NOTION ============
def fetch_new_blogs():
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    # Filter for blogs marked "Ready for Social"
    payload = {
        "filter": {
            "property": "Status",
            "select": {
                "equals": "Ready for Social"
            }
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    
    blogs = []
    for result in data.get("results", []):
        title = result["properties"]["Name"]["title"][0]["text"]["content"]
        blogs.append({
            "id": result["id"],
            "title": title
        })
    
    return blogs

# ============ LOG RESULTS TO NOTION ============
def log_to_notion(blog_title, agent_output):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    # Truncate output to fit Notion's 2000 character limit
    truncated_output = str(agent_output)[:2000]
    
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": f"Agent Log: {blog_title}"}}]},
            "Status": {"select": {"name": "Posted"}},
            "Agent Output": {"rich_text": [{"text": {"content": truncated_output}}]}
        }
    }
    
    try:
        requests.post(url, headers=headers, json=payload)
        print(f"✅ Logged results to Notion for: {blog_title}")
    except Exception as e:
        print(f"⚠️ Failed to log to Notion: {e}")

# ============ DEFINE AUTONOMOUS AGENTS ============
researcher = Agent(
    role="Senior Content Researcher",
    goal="Analyze blog content and identify the most valuable insights worth promoting",
    backstory="You are an expert at identifying viral hooks and key takeaways from long-form content.",
    llm="gemini/gemini-2.0-flash",
    verbose=True
)

strategist = Agent(
    role="Content Strategist",
    goal="Decide which platforms to post on and what angle to take for each",
    backstory="You are a social media strategist who knows which content works best on LinkedIn vs Twitter vs Instagram.",
    llm="gemini/gemini-2.0-flash",
    verbose=True
)

editor = Agent(
    role="Viral Content Editor",
    goal="Create platform-specific posts that stop the scroll",
    backstory="You are a social media expert who crafts posts that drive engagement.",
    llm="gemini/gemini-2.0-flash",
    verbose=True
)

ceo = Agent(
    role="Chief Content Officer",
    goal="Review all content for quality and brand alignment. Reject anything off-brand.",
    backstory="You are a seasoned executive who ensures only high-quality content gets published.",
    llm="gemini/gemini-2.0-flash",
    verbose=True
)

poster = Agent(
    role="Social Media Manager",
    goal="Format approved content for publishing (actual posting will be added later)",
    backstory="You handle the final formatting and preparation for social platforms.",
    llm="gemini/gemini-2.0-flash",
    verbose=True
)

# ============ RUN THE AUTONOMOUS CREW ============
def run_daily_agency():
    print(f"🚀 Starting autonomous agency run at {datetime.now()}")
    
    # Step 1: Fetch new blogs
    blogs = fetch_new_blogs()
    
    if not blogs:
        print("✅ No new blogs to process today.")
        return
    
    print(f"📝 Found {len(blogs)} blog(s) to process")
    
    # Step 2: Process each blog with autonomous agents
    for blog in blogs:
        print(f"\n🔄 Processing: {blog['title']}")
        
        # Define tasks for this blog
        research_task = Task(
            description=f"Analyze this blog and extract the 3 most valuable insights worth promoting: {blog['title']}",
            expected_output="3 key insights with viral hooks",
            agent=researcher
        )
        
        strategy_task = Task(
            description=f"Based on these insights, decide which platforms (LinkedIn, Twitter, Instagram) are best and what angle to take for each",
            expected_output="Platform strategy with specific angles for each",
            agent=strategist
        )
        
        edit_task = Task(
            description="Create platform-specific posts based on the strategy",
            expected_output="3 posts (one per platform) ready for review",
            agent=editor
        )
        
        review_task = Task(
            description="Review all posts for quality, brand alignment, and engagement potential. Approve or reject.",
            expected_output="Approved posts or rejection with feedback",
            agent=ceo
        )
        
        post_task = Task(
            description="Format the approved posts for publishing",
            expected_output="Final formatted posts ready for social media",
            agent=poster
        )
        
        # Assemble the crew
        crew = Crew(
            agents=[researcher, strategist, editor, ceo, poster],
            tasks=[research_task, strategy_task, edit_task, review_task, post_task],
            process=Process.sequential,
            verbose=True
        )
        
        # Run the crew
        result = crew.kickoff()
        
        # Log results to Notion
        log_to_notion(blog['title'], result)
        
        print(f"✅ Completed: {blog['title']}")
        print(f"Result preview: {str(result)[:200]}...\n")

if __name__ == "__main__":
    run_daily_agency()

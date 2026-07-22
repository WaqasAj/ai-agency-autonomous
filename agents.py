import os
import requests
import re
from crewai import Agent, Task, Crew, Process
from datetime import datetime
import litellm

# ============ THE FIX: Strip cache_breakpoint from every API call ============
_original_completion = litellm.completion

def _strip_cache_breakpoint(obj):
    """Recursively remove 'cache_breakpoint' from any dict in the payload."""
    if isinstance(obj, dict):
        obj.pop("cache_breakpoint", None)
        for v in obj.values():
            _strip_cache_breakpoint(v)
    elif isinstance(obj, list):
        for item in obj:
            _strip_cache_breakpoint(item)

def _patched_completion(*args, **kwargs):
    _strip_cache_breakpoint(kwargs)
    return _original_completion(*args, **kwargs)

litellm.completion = _patched_completion
# =============================================================================

# ============ LOAD SECRETS ============
NOTION_KEY = os.getenv("NOTION_API_KEY")
NOTION_DB_ID = os.getenv("NOTION_DATABASE_ID")
MISTRAL_KEY = os.getenv("MISTRAL_API_KEY")

os.environ["MISTRAL_API_KEY"] = MISTRAL_KEY

# ============ KAHAANI AI BRAND CONTEXT ============
BRAND_CONTEXT = """
Kahani AI is a web tool that creates personalized stories and bedtime stories for kids, 
complete with illustrations. Features:
- Create stories in 4 languages: English, Urdu, Arabic, Hindi
- Read stories, play audio, copy text, share links, download PDF
- Target audience: Parents, families, educators of young children
- Brand voice: Warm, family-friendly, educational, culturally sensitive, trustworthy
- Content themes: Bedtime routines, benefits of storytelling, multilingual education, 
  cultural stories, child development, screen-free activities, Islamic stories
"""

# ============ NOTION API HELPERS ============
def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

def fetch_unprocessed_published_blogs():
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "published", "checkbox": {"equals": True}},
                {"or": [
                    {"property": "Status", "select": {"equals": "Not Processed"}},
                    {"property": "Status", "select": {"is_empty": True}}
                ]}
            ]
        }
    }
    response = requests.post(url, headers=notion_headers(), json=payload)
    data = response.json()
    
    blogs = []
    for result in data.get("results", []):
        title = result["properties"]["title"]["title"][0]["text"]["content"] if result["properties"]["title"]["title"] else "Untitled"
        content = ""
        if "content" in result["properties"] and result["properties"]["content"]["type"] == "rich_text":
            if result["properties"]["content"]["rich_text"]:
                content = result["properties"]["content"]["rich_text"][0]["text"]["content"]
        meta = ""
        if "meta description" in result["properties"] and result["properties"]["meta description"]["type"] == "rich_text":
            if result["properties"]["meta description"]["rich_text"]:
                meta = result["properties"]["meta description"]["rich_text"][0]["text"]["content"]
        keywords = ""
        if "keywords" in result["properties"] and result["properties"]["keywords"]["type"] == "rich_text":
            if result["properties"]["keywords"]["rich_text"]:
                keywords = result["properties"]["keywords"]["rich_text"][0]["text"]["content"]
        
        blogs.append({
            "id": result["id"],
            "title": title,
            "content": content,
            "meta_description": meta,
            "keywords": keywords
        })
    return blogs

def create_new_blog_in_notion(title, content, slug, meta_description, keywords):
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "title": {"title": [{"text": {"content": title}}]},
            "slug": {"rich_text": [{"text": {"content": slug}}]},
            "meta description": {"rich_text": [{"text": {"content": meta_description}}]},
            "keywords": {"rich_text": [{"text": {"content": keywords}}]},
            "content": {"rich_text": [{"text": {"content": content[:2000]}}]},
            "published": {"checkbox": False},
            "Blog Source": {"select": {"name": "AI Generated"}}
        }
    }
    response = requests.post(url, headers=notion_headers(), json=payload)
    if response.status_code == 200:
        page_id = response.json()["id"]
        print(f"✅ Created new blog draft: {title}")
        return page_id
    else:
        print(f"❌ Failed to create blog: {response.status_code} - {response.text}")
        return None

def auto_publish_blog(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"published": {"checkbox": True}}}
    response = requests.patch(url, headers=notion_headers(), json=payload)
    if response.status_code == 200:
        print(f"🚀 AUTO-PUBLISHED blog to website!")
        return True
    else:
        print(f"❌ Failed to publish: {response.status_code} - {response.text}")
        return False

def update_social_status(page_id, status):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"Status": {"select": {"name": status}}}}
    requests.patch(url, headers=notion_headers(), json=payload)

def log_to_notion(blog_title, agent_output):
    url = "https://api.notion.com/v1/pages"
    truncated = str(agent_output)[:2000]
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "title": {"title": [{"text": {"content": f"📋 Log: {blog_title}"}}]},
            "content": {"rich_text": [{"text": {"content": truncated}}]},
            "published": {"checkbox": False}
        }
    }
    requests.post(url, headers=notion_headers(), json=payload)

# ============ DEFINE THE 7 AUTONOMOUS AGENTS (100% FREE - MISTRAL) ============
# Using Mistral Small - permanently free, native CrewAI support, no compatibility issues

FREE_MODEL = "mistral/mistral-small-latest"

trend_researcher = Agent(
    role="Trend Researcher for Kahani AI",
    goal="Find trending, high-value topics for parents interested in kids' stories and multilingual education",
    backstory=f"""You are a content research expert specializing in parenting and children's education.
    {BRAND_CONTEXT}
    You identify topics that will attract parents searching for bedtime story ideas, 
    multilingual education tips, and screen-free activities for kids.""",
    llm=FREE_MODEL,
    verbose=True
)

blog_writer = Agent(
    role="Kids' Story & Parenting Blog Writer",
    goal="Write engaging, warm, family-friendly blog posts optimized for both human readers and AI search engines (GEO)",
    backstory=f"""You are a beloved children's content writer with 15 years of experience.
    {BRAND_CONTEXT}
    You write blog posts that feel like advice from a trusted friend. Crucially, you structure 
    your writing for Generative Engine Optimization (GEO): you use clear headings, bullet points, 
    direct answers to common questions, and high information density without fluff, making it 
    easy for AI models to cite and rank your content.""",
    llm=FREE_MODEL,
    verbose=True
)

seo_geo_optimizer = Agent(
    role="SEO & GEO Specialist",
    goal="Optimize content to rank in both traditional search engines and AI search engines",
    backstory="""You are an expert in both traditional SEO and modern GEO. You know that AI engines 
    prioritize clear structure, authoritative facts, direct answers to questions, and high information 
    density. You create keyword-rich slugs, compelling meta descriptions, strategic keyword lists, 
    and specific 'Direct Answer' snippets that AI models love to pull into their responses.""",
    llm=FREE_MODEL,
    verbose=True
)

ceo_reviewer = Agent(
    role="Chief Content Officer at Kahani AI",
    goal="""Review blog posts for quality, brand alignment, child-safety, and GEO/SEO effectiveness. 
    If approved, output EXACTLY 'APPROVED' on a line by itself. If rejected, output 'REJECTED' with reasons.""",
    backstory=f"""You are the Chief Content Officer at Kahani AI. You are fiercely protective 
    of the brand's reputation. You ensure every piece of content is:
    - Child-safe and family-friendly
    - Culturally sensitive (English, Urdu, Arabic, Hindi audiences)
    - Genuinely helpful to parents
    - Aligned with Kahani AI's warm, trustworthy voice
    - Structured perfectly for SEO and GEO (clear headings, direct answers, no fluff)
    You reject anything that feels salesy, inappropriate, low-quality, or poorly structured.
    {BRAND_CONTEXT}""",
    llm=FREE_MODEL,
    verbose=True
)

social_strategist = Agent(
    role="Social Media Strategist",
    goal="Decide which platforms (Instagram, Facebook, TikTok, YouTube) to use and what angle for each",
    backstory="""You are a social media strategist who has grown parenting brands to millions of followers.
    You know that:
    - Instagram/TikTok = visual, emotional, reels showing happy kids
    - Facebook = parenting communities, longer storytelling posts
    - YouTube = tutorials, story previews, parenting tips
    You pick the best platforms and angles for each blog.""",
    llm=FREE_MODEL,
    verbose=True
)

content_creator = Agent(
    role="Viral Social Content Creator",
    goal="Create scroll-stopping social media posts for each platform",
    backstory="""You are a social media expert who creates viral content for parenting brands.
    You write posts that make parents stop scrolling, feel emotional, and want to try Kahani AI.
    You use emojis, hooks, and storytelling techniques that work on each platform.""",
    llm=FREE_MODEL,
    verbose=True
)

poster = Agent(
    role="Social Media Manager",
    goal="Format the final approved content for publishing across platforms",
    backstory="""You are the final step in the content pipeline. You take approved content 
    and format it perfectly for each social platform, ready to be posted.""",
    llm=FREE_MODEL,
    verbose=True
)

# ============ PHASE 1: BLOG CREATION PIPELINE ============
def run_blog_creation_phase():
    print("\n" + "="*60)
    print("📝 PHASE 1: BLOG CREATION")
    print("="*60)
    
    research_task = Task(
        description=f"""Research ONE trending blog topic perfect for Kahani AI's audience.
        Consider: bedtime routines, multilingual education, screen-free activities, 
        cultural stories, child development, Islamic stories for kids.
        Output ONLY the blog topic/title, nothing else.""",
        expected_output="A single compelling blog topic/title",
        agent=trend_researcher
    )
    
    write_task = Task(
        description="""Write a complete, engaging blog post (800-1200 words) on the topic.
        Make it warm, practical, and parent-friendly. Naturally mention how Kahani AI can help.
        CRITICAL GEO REQUIREMENT: Structure the content for AI search engines. Use clear H2/H3 headings, 
        bullet points, and provide direct, factual answers to common parent questions about the topic. 
        Avoid fluff; maximize information density.""",
        expected_output="A complete, GEO-optimized blog post (800-1200 words)",
        agent=blog_writer
    )
    
    seo_geo_task = Task(
        description="""Create SEO and GEO elements for this blog:
        1. URL slug (lowercase, hyphens, max 60 chars)
        2. Meta description (under 160 chars, compelling)
        3. 5-8 target keywords (comma-separated)
        4. GEO Direct Answer Snippets: Provide 2-3 concise, factual, standalone sentences that directly answer the core question of the blog.
        Output in this exact format:
        SLUG: [slug]
        META: [meta description]
        KEYWORDS: [keyword1, keyword2, ...]
        GEO_SNIPPETS: [snippet 1] | [snippet 2]""",
        expected_output="Slug, meta description, keywords, and GEO snippets in specified format",
        agent=seo_geo_optimizer
    )
    
    review_task = Task(
        description="""Review the blog post for:
        - Child-safety and family-friendliness
        - Cultural sensitivity (multilingual audience)
        - Brand voice alignment (warm, trustworthy)
        - Genuine value to parents
        - Quality of writing and GEO/SEO structure (clear headings, direct answers)
        If approved, output 'APPROVED' on its own line.
        If rejected, output 'REJECTED' with specific reasons.""",
        expected_output="APPROVED or REJECTED with reasons",
        agent=ceo_reviewer
    )
    
    crew = Crew(
        agents=[trend_researcher, blog_writer, seo_geo_optimizer, ceo_reviewer],
        tasks=[research_task, write_task, seo_geo_task, review_task],
        process=Process.sequential,
        verbose=True
    )
    
    crew.kickoff()
    
    title = research_task.output.raw.strip() if research_task.output else "Untitled"
    blog_content = write_task.output.raw.strip() if write_task.output else ""
    seo_output = seo_geo_task.output.raw.strip() if seo_geo_task.output else ""
    ceo_decision = review_task.output.raw.strip() if review_task.output else ""
    
    slug = ""
    meta = ""
    keywords = ""
    
    for line in seo_output.split('\n'):
        if line.startswith("SLUG:"):
            slug = line.replace("SLUG:", "").strip()
        elif line.startswith("META:"):
            meta = line.replace("META:", "").strip()
        elif line.startswith("KEYWORDS:"):
            keywords = line.replace("KEYWORDS:", "").strip()
    
    is_approved = "APPROVED" in ceo_decision and "REJECTED" not in ceo_decision
    
    print(f"\n📊 CEO Decision: {'✅ APPROVED' if is_approved else '❌ REJECTED'}")
    print(f"📝 Title: {title}")
    print(f"🔗 Slug: {slug}")
    print(f"📄 Meta: {meta}")
    print(f"🔑 Keywords: {keywords}")
    
    if is_approved and title and blog_content:
        page_id = create_new_blog_in_notion(title, blog_content, slug, meta, keywords)
        if page_id:
            auto_publish_blog(page_id)
            return {"title": title, "page_id": page_id, "status": "published"}
    
    return {"title": title, "status": "rejected"}

# ============ PHASE 2: SOCIAL MEDIA PROMOTION ============
def run_social_promotion_phase():
    print("\n" + "="*60)
    print("📱 PHASE 2: SOCIAL MEDIA PROMOTION")
    print("="*60)
    
    blogs = fetch_unprocessed_published_blogs()
    
    if not blogs:
        print("✅ No new blogs to promote today.")
        return
    
    print(f"📝 Found {len(blogs)} blog(s) to promote")
    
    for blog in blogs:
        print(f"\n🔄 Promoting: {blog['title']}")
        update_social_status(blog['id'], "Processing")
        
        blog_context = f"""
Title: {blog['title']}
Meta: {blog['meta_description']}
Keywords: {blog['keywords']}
Content preview: {blog['content'][:1500]}
"""
        
        strategy_task = Task(
            description=f"""Based on this blog, decide which platforms to use (Instagram, Facebook, TikTok, YouTube)
            and what angle/hook for each. {blog_context}""",
            expected_output="Platform strategy with specific angles",
            agent=social_strategist
        )
        
        create_task = Task(
            description="Create scroll-stopping social posts for each chosen platform",
            expected_output="Platform-specific posts with emojis and hooks",
            agent=content_creator
        )
        
        post_task = Task(
            description="Format the final posts for publishing",
            expected_output="Final formatted posts ready to publish",
            agent=poster
        )
        
        crew = Crew(
            agents=[social_strategist, content_creator, poster],
            tasks=[strategy_task, create_task, post_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        
        log_to_notion(blog['title'], result)
        update_social_status(blog['id'], "Posted")
        
        print(f"✅ Completed promotion for: {blog['title']}")

# ============ MAIN EXECUTION ============
def run_daily_agency():
    print(f"🚀 Starting Kahani AI Autonomous Agency at {datetime.now()}")
    print(BRAND_CONTEXT)
    
    try:
        blog_result = run_blog_creation_phase()
    except Exception as e:
        print(f"⚠️ Blog creation phase error: {e}")
    
    try:
        run_social_promotion_phase()
    except Exception as e:
        print(f"⚠️ Social promotion phase error: {e}")
    
    print("\n🎉 Daily agency run complete!")

if __name__ == "__main__":
    run_daily_agency()

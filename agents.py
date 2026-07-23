import os
import requests
import re
import time
from crewai import Agent, Task, Crew, Process
from datetime import datetime
import litellm

# ============ THE FIX: Strip cache_breakpoint from every API call ============
_original_completion = litellm.completion

def _strip_cache_breakpoint(obj):
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
FB_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
FB_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")

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

# ============ HUMANIZATION GUIDELINES ============
HUMANIZATION_RULES = """
CRITICAL: Write like a real human parent, NOT like an AI. Follow these rules STRICTLY:

AVOID THESE AI PATTERNS (they will be rejected):
- Never start paragraphs with "In today's world", "In the digital age", "It's important to note"
- Never use "delve", "tapestry", "landscape", "realm", "journey" (overused AI words)
- Never use "foster", "cultivate", "embark", "navigate" in cliché ways
- Never write perfectly balanced, symmetrical paragraphs
- Never use generic filler like "Let's explore", "Let's dive in"
- Never use excessive transition words like "Furthermore", "Moreover", "Additionally"

DO THESE INSTEAD (human signals):
- Vary sentence length wildly — mix 5-word sentences with 25-word ones
- Start sentences with "And", "But", "Because", "So" — like real people talk
- Include specific numbers: "my 4-year-old", "3 AM wake-ups", "15 minutes before bed"
- Use contractions: "don't", "it's", "you'll", "we've"
- Add personal-sounding moments: "I remember when...", "Last week, my daughter..."
- Ask rhetorical questions: "Sound familiar?", "You know that feeling, right?"
- Use conversational asides: "(Yes, even on the tough nights)", "(trust me on this one)"
- Include imperfect but relatable details: cold coffee, messy rooms, tired eyes
- Write like you're texting a friend who gets it
- Use occasional humor or gentle self-deprecation
- Break grammar rules occasionally for voice
"""

# ============ CLEANING HELPERS ============
def clean_title(title):
    if not title:
        return "Untitled"
    cleaned = re.sub(r'^[\s\*"\']+', '', title)
    cleaned = re.sub(r'[\s\*"\']+$', '', cleaned)
    return cleaned.strip()

def clean_blog_content(content, title):
    if not content:
        return ""
    content = re.sub(r'^```(?:markdown|md)?\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    clean_t = clean_title(title)
    content = re.sub(r'^#+\s*' + re.escape(clean_t) + r'\s*\n+', '', content, flags=re.IGNORECASE)
    content = re.sub(r'^#+\s*["\']?\*?' + re.escape(clean_t) + r'\*?["\']?\s*\n+', '', content, flags=re.IGNORECASE)
    lines = content.split('\n')
    if lines and lines[0].startswith('# ') and len(lines[0]) < 100:
        first_heading = lines[0].replace('#', '').strip()
        if clean_t.lower() in first_heading.lower() or first_heading.lower() in clean_t.lower():
            lines = lines[1:]
            content = '\n'.join(lines)
    return content.strip()

# ============ NOTION API HELPERS ============
def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

def generate_blog_image(title, keywords):
    """Generate a high-quality AI image using Pollinations.ai with Flux model."""
    # Optimized prompt for children's book style
    prompt = f"Children's book illustration, {title[:80]}, warm magical colors, cozy bedtime atmosphere, whimsical style, professional quality, detailed"
    
    # Clean up prompt
    prompt = ' '.join(prompt.split())
    encoded_prompt = requests.utils.quote(prompt)
    
    # Use flux-realism model for better quality
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=800&nologo=true&model=flux-realism&seed={hash(title) % 10000}"
    
    print(f"🎨 Generated high-quality blog image")
    return image_url
def create_notion_page_with_body(title, content, slug, meta_description, keywords, full_blog_content, image_url):
    url = "https://api.notion.com/v1/pages"
    clean_t = clean_title(title)
    clean_content = clean_blog_content(full_blog_content, clean_t)
    excerpt = clean_content[:500] if clean_content else ""
    
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Title": {"title": [{"text": {"content": clean_t}}]},
            "Slug": {"rich_text": [{"text": {"content": slug}}]},
            "Meta Description": {"rich_text": [{"text": {"content": meta_description}}]},
            "Keywords": {"rich_text": [{"text": {"content": keywords}}]},
            "Content": {"rich_text": [{"text": {"content": excerpt}}]},
            "Published": {"checkbox": False},
            "Blog Source": {"select": {"name": "AI Generated"}}
        },
        "children": [
            {"object": "block", "type": "image", "image": {"type": "external", "external": {"url": image_url}}},
            *convert_text_to_notion_blocks(clean_content)
        ]
    }
    
    print(f"\n📝 Creating Notion page...")
    response = requests.post(url, headers=notion_headers(), json=payload)
    
    if response.status_code == 200:
        page_id = response.json()["id"]
        print(f"✅ Created Notion page: {clean_t}")
        return page_id
    else:
        print(f"❌ Failed to create page: {response.status_code} - {response.text}")
        return None

def fetch_unprocessed_published_blogs():
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Published", "checkbox": {"equals": True}},
                {"or": [
                    {"property": "Status", "status": {"equals": "Not Processed"}},
                    {"property": "Status", "status": {"is_empty": True}}
                ]}
            ]
        }
    }
    response = requests.post(url, headers=notion_headers(), json=payload)
    data = response.json()
    
    blogs = []
    for result in data.get("results", []):
        title = result["properties"]["Title"]["title"][0]["text"]["content"] if result["properties"]["Title"]["title"] else "Untitled"
        content = ""
        if "Content" in result["properties"] and result["properties"]["Content"]["type"] == "rich_text":
            if result["properties"]["Content"]["rich_text"]:
                content = result["properties"]["Content"]["rich_text"][0]["text"]["content"]
        meta = ""
        if "Meta Description" in result["properties"] and result["properties"]["Meta Description"]["type"] == "rich_text":
            if result["properties"]["Meta Description"]["rich_text"]:
                meta = result["properties"]["Meta Description"]["rich_text"][0]["text"]["content"]
        keywords = ""
        if "Keywords" in result["properties"] and result["properties"]["Keywords"]["type"] == "rich_text":
            if result["properties"]["Keywords"]["rich_text"]:
                keywords = result["properties"]["Keywords"]["rich_text"][0]["text"]["content"]
        
        blogs.append({
            "id": result["id"],
            "title": title,
            "content": content,
            "meta_description": meta,
            "keywords": keywords
        })
    return blogs

def auto_publish_blog(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"Published": {"checkbox": True}}}
    print(f"🚀 Publishing blog to website...")
    response = requests.patch(url, headers=notion_headers(), json=payload)
    if response.status_code == 200:
        print(f"✅ AUTO-PUBLISHED blog to website!")
        return True
    else:
        print(f"❌ Failed to publish: {response.status_code} - {response.text}")
        return False

def update_social_status(page_id, status):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"Status": {"status": {"name": status}}}}
    response = requests.patch(url, headers=notion_headers(), json=payload)
    if response.status_code == 200:
        print(f"✅ Updated Status to: {status}")
    else:
        print(f"⚠️ Failed to update Status: {response.status_code} - {response.text}")

def log_to_notion(blog_title, agent_output):
    url = "https://api.notion.com/v1/pages"
    truncated = str(agent_output)[:2000]
    clean_t = clean_title(blog_title)
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Title": {"title": [{"text": {"content": f"📋 Log: {clean_t}"}}]},
            "Content": {"rich_text": [{"text": {"content": truncated}}]},
            "Published": {"checkbox": False}
        }
    }
    response = requests.post(url, headers=notion_headers(), json=payload)
    if response.status_code == 200:
        print(f"✅ Logged results to Notion for: {clean_t}")
    else:
        print(f"⚠️ Failed to log to Notion: {response.status_code}")

# ============ FACEBOOK & INSTAGRAM POSTING ============
def create_instagram_caption(title, content, keywords):
    """Create an Instagram-optimized caption (max 2200 chars)."""
    clean_t = clean_title(title)
    # Extract first 2-3 paragraphs as caption base
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()][:3]
    intro = ' '.join(paragraphs)[:800]
    
    # Add hashtags
    keyword_list = [k.strip().replace(' ', '') for k in keywords.split(',')[:8]]
    hashtags = ' '.join([f'#{k}' for k in keyword_list])
    
    caption = f"""✨ {clean_t}

{intro}

💭 What's your experience with this? Drop a comment below! 👇

📖 Read the full story on our blog (link in bio)

{hashtags}

#KahaniAI #BedtimeStories #ParentingTips #KidsStories"""
    
    # Ensure under 2200 chars
    if len(caption) > 2200:
        caption = caption[:2197] + "..."
    
    return caption

def create_facebook_caption(title, content, keywords):
    """Create a Facebook-optimized caption (can be longer)."""
    clean_t = clean_title(title)
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()][:5]
    intro = '\n\n'.join(paragraphs)[:1500]
    
    caption = f"""📚 {clean_t}

{intro}

---
💬 We'd love to hear from you! What's your experience with this topic? Share in the comments!

👉 Read the full article on our blog and discover how Kahani AI can help your family create magical storytelling moments.

#KahaniAI #BedtimeStories #Parenting #KidsStories #MultilingualEducation"""
    
    return caption

def post_to_instagram(image_url, caption):
    """Post to Instagram using the 2-step Graph API process."""
    if not IG_ACCOUNT_ID or not FB_ACCESS_TOKEN:
        print("❌ Instagram credentials missing. Skipping Instagram post.")
        return None
    
    print(f"\n📸 Posting to Instagram...")
    
    # Step 1: Create media container
    container_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media"
    container_payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": FB_ACCESS_TOKEN
    }
    
    response = requests.post(container_url, data=container_payload)
    
    if response.status_code != 200:
        print(f"❌ Failed to create Instagram container: {response.status_code}")
        print(f"   Error: {response.text}")
        return None
    
    container_id = response.json().get("id")
    print(f"✅ Instagram container created: {container_id}")
    
    # Wait a few seconds for Instagram to process the image
    time.sleep(5)
    
    # Step 2: Check container status
    status_url = f"https://graph.facebook.com/v19.0/{container_id}"
    status_params = {"fields": "status_code", "access_token": FB_ACCESS_TOKEN}
    status_response = requests.get(status_url, params=status_params)
    
    if status_response.status_code == 200:
        status = status_response.json().get("status_code")
        if status != "FINISHED":
            print(f"⚠️ Container status: {status}. Waiting longer...")
            time.sleep(10)
    
    # Step 3: Publish the container
    publish_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media_publish"
    publish_payload = {
        "creation_id": container_id,
        "access_token": FB_ACCESS_TOKEN
    }
    
    response = requests.post(publish_url, data=publish_payload)
    
    if response.status_code == 200:
        media_id = response.json().get("id")
        print(f"✅ Posted to Instagram! Media ID: {media_id}")
        return media_id
    else:
        print(f"❌ Failed to publish to Instagram: {response.status_code}")
        print(f"   Error: {response.text}")
        return None

def post_to_facebook(image_url, caption):
    """Post to Facebook Page with image (no link preview)."""
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        print("❌ Facebook credentials missing. Skipping Facebook post.")
        return None
    
    print(f"\n📘 Posting to Facebook...")
    
    # Use /photos endpoint to upload image directly (not as a link)
    post_url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
    post_payload = {
        "message": caption,
        "url": image_url,  # Direct image upload
        "access_token": FB_ACCESS_TOKEN
    }
    
    response = requests.post(post_url, data=post_payload)
    
    if response.status_code == 200:
        post_id = response.json().get("id")
        print(f"✅ Posted to Facebook! Photo ID: {post_id}")
        return post_id
    else:
        print(f"❌ Failed to post to Facebook: {response.status_code}")
        print(f"   Error: {response.text}")
        return None    
    print(f"\n📘 Posting to Facebook...")
    
    post_url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
    post_payload = {
        "message": caption,
        "link": image_url,  # Attach the image
        "access_token": FB_ACCESS_TOKEN
    }
    
    response = requests.post(post_url, data=post_payload)
    
    if response.status_code == 200:
        post_id = response.json().get("id")
        print(f"✅ Posted to Facebook! Post ID: {post_id}")
        return post_id
    else:
        print(f"❌ Failed to post to Facebook: {response.status_code}")
        print(f"   Error: {response.text}")
        return None

# ============ DEFINE THE 7 AUTONOMOUS AGENTS ============

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
    role="Human Blog Writer (Writes Like a Real Parent)",
    goal="Write blog posts that are 100% indistinguishable from human-written content by real parents",
    backstory=f"""You are a parent-blogger with 15 years of experience writing from real life.
    {BRAND_CONTEXT}
    {HUMANIZATION_RULES}
    You write like you're sharing advice with a friend over coffee — messy, real, warm, 
    and full of specific details from your own experience. Every sentence should feel 
    like it came from a human who has actually lived this.""",
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
    goal="""Review blog posts with EXTREME rigor. Check for: quality, brand alignment, child-safety, 
    GEO/SEO structure, AND humanization. Output in this EXACT format:
    
    DECISION: APPROVED or REJECTED
    SCORE: X/10
    REASONS: [bullet list of specific issues]
    FIXES_NEEDED: [bullet list of exact changes required]
    
    Be harsh. Reject anything that sounds AI-generated.""",
    backstory=f"""You are the Chief Content Officer at Kahani AI with 20 years in content.
    You are OBSESSED with human-sounding content. You can spot AI writing from a mile away.
    
    {BRAND_CONTEXT}
    
    YOUR REVIEW CRITERIA (score each 1-10):
    1. HUMANIZATION: Does it sound like a real parent wrote it? Check for AI clichés.
    2. Child-safety and family-friendliness
    3. Cultural sensitivity (English, Urdu, Arabic, Hindi audiences)
    4. Brand voice alignment (warm, trustworthy, real)
    5. Genuine value to parents
    6. GEO/SEO structure (clear headings, direct answers)
    
    AUTOMATIC REJECTION TRIGGERS (reject immediately if found):
    - Uses "In today's digital age", "It's important to note", "Let's dive in"
    - Uses "delve", "tapestry", "landscape", "realm", "foster", "cultivate"
    - Perfectly symmetrical paragraphs
    - Generic, vague statements without specifics
    - Robotic, balanced sentence structure throughout
    - No personal voice or emotion
    
    If APPROVED: Output "DECISION: APPROVED" and a brief praise.
    If REJECTED: Output "DECISION: REJECTED" followed by SPECIFIC reasons and EXACT fixes needed.
    The writer will read your feedback and revise. Be detailed and actionable.""",
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

# ============ PHASE 1: BLOG CREATION WITH FEEDBACK LOOP ============
def run_blog_creation_phase():
    print("\n" + "="*60)
    print("📝 PHASE 1: BLOG CREATION (with CEO feedback loop)")
    print("="*60)
    
    research_task = Task(
        description=f"""Research ONE trending blog topic perfect for Kahani AI's audience.
        Consider: bedtime routines, multilingual education, screen-free activities, 
        cultural stories, child development, Islamic stories for kids.
        Output ONLY the blog topic/title as plain text, no quotes, no markdown, nothing else.""",
        expected_output="A single compelling blog topic/title as plain text",
        agent=trend_researcher
    )
    
    research_crew = Crew(
        agents=[trend_researcher],
        tasks=[research_task],
        process=Process.sequential,
        verbose=True
    )
    
    research_crew.kickoff()
    title = clean_title(research_task.output.raw.strip()) if research_task.output else "Untitled"
    print(f"\n🎯 Topic selected: {title}")
    
    MAX_REVISIONS = 2
    ceo_feedback = None
    final_blog_content = None
    final_seo_output = None
    final_ceo_decision = None
    
    for attempt in range(1, MAX_REVISIONS + 1):
        print(f"\n{'='*40}")
        print(f"📝 ATTEMPT {attempt}/{MAX_REVISIONS}")
        print(f"{'='*40}")
        
        if ceo_feedback:
            write_description = f"""REVISE the blog post based on CEO feedback.
            
PREVIOUS CEO FEEDBACK:
{ceo_feedback}

Fix ALL the issues mentioned. Apply every specific change requested.
Maintain the same topic: {title}

{HUMANIZATION_RULES}

Output ONLY the revised blog post (800-1200 words). Do NOT repeat the title at the top. 
Start directly with the introduction paragraph. Use ## for section headings."""
        else:
            write_description = f"""Write a complete, engaging blog post (800-1200 words) on this topic: {title}

{HUMANIZATION_RULES}

Make it warm, practical, and parent-friendly. Naturally mention how Kahani AI can help.
CRITICAL GEO REQUIREMENT: Structure the content for AI search engines. Use ## for section headings, 
bullet points, and provide direct, factual answers to common parent questions about the topic. 
Avoid fluff; maximize information density.

IMPORTANT: Do NOT repeat the title at the top. Start directly with the introduction paragraph.
Use ## for section headings (not #)."""
        
        write_task = Task(
            description=write_description,
            expected_output="A complete, human-sounding, GEO-optimized blog post (800-1200 words)",
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
            description="""Review the blog post rigorously against ALL criteria:
        - HUMANIZATION (most important): Does it sound like a real parent? Check for AI clichés.
        - Child-safety and family-friendliness
        - Cultural sensitivity (multilingual audience)
        - Brand voice alignment (warm, trustworthy, real)
        - Genuine value to parents
        - GEO/SEO structure (clear headings, direct answers)
        
        Output in EXACT format:
        DECISION: APPROVED or REJECTED
        SCORE: X/10
        REASONS: [bullet list]
        FIXES_NEEDED: [bullet list - only if REJECTED]""",
            expected_output="DECISION, SCORE, REASONS, and FIXES_NEEDED",
            agent=ceo_reviewer
        )
        
        crew = Crew(
            agents=[blog_writer, seo_geo_optimizer, ceo_reviewer],
            tasks=[write_task, seo_geo_task, review_task],
            process=Process.sequential,
            verbose=True
        )
        
        crew.kickoff()
        
        blog_content = write_task.output.raw.strip() if write_task.output else ""
        seo_output = seo_geo_task.output.raw.strip() if seo_geo_task.output else ""
        ceo_decision = review_task.output.raw.strip() if review_task.output else ""
        
        print(f"\n📊 CEO Response (Attempt {attempt}):")
        print(ceo_decision[:500])
        
        is_approved = "DECISION: APPROVED" in ceo_decision.upper()
        
        if is_approved:
            print(f"\n✅ CEO APPROVED on attempt {attempt}!")
            final_blog_content = blog_content
            final_seo_output = seo_output
            final_ceo_decision = ceo_decision
            break
        else:
            print(f"\n❌ CEO REJECTED on attempt {attempt}. Extracting feedback...")
            ceo_feedback = ceo_decision
            final_blog_content = blog_content
            final_seo_output = seo_output
            final_ceo_decision = ceo_decision
            
            if attempt < MAX_REVISIONS:
                print(f"🔄 Sending feedback to writer for revision...")
            else:
                print(f"⚠️ Max revisions reached. Using last version.")
    
    slug = ""
    meta = ""
    keywords = ""
    
    for line in final_seo_output.split('\n'):
        if line.startswith("SLUG:"):
            slug = line.replace("SLUG:", "").strip()
        elif line.startswith("META:"):
            meta = line.replace("META:", "").strip()
        elif line.startswith("KEYWORDS:"):
            keywords = line.replace("KEYWORDS:", "").strip()
    
    is_approved = "DECISION: APPROVED" in final_ceo_decision.upper()
    
    print(f"\n📊 Final CEO Decision: {'✅ APPROVED' if is_approved else '❌ REJECTED'}")
    print(f"📝 Title: {title}")
    print(f"🔗 Slug: {slug}")
    print(f"📄 Meta: {meta}")
    print(f"🔑 Keywords: {keywords}")
    
    if is_approved and title and final_blog_content:
        image_url = generate_blog_image(title, keywords)
        
        page_id = create_notion_page_with_body(
            title, 
            final_blog_content[:500],
            slug, 
            meta, 
            keywords,
            final_blog_content,
            image_url
        )
        
        if page_id:
            auto_publish_blog(page_id)
            return {
                "title": title, 
                "page_id": page_id, 
                "status": "published",
                "content": final_blog_content,
                "keywords": keywords,
                "image_url": image_url
            }
    
    return {"title": title, "status": "rejected", "feedback": final_ceo_decision}

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
        
        # ===== ACTUAL POSTING TO FACEBOOK & INSTAGRAM =====
        # Generate image for the post
        image_url = generate_blog_image(blog['title'], blog['keywords'])
        
        # Create platform-specific captions
        ig_caption = create_instagram_caption(blog['title'], blog['content'], blog['keywords'])
        fb_caption = create_facebook_caption(blog['title'], blog['content'], blog['keywords'])
        
        # Post to Instagram
        print("\n" + "="*40)
        print("📸 INSTAGRAM POST")
        print("="*40)
        ig_result = post_to_instagram(image_url, ig_caption)
        
        # Post to Facebook
        print("\n" + "="*40)
        print("📘 FACEBOOK POST")
        print("="*40)
        fb_result = post_to_facebook(image_url, fb_caption)
        
        # Log results to Notion
        log_data = f"""
📱 SOCIAL MEDIA POST RESULTS
============================
Blog: {blog['title']}

📸 Instagram:
- Status: {'✅ Posted' if ig_result else '❌ Failed'}
- Media ID: {ig_result if ig_result else 'N/A'}
- Caption preview: {ig_caption[:200]}...

📘 Facebook:
- Status: {'✅ Posted' if fb_result else '❌ Failed'}
- Post ID: {fb_result if fb_result else 'N/A'}
- Caption preview: {fb_caption[:200]}...

🤖 Agent Strategy:
{str(result)[:1000]}
"""
        log_to_notion(blog['title'], log_data)
        update_social_status(blog['id'], "Posted")
        
        print(f"\n✅ Completed promotion for: {blog['title']}")

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

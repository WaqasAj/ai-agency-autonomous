import os
import requests
import re
import time
from crewai import Agent, Task, Crew, Process
from datetime import datetime, timedelta
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
STRATEGY_DB_ID = os.getenv("STRATEGY_DB_ID")
MEMORY_DB_ID = os.getenv("MEMORY_DB_ID")
PAGE_NAME = os.getenv("PAGE_NAME", "Kahani AI")

os.environ["MISTRAL_API_KEY"] = MISTRAL_KEY

# ============ BRAND CONTEXT ============
BRAND_CONTEXT = f"""
{PAGE_NAME} is a platform creating valuable, engaging content for its target audience. 
Brand voice: Warm, trustworthy, authoritative, and genuinely helpful.
Content themes: Practical advice, real-world examples, actionable insights, and family-friendly topics.
"""

# ============ HUMANIZATION GUIDELINES ============
HUMANIZATION_RULES = """
CRITICAL: Write like a real human expert, NOT like an AI. Follow these rules STRICTLY:

AVOID THESE AI PATTERNS (they will be rejected):
- Never start paragraphs with "In today's world", "In the digital age", "It's important to note"
- Never use "delve", "tapestry", "landscape", "realm", "journey", "foster", "cultivate"
- Never write perfectly balanced, symmetrical paragraphs
- Never use generic filler like "Let's explore", "Let's dive in"
- Never use excessive transition words like "Furthermore", "Moreover", "Additionally"

DO THESE INSTEAD (human signals):
- Vary sentence length wildly — mix 5-word sentences with 25-word ones
- Start sentences with "And", "But", "Because", "So" — like real people talk
- Include specific numbers and details: "my 4-year-old", "3 AM wake-ups", "15 minutes"
- Use contractions: "don't", "it's", "you'll", "we've"
- Add personal-sounding moments: "I remember when...", "Last week, I noticed..."
- Ask rhetorical questions: "Sound familiar?", "You know that feeling, right?"
- Use conversational asides: "(Yes, even on the tough nights)", "(trust me on this one)"
- Write like you're texting a knowledgeable friend who gets it
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

# ============ STRATEGY & MEMORY DATABASE FUNCTIONS ============
def fetch_active_strategy():
    if not STRATEGY_DB_ID:
        return None
    
    url = f"https://api.notion.com/v1/databases/{STRATEGY_DB_ID}/query"
    payload = {"filter": {"property": "Status", "select": {"equals": "Active"}}}
    response = requests.post(url, headers=notion_headers(), json=payload)
    
    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            strategy = results[0]["properties"]
            return {
                "goal": strategy.get("Goal", {}).get("title", [{}])[0].get("text", {}).get("content", ""),
                "target_audience": strategy.get("Target Audience", {}).get("rich_text", [{}])[0].get("text", {}).get("content", ""),
                "current_priority": strategy.get("Current Priority", {}).get("select", {}).get("name", ""),
                "brand_rules": strategy.get("Brand Rules", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
            }
    return None

def fetch_relevant_memories(memory_type=None, outcome=None, limit=10):
    if not MEMORY_DB_ID:
        return []
    
    url = f"https://api.notion.com/v1/databases/{MEMORY_DB_ID}/query"
    filters = []
    if memory_type:
        filters.append({"property": "Type", "select": {"equals": memory_type}})
    if outcome:
        filters.append({"property": "Outcome", "select": {"equals": outcome}})
    
    payload = {
        "filter": {"and": filters} if filters else {},
        "sorts": [{"property": "Confidence", "direction": "descending"}],
        "page_size": limit
    }
    
    response = requests.post(url, headers=notion_headers(), json=payload)
    memories = []
    if response.status_code == 200:
        results = response.json().get("results", [])
        for result in results:
            props = result["properties"]
            memories.append({
                "summary": props.get("Summary", {}).get("title", [{}])[0].get("text", {}).get("content", ""),
                "type": props.get("Type", {}).get("select", {}).get("name", ""),
                "content": props.get("Content", {}).get("rich_text", [{}])[0].get("text", {}).get("content", ""),
                "outcome": props.get("Outcome", {}).get("select", {}).get("name", ""),
                "reason": props.get("Reason", {}).get("rich_text", [{}])[0].get("text", {}).get("content", ""),
            })
    return memories

def save_to_memory(summary, memory_type, content, outcome, reason, confidence=5):
    if not MEMORY_DB_ID:
        return None
    
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": MEMORY_DB_ID},
        "properties": {
            "Summary": {"title": [{"text": {"content": summary[:100]}}]},
            "Type": {"select": {"name": memory_type}},
            "Content": {"rich_text": [{"text": {"content": content[:2000]}}]},
            "Outcome": {"select": {"name": outcome}},
            "Reason": {"rich_text": [{"text": {"content": reason[:500]}}]},
            "Confidence": {"number": confidence},
            "Date": {"date": {"start": datetime.now().isoformat()}},
            "App Name": {"select": {"name": PAGE_NAME}}
        }
    }
    
    response = requests.post(url, headers=notion_headers(), json=payload)
    if response.status_code == 200:
        print(f"✅ Saved to memory: {summary}")
        return response.json()["id"]
    return None

# ============ AGENT-DRIVEN IMAGE GENERATION ============
def generate_blog_image_with_agent(title, blog_content, keywords, page_name=PAGE_NAME):
    """Use an AI agent to analyze the blog content and generate a contextual image prompt."""
    print("\n🎨 Analyzing blog content for image generation...")
    
    content_preview = blog_content[:2000]
    
    image_task = Task(
        description=f"""Analyze this blog post and create a detailed image generation prompt for a professional, realistic photograph.

BLOG TITLE: {title}
KEYWORDS: {keywords}
CONTENT PREVIEW: {content_preview}

YOUR TASK:
1. Read the content and identify the CORE THEME and EMOTION
2. Determine what VISUAL SCENE would best represent this topic
3. Create a detailed prompt for a REALISTIC photograph (NOT cartoon, NOT illustration)

PROMPT STRUCTURE:
- Subject: Who/what is the main focus? (be specific)
- Setting: Where is this happening? (be detailed)
- Action: What's happening? (be dynamic)
- Style: Professional photography (camera model, lens, lighting)
- Mood: What feeling? (be emotional)
- Technical: Quality specs (resolution, focus, colors)

OUTPUT FORMAT (exact):
IMAGE_PROMPT: [your detailed prompt here]

CRITICAL: Must be REALISTIC PHOTOGRAPHY, directly relevant to content, high quality.""",
        expected_output="A detailed, contextual image generation prompt for realistic photography",
        agent=image_prompt_creator
    )
    
    image_crew = Crew(
        agents=[image_prompt_creator],
        tasks=[image_task],
        process=Process.sequential,
        verbose=True
    )
    
    image_crew.kickoff()
    image_output = image_task.output.raw.strip() if image_task.output else ""
    
    image_prompt = ""
    for line in image_output.split('\n'):
        if line.startswith("IMAGE_PROMPT:"):
            image_prompt = line.replace("IMAGE_PROMPT:", "").strip()
            break
    
    if not image_prompt:
        image_prompt = image_output
    
    print(f"✅ Agent generated contextual image prompt")
    
       # Shorten the prompt to fit URL limits
    short_prompt = image_prompt[:500]  # Limit prompt length
    seed = hash(title + page_name) % 10000
    
    # Use a simpler URL structure
    image_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(short_prompt)}?width=1200&height=675&model=flux&nologo=true&seed={seed}"
    
    # If still too long, use a fallback generic prompt
    if len(image_url) > 1900:
        fallback_prompt = f"professional photography, {title}, realistic, high quality"
        image_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(fallback_prompt)}?width=1200&height=675&model=flux&nologo=true&seed={seed}"

# ============ NOTION PAGE CREATION (WITH MULTI-SITE TAG) ============
def create_notion_page_with_body(title, content, slug, meta_description, keywords, full_blog_content, image_url, page_name=PAGE_NAME):
    """Create a Notion page with properties and body, tagged with the specific Page name."""
    url = "https://api.notion.com/v1/pages"
    
    clean_t = clean_title(title)
    clean_content = clean_blog_content(full_blog_content, clean_t)
    excerpt = clean_content[:500] if clean_content else ""
    current_datetime = datetime.now().isoformat()
    
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Title": {"title": [{"text": {"content": clean_t}}]},
            "Slug": {"rich_text": [{"text": {"content": slug}}]},
            "Meta Description": {"rich_text": [{"text": {"content": meta_description}}]},
            "Keywords": {"rich_text": [{"text": {"content": keywords}}]},
            "Content": {"rich_text": [{"text": {"content": excerpt}}]},
            "Published": {"checkbox": True},
            "Created": {"date": {"start": current_datetime}},
            "Blog Source": {"select": {"name": "AI Generated"}},
            "Page": {"select": {"name": page_name}}
        },
        "children": [
            {"object": "block", "type": "image", "image": {"type": "external", "external": {"url": image_url}}},
            *convert_text_to_notion_blocks(clean_content)
        ]
    }
    
    print(f"\n📝 Creating Notion page for {page_name}...")
    response = requests.post(url, headers=notion_headers(), json=payload)
    
    if response.status_code == 200:
        page_id = response.json()["id"]
        print(f"✅ Created Notion page: {clean_t} (Page: {page_name})")
        return page_id
    else:
        print(f"❌ Failed to create page: {response.status_code} - {response.text}")
        return None

def convert_text_to_notion_blocks(text):
    blocks = []
    paragraphs = text.split('\n\n')
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if para.startswith('### '):
            blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": para.replace('### ', '')}}]}})
        elif para.startswith('## '):
            blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": para.replace('## ', '')}}]}})
        elif para.startswith('# '):
            blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": para.replace('# ', '')}}]}})
        elif para.startswith('- ') or para.startswith('* '):
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": para[2:]}}]}})
        elif re.match(r'^\d+\. ', para):
            blocks.append({"object": "block", "type": "numbered_list_item", "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": re.sub(r'^\d+\. ', '', para)}}]}})
        else:
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": para}}]}})
    return blocks

def fetch_unprocessed_published_blogs():
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Published", "checkbox": {"equals": True}},
                {"property": "Page", "select": {"equals": PAGE_NAME}},
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

def update_social_status(page_id, status):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"Status": {"status": {"name": status}}}}
    response = requests.patch(url, headers=notion_headers(), json=payload)
    if response.status_code == 200:
        print(f"✅ Updated Status to: {status}")

def fetch_recent_blog_titles(days=30, limit=20):
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Published", "checkbox": {"equals": True}},
                {"property": "Page", "select": {"equals": PAGE_NAME}}
            ]
        },
        "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        "page_size": limit
    }
    response = requests.post(url, headers=notion_headers(), json=payload)
    titles = []
    if response.status_code == 200:
        results = response.json().get("results", [])
        for result in results:
            title_props = result["properties"].get("Title", {}).get("title", [])
            if title_props:
                title = title_props[0].get("text", {}).get("content", "")
                if title:
                    titles.append(title)
    return titles

def log_to_notion(blog_title, agent_output):
    url = "https://api.notion.com/v1/pages"
    truncated = str(agent_output)[:2000]
    clean_t = clean_title(blog_title)
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Title": {"title": [{"text": {"content": f"📋 Log: {clean_t}"}}]},
            "Content": {"rich_text": [{"text": {"content": truncated}}]},
            "Published": {"checkbox": False},
            "Page": {"select": {"name": PAGE_NAME}}
        }
    }
    response = requests.post(url, headers=notion_headers(), json=payload)
    if response.status_code == 200:
        print(f"✅ Logged results to Notion for: {clean_t}")

# ============ FACEBOOK & INSTAGRAM POSTING ============
def create_instagram_caption(title, content, keywords):
    clean_t = clean_title(title)
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()][:3]
    intro = ' '.join(paragraphs)[:800]
    keyword_list = [k.strip().replace(' ', '') for k in keywords.split(',')[:8]]
    hashtags = ' '.join([f'#{k}' for k in keyword_list])
    
    caption = f"✨ {clean_t}\n\n{intro}\n\n💭 What's your experience with this? Drop a comment below! 👇\n\n📖 Read the full story on our blog (link in bio)\n\n{hashtags}\n\n#{PAGE_NAME.replace(' ', '')}"
    return caption[:2200]

def create_facebook_caption(title, content, keywords):
    clean_t = clean_title(title)
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()][:5]
    intro = '\n\n'.join(paragraphs)[:1500]
    
    caption = f"📚 {clean_t}\n\n{intro}\n\n---\n💬 We'd love to hear from you! What's your experience with this topic? Share in the comments!\n\n👉 Read the full article on our blog.\n\n#{PAGE_NAME.replace(' ', '')}"
    return caption

def post_to_instagram(image_url, caption):
    if not IG_ACCOUNT_ID or not FB_ACCESS_TOKEN:
        print("❌ Instagram credentials missing. Skipping.")
        return None
    
    print(f"\n📸 Posting to Instagram...")
    container_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media"
    container_payload = {"image_url": image_url, "caption": caption, "access_token": FB_ACCESS_TOKEN}
    
    response = requests.post(container_url, data=container_payload)
    if response.status_code != 200:
        print(f"❌ Failed to create Instagram container: {response.text}")
        return None
    
    container_id = response.json().get("id")
    time.sleep(5)
    
    publish_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media_publish"
    publish_payload = {"creation_id": container_id, "access_token": FB_ACCESS_TOKEN}
    
    response = requests.post(publish_url, data=publish_payload)
    if response.status_code == 200:
        print(f"✅ Posted to Instagram! Media ID: {response.json().get('id')}")
        return response.json().get("id")
    return None

def post_to_facebook(image_url, caption):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        print("❌ Facebook credentials missing. Skipping.")
        return None
    
    print(f"\n📘 Posting to Facebook...")
    post_url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
    post_payload = {"message": caption, "url": image_url, "access_token": FB_ACCESS_TOKEN}
    
    response = requests.post(post_url, data=post_payload)
    if response.status_code == 200:
        print(f"✅ Posted to Facebook! Photo ID: {response.json().get('id')}")
        return response.json().get("id")
    return None

# ============ DEFINE THE AUTONOMOUS AGENTS ============
FREE_MODEL = "mistral/mistral-small-latest"

trend_researcher = Agent(
    role="Senior Content Strategist & Trend Analyst",
    goal="Identify UNIQUE, HIGH-VALUE blog topics that solve real problems and have low competition",
    backstory=f"""You are a veteran content strategist. You DON'T just find trending topics - you find CONTENT GAPS.
    {BRAND_CONTEXT}
    You output topics that are specific, timely, valuable, and defensible. Avoid generic topics.""",
    llm=FREE_MODEL,
    verbose=True
)

blog_writer = Agent(
    role="Expert Blog Writer & Storyteller",
    goal="Write blog posts that feel like they were written by a trusted friend who happens to be an expert",
    backstory=f"""You are a master storyteller. Your writing feels like a conversation with a knowledgeable friend.
    {BRAND_CONTEXT}
    {HUMANIZATION_RULES}
    Structure: Hook, Problem/Context, Solution/Insight, Examples, Common Mistakes, Step-by-Step Guide, FAQ, Conclusion.
    Aim for 1,500-2,000 words. Write for HUMANS first, search engines second.""",
    llm=FREE_MODEL,
    verbose=True
)

seo_geo_optimizer = Agent(
    role="SEO & GEO Specialist",
    goal="Optimize content to rank #1 on Google AND appear in AI-generated answers",
    backstory="""You are an SEO expert adapted to the AI search era. You optimize for both human readers and machine understanding.
    Output EXACT format:
    SLUG: [url-friendly-slug]
    META: [compelling meta description with keyword and CTA, under 155 chars]
    KEYWORDS: [primary keyword, variation 1, variation 2, ...]
    GEO_SNIPPETS: [Direct answer 1] | [Direct answer 2]""",
    llm=FREE_MODEL,
    verbose=True
)

ceo_reviewer = Agent(
    role="Chief Content Officer & Quality Gatekeeper",
    goal="Ensure every piece of content meets the highest standards of quality, originality, and brand alignment",
    backstory=f"""You are the final quality gate. You are OBSESSED with human-sounding content and can spot AI writing from a mile away.
    {BRAND_CONTEXT}
    
    REVIEW CRITERIA:
    1. HUMANIZATION (40%): Real person voice, no AI clichés, specific examples.
    2. ORIGINALITY (30%): Fresh angle, actionable advice.
    3. BRAND ALIGNMENT (15%): Matches voice and values.
    4. SEO/GEO (10%): Optimized structure.
    5. TECHNICAL (5%): Grammar, formatting.
    
    DUPLICATE CONTENT CHECK: Compare against recent posts. If topic overlaps >60%, REJECT immediately.
    
    Output EXACT format:
    DECISION: APPROVED or REJECTED
    SCORE: X/10
    REASONS: [bullet list]
    FIXES_NEEDED: [bullet list - only if REJECTED]""",
    llm=FREE_MODEL,
    verbose=True
)

image_prompt_creator = Agent(
    role="Visual Content Director & Image Prompt Engineer",
    goal="Analyze blog content and create detailed, contextual image prompts for professional, realistic photographs",
    backstory="""You are a visual storytelling expert who understands what makes images perform well on blogs and social media.
    
YOUR EXPERTISE:
- You can read a blog post and instantly identify the CORE EMOTION and KEY SCENE
- You know that REALISTIC PHOTOGRAPHY gets 73% more engagement than illustrations
- You understand composition, lighting, color theory, and visual hierarchy
- You create prompts that generate authentic, diverse, emotionally resonant images

YOUR PROCESS:
1. Read the blog content thoroughly
2. Identify the main theme, emotion, and key message
3. Determine what VISUAL SCENE would best represent this content
4. Create a detailed prompt following this structure:
   - Subject: Who/what is the focus? (be specific and human)
   - Setting: Where is this? (be detailed and atmospheric)
   - Action: What's happening? (be dynamic and storytelling)
   - Style: Professional photography (camera model, lens, lighting)
   - Mood: What emotion? (warm, joyful, intimate, inspiring)
   - Technical: Quality specs (resolution, focus, colors)
   - Diversity: Authentic, inclusive representation

CRITICAL RULES:
- ALWAYS specify REALISTIC PHOTOGRAPHY (never cartoon, illustration, or anime)
- ALWAYS include specific camera/lens details for authenticity
- ALWAYS emphasize natural lighting and authentic emotions
- ALWAYS ensure the image directly relates to the blog content
- ALWAYS include diverse, realistic human subjects when appropriate

You create images that stop the scroll and build emotional connection.""",
    llm=FREE_MODEL,
    verbose=True
)

social_strategist = Agent(
    role="Social Media Strategist",
    goal="Decide which platforms to use and what angle for each",
    backstory="You are a social media strategist who has grown brands to millions of followers. You pick the best platforms and angles.",
    llm=FREE_MODEL,
    verbose=True
)

content_creator = Agent(
    role="Viral Social Content Creator",
    goal="Create scroll-stopping social media posts for each platform",
    backstory="You create viral content. You write posts that make people stop scrolling, feel emotional, and want to engage.",
    llm=FREE_MODEL,
    verbose=True
)

poster = Agent(
    role="Social Media Manager",
    goal="Format the final approved content for publishing across platforms",
    backstory="You are the final step. You take approved content and format it perfectly for each social platform.",
    llm=FREE_MODEL,
    verbose=True
)

# ============ PHASE 1: BLOG CREATION WITH FEEDBACK LOOP ============
def run_blog_creation_phase():
    print("\n" + "="*60)
    print(f"PHASE 1: BLOG CREATION for {PAGE_NAME}")
    print("="*60)
    
    strategy = fetch_active_strategy()
    failure_memories = fetch_relevant_memories(outcome="Failure", limit=5)
    success_memories = fetch_relevant_memories(outcome="Success", limit=5)
    
    MAX_REVISIONS = 2
    ceo_feedback = None
    final_blog_content = None
    final_seo_output = None
    final_ceo_decision = None
    final_title = None
    
    for attempt in range(1, MAX_REVISIONS + 1):
        print(f"\n{'='*40}")
        print(f"ATTEMPT {attempt}/{MAX_REVISIONS}")
        print(f"{'='*40}")
        
        print(f"\n[Step 1] Researching fresh topic...")
        if ceo_feedback:
            research_description = (
                "Research ONE trending blog topic.\n\n"
                "CRITICAL: The previous topic was REJECTED. You MUST pick a COMPLETELY DIFFERENT topic. "
                "Do NOT revisit the same subject. Output ONLY the blog topic/title as plain text."
            )
        else:
            research_description = (
                "Research ONE trending, high-value blog topic perfect for our audience. "
                "Output ONLY the blog topic/title as plain text, no quotes, no markdown."
            )
        
        research_task = Task(description=research_description, expected_output="A single compelling blog topic/title", agent=trend_researcher)
        research_crew = Crew(agents=[trend_researcher], tasks=[research_task], process=Process.sequential, verbose=True)
        research_crew.kickoff()
        
        title = clean_title(research_task.output.raw.strip()) if research_task.output else "Untitled"
        final_title = title
        print(f"\nTopic selected: {title}")
        
        recent_titles = fetch_recent_blog_titles(days=30, limit=15)
        recent_titles_text = "\n".join([f"- {t}" for t in recent_titles]) if recent_titles else "No recent posts"
        
        memory_context = ""
        if failure_memories:
            memory_context += "\n\nAVOID THESE PAST FAILURES:\n" + "\n".join([f"- {mem['summary']}: {mem['reason']}" for mem in failure_memories[:3]])
        if success_memories:
            memory_context += "\n\nFOLLOW THESE PAST SUCCESSES:\n" + "\n".join([f"- {mem['summary']}" for mem in success_memories[:3]])
        
        print(f"\n[Step 2] Writing blog post...")
        write_description = (
            f"Write a complete, engaging blog post (1500-2000 words) on this topic: {title}\n\n"
            f"{HUMANIZATION_RULES}\n{memory_context}\n\n"
            "Structure: Hook, Problem, Solution, Examples, Common Mistakes, Step-by-Step, FAQ, Conclusion. "
            "Use ## for section headings. Do NOT repeat the title at the top."
        )
        write_task = Task(description=write_description, expected_output="A complete, human-sounding blog post", agent=blog_writer)
        
        print(f"\n[Step 3] Optimizing SEO/GEO...")
        seo_geo_task = Task(
            description="Create SEO and GEO elements: SLUG, META, KEYWORDS, GEO_SNIPPETS",
            expected_output="Slug, meta, keywords, and GEO snippets in specified format",
            agent=seo_geo_optimizer
        )
        
        print(f"\n[Step 4] CEO reviewing...")
        strategy_context = f"\nFOUNDER'S STRATEGY:\n- Goal: {strategy['goal']}\n- Audience: {strategy['target_audience']}\n" if strategy else ""
        
        review_description = (
            "Review the blog post rigorously.\n"
            "DUPLICATE CONTENT CHECK: Compare against recent posts:\n"
            f"{recent_titles_text}\n\n"
            "If the topic is TOO SIMILAR, REJECT it with: 'DECISION: REJECTED - DUPLICATE CONTENT: This topic overlaps with [title]. Choose a different angle.'\n\n"
            f"{strategy_context}"
            "Output in EXACT format: DECISION, SCORE, REASONS, FIXES_NEEDED"
        )
        review_task = Task(description=review_description, expected_output="DECISION, SCORE, REASONS, FIXES_NEEDED", agent=ceo_reviewer)
        
        crew = Crew(agents=[blog_writer, seo_geo_optimizer, ceo_reviewer], tasks=[write_task, seo_geo_task, review_task], process=Process.sequential, verbose=True)
        crew.kickoff()
        
        blog_content = write_task.output.raw.strip() if write_task.output else ""
        seo_output = seo_geo_task.output.raw.strip() if seo_geo_task.output else ""
        ceo_decision = review_task.output.raw.strip() if review_task.output else ""
        
        print(f"\nCEO Response (Attempt {attempt}):\n{ceo_decision[:500]}")
        
        is_approved = "DECISION: APPROVED" in ceo_decision.upper()
        
        if is_approved:
            print(f"\nCEO APPROVED on attempt {attempt}!")
            final_blog_content = blog_content
            final_seo_output = seo_output
            final_ceo_decision = ceo_decision
            save_to_memory(summary=f"Approved: {title}", memory_type="Pattern", content=f"Approved on attempt {attempt}", outcome="Success", reason="Met standards", confidence=7)
            break
        else:
            print(f"\nCEO REJECTED on attempt {attempt}.")
            ceo_feedback = ceo_decision
            final_blog_content = blog_content
            final_seo_output = seo_output
            final_ceo_decision = ceo_decision
            save_to_memory(summary=f"Rejected: {title[:50]}", memory_type="Feedback", content=ceo_decision[:500], outcome="Failure", reason="Did not meet standards", confidence=6)
            if attempt < MAX_REVISIONS:
                print(f"Will research a NEW topic for next attempt...")
    
    slug, meta, keywords = "", "", ""
    if final_seo_output:
        for line in final_seo_output.split('\n'):
            if line.startswith("SLUG:"): slug = line.replace("SLUG:", "").strip()
            elif line.startswith("META:"): meta = line.replace("META:", "").strip()
            elif line.startswith("KEYWORDS:"): keywords = line.replace("KEYWORDS:", "").strip()
    
    is_approved = "DECISION: APPROVED" in final_ceo_decision.upper() if final_ceo_decision else False
    
    print(f"\nFinal CEO Decision: {'APPROVED' if is_approved else 'REJECTED'}")
    print(f"Final Title: {final_title}")
    
    if is_approved and final_title and final_blog_content:
        image_url = generate_blog_image_with_agent(final_title, final_blog_content, keywords, PAGE_NAME)
        page_id = create_notion_page_with_body(final_title, final_blog_content[:500], slug, meta, keywords, final_blog_content, image_url, PAGE_NAME)
        
        if page_id:
            print(f"✅ Blog saved to Notion for {PAGE_NAME}")
            return {"title": final_title, "page_id": page_id, "status": "published", "content": final_blog_content, "keywords": keywords, "image_url": image_url}
    
    return {"title": final_title, "status": "rejected", "feedback": final_ceo_decision}

# ============ PHASE 2: SOCIAL MEDIA PROMOTION ============
def run_social_promotion_phase():
    print("\n" + "="*60)
    print(f"📱 PHASE 2: SOCIAL MEDIA PROMOTION for {PAGE_NAME}")
    print("="*60)
    
    blogs = fetch_unprocessed_published_blogs()
    if not blogs:
        print("✅ No new blogs to promote today.")
        return
    
    print(f"📝 Found {len(blogs)} blog(s) to promote")
    
    for blog in blogs:
        print(f"\n🔄 Promoting: {blog['title']}")
        update_social_status(blog['id'], "Processing")
        
        ig_caption = create_instagram_caption(blog['title'], blog['content'], blog['keywords'])
        fb_caption = create_facebook_caption(blog['title'], blog['content'], blog['keywords'])
        image_url = generate_blog_image_with_agent(blog['title'], blog['content'], blog['keywords'], PAGE_NAME)
        
        ig_result = post_to_instagram(image_url, ig_caption)
        fb_result = post_to_facebook(image_url, fb_caption)
        
        log_data = f"Instagram: {'✅ Posted' if ig_result else '❌ Failed'}\nFacebook: {'✅ Posted' if fb_result else '❌ Failed'}"
        log_to_notion(blog['title'], log_data)
        update_social_status(blog['id'], "Posted")
        print(f"\n✅ Completed promotion for: {blog['title']}")

# ============ MAIN EXECUTION ============
def run_daily_agency():
    print(f"🚀 Starting Autonomous Agency for {PAGE_NAME} at {datetime.now()}")
    print(BRAND_CONTEXT)
    
    try:
        run_blog_creation_phase()
    except Exception as e:
        print(f"⚠️ Blog creation phase error: {e}")
    
    try:
        run_social_promotion_phase()
    except Exception as e:
        print(f"⚠️ Social promotion phase error: {e}")
    
    print("\n🎉 Daily agency run complete!")

if __name__ == "__main__":
    run_daily_agency()

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
PAGE_NICHE = os.getenv("PAGE_NICHE", "general")
PAGE_DESCRIPTION = os.getenv("PAGE_DESCRIPTION", "")

os.environ["MISTRAL_API_KEY"] = MISTRAL_KEY

# ============ DEEP PRODUCT CONTEXT ============
# Each page gets detailed knowledge about what the product actually does

PRODUCT_CONTEXT = {
    "Kahani AI": """
Kahani AI is a web application that generates personalized bedtime stories and kids' stories using AI.

CORE FEATURES:
- Creates custom stories with the child's name, favorite characters, and chosen themes
- Supports 4 languages: English, Urdu, Arabic, Hindi
- Generates beautiful illustrations for each story
- Offers audio narration, PDF download, and shareable links
- Target users: Parents of children ages 2-10, educators, grandparents

WHAT MAKES IT UNIQUE:
- Personalization: Each story is tailored to the specific child
- Multilingual: Supports South Asian and Middle Eastern languages
- Visual: AI-generated illustrations make stories come alive
- Accessible: Works on any device, no app download needed

CONTENT SHOULD EXPLORE:
- The science and psychology behind bedtime storytelling
- How personalized stories boost child development and imagination
- Multilingual parenting challenges and solutions
- Screen-free bedtime routines that actually work
- Cultural stories and traditions from South Asian/Middle Eastern cultures
- Islamic stories and values for Muslim families
- Child psychology and the science behind storytelling
- How AI tools like Kahani AI are changing family storytelling
- Practical parenting tips related to reading, sleep, and creativity
- The magic of making children the hero of their own stories

CONTENT ANGLES TO AVOID:
- Generic parenting advice unrelated to stories/reading/creativity
- Product reviews or tech comparisons
- Overly promotional content (mention Kahani AI naturally, not forced)
""",
    "Geo Analyzer": """
Geo Analyzer is a web tool that scans URLs and text content to check if they are optimized for both traditional SEO and Generative Engine Optimization (GEO).

CORE FEATURES:
- Scans any URL or pasted text for SEO and GEO optimization
- Checks if content is structured for AI search engines (ChatGPT, Perplexity, Gemini)
- Provides actionable recommendations to improve search visibility
- Supports MCP (Model Context Protocol) integration
- Analyzes heading structure, FAQ sections, schema markup, and direct answer snippets

WHAT MAKES IT UNIQUE:
- Dual optimization: Traditional SEO + AI search engine optimization
- MCP integration: Prepares content for the future of AI-powered search
- Actionable insights: Not just problems, but specific fixes
- Works on any URL or pasted text

CONTENT SHOULD EXPLORE:
- How AI search engines (ChatGPT, Perplexity, Gemini) are changing SEO
- GEO (Generative Engine Optimization) techniques and best practices
- How to structure content so AI engines quote and cite it
- Schema markup, FAQ optimization, and featured snippets
- The future of search: from keywords to conversational AI
- MCP integration and what it means for content creators
- Practical SEO audits and before/after case studies
- How to write content that ranks in both Google AND AI answers
- Technical SEO for the AI era
- Content structure that both humans and AI engines love

CONTENT ANGLES TO AVOID:
- Generic marketing advice
- Basic SEO tips that everyone already knows (unless with a fresh angle)
- Overly technical jargon without explanation
"""
}

# Get product context for current page
product_info = PRODUCT_CONTEXT.get(PAGE_NAME, f"""
{PAGE_NAME} is a platform focused on {PAGE_NICHE}.
{PAGE_DESCRIPTION if PAGE_DESCRIPTION else 'Creating valuable content in this niche.'}
All content should naturally relate to {PAGE_NAME}'s purpose and audience.
""")

BRAND_CONTEXT = f"""
{product_info}

Brand voice: Warm, trustworthy, authoritative, and genuinely helpful.
Write for HUMANS first, search engines second.
"""

# ============ HUMANIZATION GUIDELINES ============
HUMANIZATION_RULES = """
CRITICAL: Write like a real human expert, NOT like an AI.

AVOID THESE AI PATTERNS:
- Never start with "In today's world", "In the digital age", "It's important to note"
- Never use "delve", "tapestry", "landscape", "realm", "journey", "foster", "cultivate"
- Never use generic filler like "Let's explore", "Let's dive in"
- Never use excessive transitions like "Furthermore", "Moreover", "Additionally"

DO THESE INSTEAD:
- Vary sentence length wildly
- Start sentences with "And", "But", "Because", "So"
- Include specific numbers and details
- Use contractions: "don't", "it's", "you'll"
- Add personal-sounding moments: "I remember when...", "Last week..."
- Ask rhetorical questions: "Sound familiar?"
- Use conversational asides: "(trust me on this one)"
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
    payload = {
        "filter": {
            "and": [
                {"property": "Status", "select": {"equals": "Active"}},
                {"property": "Page", "select": {"equals": PAGE_NAME}}
            ]
        }
    }
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

# ============ FETCH RECENT TOPICS (CRITICAL FOR AVOIDING DUPLICATES) ============
def fetch_recent_blog_titles(days=30, limit=20):
    """Fetch recent titles so agents know what's been covered."""
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    thirty_days_ago = (datetime.now() - timedelta(days=days)).isoformat()
    payload = {
        "filter": {
            "and": [
                {"property": "Published", "checkbox": {"equals": True}},
                {"property": "Page", "select": {"equals": PAGE_NAME}},
                {"property": "Created", "date": {"on_or_after": thirty_days_ago}}
            ]
        },
        "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        "page_size": limit
    }
    response = requests.post(url, headers=notion_headers(), json=payload)
    titles = []
    if response.status_code == 200:
        for result in response.json().get("results", []):
            title_props = result["properties"].get("Title", {}).get("title", [])
            if title_props:
                title = title_props[0].get("text", {}).get("content", "")
                if title:
                    titles.append(title)
    return titles

# ============ AGENT-DRIVEN IMAGE GENERATION ============
def generate_blog_image_with_agent(title, blog_content, keywords, page_name=PAGE_NAME):
    print("\n🎨 Analyzing blog content for image generation...")
    try:
        content_preview = blog_content[:1500]
        image_task = Task(
            description=f"""Create a SHORT image prompt (max 200 chars) for a realistic photograph representing this blog.
TITLE: {title}
KEYWORDS: {keywords}
PREVIEW: {content_preview[:400]}
OUTPUT: IMAGE_PROMPT: [prompt under 200 chars, realistic photography only]""",
            expected_output="IMAGE_PROMPT: [short prompt]",
            agent=image_prompt_creator
        )
        image_crew = Crew(agents=[image_prompt_creator], tasks=[image_task], process=Process.sequential, verbose=False)
        image_crew.kickoff()
        image_output = image_task.output.raw.strip() if image_task.output else ""
        image_prompt = ""
        for line in image_output.split('\n'):
            if "IMAGE_PROMPT:" in line:
                image_prompt = line.split("IMAGE_PROMPT:")[-1].strip()
                break
        if not image_prompt or len(image_prompt) < 10:
            image_prompt = f"professional photography, {title[:40]}, realistic, high quality"
        image_prompt = image_prompt[:200]
        seed = hash(title + page_name) % 10000
        encoded_prompt = requests.utils.quote(image_prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=675&model=flux&nologo=true&seed={seed}"
        if len(image_url) > 1900:
            image_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(title[:30])}?width=1200&height=675&model=flux&nologo=true&seed={seed}"
        return image_url
    except Exception as e:
        print(f"❌ Image generation error: {e}")
        seed = hash(title + page_name) % 10000
        return f"https://image.pollinations.ai/prompt/professional%20photography?width=1200&height=675&model=flux&nologo=true&seed={seed}"

# ============ NOTION PAGE CREATION ============
def create_notion_page_with_body(title, content, slug, meta_description, keywords, full_blog_content, image_url, page_name=PAGE_NAME):
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
        print(f"✅ Created Notion page: {clean_t}")
        return page_id
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")
        return None

def convert_text_to_notion_blocks(text):
    blocks = []
    for para in text.split('\n\n'):
        para = para.strip()
        if not para: continue
        if para.startswith('### '):
            blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": para[4:]}}]}})
        elif para.startswith('## '):
            blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": para[3:]}}]}})
        elif para.startswith('# '):
            blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": para[2:]}}]}})
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
        if "Content" in result["properties"] and result["properties"]["Content"]["type"] == "rich_text" and result["properties"]["Content"]["rich_text"]:
            content = result["properties"]["Content"]["rich_text"][0]["text"]["content"]
        meta = ""
        if "Meta Description" in result["properties"] and result["properties"]["Meta Description"]["type"] == "rich_text" and result["properties"]["Meta Description"]["rich_text"]:
            meta = result["properties"]["Meta Description"]["rich_text"][0]["text"]["content"]
        keywords = ""
        if "Keywords" in result["properties"] and result["properties"]["Keywords"]["type"] == "rich_text" and result["properties"]["Keywords"]["rich_text"]:
            keywords = result["properties"]["Keywords"]["rich_text"][0]["text"]["content"]
        blogs.append({"id": result["id"], "title": title, "content": content, "meta_description": meta, "keywords": keywords})
    return blogs

def update_social_status(page_id, status):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"Status": {"status": {"name": status}}}}
    requests.patch(url, headers=notion_headers(), json=payload)

def log_to_notion(blog_title, agent_output):
    url = "https://api.notion.com/v1/pages"
    clean_t = clean_title(blog_title)
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Title": {"title": [{"text": {"content": f"Log: {clean_t}"}}]},
            "Content": {"rich_text": [{"text": {"content": str(agent_output)[:2000]}}]},
            "Published": {"checkbox": False},
            "Page": {"select": {"name": PAGE_NAME}}
        }
    }
    requests.post(url, headers=notion_headers(), json=payload)

# ============ FACEBOOK & INSTAGRAM POSTING ============
def create_instagram_caption(title, content, keywords):
    clean_t = clean_title(title)
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()][:3]
    intro = ' '.join(paragraphs)[:800]
    keyword_list = [k.strip().replace(' ', '') for k in keywords.split(',')[:8]]
    hashtags = ' '.join([f'#{k}' for k in keyword_list])
    caption = f"✨ {clean_t}\n\n{intro}\n\n💭 What's your experience? Drop a comment! 👇\n\n{hashtags}\n\n#{PAGE_NAME.replace(' ', '')}"
    return caption[:2200]

def create_facebook_caption(title, content, keywords):
    clean_t = clean_title(title)
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()][:5]
    intro = '\n\n'.join(paragraphs)[:1500]
    caption = f"📚 {clean_t}\n\n{intro}\n\n---\n💬 What's your experience? Share in the comments!\n\n#{PAGE_NAME.replace(' ', '')}"
    return caption

def post_to_instagram(image_url, caption):
    if not IG_ACCOUNT_ID or not FB_ACCESS_TOKEN:
        print("❌ Instagram credentials missing. Skipping.")
        return None
    print(f"\n📸 Posting to Instagram...")
    container_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media"
    response = requests.post(container_url, data={"image_url": image_url, "caption": caption, "access_token": FB_ACCESS_TOKEN})
    if response.status_code != 200: return None
    container_id = response.json().get("id")
    time.sleep(5)
    response = requests.post(f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media_publish", data={"creation_id": container_id, "access_token": FB_ACCESS_TOKEN})
    if response.status_code == 200:
        print(f"✅ Posted to Instagram!")
        return response.json().get("id")
    return None

def post_to_facebook(image_url, caption):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        print("❌ Facebook credentials missing. Skipping.")
        return None
    print(f"\n📘 Posting to Facebook...")
    response = requests.post(f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos", data={"message": caption, "url": image_url, "access_token": FB_ACCESS_TOKEN})
    if response.status_code == 200:
        print(f"✅ Posted to Facebook!")
        return response.json().get("id")
    return None

# ============ DEFINE AGENTS ============
FREE_MODEL = "mistral/mistral-small-latest"

trend_researcher = Agent(
    role=f"Content Strategist for {PAGE_NAME}",
    goal=f"Find UNIQUE, high-value blog topics that haven't been covered recently and align perfectly with {PAGE_NAME}'s purpose",
    backstory=f"""You are a content strategist for {PAGE_NAME}.
{BRAND_CONTEXT}

YOUR JOB:
- Find CONTENT GAPS: topics people search for but find poor answers to
- Ensure topics are FRESH and haven't been covered in the last 30 days
- Topics must directly relate to {PAGE_NAME}'s core features and audience
- Be specific and creative. Avoid generic topics.

You will receive a list of recent topics. You MUST suggest something completely different.""",
    llm=FREE_MODEL, verbose=True
)

blog_writer = Agent(
    role=f"Expert Blog Writer for {PAGE_NAME}",
    goal=f"Write engaging, human-sounding blog posts that naturally relate to {PAGE_NAME} and provide genuine value",
    backstory=f"""You write for {PAGE_NAME}.
{BRAND_CONTEXT}
{HUMANIZATION_RULES}

YOUR APPROACH:
- Start with a compelling hook that grabs attention
- Provide specific, actionable advice (not generic fluff)
- Include real examples and case studies
- Naturally mention {PAGE_NAME} where relevant (1-2 times max, not forced)
- End with a clear takeaway or call-to-action

Structure: Hook, Problem, Solution, Examples, Common Mistakes, Step-by-Step, FAQ, Conclusion.
1,500-2,000 words.""",
    llm=FREE_MODEL, verbose=True
)

seo_geo_optimizer = Agent(
    role="SEO & GEO Specialist",
    goal="Optimize for Google AND AI search engines",
    backstory="""You optimize content for both traditional search and AI engines.
Output EXACT format:
SLUG: [slug]
META: [meta under 155 chars]
KEYWORDS: [keyword1, keyword2, ...]
GEO_SNIPPETS: [answer 1] | [answer 2]""",
    llm=FREE_MODEL, verbose=True
)

ceo_reviewer = Agent(
    role=f"Chief Content Officer for {PAGE_NAME}",
    goal=f"Maintain the highest quality standards. Only approve truly excellent content that aligns with {PAGE_NAME}'s brand and provides real value.",
    backstory=f"""You are the quality gatekeeper for {PAGE_NAME}.
{BRAND_CONTEXT}

YOUR STANDARDS (BE STRICT):
1. HUMANIZATION (40%): Does it sound like a real expert wrote it? Reject if it sounds AI-generated.
2. RELEVANCE (30%): Does it directly relate to {PAGE_NAME}'s niche and audience? Reject if off-topic.
3. ORIGINALITY (20%): Is this a fresh angle or just rehashed info? Reject if generic.
4. VALUE (10%): Does it provide actionable insights? Reject if it's just fluff.

DUPLICATE CHECK: If this topic was covered in the last 30 days with the same angle, REJECT.
Similar topics are OK if the angle is different.

Be harsh. Only approve content you'd be proud to publish under the {PAGE_NAME} brand.

Output EXACT format:
DECISION: APPROVED or REJECTED
SCORE: X/10
REASONS: [specific issues]
FIXES_NEEDED: [exact changes required - only if REJECTED]""",
    llm=FREE_MODEL, verbose=True
)

image_prompt_creator = Agent(
    role="Image Prompt Creator",
    goal="Create short, realistic photography prompts for blog images",
    backstory="""Create SHORT prompts (under 200 chars) for REALISTIC photographs.
Never cartoon, illustration, or anime. Always professional photography.""",
    llm=FREE_MODEL, verbose=True
)

social_strategist = Agent(role="Social Media Strategist", goal="Plan social media angles", backstory="You plan social media strategy.", llm=FREE_MODEL, verbose=True)
content_creator = Agent(role="Social Content Creator", goal="Create social posts", backstory="You create engaging social media content.", llm=FREE_MODEL, verbose=True)
poster = Agent(role="Social Media Manager", goal="Format posts for publishing", backstory="You format content for social platforms.", llm=FREE_MODEL, verbose=True)

# ============ PHASE 1: BLOG CREATION ============
def run_blog_creation_phase():
    print("\n" + "="*60)
    print(f"PHASE 1: BLOG CREATION for {PAGE_NAME} ({PAGE_NICHE})")
    print("="*60)

    strategy = fetch_active_strategy()
    if strategy:
        print(f"\nActive Strategy: {strategy['goal']}")
        print(f"Target Audience: {strategy['target_audience']}")

    # CRITICAL: Fetch recent topics so agents know what's been covered
    recent_titles = fetch_recent_blog_titles(days=30, limit=20)
    recent_text = "\n".join([f"- {t}" for t in recent_titles]) if recent_titles else "No recent posts"
    print(f"\n📋 Recent topics (last 30 days): {len(recent_titles)} posts")

    failure_memories = fetch_relevant_memories(outcome="Failure", limit=3)
    success_memories = fetch_relevant_memories(outcome="Success", limit=3)

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

        print(f"\n[Step 1] Researching FRESH topic for {PAGE_NAME}...")
        
        # CRITICAL: Give researcher the list of recent topics to avoid
        if ceo_feedback:
            research_desc = (
                f"Research ONE NEW blog topic for {PAGE_NAME} in the {PAGE_NICHE} niche.\n\n"
                f"The previous topic was rejected. Pick a COMPLETELY DIFFERENT angle.\n\n"
                f"RECENT TOPICS (AVOID THESE):\n{recent_text}\n\n"
                f"Your topic MUST be different from all of the above.\n"
                f"Output ONLY the title as plain text."
            )
        else:
            research_desc = (
                f"Research ONE trending, high-value blog topic for {PAGE_NAME}.\n\n"
                f"Focus: {PAGE_DESCRIPTION if PAGE_DESCRIPTION else PAGE_NICHE}\n\n"
                f"RECENT TOPICS (AVOID THESE):\n{recent_text}\n\n"
                f"Your topic MUST be different from all of the above.\n"
                f"Output ONLY the title as plain text."
            )

        research_task = Task(description=research_desc, expected_output="A single blog topic title", agent=trend_researcher)
        Crew(agents=[trend_researcher], tasks=[research_task], process=Process.sequential, verbose=True).kickoff()

        title = clean_title(research_task.output.raw.strip()) if research_task.output else "Untitled"
        final_title = title
        print(f"\n✅ Topic: {title}")

        memory_context = ""
        if failure_memories:
            memory_context += "\nAVOID: " + "; ".join([m['summary'] for m in failure_memories[:2]])
        if success_memories:
            memory_context += "\nFOLLOW: " + "; ".join([m['summary'] for m in success_memories[:2]])

        print(f"\n[Step 2] Writing blog post...")
        write_desc = (
            f"Write a 1500-2000 word blog post: {title}\n\n"
            f"This is for {PAGE_NAME}: {PAGE_DESCRIPTION if PAGE_DESCRIPTION else PAGE_NICHE}\n\n"
            f"{HUMANIZATION_RULES}\n{memory_context}\n\n"
            "Structure: Hook, Problem, Solution, Examples, FAQ, Conclusion. "
            "Use ## headings. Do NOT repeat the title at top."
        )
        write_task = Task(description=write_desc, expected_output="Complete blog post", agent=blog_writer)

        print(f"\n[Step 3] SEO/GEO optimization...")
        seo_task = Task(description="Create: SLUG, META, KEYWORDS, GEO_SNIPPETS", expected_output="SEO elements", agent=seo_geo_optimizer)

        print(f"\n[Step 4] CEO review (STRICT STANDARDS)...")
        strategy_ctx = ""
        if strategy:
            strategy_ctx = f"\nStrategy: {strategy['goal']}. Audience: {strategy['target_audience']}."

        review_desc = (
            f"Review this blog post for {PAGE_NAME} with STRICT standards.\n\n"
            f"RECENT TOPICS (check for duplicates):\n{recent_text}\n\n"
            f"If this is a duplicate (same topic + same angle), REJECT.\n"
            f"If it's off-topic or sounds AI-generated, REJECT.\n"
            f"Only APPROVE if it's genuinely excellent.{strategy_ctx}\n\n"
            "Output: DECISION, SCORE, REASONS, FIXES_NEEDED"
        )
        review_task = Task(description=review_desc, expected_output="DECISION, SCORE, REASONS, FIXES_NEEDED", agent=ceo_reviewer)

        Crew(agents=[blog_writer, seo_geo_optimizer, ceo_reviewer], tasks=[write_task, seo_task, review_task], process=Process.sequential, verbose=True).kickoff()

        blog_content = write_task.output.raw.strip() if write_task.output else ""
        seo_output = seo_task.output.raw.strip() if seo_task.output else ""
        ceo_decision = review_task.output.raw.strip() if review_task.output else ""

        print(f"\nCEO: {ceo_decision[:300]}")

        if "DECISION: APPROVED" in ceo_decision.upper():
            print(f"\n✅ APPROVED on attempt {attempt}!")
            final_blog_content = blog_content
            final_seo_output = seo_output
            final_ceo_decision = ceo_decision
            save_to_memory(f"Approved: {title}", "Pattern", f"Approved attempt {attempt}", "Success", "Met standards", 7)
            break
        else:
            print(f"\n❌ Rejected attempt {attempt}.")
            ceo_feedback = ceo_decision
            final_blog_content = blog_content
            final_seo_output = seo_output
            final_ceo_decision = ceo_decision
            save_to_memory(f"Rejected: {title[:50]}", "Feedback", ceo_decision[:500], "Failure", "Did not meet standards", 6)

    slug, meta, keywords = "", "", ""
    if final_seo_output:
        for line in final_seo_output.split('\n'):
            if line.startswith("SLUG:"): slug = line.replace("SLUG:", "").strip()
            elif line.startswith("META:"): meta = line.replace("META:", "").strip()
            elif line.startswith("KEYWORDS:"): keywords = line.replace("KEYWORDS:", "").strip()

    is_approved = "DECISION: APPROVED" in final_ceo_decision.upper() if final_ceo_decision else False

    print(f"\nFinal: {'APPROVED' if is_approved else 'REJECTED'} | Title: {final_title}")

    if is_approved and final_title and final_blog_content:
        image_url = generate_blog_image_with_agent(final_title, final_blog_content, keywords, PAGE_NAME)
        page_id = create_notion_page_with_body(final_title, final_blog_content[:500], slug, meta, keywords, final_blog_content, image_url, PAGE_NAME)
        if page_id:
            return {"title": final_title, "page_id": page_id, "status": "published", "content": final_blog_content, "keywords": keywords, "image_url": image_url}

    return {"title": final_title, "status": "rejected", "feedback": final_ceo_decision}

# ============ PHASE 2: SOCIAL MEDIA ============
def run_social_promotion_phase():
    print("\n" + "="*60)
    print(f"PHASE 2: SOCIAL MEDIA for {PAGE_NAME}")
    print("="*60)
    blogs = fetch_unprocessed_published_blogs()
    if not blogs:
        print("✅ No new blogs to promote.")
        return
    for blog in blogs:
        print(f"\nPromoting: {blog['title']}")
        update_social_status(blog['id'], "Processing")
        ig_caption = create_instagram_caption(blog['title'], blog['content'], blog['keywords'])
        fb_caption = create_facebook_caption(blog['title'], blog['content'], blog['keywords'])
        image_url = generate_blog_image_with_agent(blog['title'], blog['content'], blog['keywords'], PAGE_NAME)
        ig_result = post_to_instagram(image_url, ig_caption)
        fb_result = post_to_facebook(image_url, fb_caption)
        log_to_notion(blog['title'], f"IG: {'OK' if ig_result else 'Skip'} | FB: {'OK' if fb_result else 'Skip'}")
        update_social_status(blog['id'], "Posted")

# ============ MAIN ============
def run_daily_agency():
    print(f"\n{'='*60}")
    print(f"DEBUG: PAGE_NAME={PAGE_NAME} | NICHE={PAGE_NICHE}")
    print(f"{'='*60}")
    print(f"🚀 Starting agency for {PAGE_NAME} ({PAGE_NICHE})")

    try:
        run_blog_creation_phase()
    except Exception as e:
        print(f"⚠️ Blog error: {e}")

    try:
        run_social_promotion_phase()
    except Exception as e:
        print(f"⚠️ Social error: {e}")

    print("\n🎉 Done!")

if __name__ == "__main__":
    run_daily_agency()

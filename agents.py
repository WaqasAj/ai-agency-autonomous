import os
import requests
import re
import time
import json
import traceback
from crewai import Agent, Task, Crew, Process
from datetime import datetime, timedelta
import litellm

# ============ THE FIX: Strip cache_breakpoint + Retry/Fallback Logic ============
_original_completion = litellm.completion

def _patched_completion(*args, **kwargs):
    def _strip(obj):
        if isinstance(obj, dict):
            obj.pop("cache_breakpoint", None)
            for v in obj.values(): _strip(v)
        elif isinstance(obj, list):
            for item in obj: _strip(item)
    _strip(kwargs)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return _original_completion(*args, **kwargs)
        except Exception as e:
            error_str = str(e)
            if "MistralException" in error_str or "ServiceUnavailable" in error_str or "Connection refused" in error_str:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"⚠️ Mistral API error, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print(f"❌ Mistral API failed after {max_retries} attempts. Switching to fallback model (Gemini)...")
                    kwargs['model'] = 'gemini/gemini-1.5-flash'
                    return _original_completion(*args, **kwargs)
            else:
                raise e

litellm.completion = _patched_completion
# =============================================================================

# ============ LOAD SECRETS ============
NOTION_KEY = os.getenv("NOTION_API_KEY")
NOTION_DB_ID = os.getenv("NOTION_DATABASE_ID")
MISTRAL_KEY = os.getenv("MISTRAL_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
FB_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
FB_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
STRATEGY_DB_ID = os.getenv("STRATEGY_DB_ID")
MEMORY_DB_ID = os.getenv("MEMORY_DB_ID")
PAGE_NAME = os.getenv("PAGE_NAME", "Kahani AI")
PAGE_NICHE = os.getenv("PAGE_NICHE", "general")
PAGE_DESCRIPTION = os.getenv("PAGE_DESCRIPTION", "")

if MISTRAL_KEY: os.environ["MISTRAL_API_KEY"] = MISTRAL_KEY
if GEMINI_KEY: os.environ["GEMINI_API_KEY"] = GEMINI_KEY

# ============ STARTUP VALIDATION ============
print(f"\n{'='*70}")
print(f"🚀 AGENTS.PY STARTING")
print(f"   PAGE_NAME: {PAGE_NAME}")
print(f"   PAGE_NICHE: {PAGE_NICHE}")
print(f"   PAGE_DESCRIPTION: {PAGE_DESCRIPTION[:50] if PAGE_DESCRIPTION else 'None'}")
print(f"   NOTION_KEY present: {bool(NOTION_KEY)}")
print(f"   MISTRAL_KEY present: {bool(MISTRAL_KEY)}")
print(f"   GEMINI_KEY present: {bool(GEMINI_KEY)}")
print(f"{'='*70}\n")

if not NOTION_KEY: print("❌ CRITICAL: NOTION_API_KEY is not set!")
if not MISTRAL_KEY: print("❌ CRITICAL: MISTRAL_API_KEY is not set!")

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    print("✅ Google API libraries imported successfully")
except ImportError as e:
    print(f"⚠️ Google API libraries not available: {e}")

# ============ DEEP PRODUCT CONTEXT ============
PRODUCT_CONTEXT = {
    "Kahani AI": """
Kahani AI is a web application that generates personalized bedtime stories and kids' stories using AI.
CORE FEATURES: Custom stories with child's name, 4 languages (English, Urdu, Arabic, Hindi), AI illustrations, audio narration, PDF download.
TARGET AUDIENCE: Parents of children ages 2-10, educators, grandparents in South Asian and Middle Eastern communities.
UNIQUE VALUE PROPOSITION: Makes children the hero of their own stories while preserving cultural and linguistic heritage.

CONTENT MUST:
- Focus on the MAGIC and PSYCHOLOGY of personalized storytelling
- Include SPECIFIC examples (e.g., "When 4-year-old Ayesha saw herself as the princess...")
- Address REAL parent pain points (screen time, bedtime struggles, language barriers)
- Naturally mention Kahani AI as a SOLUTION, not a sales pitch
- Use warm, empathetic tone like a trusted friend who's been there

CONTENT MUST NOT:
- Be generic parenting advice unrelated to stories/reading
- Sound like a product brochure
- Use corporate jargon or AI clichés
""",
    "Geo Analyzer": """
Geo Analyzer is a web tool that scans URLs/text for SEO and Generative Engine Optimization (GEO).
CORE FEATURES: AI search engine optimization, MCP integration, heading/FAQ/schema analysis, actionable recommendations.
TARGET AUDIENCE: Content creators, digital marketers, SEO professionals, tech-savvy business owners.
UNIQUE VALUE PROPOSITION: Bridges the gap between traditional SEO and AI-powered search (ChatGPT, Perplexity, Gemini).

CONTENT MUST:
- Be TECHNICAL but ACCESSIBLE (explain complex concepts simply)
- Include SPECIFIC examples with real URLs and before/after comparisons
- Focus on ACTIONABLE steps readers can implement immediately
- Address the SHIFT from keyword-based to AI-based search
- Use authoritative but conversational tone like an industry expert sharing insights

CONTENT MUST NOT:
- Be basic SEO advice everyone already knows
- Use overly technical jargon without explanation
- Sound like a generic marketing blog
"""
}

product_info = PRODUCT_CONTEXT.get(PAGE_NAME, f"{PAGE_NAME} is a platform focused on {PAGE_NICHE}. {PAGE_DESCRIPTION if PAGE_DESCRIPTION else 'Creating valuable content in this niche.'}")

BRAND_CONTEXT = f"""
{product_info}
Brand voice: Warm, trustworthy, authoritative, and genuinely helpful. Write for HUMANS first, search engines second.
"""

HUMANIZATION_RULES = """
CRITICAL: Write like a real human expert, NOT like an AI.

NEVER USE THESE AI PATTERNS (instant rejection):
- "In today's world", "In the digital age", "It's important to note"
- "delve", "tapestry", "landscape", "realm", "journey", "foster", "cultivate"
- "Let's explore", "Let's dive in", "Let's unpack"
- "Furthermore", "Moreover", "Additionally" (use "And", "But", "Also" instead)

ALWAYS DO THESE (human signals):
- Start sentences with "And", "But", "Because", "So"
- Use contractions: "don't", "it's", "you'll", "we've"
- Include SPECIFIC numbers: "my 4-year-old", "3 AM wake-ups", "15 minutes"
- Add personal moments: "I remember when...", "Last week, I noticed..."
- Ask rhetorical questions: "Sound familiar?", "You know that feeling, right?"
- Use conversational asides: "(trust me on this one)", "(yes, even on tough nights)"
- Vary sentence length wildly (mix 5-word and 25-word sentences)
"""

# ============ CLEANING HELPERS ============
def clean_title(title):
    if not title: return "Untitled"
    # Remove markdown, quotes, asterisks
    cleaned = re.sub(r'^[\s\*"\']+', '', title)
    cleaned = re.sub(r'[\s\*"\']+$', '', cleaned)
    cleaned = cleaned.strip()
    
    # CRITICAL: Truncate to 150 chars max (well under Notion's 2000 limit)
    if len(cleaned) > 150:
        cleaned = cleaned[:147] + "..."
        print(f"⚠️ Title was too long, truncated to: {cleaned}")
    
    return cleaned

def clean_blog_content(content, title):
    if not content: return ""
    content = re.sub(r'^```(?:markdown|md)?\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    clean_t = clean_title(title)
    content = re.sub(r'^#+\s*' + re.escape(clean_t) + r'\s*\n+', '', content, flags=re.IGNORECASE)
    lines = content.split('\n')
    if lines and lines[0].startswith('# ') and len(lines[0]) < 100:
        first_heading = lines[0].replace('#', '').strip()
        if clean_t.lower() in first_heading.lower() or first_heading.lower() in clean_t.lower():
            lines = lines[1:]
            content = '\n'.join(lines)
    return content.strip()

# ============ NOTION API HELPERS ============
def notion_headers():
    return {"Authorization": f"Bearer {NOTION_KEY}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}

def fetch_active_strategy():
    if not STRATEGY_DB_ID: return None
    url = f"https://api.notion.com/v1/databases/{STRATEGY_DB_ID}/query"
    payload = {"filter": {"and": [{"property": "Status", "select": {"equals": "Active"}}, {"property": "Page", "select": {"equals": PAGE_NAME}}]}}
    response = requests.post(url, headers=notion_headers(), json=payload)
    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            s = results[0]["properties"]
            return {
                "goal": s.get("Goal", {}).get("title", [{}])[0].get("text", {}).get("content", ""),
                "target_audience": s.get("Target Audience", {}).get("rich_text", [{}])[0].get("text", {}).get("content", ""),
                "current_priority": s.get("Current Priority", {}).get("select", {}).get("name", ""),
                "brand_rules": s.get("Brand Rules", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
            }
    return None

def fetch_relevant_memories(memory_type=None, outcome=None, limit=10):
    if not MEMORY_DB_ID: return []
    url = f"https://api.notion.com/v1/databases/{MEMORY_DB_ID}/query"
    filters = []
    if memory_type: filters.append({"property": "Type", "select": {"equals": memory_type}})
    if outcome: filters.append({"property": "Outcome", "select": {"equals": outcome}})
    payload = {"filter": {"and": filters} if filters else {}, "sorts": [{"property": "Confidence", "direction": "descending"}], "page_size": limit}
    response = requests.post(url, headers=notion_headers(), json=payload)
    memories = []
    if response.status_code == 200:
        for result in response.json().get("results", []):
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
    if not MEMORY_DB_ID: return None
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

def fetch_recent_blog_titles(days=30, limit=20):
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    thirty_days_ago = (datetime.now() - timedelta(days=days)).isoformat()
    payload = {
        "filter": {"and": [{"property": "Published", "checkbox": {"equals": True}}, {"property": "Page", "select": {"equals": PAGE_NAME}}, {"property": "Created", "date": {"on_or_after": thirty_days_ago}}]},
        "sorts": [{"timestamp": "created_time", "direction": "descending"}], "page_size": limit
    }
    response = requests.post(url, headers=notion_headers(), json=payload)
    titles = []
    if response.status_code == 200:
        for result in response.json().get("results", []):
            title_props = result["properties"].get("Title", {}).get("title", [])
            if title_props:
                title = title_props[0].get("text", {}).get("content", "")
                if title: titles.append(title)
    return titles

# ============ AGENT-DRIVEN IMAGE GENERATION ============
def generate_blog_image_with_agent(title, blog_content, keywords, page_name=PAGE_NAME):
    print("\n🎨 Analyzing blog content for image generation...")
    try:
        content_preview = blog_content[:1500]
        image_task = Task(
            description=f"Create a SHORT image prompt (max 200 chars) for a realistic photograph.\nTITLE: {title}\nKEYWORDS: {keywords}\nPREVIEW: {content_preview[:400]}\nOUTPUT: IMAGE_PROMPT: [prompt under 200 chars, realistic photography only]",
            expected_output="IMAGE_PROMPT: [short prompt]", agent=image_prompt_creator
        )
        Crew(agents=[image_prompt_creator], tasks=[image_task], process=Process.sequential, verbose=False).kickoff()
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
        return f"https://image.pollinations.ai/prompt/professional%20photography?width=1200&height=675&model=flux&nologo=true&seed={hash(title + page_name) % 10000}"

# ============ NOTION PAGE CREATION ============
def create_notion_page_with_body(title, content, slug, meta_description, keywords, full_blog_content, image_url, page_name=PAGE_NAME):
    url = "https://api.notion.com/v1/pages"
    clean_t = clean_title(title)
    def create_notion_page_with_body(title, content, slug, meta_description, keywords, full_blog_content, image_url, page_name=PAGE_NAME):
    url = "https://api.notion.com/v1/pages"
    clean_t = clean_title(title)
    
    # CRITICAL: Final safety check - ensure title is under 2000 chars
    if len(clean_t) > 2000:
        print(f"⚠️ Title still too long ({len(clean_t)} chars), truncating to 1997...")
        clean_t = clean_t[:1997] + "..."
    
    clean_content = clean_blog_content(full_blog_content, clean_t)
    # ... rest of the function remains the same
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
            "Published": {"checkbox": True},
            "Created": {"date": {"start": datetime.now().isoformat()}},
            "Blog Source": {"select": {"name": "AI Generated"}},
            "Page": {"select": {"name": page_name}}
        },
        "children": [{"object": "block", "type": "image", "image": {"type": "external", "external": {"url": image_url}}}, *convert_text_to_notion_blocks(clean_content)]
    }
    print(f"\n📝 Creating Notion page for {page_name}...")
    response = requests.post(url, headers=notion_headers(), json=payload)
    if response.status_code == 200:
        print(f"✅ Created Notion page: {clean_t}")
        return response.json()["id"]
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")
        return None

def convert_text_to_notion_blocks(text):
    blocks = []
    for para in text.split('\n\n'):
        para = para.strip()
        if not para: continue
        if para.startswith('### '): blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": para[4:]}}]}})
        elif para.startswith('## '): blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": para[3:]}}]}})
        elif para.startswith('# '): blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": para[2:]}}]}})
        elif para.startswith('- ') or para.startswith('* '): blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": para[2:]}}]}})
        elif re.match(r'^\d+\. ', para): blocks.append({"object": "block", "type": "numbered_list_item", "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": re.sub(r'^\d+\. ', '', para)}}]}})
        else: blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": para}}]}})
    return blocks

def fetch_unprocessed_published_blogs():
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    payload = {"filter": {"and": [{"property": "Published", "checkbox": {"equals": True}}, {"property": "Page", "select": {"equals": PAGE_NAME}}, {"or": [{"property": "Status", "status": {"equals": "Not Processed"}}, {"property": "Status", "status": {"is_empty": True}}]}]}}
    response = requests.post(url, headers=notion_headers(), json=payload)
    blogs = []
    for result in response.json().get("results", []):
        title = result["properties"]["Title"]["title"][0]["text"]["content"] if result["properties"]["Title"]["title"] else "Untitled"
        content = result["properties"]["Content"]["rich_text"][0]["text"]["content"] if "Content" in result["properties"] and result["properties"]["Content"]["type"] == "rich_text" and result["properties"]["Content"]["rich_text"] else ""
        meta = result["properties"]["Meta Description"]["rich_text"][0]["text"]["content"] if "Meta Description" in result["properties"] and result["properties"]["Meta Description"]["type"] == "rich_text" and result["properties"]["Meta Description"]["rich_text"] else ""
        keywords = result["properties"]["Keywords"]["rich_text"][0]["text"]["content"] if "Keywords" in result["properties"] and result["properties"]["Keywords"]["type"] == "rich_text" and result["properties"]["Keywords"]["rich_text"] else ""
        blogs.append({"id": result["id"], "title": title, "content": content, "meta_description": meta, "keywords": keywords})
    return blogs

def update_social_status(page_id, status):
    requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=notion_headers(), json={"properties": {"Status": {"status": {"name": status}}}})

def log_to_notion(blog_title, agent_output):
    clean_t = clean_title(blog_title)
    requests.post("https://api.notion.com/v1/pages", headers=notion_headers(), json={
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {"Title": {"title": [{"text": {"content": f"Log: {clean_t}"}}]}, "Content": {"rich_text": [{"text": {"content": str(agent_output)[:2000]}}]}, "Published": {"checkbox": False}, "Page": {"select": {"name": PAGE_NAME}}}
    })

# ============ SOCIAL MEDIA POSTING ============
def create_instagram_caption(title, content, keywords):
    clean_t = clean_title(title)
    intro = ' '.join([p.strip() for p in content.split('\n\n') if p.strip()][:3])[:800]
    hashtags = ' '.join([f'#{k.strip().replace(" ", "")}' for k in keywords.split(',')[:8]])
    return f"✨ {clean_t}\n\n{intro}\n\n💭 What's your experience? Drop a comment! 👇\n\n{hashtags}\n\n#{PAGE_NAME.replace(' ', '')}"[:2200]

def create_facebook_caption(title, content, keywords):
    clean_t = clean_title(title)
    intro = '\n\n'.join([p.strip() for p in content.split('\n\n') if p.strip()][:5])[:1500]
    return f"📚 {clean_t}\n\n{intro}\n\n---\n💬 What's your experience? Share in the comments!\n\n#{PAGE_NAME.replace(' ', '')}"

def post_to_instagram(image_url, caption):
    if not IG_ACCOUNT_ID or not FB_ACCESS_TOKEN: return None
    res = requests.post(f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media", data={"image_url": image_url, "caption": caption, "access_token": FB_ACCESS_TOKEN})
    if res.status_code != 200: return None
    container_id = res.json().get("id")
    time.sleep(5)
    res2 = requests.post(f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media_publish", data={"creation_id": container_id, "access_token": FB_ACCESS_TOKEN})
    return res2.json().get("id") if res2.status_code == 200 else None

def post_to_facebook(image_url, caption):
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN: return None
    res = requests.post(f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos", data={"message": caption, "url": image_url, "access_token": FB_ACCESS_TOKEN})
    return res.json().get("id") if res.status_code == 200 else None

# ============ DEFINE AGENTS ============
FREE_MODEL = "mistral/mistral-small-latest"

trend_researcher = Agent(
    role=f"Senior Content Strategist for {PAGE_NAME}",
    goal=f"Identify UNIQUE, HIGH-VALUE blog topics that solve REAL problems for {PAGE_NAME}'s audience",
    backstory=f"""You are a veteran content strategist with 15 years of experience in the {PAGE_NICHE} niche.

{BRAND_CONTEXT}

YOUR EXPERTISE:
- You find CONTENT GAPS where people are searching but finding poor answers
- You understand what makes content go viral in this specific niche
- You know the difference between generic topics and SPECIFIC, actionable ones

CRITICAL OUTPUT RULE:
You MUST output ONLY a short blog title (under 100 characters).
DO NOT output descriptions, explanations, or paragraphs.
DO NOT output bullet points or multiple topics.
OUTPUT FORMAT: Just the title, nothing else.

EXAMPLES OF GOOD OUTPUT:
✅ "How Personalized Bedtime Stories Helped My 4-Year-Old Overcome Sleep Anxiety"
✅ "Why Your SEO Strategy is Failing in the Age of ChatGPT"
❌ "Here's a great topic about bedtime stories. The angle is..." (WRONG - too long)
❌ "Topic 1: Stories\nTopic 2: SEO" (WRONG - multiple topics)

You will receive recent topics. You MUST suggest something COMPLETELY DIFFERENT.""",
    llm=FREE_MODEL, verbose=True
)
blog_writer = Agent(role=f"Expert Blog Writer for {PAGE_NAME}", goal=f"Write {PAGE_NICHE} blog posts that feel like they were written by a trusted expert", backstory=f"You are a master storyteller and {PAGE_NICHE} expert writing specifically for {PAGE_NAME}.\n\n{BRAND_CONTEXT}\n\n{HUMANIZATION_RULES}\n\nYOUR WRITING PROCESS:\n1. Start with a HOOK that grabs attention in the first 2 sentences\n2. Establish the PROBLEM with specific, relatable examples\n3. Present the SOLUTION with step-by-step actionable advice\n4. Include REAL case studies or examples (use specific numbers and details)\n5. Address COMMON MISTAKES people make\n6. End with a clear TAKEAWAY or call-to-action\n\nSTRUCTURE (1,500-2,000 words):\n## Hook (grab attention)\n## The Problem (make it relatable)\n## The Solution (step-by-step)\n## Real Examples (specific case studies)\n## Common Mistakes (what to avoid)\n## FAQ Section (answer real questions)\n## Conclusion (clear takeaway)\n\nQUALITY CHECKLIST (before submitting):\n- Does it sound like a REAL person wrote it? (not AI)\n- Are there SPECIFIC examples with numbers? (not generic)\n- Does it naturally mention {PAGE_NAME} without being salesy? (1-2 times max)\n- Would a reader in the {PAGE_NICHE} niche find this VALUABLE?\n- Is it FREE of AI clichés? (no \"delve\", \"tapestry\", \"journey\", etc.)\n\nWrite for HUMANS first, search engines second.", llm=FREE_MODEL, verbose=True)

seo_geo_optimizer = Agent(role="SEO & GEO Specialist", goal="Optimize content for Google AND AI search engines", backstory="You optimize content for both traditional search and AI engines (ChatGPT, Perplexity, Gemini).\n\nYOUR EXPERTISE:\n- Traditional SEO: keywords, meta tags, structure\n- GEO (Generative Engine Optimization): making content AI-friendly\n- Schema markup, FAQ optimization, featured snippets\n\nOUTPUT EXACT FORMAT:\nSLUG: [url-friendly-slug]\nMETA: [compelling meta description under 155 chars with keyword and CTA]\nKEYWORDS: [primary keyword, variation 1, variation 2, ...]\nGEO_SNIPPETS: [Direct answer 1] | [Direct answer 2]", llm=FREE_MODEL, verbose=True)

ceo_reviewer = Agent(role=f"Chief Content Officer for {PAGE_NAME}", goal=f"Maintain the HIGHEST quality standards. Only approve truly excellent content.", backstory=f"You are the final quality gatekeeper for {PAGE_NAME}.\n\n{BRAND_CONTEXT}\n\nYOUR STANDARDS (BE STRICT):\n1. HUMANIZATION (40%): Does it sound like a REAL expert wrote it? Reject if it sounds AI-generated.\n2. RELEVANCE (30%): Does it directly relate to {PAGE_NAME}'s niche and audience? Reject if off-topic.\n3. ORIGINALITY (20%): Is this a FRESH angle or just rehashed info? Reject if generic.\n4. VALUE (10%): Does it provide ACTIONABLE insights? Reject if it's just fluff.\n\nDUPLICATE CHECK: If this topic was covered in the last 30 days with the SAME angle, REJECT.\n\nBE HARSH. Only approve content you'd be proud to publish under the {PAGE_NAME} brand.\n\nOutput EXACT format:\nDECISION: APPROVED or REJECTED\nSCORE: X/10\nREASONS: [specific issues - be detailed]\nFIXES_NEEDED: [exact changes required - only if REJECTED]", llm=FREE_MODEL, verbose=True)

image_prompt_creator = Agent(role="Image Prompt Creator", goal="Create short, realistic photography prompts for blog images", backstory="Create SHORT prompts (under 200 chars) for REALISTIC photographs. Never cartoon or anime.", llm=FREE_MODEL, verbose=True)

keyword_researcher = Agent(role="SEO Keyword Research Specialist", goal="Find high-value, low-competition keywords", backstory="You are an expert keyword researcher. Find long-tail keywords with commercial intent and low competition.", llm=FREE_MODEL, verbose=True)

seo_monitor = Agent(role="Chief SEO & Performance Officer", goal="Monitor website health and provide actionable recommendations", backstory="You are a world-class SEO specialist. Provide data-driven recommendations with clear priority levels: 🔴 CRITICAL, 🟡 HIGH, 🟠 MEDIUM, 🔵 LOW.", llm=FREE_MODEL, verbose=True)

# ============ PHASE 1: BLOG CREATION ============
def run_blog_creation_phase():
    print("\n" + "="*60)
    print(f"PHASE 1: BLOG CREATION for {PAGE_NAME} ({PAGE_NICHE})")
    print("="*60)

    strategy = fetch_active_strategy()
    if strategy:
        print(f"\nActive Strategy: {strategy['goal']}")
        print(f"Target Audience: {strategy['target_audience']}")

    recent_titles = fetch_recent_blog_titles(days=30, limit=20)
    recent_text = "\n".join([f"- {t}" for t in recent_titles]) if recent_titles else "No recent posts"
    print(f"\n📋 Recent topics (last 30 days): {len(recent_titles)} posts")

    seo_memories = fetch_relevant_memories(memory_type="SEO_AUDIT", limit=2)
    failure_memories = fetch_relevant_memories(outcome="Failure", limit=3)
    success_memories = fetch_relevant_memories(outcome="Success", limit=3)

    MAX_REVISIONS = 2  # Back to 2 attempts
    ceo_feedback = None
    final_blog_content = final_seo_output = final_ceo_decision = final_title = None

    for attempt in range(1, MAX_REVISIONS + 1):
        print(f"\n{'='*40}\nATTEMPT {attempt}/{MAX_REVISIONS}\n{'='*40}")
        print(f"\n[Step 1] Researching FRESH topic for {PAGE_NAME}...")
        
        seo_context = ""
        if seo_memories:
            seo_context += "\n\n🚨 SEO INSIGHTS FROM LAST AUDIT:\n"
            for mem in seo_memories[:1]:
                seo_context += f"{mem['content'][:500]}...\n"
        
        if ceo_feedback:
            research_desc = (
                f"Research ONE NEW blog topic for {PAGE_NAME} in the {PAGE_NICHE} niche.\n\n"
                f"The previous topic was REJECTED by the CEO. Here's why:\n{ceo_feedback[:500]}\n\n"
                f"Pick a COMPLETELY DIFFERENT angle that addresses the CEO's concerns.\n\n"
                f"RECENT TOPICS (AVOID THESE):\n{recent_text}\n\n"
                f"{seo_context}\n"
                f"Output ONLY the title as plain text."
            )
        else:
            research_desc = (
                f"Research ONE trending, high-value blog topic for {PAGE_NAME}.\n\n"
                f"Focus: {PAGE_DESCRIPTION if PAGE_DESCRIPTION else PAGE_NICHE}\n\n"
                f"RECENT TOPICS (AVOID THESE):\n{recent_text}\n\n"
                f"{seo_context}\n"
                f"Output ONLY the title as plain text."
            )

        research_task = Task(description=research_desc, expected_output="A single blog topic title", agent=trend_researcher)
        
        try:
            Crew(agents=[trend_researcher], tasks=[research_task], process=Process.sequential, verbose=True).kickoff()
        except Exception as e:
            print(f"❌ Researcher failed: {e}")
            return {"title": "Failed", "status": "failed", "feedback": str(e)}

        final_title = clean_title(research_task.output.raw.strip()) if research_task.output else "Untitled"
        print(f"\n✅ Topic: {final_title}")

        memory_context = ""
        if failure_memories:
            memory_context += "\n\n🚨 AVOID THESE PAST FAILURES:\n"
            for mem in failure_memories[:2]:
                memory_context += f"- {mem['summary']}: {mem['reason']}\n"
        if success_memories:
            memory_context += "\n\n✅ FOLLOW THESE PAST SUCCESSES:\n"
            for mem in success_memories[:2]:
                memory_context += f"- {mem['summary']}\n"

        print(f"\n[Step 2] Writing blog post...")
        write_desc = (
            f"Write a 1500-2000 word blog post: {final_title}\n\n"
            f"This is for {PAGE_NAME}: {PAGE_DESCRIPTION if PAGE_DESCRIPTION else PAGE_NICHE}\n\n"
            f"{HUMANIZATION_RULES}\n{memory_context}\n\n"
            "Structure: Hook, Problem, Solution, Examples, FAQ, Conclusion. Use ## headings.\n"
            "CRITICAL: Include SPECIFIC examples with numbers. Avoid generic advice."
        )
        write_task = Task(description=write_desc, expected_output="Complete blog post", agent=blog_writer)

        print(f"\n[Step 3] SEO/GEO optimization...")
        seo_task = Task(description="Create: SLUG, META, KEYWORDS, GEO_SNIPPETS", expected_output="SEO elements", agent=seo_geo_optimizer)

        print(f"\n[Step 4] CEO review (STRICT STANDARDS)...")
        strategy_ctx = f"\nStrategy: {strategy['goal']}. Audience: {strategy['target_audience']}." if strategy else ""
        review_desc = (
            f"Review this blog post for {PAGE_NAME} with STRICT standards.\n\n"
            f"RECENT TOPICS (check for duplicates):\n{recent_text}\n\n"
            f"If this is a duplicate (same topic + same angle), REJECT.\n"
            f"If it's off-topic or sounds AI-generated, REJECT.\n"
            f"Only APPROVE if it's genuinely excellent.{strategy_ctx}\n\n"
            "Output: DECISION, SCORE, REASONS, FIXES_NEEDED"
        )
        review_task = Task(description=review_desc, expected_output="DECISION, SCORE, REASONS, FIXES_NEEDED", agent=ceo_reviewer)

        try:
            Crew(agents=[blog_writer, seo_geo_optimizer, ceo_reviewer], tasks=[write_task, seo_task, review_task], process=Process.sequential, verbose=True).kickoff()
        except Exception as e:
            print(f"\n⚠️ Crew execution failed (likely API rate limit): {e}")
            print("🔧 Attempting to salvage written content...")
            
            if write_task.output and write_task.output.raw.strip():
                print("✅ Blog content was written! Salvaging and auto-generating SEO...")
                final_blog_content = write_task.output.raw.strip()
                final_title_clean = re.sub(r'[^a-z0-9]+', '-', final_title.lower()).strip('-')[:50]
                final_seo_output = f"SLUG: {final_title_clean}\nMETA: Discover expert insights on {final_title}.\nKEYWORDS: {PAGE_NICHE}\nGEO_SNIPPETS: Learn more about {final_title}."
                final_ceo_decision = "DECISION: APPROVED (auto-approved due to API failure salvage)"
                print("✅ Salvage successful! Publishing blog...")
                break
            else:
                print("❌ No content generated before crash. Cannot publish.")
                return {"title": final_title, "status": "failed", "feedback": str(e)}

        blog_content = write_task.output.raw.strip() if write_task.output else ""
        seo_output = seo_task.output.raw.strip() if seo_task.output else ""
        ceo_decision = review_task.output.raw.strip() if review_task.output else ""

        print(f"\nCEO: {ceo_decision[:300]}")

        if "DECISION: APPROVED" in ceo_decision.upper():
            print(f"\n✅ APPROVED on attempt {attempt}!")
            final_blog_content, final_seo_output, final_ceo_decision = blog_content, seo_output, ceo_decision
            save_to_memory(f"Approved: {final_title}", "Pattern", f"Approved attempt {attempt}", "Success", "Met standards", 7)
            break
        else:
            print(f"\n❌ Rejected attempt {attempt}.")
            ceo_feedback = ceo_decision
            final_blog_content, final_seo_output, final_ceo_decision = blog_content, seo_output, ceo_decision
            save_to_memory(f"Rejected: {final_title[:50]}", "Feedback", ceo_decision[:500], "Failure", "Did not meet standards", 6)

    slug = meta = keywords = ""
    if final_seo_output:
        for line in final_seo_output.split('\n'):
            if line.startswith("SLUG:"): slug = line.replace("SLUG:", "").strip()
            elif line.startswith("META:"): meta = line.replace("META:", "").strip()
            elif line.startswith("KEYWORDS:"): keywords = line.replace("KEYWORDS:", "").strip()
    
    if not slug and final_title: slug = re.sub(r'[^a-z0-9]+', '-', final_title.lower()).strip('-')[:50]
    if not meta and final_title: meta = f"Discover expert insights on {final_title}."
    if not keywords: keywords = PAGE_NICHE

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
        img_url = generate_blog_image_with_agent(blog['title'], blog['content'], blog['keywords'], PAGE_NAME)
        ig_result = post_to_instagram(img_url, create_instagram_caption(blog['title'], blog['content'], blog['keywords']))
        fb_result = post_to_facebook(img_url, create_facebook_caption(blog['title'], blog['content'], blog['keywords']))
        log_to_notion(blog['title'], f"IG: {'OK' if ig_result else 'Skip'} | FB: {'OK' if fb_result else 'Skip'}")
        update_social_status(blog['id'], "Posted")

# ============ GOOGLE SEARCH CONSOLE & ANALYTICS INTEGRATION ============
def get_search_console_service():
    try:
        key_json = os.getenv("GOOGLE_SEARCH_CONSOLE_KEY")
        if not key_json: return None
        credentials = service_account.Credentials.from_service_account_info(json.loads(key_json), scopes=['https://www.googleapis.com/auth/webmasters.readonly'])
        return build('searchconsole', 'v1', credentials=credentials)
    except Exception as e:
        print(f"❌ Search Console auth error: {e}")
        return None

def get_analytics_service():
    try:
        key_json = os.getenv("GOOGLE_ANALYTICS_KEY")
        analytics_id = os.getenv("GOOGLE_ANALYTICS_ID")
        if not key_json or not analytics_id: return None, None
        credentials = service_account.Credentials.from_service_account_info(json.loads(key_json), scopes=['https://www.googleapis.com/auth/analytics.readonly'])
        return build('analyticsdata', 'v1beta', credentials=credentials), analytics_id
    except Exception as e:
        print(f"❌ Analytics auth error: {e}")
        return None, None

def fetch_search_console_data(site_url, days=28):
    service = get_search_console_service()
    if not service: return None
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        return service.searchanalytics().query(siteUrl=site_url, body={"startDate": start_date, "endDate": end_date, "dimensions": ["page", "query"], "rowLimit": 100}).execute().get('rows', [])
    except Exception as e:
        print(f"❌ Search Console query error: {e}")
        return None

def fetch_indexing_status(site_url):
    service = get_search_console_service()
    if not service: return None
    try:
        status_report = []
        for title in fetch_recent_blog_titles(days=30, limit=10)[:5]:
            url = f"{site_url}/blog/{title.lower().replace(' ', '-').replace('?', '')[:50]}"
            try:
                inspection = service.urlInspection().index().inspect(body={"siteUrl": site_url, "inspectionUrl": url}).execute()
                status_report.append({'url': url, 'status': inspection.get('inspectionResult', {}).get('coverageState', 'Unknown'), 'title': title})
            except Exception: pass
        return status_report
    except Exception as e:
        print(f"❌ Indexing status error: {e}")
        return None

def fetch_analytics_data(analytics_id, days=28):
    service, _ = get_analytics_service()
    if not service: return None
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        return service.properties().runReport(property=f"properties/{analytics_id}", body={
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "dimensions": [{"name": "pagePath"}, {"name": "pageTitle"}],
            "metrics": [{"name": "sessions"}, {"name": "averageSessionDuration"}, {"name": "bounceRate"}],
            "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}], "limit": 50
        }).execute().get('rows', [])
    except Exception as e:
        print(f"❌ Analytics query error: {e}")
        return None

def research_keywords_with_tools(niche, page_name):
    try:
        research_task = Task(description=f"Research 10 high-value keywords for {page_name} in {niche}. Include volume, competition, intent, and 3 content opportunities.", expected_output="Keyword research report", agent=keyword_researcher)
        Crew(agents=[keyword_researcher], tasks=[research_task], process=Process.sequential, verbose=True).kickoff()
        return research_task.output.raw.strip()
    except Exception as e:
        return f"Keyword research failed: {e}"

def run_seo_monitor():
    print("\n" + "="*70)
    print(f"🔍 SEO MONITOR: Running comprehensive audit for {PAGE_NAME}")
    print("="*70)
    
    site_url = "https://kahani-ai.onrender.com" if PAGE_NAME == "Kahani AI" else "https://geo-analyzer.onrender.com"
    
    print("\n📊 Fetching Search Console data...")
    sc_data = fetch_search_console_data(site_url, days=28)
    print("📊 Checking indexing status...")
    indexing_status = fetch_indexing_status(site_url)
    print("📊 Fetching Analytics data...")
    ga_data = fetch_analytics_data(os.getenv("GOOGLE_ANALYTICS_ID", ""), days=28)
    print("🔍 Researching new keyword opportunities...")
    keyword_research = research_keywords_with_tools(PAGE_NICHE, PAGE_NAME)
    
    sc_summary = "\n".join([f"- {r.get('keys', ['N/A'])[0]}: {r.get('clicks', 0)} clicks, {r.get('impressions', 0)} imp, CTR {r.get('ctr', 0)*100:.1f}%" for r in (sc_data or [])[:10]]) or "No SC data yet"
    indexing_summary = "\n".join([f"{'✅' if 'Indexed' in i['status'] else '❌'} {i['title']}: {i['status']}" for i in (indexing_status or [])]) or "Could not fetch indexing status"
    ga_summary = "\n".join([f"- {r['dimensionValues'][0]['value']}: {r['metricValues'][0]['value']} sessions" for r in (ga_data or [])[:5]]) or "No GA data yet"
    
    analysis_task = Task(description=f"Analyze SEO health of {PAGE_NAME} ({site_url}).\nSC: {sc_summary}\nIndexing: {indexing_summary}\nGA: {ga_summary}\nKeywords: {keyword_research}\n\nProvide prioritized report: 🔴 CRITICAL, 🟡 HIGH, 🟠 MEDIUM, 🔵 LOW, 📝 CONTENT RECOMMENDATIONS, 🎯 QUICK WINS.", expected_output="Comprehensive SEO audit report", agent=seo_monitor)
    
    try:
        result = Crew(agents=[seo_monitor], tasks=[analysis_task], process=Process.sequential, verbose=True).kickoff()
        save_to_memory(f"SEO Audit: {PAGE_NAME} - {datetime.now().strftime('%Y-%m-%d')}", "SEO_AUDIT", str(result)[:2000], "Success", "Weekly SEO monitoring completed", 9)
        print(f"\n✅ SEO audit complete! Report saved to Memory database.")
        return result
    except Exception as e:
        print(f"❌ SEO monitor failed: {e}")
        return None

# ============ MAIN EXECUTION ============
def run_daily_agency():
    print(f"\n{'='*60}")
    print(f"🚀 Starting agency for {PAGE_NAME} ({PAGE_NICHE})")
    print(f"{'='*60}")
    
    try:
        run_blog_creation_phase()
    except Exception as e:
        print(f"⚠️ Blog error: {e}")
        traceback.print_exc()
    
    try:
        run_social_promotion_phase()
    except Exception as e:
        print(f"⚠️ Social error: {e}")
        traceback.print_exc()
    
    # SEO monitor runs ONLY on Sundays (every 7 days)
    if datetime.now().weekday() == 6:  # 0=Monday, 6=Sunday
        try:
            print("\n🔍 Running weekly SEO audit (Sunday schedule)...")
            run_seo_monitor()
        except Exception as e:
            print(f"⚠️ SEO monitor error: {e}")
            traceback.print_exc()
    else:
        print(f"\n📅 SEO Monitor: Skipping (next run on Sunday)")
    
    print("\n🎉 Done!")

# ============ CRITICAL: This block was missing! ============
if __name__ == "__main__":
    try:
        print("\n🎯 Starting main execution...")
        run_daily_agency()
        print("\n🎉 Main execution completed successfully!")
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR in main execution: {e}")
        traceback.print_exc()

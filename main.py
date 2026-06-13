import requests
import base64
import cloudinary
import cloudinary.uploader
import openai
import replicate
from niche_engine import ( 
    NicheEngine, classify_niche, generate_dynamic_profile, get_page_variant,
    _get_business_tokens, _hue_shift, get_section_order,
    NICHE_PROFILES, NICHE_MAP, get_section_bg, niche_font_import, BG_COLORS
)
from mode1_landing_engine import build_mode1_landing_page
import anthropic
import json
import random
import sys
from html import escape
import re
import os
import time
from datetime import datetime
from collections import defaultdict
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# ==============================================================================
# 🔗 NEW IMPORTS FOR BACKLINKS
# ==============================================================================
import os.path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ==============================================================================
# 🛡️ SYSTEM SETUP & CONFIGURATION
# ==============================================================================
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

print("=" * 80)
print(" 🚀 UNIVERSAL WORDPRESS GENERATOR V7.0 - GITHUB ACTIONS EDITION")
print(" 💎 ALL ISSUES FIXED: CSS Grids, Image Model Selection, Prompt Contexts")
print(" 💎 ENHANCED SEO: Related Keywords, Entities, Rich Snippets")
print(" 💎 MOBILE HERO: Form ALWAYS visible - 100% guaranteed with short placeholders")
print(" 💎 GRID FIX: Strict 3-col Desktop, 2-col Tablet, 1-col Mobile (No Inline Overrides)")
print(" 💎 MENU TEXT: Properly shortened to 2-3 words max")
print(" 💎 IMAGE CONTEXT: Accurate physical labor prompts, NO 'tablets' for trades")
print(" 💎 SEPARATE MENU & FOOTER SYSTEM: Exported as Widgets flawlessly")
print("=" * 80)

class Config:
    # -------------------------------------------------------------------------
    # 🔐 ALL SECRETS FROM ENVIRONMENT — GitHub Secrets se aayenge
    # Local testing: terminal me 'export OPENAI_API_KEY=...' set karein
    # -------------------------------------------------------------------------
    OPENAI_API_KEY        = os.environ.get("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
    REPLICATE_API_TOKEN   = os.environ.get("REPLICATE_API_TOKEN", "")

    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY    = os.environ.get("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")

    DEVTO_API_KEY         = os.environ.get("DEVTO_API_KEY", "")
    BLOGGER_ID            = None

    # -------------------------------------------------------------------------
    # 🌐 WORDPRESS TARGET — URL/User config.json se override honge (run_generator me)
    # App Password SIRF environment/Secret se — kabhi config.json me nahi!
    # -------------------------------------------------------------------------
    WP_URL          = os.environ.get("WP_URL", "")
    WP_USER         = os.environ.get("WP_USER", "")
    WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")

    # 🌍 MASTER LOCATIONS LIST
    LOCATIONS = []

    # IMAGE MODEL SELECTION
    IMAGE_MODEL = "hybrid"   # config.json se override hoga
    PHOTO_MODEL = "replicate"
    LOGO_MODEL  = "openai"

    # RATE LIMIT PROTECTION
    REPLICATE_REQUEST_DELAY = 20

    # DATA TRACKING (apna Apps Script / Netlify proxy URL — env se)
    GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL", "")

    # DYNAMIC PATH SETTING
    SERVICE_BASE_PATH = "/services/"

    # GLOBAL LANGUAGE PREFIX ROUTING
    LANG_PREFIX = ""

    # MODELS — Claude-first, OpenAI fallback (repo standard)
    CLAUDE_MODEL    = "claude-sonnet-4-6"
    MODEL_HIGH_TIER = "gpt-4o"
    MODEL_LOW_TIER  = "gpt-4o-mini"
    API_DELAY   = 2
    MAX_RETRIES = 3
    IMAGE_QUALITY = 90

    SITE_URL = ""   # run_generator me WP_URL se set hoga

    # BACKLINK & INTERNAL LINKS CONTROLS
    GENERATE_BACKLINKS      = False
    GENERATE_INTERNAL_LINKS = True

    # LOGO SETTINGS
    LOGO_URL    = ""
    LOGO_WIDTH  = "200"
    LOGO_HEIGHT = "80"

    # HUB MODE TARGET URL
    HUB_TARGET_URL = ""

    # SOCIAL MEDIA LINKS
    SOCIAL_LINKS = {
        "facebook": "", "twitter": "", "instagram": "",
        "linkedin": "", "youtube": "", "pinterest": ""
    }

    # ENTITY CACHE
    ENTITY_CACHE = {}

# ==============================================================================
# 🛠️ HELPER FUNCTIONS
# ==============================================================================
# <<< NEW SEO & RTL HELPERS - PASTE ABOVE strip_markdown >>>
def get_language_direction(lang_code):
    """Determine if a language code requires RTL layout."""
    rtl_languages = ['ar', 'he', 'ur', 'fa']
    if any(lang_code.lower().startswith(rtl) for rtl in rtl_languages):
        return 'rtl'
    return 'ltr'

def extract_keyword_tiers(b_data, service_name, industry, location, target_lang="en"):
    """3-tier SEO keywords — Claude-powered (real search-intent), OpenAI fallback. Cached per service."""
    cache_key = f"keyword_tiers_{service_name}_{industry}_{location}_{target_lang}"
    if cache_key in Config.ENTITY_CACHE:
        return Config.ENTITY_CACHE[cache_key]

    current_year = datetime.now().year
    fallback = {
        "high_intent": [f"{service_name} {location}".lower(), f"best {service_name} {location}".lower(),
                        f"emergency {service_name} near me".lower()],
        "semantic": [f"{service_name} cost", f"professional {service_name} service",
                     f"{service_name} maintenance"],
        "local_time": [f"{service_name} {location} {current_year}".lower(),
                       f"24/7 {service_name} {location}".lower()]
    }

    lang_names = {"en": "English", "ar": "Arabic", "es": "Spanish", "fr": "French", "de": "German"}
    lang_name = lang_names.get(target_lang, "English") + (" (native script)" if target_lang == 'ar' else "")
    prompt = f"""You are a local-SEO keyword strategist for service businesses.
Generate the exact keyword tiers a top agency would target for ONE page.

SERVICE: {service_name}
INDUSTRY: {industry}
LOCATION: {location}
LANGUAGE: {lang_name} — every keyword in this language
YEAR: {current_year}

TIERS (5 keywords each):
1. "high_intent": money keywords a ready-to-buy customer types into Google.
   Patterns: "[service] [city]", "best/cheap/emergency/same-day [service] [city]",
   "[service] near me". Lowercase, exactly how people type.
2. "semantic": LSI/topic terms Google associates with this service — real parts,
   symptoms, sub-jobs, techniques (e.g. for fridge repair: "compressor replacement",
   "fridge not cooling", "gas refilling"). NOT generic words like "techniques".
3. "local_time": geo + time modifiers — "[service] [city] {current_year}",
   "24/7 [service] [city]", "[service] open now", weekend/holiday variants.

HARD RULES:
- Every keyword unique, max 6 words, no brand names, no quotes inside keywords.
- Only phrases a real human would type into Google. If it sounds like AI filler, drop it.

Return ONLY JSON:
{{"high_intent": ["..."], "semantic": ["..."], "local_time": ["..."]}}"""

    # 1st choice: Claude (best intent understanding)
    try:
        content = call_claude_json(prompt, "You are an SEO keyword strategist. Output only valid JSON.")
        if content and content.get('high_intent'):
            Config.ENTITY_CACHE[cache_key] = content
            return content
    except Exception:
        pass

    # 2nd choice: OpenAI fallback
    if CLIENTS.get('openai'):
        try:
            response = CLIENTS['openai'].chat.completions.create(
                model=Config.MODEL_HIGH_TIER,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}, temperature=0.5)
            content = clean_json_response(response.choices[0].message.content)
            if content and content.get('high_intent'):
                Config.ENTITY_CACHE[cache_key] = content
                return content
        except Exception:
            pass

    Config.ENTITY_CACHE[cache_key] = fallback
    return fallback

def generate_seo_title_with_year(service_name, location, business_name, year=None):
    """Generate time-sensitive SEO title with current year"""
    year = year or datetime.now().year
    clean_srv = clean_title(service_name)
    variations = [
        f"Best {clean_srv} in {location} - {year}",
        f"Professional {clean_srv} Services {location} | {business_name}",
        f"{clean_srv} Experts in {location} - 24/7 Service {year}"
    ]
    return random.choice(variations)
# <<< END NEW HELPERS >>>
def strip_markdown(text):
    """Remove markdown formatting from text."""
    if not isinstance(text, str):
        return text
    text = re.sub(r'\*\*|__|##|###|---', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    return text.strip()
def clean_schema_text(text, limit=155):
    """Strips HTML and safely shortens text for Schema without cutting words in half."""
    if not text: return ""
    clean = re.sub(r'<[^>]+>', '', str(text)).strip()
    if len(clean) <= limit: return clean
    return clean[:limit].rsplit(' ', 1)[0] + '...'
def clean_json_response(raw_text):
    """Clean and parse JSON from AI response."""
    try:
        if not raw_text:
            return None
        clean_text = re.sub(r'```json\s*', '', raw_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'```', '', clean_text)
        
        # 🛡️ FIX: Support both JSON Objects {...} and JSON Arrays [...]
        start_obj = clean_text.find('{')
        start_arr = clean_text.find('[')
        
        if start_obj != -1 and (start_arr == -1 or start_obj < start_arr):
            start = start_obj
            end = clean_text.rfind('}') + 1
        elif start_arr != -1:
            start = start_arr
            end = clean_text.rfind(']') + 1
        else:
            return None
            
        if start != -1 and end != 0:
            json_str = clean_text[start:end]
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            return json.loads(json_str.strip())
        return None
    except:
        return None

def call_claude_json(prompt, system_prompt="You are an elite SEO copywriter. Always output valid JSON."):
    """Helper function to call Claude and return parsed JSON.
    RESILIENT: 4 attempts with growing delay (3s/6s/9s) — survives net blips,
    rate limits, and overloaded errors."""
    if not CLIENTS.get('claude'):
        return None
    for _attempt in range(4):
        try:
            message = CLIENTS['claude'].messages.create(
                model=Config.CLAUDE_MODEL,
                max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt + "\n\nCRITICAL: Return ONLY valid JSON. No markdown blocks outside the JSON."}]
            )
            return clean_json_response(message.content[0].text)
        except Exception as e:
            _wait = 3 * (_attempt + 1)
            print(f"   ⚠️ Claude API Error (attempt {_attempt+1}/4): {str(e)[:90]}")
            if _attempt < 3:
                print(f"      ⏳ Retrying in {_wait}s...")
                time.sleep(_wait)
    return None

def slugify(text):
    """Convert text to URL-friendly slug."""
    if not text:
        return ""
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')

def clean_title(text, b_data=None):
    """Clean and title case text."""
    if not text:
        return ""
    text_str = str(text).replace("-", " ").replace("_", " ").strip()
    text_str = strip_markdown(text_str)
    words = text_str.split()
    title_words = []
    for word in words:
        if word.isupper() and len(word) > 1:
            title_words.append(word)
        else:
            title_words.append(word.title())
    return " ".join(title_words)
def get_dynamic_icon(text):
    """Automatically assigns a highly relevant MDI (Iconify) Icon based on the service name."""
    t = text.lower()
    if any(x in t for x in ['plumb', 'pipe', 'water', 'leak']): return "mdi:water"
    if any(x in t for x in ['elect', 'light', 'wire', 'panel', 'power', 'volt']): return "mdi:lightning-bolt"
    if any(x in t for x in ['ac', 'hvac', 'cool', 'heat', 'air', 'duct']): return "mdi:snowflake"
    if any(x in t for x in ['clean', 'wash', 'sweep', 'maid', 'pest']): return "mdi:spray"
    if any(x in t for x in ['roof', 'build', 'construct', 'remodel', 'floor']): return "mdi:home-roof"
    if any(x in t for x in ['health', 'medic', 'spa', 'clinic', 'skin', 'therapy', 'laser', 'facial']): return "mdi:medical-bag"
    if any(x in t for x in ['auto', 'car', 'mechanic', 'repair']): return "mdi:car-wrench"
    if any(x in t for x in ['seo', 'market', 'web', 'design', 'digital']): return "mdi:bullseye-arrow"
    if any(x in t for x in ['law', 'legal', 'attorney']): return "mdi:scale-balance"
    if any(x in t for x in ['security', 'lock', 'safe']): return "mdi:shield-check"
    if any(x in t for x in ['smart', 'home', 'automation']): return "mdi:chip"
    if any(x in t for x in ['data', 'analytics']): return "mdi:database"
    if any(x in t for x in ['creative', 'art', 'draw']): return "mdi:palette"
    
    # A beautiful, solid default MDI icon instead of the hollow rectangle!
    return "mdi:check-circle"
def shorten_menu_text(text, max_words=2):
    """Shorten menu text for cleaner display."""
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text
    shortened = " ".join(words[:max_words])
    return shortened

def detangle_urls(raw_text):
    """Extract URLs and clean them."""
    if not raw_text:
        return []
    cleaned = raw_text.replace("https://", "\nhttps://").replace("http://", "\nhttp://")
    urls = []
    for line in cleaned.split('\n'):
        line = line.strip()
        if line and ('http://' in line or 'https://' in line):
            parts = line.split('/')
            if len(parts) > 3:
                for part in reversed(parts):
                    if part and part not in ['www.', '']:
                        urls.append(part)
                        break
    return urls

def validate_url(url_type, slug, mode, dummy_data=None):
    """
    💎 THE SINGLE SOURCE OF TRUTH FOR ALL URLS.
    Ensures a 100% match with published WP permalinks (Menu, Footer, Internal Links, Schema, Canonical).
    Prevents 404s across all languages by perfectly mimicking WordPress URL hierarchy.
    """
    prefix_raw = getattr(Config, 'LANG_PREFIX', "")
    prefix = prefix_raw.replace('/', '') 
    
    # Base path logic crucial for Mode 2 (Hub setup)
    base_path = getattr(Config, 'SERVICE_BASE_PATH', "/services/")
    if not base_path.startswith('/'): base_path = '/' + base_path
    if not base_path.endswith('/'): base_path = base_path + '/'

    if url_type == "home":
        return f"/{prefix}home/" if prefix else "/"
        
    elif url_type in ["services_index", "categories_index"]:
        if str(mode) == "2": return base_path
        return f"/{prefix}services/" if prefix else "/services/"
        
    elif url_type == "contact":
        return f"/{prefix}contact/"
        
    elif url_type == "about":
        return f"/{prefix}about/"
        
    elif url_type == "blog":
        return f"/{prefix}blog/"
        
    elif url_type == "category" and slug:
        return f"/{prefix}{slugify(slug)}/"
        
    elif url_type == "service" and slug:
        # 🛡️ FIX: Strip "Services" from the slug to prevent URL bloat
        clean_slug = re.sub(r'(?i)\s+services?$', '', slug).strip()
        
        if str(mode) == "3":
            rel = get_service_relationships(clean_slug)
            cat = rel.get('category')
            if cat and cat != "General":
                parent_slug = f"{prefix}{slugify(cat)}"
                return f"/{parent_slug}/{slugify(clean_slug)}/"
        elif str(mode) == "2":
            return f"{base_path}{slugify(clean_slug)}/"
            
        return f"/{prefix}{slugify(clean_slug)}/"
    return "/"
def retry_operation(max_retries=3, delay=2):
    """Decorator for retrying operations on failure."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    wait = delay * (attempt + 1)
                    print(f"   ⚠️ [Retry {attempt + 1}/{max_retries}] {func.__name__}: {str(e)[:100]}. Waiting {wait}s...")
                    time.sleep(wait)
            print(f"   ❌ {func.__name__} failed completely.")
            return None
        return wrapper
    return decorator

# ==============================================================================
# 🔧 API CLIENT INITIALIZATION
# ==============================================================================
def init_clients():
    """Initializes all external API clients with error handling."""
    clients = {}
    
    # OpenAI
    if Config.OPENAI_API_KEY and "sk-" in Config.OPENAI_API_KEY:
        try:
            clients['openai'] = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
            print("✅ OpenAI Client Initialized")
        except Exception as e:
            print(f"⚠️ OpenAI Error: {e}")
            clients['openai'] = None
    else:
        clients['openai'] = None
        print("⚠️ OpenAI API Key missing.")

    # Claude (Anthropic) — content generation primary engine
    if Config.ANTHROPIC_API_KEY:
        try:
            clients['claude'] = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
            print("✅ Claude Client Initialized")
        except Exception as e:
            print(f"⚠️ Claude Error: {e}")
            clients['claude'] = None
    else:
        clients['claude'] = None
        print("⚠️ Anthropic API Key missing — OpenAI fallback active.")

    # Replicate
    if Config.REPLICATE_API_TOKEN and "r8_" in Config.REPLICATE_API_TOKEN:
        os.environ["REPLICATE_API_TOKEN"] = Config.REPLICATE_API_TOKEN
        try:
            clients['replicate'] = True
            print("✅ Replicate API Configured")
        except Exception as e:
            print(f"⚠️ Replicate Test Failed: {e}")
            clients['replicate'] = False
    else:
        clients['replicate'] = False
        print("⚠️ Replicate API Token missing.")

    # Cloudinary
    try:
        if Config.CLOUDINARY_CLOUD_NAME:
            cloudinary.config(
                cloud_name=Config.CLOUDINARY_CLOUD_NAME,
                api_key=Config.CLOUDINARY_API_KEY,
                api_secret=Config.CLOUDINARY_API_SECRET,
                secure=True
            )
            print("✅ Cloudinary Configured")
            clients['cloudinary'] = True
        else:
            print("⚠️ Cloudinary keys missing.")
            clients['cloudinary'] = False
    except Exception as e:
        print(f"⚠️ Cloudinary Error: {e}")
        clients['cloudinary'] = False
        
    return clients

CLIENTS = init_clients()

# ==============================================================================
# 🎨 NICHE-AWARE DESIGN PROFILE SYSTEM — now imported from niche_engine.py
# ==============================================================================

# Data Caches
IMAGE_CACHE = {} 
ZIGZAG_CONTENT_CACHE = {}
CATEGORY_IMAGE_CACHE = {}
SERVICE_FAQS_CACHE = {}
LAYOUT_STYLES_CACHE = {}
HERO_DROPDOWN_CACHE = []  
SERVICE_HIERARCHY = {}
LAST_REPLICATE_REQUEST = 0

# ==============================================================================
# 🎨 LOGO GENERATION
# ==============================================================================
@retry_operation(max_retries=2)
def generate_logo(b_data, output_folder=""):
    """
    ADVANCED AI LOGO GENERATOR: Dynamically injects brand colors and uses 
    premium vector-style prompting for flawless, responsive desktop/mobile logos.
    """
    logo_url = ""
    business_name = b_data.get('name', 'Company')
    industry = b_data.get('industry', 'Business')
    
    # Extract actual brand colors from your generator's state
    primary_color = b_data.get('primary', '#1A73E8')
    accent_color = b_data.get('accent', '#FFB300')
    
    # Master prompt engineered specifically to prevent 3D mockups and force clean vector branding
    pro_logo_prompt = (
        f"A premium, modern minimalist corporate logo for a {industry} company named '{business_name}'. "
        f"Design style: Flat vector graphic, clean geometric lines, highly professional, designed by a top branding agency. "
        f"Color palette: Strictly uses {primary_color} as the primary color and {accent_color} as the secondary accent. "
        f"Background: Pure solid white background. "
        f"CRITICAL: No 3D effects, no shadows, no physical mockups (do not put the logo on a wall or paper), no gradients. "
        f"The logo must be perfectly centered and clearly legible."
        ) # <--- ADDED MISSING PARENTHESIS
    if CLIENTS.get('openai'):
        try:
            print(f"   🎨 Generating PRO Logo with GPT-Image-2...")
            
            response = CLIENTS['openai'].images.generate(
                model="gpt-image-2",
                prompt=pro_logo_prompt,
                size="1024x1024",
                quality="medium",
                n=1
            )
            
            if response and response.data and len(response.data) > 0:
                b64 = getattr(response.data[0], 'b64_json', None)
                if b64:
                    image_url = f"data:image/png;base64,{b64}"
                else:
                    image_url = response.data[0].url
                
                if image_url and CLIENTS.get('cloudinary'):
                    # Standardized responsive cropping for Desktop and Mobile compatibility
                    res = cloudinary.uploader.upload(
                        image_url,
                        folder="static_website/logos",
                        public_id=f"logo_{slugify(business_name)}_{int(time.time())}",
                        quality=90,
                        format="png",
                        transformation=[
                            {"width": 600, "crop": "limit"}, # Perfect max-width for retina displays
                            {"quality": "auto:best"},
                            {"fetch_format": "auto"}
                        ]
                    )
                    logo_url = res.get('secure_url', image_url)
                    print(f"   ✅ PRO Logo generated with GPT-Image-2: {logo_url[:50]}...")
                    return logo_url
                    
        except Exception as e:
            print(f"   ⚠️ DALL-E 3 logo generation failed: {e}")
    
    # Fallback to Replicate if GPT fails, using the same master prompt
    if not logo_url and CLIENTS.get('replicate') and CLIENTS.get('cloudinary'):
        try:
            print(f"   🎨 Attempting PRO Logo generation with Replicate FLUX...")
            
            global LAST_REPLICATE_REQUEST
            elapsed = time.time() - LAST_REPLICATE_REQUEST
            if elapsed < Config.REPLICATE_REQUEST_DELAY:
                time.sleep(Config.REPLICATE_REQUEST_DELAY - elapsed)
            
            output = replicate.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": pro_logo_prompt,
                    "aspect_ratio": "1:1",
                    "output_format": "png",
                    "output_quality": 90,
                    "go_fast": True,
                    "num_inference_steps": 4
                }
            )
            LAST_REPLICATE_REQUEST = time.time()
            
            image_url = None
            if output:
                if isinstance(output, list) and len(output) > 0:
                    image_url = str(output[0])
                elif isinstance(output, str):
                    image_url = output
            
            if image_url:
                res = cloudinary.uploader.upload(
                    image_url,
                    folder="static_website/logos",
                    public_id=f"logo_{slugify(business_name)}_{int(time.time())}",
                    quality=90,
                    format="png",
                    transformation=[
                        {"width": 600, "crop": "limit"},
                        {"quality": "auto:best"},
                        {"fetch_format": "auto"}
                    ]
                )
                logo_url = res.get('secure_url', image_url)
                print(f"   ✅ PRO Logo generated with Replicate: {logo_url[:50]}...")
                return logo_url
                
        except Exception as e:
            print(f"   ⚠️ Replicate logo generation failed: {e}")
    
    # Ultimate Fallback: Industry-specific Iconify icons colored to match branding
    if not logo_url:
        industry_lower = industry.lower()
        icon_name = "mdi:tools" # Default
        
        if any(x in industry_lower for x in ['plumb', 'pipe']): icon_name = "mdi:pipe-wrench"
        elif any(x in industry_lower for x in ['elect', 'light']): icon_name = "mdi:lightning-bolt"
        elif any(x in industry_lower for x in ['hvac', 'heat', 'cool']): icon_name = "mdi:air-conditioner"
        elif any(x in industry_lower for x in ['roof']): icon_name = "mdi:home-roof"
        elif any(x in industry_lower for x in ['paint']): icon_name = "mdi:format-paint"
        elif any(x in industry_lower for x in ['clean']): icon_name = "mdi:broom"
        elif any(x in industry_lower for x in ['lock']): icon_name = "mdi:lock"
        elif any(x in industry_lower for x in ['mechanic', 'auto']): icon_name = "mdi:car-wrench"
        elif any(x in industry_lower for x in ['dent', 'teeth']): icon_name = "mdi:tooth"
        elif any(x in industry_lower for x in ['medic', 'doctor', 'health']): icon_name = "mdi:medical-bag"
        elif any(x in industry_lower for x in ['law', 'attorney', 'legal']): icon_name = "mdi:scale-balance"
        elif any(x in industry_lower for x in ['seo', 'market', 'digital']): icon_name = "mdi:chart-line"
        elif any(x in industry_lower for x in ['beauty', 'salon', 'spa']): icon_name = "mdi:content-cut"
        
        # Output clean Iconify span styling it with the brand's primary color
        logo_url = f'<span class="iconify" data-icon="{icon_name}" data-width="45" data-height="45" style="color: {primary_color};"></span>'
        print(f"   ℹ️ Using industry-specific icon fallback: {icon_name}")
        
    return logo_url
# ==============================================================================
# 🖼️ PERFECT UNIVERSAL IMAGE ENGINE V12 (PRO ENVIRONMENT SPLIT + VISION INSPECTOR)
# ==============================================================================
import time
import random

# Caches
VISUAL_CONTEXT_CACHE = {}
# Assuming IMAGE_CACHE and CATEGORY_IMAGE_CACHE are defined elsewhere in your globals

def detect_business_context(industry, service_name="", context_mode="hero"):
    """
    UNIVERSAL VISUAL DIRECTOR: Uses AI to dynamically generate hyper-specific, relevant constraints.
    💎 FIXED: Forces Full-Body wide shots to prevent "just legs" or cut-off heads.
    """
    clean_ind = str(industry).lower().strip() if industry else "professional services"
    clean_svc = str(service_name).lower().strip() if service_name else clean_ind
    
    cache_key = f"visual_{clean_ind}_{clean_svc}_{context_mode}"
    if cache_key in VISUAL_CONTEXT_CACHE:
        return VISUAL_CONTEXT_CACHE[cache_key]

    if context_mode == "hero":
        fallback = {
            "subject": f"A smiling, professional {clean_ind} technician interacting with a {clean_svc} unit",
            "framing": "Medium close-up, focusing clearly on the professional's face and interaction",
            "environment": f"A bright, pristine {clean_ind} setting",
            "action": "Smiling warmly and working expertly with the equipment"
        }
    else:
        fallback = {
            "subject": f"A pristine, modern {clean_svc} workspace and professional equipment. No detailed faces.",
            "framing": "Wide architectural environmental shot or close-up on equipment",
            "environment": f"A bright, high-end {clean_ind} facility",
            "action": "Empty room or focus on the professional process and machinery, no people in the foreground"
        }

    if not CLIENTS.get('openai'):
        return fallback

    system_prompt = f"""You are an elite Commercial Photography Director. 
    Design a safe, highly specific photo for a business service.
    
    CRITICAL RULES FOR IMAGE HIERARCHY (Current Mode: '{context_mode}'):
    If mode is 'hero':
    - Subject: Focus on a smiling, professional technician interacting with a unit/equipment.
    - Framing: MUST be a MEDIUM CLOSE-UP.
    - Their face must be the central focus, perfectly visible and welcoming.
    - Specify exact, accurate attire (scrubs for medical, uniforms for trades. NO business suits for physical labor).
    
    If mode is 'grid' or 'zigzag':
    - The ROOM, EQUIPMENT, or WORKSPACE is the primary focus (100% of frame).
    - Describe a wide architectural shot of the environment, machinery, or the professional process itself.
    - Humans should be completely ABSENT, or if present, NO DETAILED FACES should be visible (focus hands/tools instead).
    BANS:
    - NEVER generate cellphones, smartphones, or tablets. 
    - Do NOT use the words 'hands', 'fingers', 'arms', or 'smartphones' in your output to prevent triggering AI hallucination biases.
    
    Output valid JSON exactly matching these keys: subject, framing, environment, action"""

    user_prompt = f"Generate the explicit visual context for Industry: '{clean_ind}', Specific Service: '{clean_svc}'."

    try:
        print(f"   🧠 Generating dynamic visual context ({context_mode}) for {clean_svc[:30]}...")
        dynamic_model = Config.MODEL_HIGH_TIER if context_mode == "hero" else Config.MODEL_LOW_TIER
        response = CLIENTS['openai'].chat.completions.create(
            model=dynamic_model, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=300
        )
        
        context = clean_json_response(response.choices[0].message.content)
        if context and "subject" in context:
            VISUAL_CONTEXT_CACHE[cache_key] = context
            return context
            
    except Exception as e:
        print(f"   ⚠️ Visual Context Generation Error: {e}")

    return fallback

def validate_image_content(image_url, service_name, context_dict):
    """
    THE VISION INSPECTOR: Uses GPT-4o Vision to literally count fingers and verify anatomy.
    💎 UPGRADED: Now aggressively flags missing arms, missing faces, and cellphones.
    """
    if not CLIENTS.get('openai'):
        return True 
    
    try:
        subject = context_dict.get('subject', 'professional')
        prompt = f"""You are a strict Quality Assurance Inspector for commercial photography. 
        Analyze this generated image for a '{service_name}' business. 
        
        CHECK FOR THESE FATAL ERRORS:
        1. MISSING LIMBS: Are there missing arms? Does the person look like an amputee when they shouldn't?
        2. FACELESS: Is the person's face missing, turned completely away awkwardly, cut off, or blurred out into a monster?
        3. HANDS/MUTATIONS: Are there extra arms, three hands, floating limbs, or severe AI mutations?
        4. UNWANTED OBJECTS: Are they holding a glowing cellphone, smartphone, or tablet? (This is strictly banned).
        5. GENDER/ATTIRE MISMATCH: Is there a highly inappropriate grooming or attire mismatch for: '{subject}'?
        
        If ANY of these errors exist, reply EXACTLY with: INVALID - [Specific Reason].
        If the image looks perfectly human, natural, and safe, reply EXACTLY with: VALID.
        """

        response = CLIENTS['openai'].chat.completions.create(
            model=Config.MODEL_LOW_TIER, 
            messages=[
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            max_tokens=50,
            temperature=0.1
        )
        
        result = response.choices[0].message.content.strip().upper()
        if "INVALID" in result:
            print(f"   ❌ Vision Inspector Rejected: {result}")
            return False
            
        print(f"   ✅ Vision Inspector Approved Image!")
        return True
        
    except Exception as e:
        print(f"   ⚠️ Vision API error (passing by default): {e}")
        return True 


def get_composition_and_culture(target_lang="en", context_mode="hero"):
    cultural = "modern Middle Eastern setting, Dubai/UAE professional attire" if target_lang == 'ar' else "modern, professional setting, diverse team, high quality"
    
    compositions = {
        "hero": "8k ultra HD, hyper-realistic, wide cinematic shot, shallow depth of field, professional lighting",
        "grid": "4k professional architectural photography, medium shot, clear flattering light",
        "zigzag": "8k cinematic quality, photorealistic, wide environmental shot, natural bright lighting"
    }
    return cultural, compositions.get(context_mode, compositions["hero"])

# ==============================================================================
# 🖼️ WORDPRESS MEDIA LIBRARY UPLOADER (Cloudinary replacement + compression)
# ==============================================================================
def upload_image_to_wp_media(image_url_or_data, alt_text="", filename_hint="image", quality=82, max_width=1600):
    """
    Downloads/decodes an image (URL or base64 data-uri), compresses it with PIL
    (matches old image_localizer.py behavior — JPEG quality + max-width resize),
    then uploads to WordPress Media Library via REST API.
    Returns the WP-hosted attachment URL (or None on failure).
    """
    try:
        from PIL import Image
        from io import BytesIO

        # 1. Get raw bytes (handle both http URLs and data:image/...;base64 URIs)
        if image_url_or_data.startswith("data:image"):
            b64_part = image_url_or_data.split(",", 1)[1]
            raw_bytes = base64.b64decode(b64_part)
        else:
            resp = requests.get(image_url_or_data, timeout=30)
            resp.raise_for_status()
            raw_bytes = resp.content

        # 2. Open + resize + compress with PIL (mirrors image_localizer.py quality=82)
        img = Image.open(BytesIO(raw_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        out_buffer = BytesIO()
        img.save(out_buffer, format="JPEG", quality=quality, optimize=True)
        out_buffer.seek(0)
        compressed_bytes = out_buffer.getvalue()
        print(f"   📉 Image compressed: {len(raw_bytes)//1024}KB → {len(compressed_bytes)//1024}KB")

        # 3. SEO-friendly filename (mirrors image_localizer.py _make_filename / _slug)
        safe_name = slugify(filename_hint)[:60] or "image"
        filename = f"{safe_name}-{int(time.time())}-{random.randint(100,999)}.jpg"

        # 4. Upload to WP Media Library
        auth = base64.b64encode(f"{Config.WP_USER}:{Config.WP_APP_PASSWORD}".encode()).decode('utf-8')
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/jpeg",
            "User-Agent": "Mozilla/5.0"
        }
        media_url = f"{Config.WP_URL.rstrip('/')}/wp-json/wp/v2/media"
        response = requests.post(media_url, headers=headers, data=compressed_bytes, verify=False, timeout=60)

        if response.status_code == 201:
            media_data = response.json()
            attachment_id = media_data['id']
            source_url = media_data['source_url']

            # 5. Set ALT text for SEO (separate PATCH call)
            if alt_text:
                patch_headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
                requests.patch(
                    f"{media_url}/{attachment_id}",
                    headers=patch_headers,
                    json={"alt_text": alt_text[:120], "title": alt_text[:100]},
                    verify=False, timeout=30
                )

            print(f"   ✅ Uploaded to WP Media Library: {filename}")
            return source_url
        else:
            print(f"   ⚠️ WP Media upload failed: {response.status_code} - {response.text[:150]}")
            return None

    except Exception as e:
        print(f"   ⚠️ Image localization error: {e}")
        return None
@retry_operation(max_retries=3)
def get_hosted_image(prompt_text, context_mode="hero", industry="General", is_category=False, service_name="", category_name="", target_lang="en"):
    """
    PERFECT IMAGE GENERATOR V12 - Natural Language Prompting for FLUX
    """
    service_clean = clean_title(service_name or prompt_text)
    cache_key_base = service_name if service_name else prompt_text
    
    cache_key = f"{cache_key_base}_{industry}_{target_lang}_{Config.IMAGE_MODEL}_{context_mode}".lower()
    
    if cache_key in IMAGE_CACHE:
        print(f"   📸 Using cached image for {service_clean[:25]}...")
        return IMAGE_CACHE[cache_key]

    if is_category and cache_key_base in CATEGORY_IMAGE_CACHE:
        return CATEGORY_IMAGE_CACHE[cache_key_base]

    use_gpt = (
        Config.IMAGE_MODEL == "gpt"
        or Config.IMAGE_MODEL == "openai"
        or (Config.IMAGE_MODEL == "hybrid" and Config.PHOTO_MODEL == "openai")
    )
    
    # 1. Get Context & SEO Keywords
    context = detect_business_context(industry, service_clean, context_mode) 
    cultural, comp = get_composition_and_culture(target_lang, context_mode)
    img_entities = get_related_entities(service_clean, industry, "Global", "en")
    img_keywords = ", ".join(img_entities.get("keywords", [])[:3])
    
    # 💎 FLUX PREFERS NATURAL SENTENCES: We ditched the "Subject: X, Action: Y" format.
    # By making it read like a flowing description, FLUX generates vastly superior, photorealistic images.
    full_prompt = (
        f"A {comp} commercial photography shot. "
        f"{cultural}. "
        f"The main focus is {context.get('subject', service_clean)}. "
        f"They are {context.get('action', 'standing naturally')} in {context.get('environment', 'a professional setting')}. "
        f"Framing: {context.get('framing', 'wide shot')}. "
        f"Visual themes: {img_keywords}. "
        f"Extremely high quality, realistic lighting, pristine, no digital screens."
    )
    
    max_attempts = 3
    final_image_url = None

    for attempt in range(max_attempts):
        if attempt > 0:
            print(f"   🔄 Attempt {attempt + 1}/{max_attempts} to get perfect anatomy...")
            
        model_name = "GPT-Image-2" if use_gpt else "Replicate FLUX"
        print(f"📷 Generating image using {model_name} for {service_clean[:25]}...")
        temp_image_url = None
        
        try:
            # ---------- OPENAI GPT-IMAGE-2 ----------
            if use_gpt and CLIENTS.get('openai'):
                size = "1536x1024" if context_mode == "hero" else "1024x1024"
                response = CLIENTS['openai'].images.generate(
                    model="gpt-image-1",
                    prompt=full_prompt,
                    size=size,
                    quality="high" if context_mode == "hero" else "medium",
                    n=1
                )
                if response and response.data:
                    b64 = getattr(response.data[0], 'b64_json', None)
                    if b64:
                        temp_image_url = f"data:image/png;base64,{b64}"
                    else:
                        temp_image_url = response.data[0].url

            # ---------- REPLICATE FLUX ----------
            elif CLIENTS.get('replicate'):
                global LAST_REPLICATE_REQUEST
                elapsed = time.time() - LAST_REPLICATE_REQUEST
                if elapsed < Config.REPLICATE_REQUEST_DELAY:
                    time.sleep(Config.REPLICATE_REQUEST_DELAY - elapsed)
                    
                aspect = "16:9" if context_mode == "hero" else "1:1"
                output = replicate.run(
                    "black-forest-labs/flux-schnell",
                    input={
                        "prompt": full_prompt,
                        "aspect_ratio": aspect,
                        "output_format": "jpg",
                        "output_quality": 90,
                        "go_fast": True,
                        "num_inference_steps": 4
                    }
                )
                LAST_REPLICATE_REQUEST = time.time()
                if output:
                    temp_image_url = str(output[0]) if isinstance(output, list) else output

            # ---------- VISION VALIDATION ----------
            if temp_image_url:
                # We ONLY run expensive vision checks on images with humans (Hero mode). 
                # Since Grid/Zigzag are now equipment/rooms, they rarely fail anatomy checks!
                if context_mode == "hero":
                    if validate_image_content(temp_image_url, service_clean, context):
                        final_image_url = temp_image_url
                        break
                    else:
                        full_prompt += " Ensure flawless photorealism."
                else:
                    final_image_url = temp_image_url
                    break
                    
        except Exception as e:
            print(f"   ⚠️ Generation error on attempt {attempt + 1}: {str(e)[:100]}")

    # 4. Upload & Cache — WordPress Media Library (replaces Cloudinary)
    if final_image_url:
        width = 1600 if context_mode == "hero" else 1000
        alt_text = f"{clean_title(service_clean)} - {clean_title(industry)}"
        wp_url = upload_image_to_wp_media(
            final_image_url,
            alt_text=alt_text,
            filename_hint=f"{service_clean}-{context_mode}",
            quality=82,
            max_width=width
        )
        if wp_url:
            final_image_url = wp_url
        else:
            print(f"   ⚠️ WP Media upload failed, falling back to original URL")  
            
    # 5. Ultimate Emergency Fallback
    if not final_image_url:
        print(f"   🆘 All generations failed. Using industry-safe Unsplash fallback.")
        ind_lower = industry.lower()
        
        if any(x in ind_lower for x in ['medic', 'dentist', 'health', 'clinic', 'spa', 'skin']):
            fallback_list = ["https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=1200&q=80"]
        elif any(x in ind_lower for x in ['beauty', 'salon', 'hair']):
            fallback_list = ["https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=1200&q=80"]
        elif any(x in ind_lower for x in ['market', 'seo', 'software', 'digital']):
            fallback_list = ["https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=1200&q=80"]
        else:
            fallback_list = [
                "https://images.unsplash.com/photo-1581578731548-c64695cc6952?auto=format&fit=crop&w=1200&q=80",
                "https://images.unsplash.com/photo-1540569014015-19a7be504e3a?auto=format&fit=crop&w=1200&q=80"
            ]
            
        final_image_url = random.choice(fallback_list)

    IMAGE_CACHE[cache_key] = final_image_url
    if is_category: 
        CATEGORY_IMAGE_CACHE[cache_key_base] = final_image_url
        
    return final_image_url
# ==============================================================================
# 🏙️ UNIVERSAL HEADER SYSTEM
# ==============================================================================

class UniversalHeader:
    """Generates universal header for WordPress with mega menu support."""
    
    @staticmethod
    def generate_root_id():
        return f"univ-header-{random.randint(10000, 99999)}"
    
    @staticmethod
    def get_translated_text(b_data, key, default):
        ui = b_data.get('ui', {})
        return ui.get(key, default)
    
    @staticmethod
    def generate_contact_items(b_data):
        items = []
        email = f"info@{b_data.get('domain', 'example.com')}"
        items.append({"icon": "fa-envelope", "text": email, "url": f"mailto:{email}"})
        
        phone = b_data.get('phone', '+1234567890')
        items.append({"icon": "fa-phone-alt", "text": phone, "url": f"tel:{phone}"})
        
        city = b_data.get('city', '')
        country = b_data.get('country', '')
        if city:
            location = f"{city}, {country}" if country else city
            items.append({"icon": "fa-map-marker-alt", "text": location[:30], "url": "#"})
        
        return items
    
    @staticmethod
    def generate_social_items(b_data):
        items = []
        social_platforms = ['facebook', 'twitter', 'instagram', 'linkedin', 'youtube']
        social_icons = {
            'facebook': 'fab fa-facebook-f', 'twitter': 'fab fa-twitter',
            'instagram': 'fab fa-instagram', 'linkedin': 'fab fa-linkedin-in',
            'youtube': 'fab fa-youtube'
        }
        
        for platform in social_platforms:
            url = b_data.get(platform, '')
            if url and url != '#':
                items.append({"icon": social_icons.get(platform), "url": url})
        
        if not items:
            items = [
                {"icon": "fab fa-facebook-f", "url": "#"},
                {"icon": "fab fa-twitter", "url": "#"},
                {"icon": "fab fa-instagram", "url": "#"}
            ]
        return items[:4]
    
    @staticmethod
    def generate_desktop_menu_items(b_data, structure, mode, hub_target_url=""):
        items = []
        ui = b_data.get('ui', {})
        is_rtl = b_data.get('is_rtl', False)
        
        # Home
        items.append({
            "type": "link", 
            "title": UniversalHeader.get_translated_text(b_data, 'home', 'Home'), 
            "url": validate_url("home", None, mode),
            "icon": "fa-home", 
            "has_dropdown": False
        })
        
        # Services
        services_item = {
            "type": "dropdown", 
            "title": UniversalHeader.get_translated_text(b_data, 'services', 'Services'), 
            "url": validate_url("services_index", None, mode),
            "icon": "fa-tools", 
            "has_dropdown": True,
            "dropdown_type": "standard", 
            "columns": []
        }
        
        if mode == "1" and b_data.get('flat_services_list'):
            main = b_data.get('flat_services_list')[0]
            services_item["title"] = shorten_menu_text(clean_title(main), 2)
            services_item["url"] = validate_url("service", main, mode)
            services_item["columns"] = [{
                "title": "Related Services", 
                "links": [{
                    "title": shorten_menu_text(clean_title(svc), 3), 
                    "url": validate_url("service", svc, mode)
                } for svc in generate_sub_services(b_data, main)[:8]]
            }]
        elif mode == "2":
            if hub_target_url: 
                services_item["url"] = hub_target_url
            all_services = b_data.get('flat_services_list', [])
            chunk_size = 8
            chunks = [all_services[i:i + chunk_size] for i in range(0, len(all_services), chunk_size)]
            services_item["dropdown_type"] = "mega"
            for i, chunk in enumerate(chunks):
                if i >= 4: break
                col_title = "Our Services" if i == 0 else f"More {b_data.get('industry', 'Services')}"
                services_item["columns"].append({
                    "title": col_title,
                    "links": [{
                        "title": shorten_menu_text(clean_title(svc), 3), 
                        "url": validate_url("service", svc, mode)
                    } for svc in chunk]
                })
        elif mode == "3" and structure:
            services_item["dropdown_type"] = "mega"
            for category, data in structure.items():
                if isinstance(data, dict) and 'children' in data and data.get('children'):
                    services_item["columns"].append({
                        "title": shorten_menu_text(clean_title(category), 2), 
                        "url": validate_url("category", category, mode), 
                        "links": [{
                            "title": shorten_menu_text(clean_title(child), 3), 
                            "url": validate_url("service", child, mode)
                        } for child in data.get('children', [])[:8]]
                    })
        
        items.append(services_item)
        
        # Locations
        locations_title = UniversalHeader.get_translated_text(b_data, 'locations', 'Locations')
        items.append({
            "type": "link", 
            "title": locations_title, 
            "url": "#locations",
            "icon": "fa-globe", 
            "has_dropdown": False
        })
        
        # Blog
        items.append({
            "type": "link", 
            "title": UniversalHeader.get_translated_text(b_data, 'blog', 'Blog'), 
            "url": validate_url("blog", None, mode),
            "icon": "fa-newspaper", 
            "has_dropdown": False
        })
        
        # Contact
        items.append({
            "type": "dropdown", 
            "title": UniversalHeader.get_translated_text(b_data, 'contact', 'Contact'), 
            "url": validate_url("contact", None, mode),
            "icon": "fa-phone-alt", 
            "has_dropdown": True, 
            "dropdown_type": "standard",
            "columns": [{
                "title": "Get in Touch",
                "links": [
                    {"title": "Contact Us", "url": validate_url("contact", None, mode)},
                    {"title": "About Us", "url": validate_url("about", None, mode)}
                ]
            }]
        })
        
        return items
    
    @staticmethod
    def generate_mobile_menu_items(b_data, structure, mode, hub_target_url=""):
        items = []
        ui = b_data.get('ui', {})
        
        # Home
        items.append({
            "type": "standalone", 
            "title": UniversalHeader.get_translated_text(b_data, 'home', 'Home'), 
            "url": validate_url("home", None, mode), 
            "icon": "fa-home"
        })
        
        # Services
        if mode == "3" and structure:
            for category, data in structure.items():
                if isinstance(data, dict) and data.get('children'):
                    items.append({
                        "type": "accordion", 
                        "title": shorten_menu_text(clean_title(category), 2), 
                        "icon": "fa-folder-open",
                        "url": validate_url("category", category, mode),
                        "links": [{
                            "title": shorten_menu_text(clean_title(child), 3), 
                            "url": validate_url("service", child, mode)
                        } for child in data.get('children', [])[:15]]
                    })
        elif mode == "2":
            services = b_data.get('flat_services_list', [])
            if services:
                items.append({
                    "type": "grid", 
                    "title": "Our Services", 
                    "icon": "fa-tools",
                    "url": hub_target_url if hub_target_url else validate_url("services_index", None, mode),
                    "links": [{
                        "title": shorten_menu_text(clean_title(svc), 3), 
                        "url": validate_url("service", svc, mode)
                    } for svc in services[:30]]
                })
        
        # Locations
        locations_title = UniversalHeader.get_translated_text(b_data, 'locations', 'Locations')
        items.append({
            "type": "standalone", 
            "title": locations_title, 
            "url": "#locations", 
            "icon": "fa-globe"
        })
        
        # Contact & Blog
        items.append({
            "type": "standalone", 
            "title": UniversalHeader.get_translated_text(b_data, 'contact', 'Contact'), 
            "url": validate_url("contact", None, mode), 
            "icon": "fa-phone-alt"
        })
        items.append({
            "type": "standalone", 
            "title": UniversalHeader.get_translated_text(b_data, 'blog', 'Blog'), 
            "url": validate_url("blog", None, mode), 
            "icon": "fa-newspaper"
        })
        
        return items
    
    @staticmethod
    def render(b_data, structure=None, mode="3", hub_target_url=""):
        root_id = UniversalHeader.generate_root_id()
        is_rtl = b_data.get('is_rtl', False)
        ui = b_data.get('ui', {})
        
        # 🛑 CRITICAL FIX: Inject RTL dir attribute so the menu renders Right-to-Left correctly
        dir_attr = "rtl" if is_rtl else "ltr"
        
        primary_color = b_data.get('primary', '#1A73E8').lstrip('#')
        accent_color = b_data.get('accent', '#FFB300').lstrip('#')
        
        contact_items = UniversalHeader.generate_contact_items(b_data)
        social_items = UniversalHeader.generate_social_items(b_data)
        
        contact_items_html = ""
        for i, item in enumerate(contact_items):
            hide_class = "hide-on-mobile" if i != 1 else "center-on-mobile" # Keep phone (usually index 1)
            contact_items_html += f"""
            <a href="{item['url']}" class="{hide_class}" style="display:flex; align-items:center; gap:8px; color:#94a3b8; text-decoration:none; font-size:13px;">
                <i class="fas {item['icon']}" style="color:#{accent_color};"></i>
                <span>{item['text']}</span>
            </a>"""
        social_items_html = ""
        for item in social_items[:3]:
            social_items_html += f"""
            <a href="{item['url']}" class="hide-on-mobile" style="color:#94a3b8; font-size:14px; text-decoration:none;" target="_blank">
                <i class="{item['icon']}"></i>
            </a>"""
        
        logo_url = b_data.get('logo_url', '')
        is_font_awesome = logo_url.startswith('fas ') or logo_url.startswith('fa-')
        
        if is_font_awesome:
            logo_content = f'<i class="{logo_url}" style="font-size:32px; color:#{accent_color};"></i>'
            logo_text = f'<span style="font-family:Outfit,sans-serif; font-size:1.3rem; font-weight:700; color:#{primary_color}; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:220px;">{b_data.get("name", "")}</span>'
        elif logo_url:
            logo_content = f'<img src="{logo_url}" alt="{b_data.get("name", "")} Logo" style="max-width:180px; max-height:60px;">'
            logo_text = ""
        else:
            logo_content = ""
            logo_text = f'<span style="font-family:Outfit,sans-serif; font-size:1.3rem; font-weight:700; color:#{primary_color}; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:220px;">{b_data.get("name", "")}</span>'
        
        # Desktop menu
        desktop_items = UniversalHeader.generate_desktop_menu_items(b_data, structure, mode, hub_target_url)
        desktop_menu_html = ""
        
        for item in desktop_items:
            if item["has_dropdown"] and item.get("columns"):
                # Position adjustments based on LTR/RTL
                dropdown_position = "right: 0;" if is_rtl else "left: -300px;"
                icon_margin = "margin-right: 8px;" if is_rtl else "margin-left: 8px;"
                desktop_menu_html += f"""
                <div style="position:relative;">
                    <a href="{item['url']}" style="display:flex; align-items:center; gap:5px; color:#{primary_color}; font-weight:600; text-decoration:none; padding:8px 12px; font-size:15px;">
                        <i class="fas {item['icon']}" style="color:#{accent_color};"></i> {item['title']} <i class="fas fa-chevron-down" style="font-size:11px; {icon_margin}"></i>
                    </a>
                    <div style="position:absolute; top:100%; {dropdown_position} background:white; min-width:800px; box-shadow:0 10px 25px rgba(0,0,0,0.1); border-radius:8px; padding:25px; opacity:0; visibility:hidden; transition:0.2s; z-index:1000; border-top:3px solid #{accent_color}; display:grid; grid-template-columns:repeat(4,1fr); gap:25px; text-align: {("right" if is_rtl else "left")};">
                """
                for col in item["columns"]:
                    desktop_menu_html += f"""
                        <div>
                            <h4 style="color:#{primary_color}; font-size:0.9rem; font-weight:700; margin-bottom:15px; border-bottom:2px solid #{accent_color}; padding-bottom:8px;">{col['title']}</h4>"""
                    for link in col.get("links", [])[:8]:
                        desktop_menu_html += f"""
                            <a href="{link['url']}" style="display:block; padding:6px 0; color:#64748b; font-size:0.9rem; text-decoration:none;">{link['title']}</a>"""
                    desktop_menu_html += "</div>"
                desktop_menu_html += "</div></div>"
            else:
                desktop_menu_html += f"""
                <div>
                    <a href="{item['url']}" style="display:flex; align-items:center; gap:5px; color:#{primary_color}; font-weight:600; text-decoration:none; padding:8px 12px; font-size:15px;">
                        <i class="fas {item['icon']}" style="color:#{accent_color};"></i> {item['title']}
                    </a>
                </div>"""
        
        # Mobile menu
        mobile_items = UniversalHeader.generate_mobile_menu_items(b_data, structure, mode, hub_target_url)
        mobile_menu_html = ""
        
        for item in mobile_items:
            if item["type"] in ["accordion", "grid"]:
                mobile_menu_html += f"""
                <div style="border:1px solid #e2e8f0; border-radius:8px; overflow:hidden; margin-bottom:10px;">
                    <div onclick="this.parentElement.classList.toggle('active'); this.nextElementSibling.style.maxHeight = this.parentElement.classList.contains('active') ? this.nextElementSibling.scrollHeight + 'px' : '0'" 
                         style="padding:15px; display:flex; justify-content:space-between; align-items:center; cursor:pointer; background:#f8fafc; font-weight:600; color:{primary_color};">
                        <div style="display:flex; align-items:center; gap:12px;">
                            <i class="fas {item['icon']}" style="color:{accent_color};"></i>
                            <span>{item['title']}</span>
                        </div>
                        <i class="fas fa-chevron-down" style="color:#cbd5e1;"></i>
                    </div>
                    <div style="max-height:0; overflow:hidden; transition:0.3s; display:grid; grid-template-columns:repeat(2,1fr); gap:8px; padding:0 10px;">
                """
                for link in item["links"][:8]:
                    mobile_menu_html += f"""
                        <a href="{link['url']}" style="display:block; padding:10px; border:1px solid #e2e8f0; border-radius:6px; text-align:center; color:#475569; font-size:0.9rem; text-decoration:none; background:white;">{link['title']}</a>"""
                mobile_menu_html += "</div></div>"
            else:
                mobile_menu_html += f"""
                <a href="{item['url']}" style="display:block; padding:15px; border:1px solid #e2e8f0; border-radius:8px; background:white; color:{primary_color}; font-weight:600; text-decoration:none;">
                    <i class="fas {item['icon']}" style="margin-right:12px; color:{accent_color};"></i>
                    {item['title']}
                </a>"""
        
        if mode == "1":
            anchors_present = b_data.get('_m1_anchors', ['services', 'faq', 'contact'])
            target_lang = b_data.get('target_lang', 'en')

            if target_lang == 'ar':
                m1_labels = {"services": "خدماتنا", "pricing": "الأسعار",
                             "reviews": "آراء العملاء", "faq": "الأسئلة الشائعة",
                             "contact": "اتصل بنا"}
                menu_word = "القائمة"
                urgency_txt = "⚡ خدمة طوارئ 24/7 — استجابة سريعة"
            else:
                m1_labels = {"services": "Services", "pricing": "Pricing",
                             "reviews": "Reviews", "faq": "FAQ", "contact": "Contact"}
                menu_word = "Menu"
                urgency_txt = "⚡ 24/7 Emergency Service — Fast Response"

            m1_icons = {"services": "fa-tools", "pricing": "fa-tags",
                        "reviews": "fa-star", "faq": "fa-question-circle",
                        "contact": "fa-phone-alt"}

            menu_order = [k for k in ["services", "pricing", "reviews", "faq", "contact"]
                          if k in anchors_present]
            if "contact" not in menu_order:
                menu_order.append("contact")

            _pc = primary_color
            _ac = accent_color

            desktop_nav = ""
            drawer_nav = ""
            for key in menu_order:
                desktop_nav += f'''
                <a href="#{key}" style="color:#{_pc}; font-weight:600; text-decoration:none; padding:8px 10px; font-size:15px; display:inline-flex; align-items:center; gap:6px; border-radius:8px;">
                    <i class="fas {m1_icons[key]}" style="color:#{_ac}; font-size:13px;"></i> {m1_labels[key]}
                </a>'''
                drawer_nav += f'''
                <a href="#{key}" style="display:flex; align-items:center; gap:12px; padding:15px; border:1px solid #e2e8f0; border-radius:10px; background:white; color:#{_pc}; font-weight:600; text-decoration:none;">
                    <i class="fas {m1_icons[key]}" style="color:#{_ac};"></i> {m1_labels[key]}
                </a>'''

            funnel_header_html = f"""
<div id="{root_id}-funnel" style="width:100%; font-family:'Outfit',sans-serif; position:sticky; top:0; z-index:9999; direction:{dir_attr};">
    <div style="background:#0C2340; color:#E8F4FD; padding:7px 20px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; border-bottom:2px solid #1D9E75;">
        <div style="display:flex; align-items:center; gap:8px;">
            <span style="width:8px; height:8px; border-radius:50%; background:#5DCAA5; display:inline-block;"></span>
            <span style="font-size:12px; font-weight:600;">{urgency_txt}</span>
        </div>
        <div style="display:flex; gap:8px;">
            <a href="tel:{b_data.get('phone','')}" style="background:#1D9E75; color:#E1F5EE; padding:5px 14px; border-radius:20px; font-size:11px; font-weight:700; text-decoration:none; white-space:nowrap;">📞 {b_data.get('phone','')}</a>
            <a href="https://wa.me/{b_data.get('whatsapp','')}" target="_blank" style="background:#25D366; color:white; padding:5px 14px; border-radius:20px; font-size:11px; font-weight:700; text-decoration:none; white-space:nowrap;">💬 WhatsApp</a>
        </div>
    </div>
    <div style="background:white; box-shadow:0 2px 10px rgba(0,0,0,0.08);">
        <div style="max-width:1200px; margin:0 auto; padding:10px 20px; display:flex; justify-content:space-between; align-items:center; gap:16px; flex-wrap:nowrap;">
            <a href="#top" style="display:flex; align-items:center; gap:10px; text-decoration:none; flex-shrink:0; min-width:0; overflow:hidden;">
                {logo_content}
                {logo_text}
            </a>
            <nav class="m1-desktop-nav" style="display:flex; align-items:center; gap:4px; flex-wrap:nowrap; overflow:hidden; flex-shrink:1; min-width:0;">
                {desktop_nav}
                <a href="#contact" style="margin-left:10px; flex-shrink:0; white-space:nowrap; display:inline-flex; align-items:center; gap:7px; background:linear-gradient(135deg, #{_ac} 0%, #{_pc} 100%); color:white; padding:11px 24px; border-radius:50px; font-weight:700; text-decoration:none; font-size:0.9rem; box-shadow:0 4px 12px rgba(0,0,0,0.2);">
                    <i class="fas fa-file-invoice-dollar"></i> {ui.get('get_quote', 'Get Quote')}
                </a>
            </nav>
            <div style="display:flex; gap:8px; align-items:center;">
                <a href="tel:{b_data.get('phone','')}" class="m1-phone-pill" style="display:inline-flex; align-items:center; gap:7px; background:#{_pc}; color:white; padding:10px 18px; border-radius:50px; font-weight:700; text-decoration:none; font-size:0.85rem;">
                    <i class="fas fa-phone-alt"></i><span class="funnel-phone-text">{b_data.get('phone','')}</span>
                </a>
                <button id="{root_id}-m1-toggle" style="display:none; background:none; border:none; font-size:24px; cursor:pointer; color:#{_pc}; padding:8px;">
                    <i class="fas fa-bars"></i>
                </button>
            </div>
        </div>
    </div>
    <div id="{root_id}-m1-overlay" style="position:fixed; inset:0; background:rgba(15,23,42,0.85); z-index:100000; opacity:0; visibility:hidden; transition:0.3s;"></div>
    <div id="{root_id}-m1-drawer" style="position:fixed; top:0; right:-100%; width:85%; max-width:380px; height:100vh; background:#f8fafc; z-index:100001; transition:0.4s; box-shadow:-10px 0 30px rgba(0,0,0,0.1); overflow-y:auto; direction:{dir_attr};">
        <div style="padding:22px; border-bottom:1px solid #e2e8f0; display:flex; justify-content:space-between; align-items:center; background:white;">
            <h3 style="font-size:1.15rem; color:#{_pc}; font-weight:700; margin:0;">{menu_word}</h3>
            <button id="{root_id}-m1-close" style="background:none; border:none; font-size:28px; cursor:pointer; color:#{_pc};">&times;</button>
        </div>
        <div style="padding:22px; display:flex; flex-direction:column; gap:12px;">
            {drawer_nav}
            <a href="tel:{b_data.get('phone','')}" style="display:block; padding:15px; background:#{_pc}; color:white; text-align:center; font-weight:700; text-decoration:none; border-radius:10px;">
                <i class="fas fa-phone-alt"></i> {b_data.get('phone','')}
            </a>
            <a href="https://wa.me/{b_data.get('whatsapp','')}" target="_blank" style="display:block; padding:15px; background:#25D366; color:white; text-align:center; font-weight:700; text-decoration:none; border-radius:10px;">
                <i class="fab fa-whatsapp"></i> WhatsApp
            </a>
        </div>
    </div>
</div>
<style>
html {{ scroll-behavior: smooth; }}
@media (max-width:1280px) {{
    #{root_id}-funnel .m1-desktop-nav {{ display:none !important; }}
    #{root_id}-funnel #{root_id}-m1-toggle {{ display:block !important; }}
}}
@media (max-width:600px) {{
    #{root_id}-funnel .funnel-phone-text {{ display:none !important; }}
}}
</style>
<script>
(function() {{
    var toggle  = document.getElementById('{root_id}-m1-toggle');
    var drawer  = document.getElementById('{root_id}-m1-drawer');
    var overlay = document.getElementById('{root_id}-m1-overlay');
    var closeB  = document.getElementById('{root_id}-m1-close');
    function openM()  {{ drawer.style.right='0'; overlay.style.opacity='1'; overlay.style.visibility='visible'; }}
    function closeM() {{ drawer.style.right='-100%'; overlay.style.opacity='0'; overlay.style.visibility='hidden'; }}
    if(toggle)  toggle.addEventListener('click', openM);
    if(closeB)  closeB.addEventListener('click', closeM);
    if(overlay) overlay.addEventListener('click', closeM);
    if(drawer)  drawer.querySelectorAll('a[href^="#"]').forEach(function(a) {{ a.addEventListener('click', closeM); }});
}})();
</script>
"""
            return funnel_header_html

        # 🛑 RTL FIX INJECTED INTO ROOT DIV
        return f"""
        <div id="{root_id}" dir="{dir_attr}" style="width:100%; display:block; background:white; box-shadow:0 2px 10px rgba(0,0,0,0.05); font-family:'Outfit', sans-serif;">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
            
            <div class="top-bar-wrapper" style="background:#0f172a; color:#94a3b8; padding:8px 0; font-size:13px;">
                <div class="top-bar-inner" style="max-width:1400px; margin:0 auto; padding:0 20px; display:flex; justify-content:space-between; align-items:center;">
                    <div class="top-bar-left" style="display:flex; gap:20px;">{contact_items_html}</div>
                    <div class="top-bar-right" style="display:flex; gap:15px;">{social_items_html}</div>
                </div>
            </div>
            
            <header style="display:flex; align-items:center; justify-content:space-between; max-width:1400px; margin:0 auto; padding:15px 20px; background:white;">
                <a href="{validate_url('home', None, mode)}" style="display:flex; align-items:center; gap:10px; text-decoration:none;">
                    {logo_content}
                    {logo_text}
                </a>
                
                <nav style="display:flex; align-items:center; gap:25px;">
                    {desktop_menu_html}
                    <a href="{validate_url('contact', None, mode)}" 
                       style="background:linear-gradient(135deg, #{accent_color} 0%, #{primary_color} 100%);
                              color:white; padding:12px 28px; border-radius:50px; font-weight:600; 
                              text-decoration:none; display:inline-flex; align-items:center; gap:8px;
                              box-shadow:0 4px 15px rgba(0,0,0,0.2); transition:all 0.3s ease;
                              border:none; font-size:0.95rem; cursor:pointer;">
                        <i class="fas fa-file-invoice-dollar"></i> {ui.get('get_quote', 'Get Quote')}
                    </a>
                </nav>
                
                <button id="{root_id}-mobile-toggle" 
                        style="display:none; background:none; border:none; font-size:24px; cursor:pointer; color:#{primary_color}; padding:10px;">
                    <i class="fas fa-bars"></i>
                </button>
            </header>
            
            <div id="{root_id}-overlay" style="position:fixed; inset:0; background:rgba(15,23,42,0.85); z-index:100000; opacity:0; visibility:hidden; transition:0.3s;"></div>
            <div id="{root_id}-drawer" style="position:fixed; top:0; {("left:-100%;" if is_rtl else "right:-100%;")} width:85%; max-width:400px; height:100vh; background:white; z-index:100001; transition:0.4s; box-shadow:-10px 0 30px rgba(0,0,0,0.1); overflow-y:auto;">
                <div style="padding:25px; border-bottom:1px solid #e2e8f0; display:flex; justify-content:space-between; align-items:center; background:#f8fafc;">
                    <h3 style="font-size:1.2rem; color:#{primary_color}; font-weight:700; margin:0;">Menu</h3>
                    <button id="{root_id}-close-btn" style="background:none; border:none; font-size:28px; cursor:pointer; color:#{primary_color};">&times;</button>
                </div>
                <div style="padding:25px;">
                    <div style="display:flex; flex-direction:column; gap:15px;">
                        {mobile_menu_html}
                        <div style="margin-top:20px; display:flex; flex-direction:column; gap:10px;">
                            <a href="tel:{b_data.get('phone', '')}" style="display:block; padding:15px; background:#2563eb; color:white; text-align:center; font-weight:600; text-decoration:none; border-radius:8px;">
                                <i class="fas fa-phone-alt"></i> {ui.get('call_now', 'Call Now')}
                            </a>
                            <a href="{validate_url('contact', None, mode)}" style="display:block; padding:15px; background:#d4af37; color:white; text-align:center; font-weight:600; text-decoration:none; border-radius:8px;">
                                <i class="fas fa-file-invoice-dollar"></i> {ui.get('get_quote', 'Get Quote')}
                            </a>
                        </div>
                    </div>
                </div>
            </div>
            
            <style>
                #{root_id} div[style*="position:absolute; top:100%;"] {{
                    opacity: 0;
                    visibility: hidden;
                    transition: opacity 0.2s, visibility 0.2s;
                }}
                #{root_id} div[style*="position:relative;"]:hover div[style*="position:absolute; top:100%;"] {{
                    opacity: 1 !important;
                    visibility: visible !important;
                }}
                @media (max-width: 1150px) {{
                    #{root_id} nav {{ display: none !important; }}
                    #{root_id} #{root_id}-mobile-toggle {{ display: block !important; }}
                }}
                @media (max-width: 768px) {{
                    #{root_id} .hide-on-mobile {{ display: none !important; }}
                    #{root_id} .top-bar-inner {{ justify-content: center !important; }}
                    #{root_id} .top-bar-left {{ width: 100% !important; justify-content: center !important; }}
                }}
            </style>
            
            <script>
            (function() {{
                const root = document.getElementById('{root_id}');
                const trigger = root.querySelector('#{root_id}-mobile-toggle');
                const closeBtn = root.querySelector('#{root_id}-close-btn');
                const overlay = root.querySelector('#{root_id}-overlay');
                const drawer = root.querySelector('#{root_id}-drawer');
                
                function openMenu() {{
                    if("{dir_attr}" === "rtl") {{
                        drawer.style.left = '0';
                    }} else {{
                        drawer.style.right = '0';
                    }}
                    overlay.style.opacity = '1';
                    overlay.style.visibility = 'visible';
                    document.body.style.overflow = 'hidden';
                }}
                
                function closeMenu() {{
                    if("{dir_attr}" === "rtl") {{
                        drawer.style.left = '-100%';
                    }} else {{
                        drawer.style.right = '-100%';
                    }}
                    overlay.style.opacity = '0';
                    overlay.style.visibility = 'hidden';
                    document.body.style.overflow = '';
                }}
                
                if(trigger) trigger.addEventListener('click', openMenu);
                if(closeBtn) closeBtn.addEventListener('click', closeMenu);
                if(overlay) overlay.addEventListener('click', closeMenu);
                
                document.addEventListener('keydown', function(e) {{
                    if (e.key === 'Escape') closeMenu();
                }});
                
                window.addEventListener('resize', function() {{
                    if (window.innerWidth > 1150 && (drawer.style.right === '0px' || drawer.style.left === '0px')) closeMenu();
                }});
            }})();
            </script>
        </div>
        """

# ==============================================================================
# 🍔 SEPARATE MENU EXPORT SYSTEM
# ==============================================================================

def export_mega_menu_as_page(wp_conf, b_data, structure, mode, hub_target_url=""):
    """
    Creates a dedicated WordPress page that contains the mega menu HTML.
    This page can be used to copy the menu code once and reuse across all pages.
    """
    
    # Generate the full header HTML (which includes the mega menu)
    header_html = UniversalHeader.render(b_data, structure, mode, hub_target_url)
    
    # Create a minimal wrapper page just for the menu
    menu_page_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mega Menu Code - Copy and Paste</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                padding: 20px; 
                background: #f5f5f5;
                line-height: 1.6;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .instruction-box {{
                background: #e8f0fe;
                padding: 25px;
                border-left: 5px solid #0073aa;
                margin: 20px 0;
                border-radius: 8px;
            }}
            .menu-code-box {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            pre {{
                background: #1e1e1e;
                color: #d4d4d4;
                padding: 20px;
                border-radius: 8px;
                overflow-x: auto;
                font-family: 'Courier New', monospace;
                font-size: 13px;
                line-height: 1.5;
                max-height: 500px;
                overflow-y: auto;
            }}
            button {{
                background: #0073aa;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                font-weight: bold;
                margin: 10px 0;
                transition: background 0.3s;
            }}
            button:hover {{
                background: #005a87;
            }}
            .preview-box {{
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 0;
                margin: 20px 0;
                overflow: hidden;
            }}
            .preview-header {{
                background: #f0f0f0;
                padding: 15px;
                border-bottom: 1px solid #ddd;
                font-weight: bold;
            }}
            .instructions {{
                background: #f9f9f9;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
            }}
            h1, h2, h3 {{
                margin: 20px 0 10px;
                color: #333;
            }}
            .success {{
                background: #d4edda;
                color: #155724;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
                border-left: 4px solid #28a745;
            }}
            .warning {{
                background: #fff3cd;
                color: #856404;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
                border-left: 4px solid #ffc107;
            }}
            .steps {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
            }}
            .steps ol {{
                margin-left: 20px;
            }}
            .steps li {{
                margin: 10px 0;
            }}
            code {{
                background: #f4f4f4;
                padding: 2px 5px;
                border-radius: 3px;
                font-family: monospace;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success">
                <strong>✅ Mega Menu Generated Successfully!</strong> 
                Follow the instructions below to install this menu on your WordPress site.
            </div>
            
            <div class="instruction-box">
                <h2>📋 Quick Installation Guide</h2>
                <p>This menu needs to be installed <strong>ONCE</strong> and will automatically appear on all pages.</p>
            </div>
            
            <div class="steps">
                <h3>Method 1: Install via WordPress Widget (Recommended)</h3>
                <ol>
                    <li>Click the <strong>"Copy to Clipboard"</strong> button below</li>
                    <li>Go to <strong>WordPress Admin → Appearance → Widgets</strong></li>
                    <li>Find the <strong>"Header"</strong> or <strong>"Top Bar"</strong> widget area</li>
                    <li>Add a <strong>"Custom HTML"</strong> widget</li>
                    <li>Paste the copied code and click <strong>"Save"</strong></li>
                    <li>Your mega menu will now appear on all pages!</li>
                </ol>
                
                <h3>Method 2: Add to Theme Files (Advanced)</h3>
                <ol>
                    <li>Copy the code below</li>
                    <li>Go to <strong>Appearance → Theme File Editor</strong></li>
                    <li>Open <strong>header.php</strong> file</li>
                    <li>Paste the code right after the <code>&lt;body&gt;</code> tag</li>
                    <li>Click <strong>"Update File"</strong></li>
                </ol>
                
                <div class="warning">
                    <strong>⚠️ Important:</strong> 
                    <ul style="margin-top: 10px; margin-left: 20px;">
                        <li>This menu uses <strong>Font Awesome 6</strong> icons - ensure your site supports it</li>
                        <li>The menu is fully responsive and works on mobile devices</li>
                        <li>You can customize colors by modifying the CSS variables in the code</li>
                        <li>If you regenerate the menu, you'll need to update the widget with the new code</li>
                    </ul>
                </div>
            </div>
            
            <div class="menu-code-box">
                <h3>📝 Mega Menu HTML Code:</h3>
                <button onclick="copyToClipboard()">📋 Copy to Clipboard</button>
                <pre id="menu-code"><code>{escape(header_html)}</code></pre>
            </div>
            
            <div class="preview-box">
                <div class="preview-header">
                    <strong>🔍 Live Preview:</strong> This is how your menu will look on the site
                </div>
                <div style="padding: 0;">
                    {header_html}
                </div>
            </div>
            
            <div class="instructions">
                <h3>💡 Pro Tips:</h3>
                <ul>
                    <li>To customize colors, find the CSS variables in the code and modify the hex values</li>
                    <li>To update menu links, you'll need to regenerate this menu and update the widget</li>
                    <li>The menu includes your business contact info, social links, and service categories</li>
                    <li>Mobile menu opens as a drawer from the right side</li>
                </ul>
            </div>
        </div>
        
        <script>
        function copyToClipboard() {{
            const code = document.getElementById('menu-code').innerText;
            navigator.clipboard.writeText(code).then(() => {{
                alert('✅ Menu code copied to clipboard!\\n\\nNow go to WordPress Admin → Appearance → Widgets and paste it into a Custom HTML widget.');
            }}).catch(() => {{
                alert('Unable to copy automatically. Please select the code manually and press Ctrl+C');
            }});
        }}
        </script>
    </body>
    </html>
    '''
    
    # Publish as a draft page so it's not public but accessible via admin
    auth = base64.b64encode(f"{wp_conf['user']}:{wp_conf['pass']}".encode()).decode('utf-8')
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    payload = {
        "title": "Mega Menu Code (Copy This)",
        "content": menu_page_content,
        "slug": "mega-menu-code",
        "status": "draft",  # Draft so it's not public
    }
    
    try:
        # Check if page already exists
        check_url = f"{wp_conf['url'].rstrip('/')}/wp-json/wp/v2/pages?slug=mega-menu-code"
        check_response = requests.get(check_url, headers=headers, verify=False, timeout=30)
        
        if check_response.status_code == 200 and check_response.json():
            # Update existing page
            existing_id = check_response.json()[0]['id']
            response = requests.put(
                f"{wp_conf['url'].rstrip('/')}/wp-json/wp/v2/pages/{existing_id}",
                headers=headers,
                json=payload,
                verify=False,
                timeout=30
            )
            if response.status_code == 200:
                page_id = response.json()['id']
                page_url = f"{wp_conf['url'].rstrip('/')}/wp-admin/post.php?post={page_id}&action=edit"
                print(f"\n✅ Mega Menu Code Page Updated!")
                print(f"   📍 Edit page: {page_url}")
                print(f"   📋 Copy the code from this page and paste into your header widget")
                return True
        else:
            # Create new page
            response = requests.post(
                f"{wp_conf['url'].rstrip('/')}/wp-json/wp/v2/pages",
                headers=headers,
                json=payload,
                verify=False,
                timeout=30
            )
            if response.status_code == 201:
                page_id = response.json()['id']
                page_url = f"{wp_conf['url'].rstrip('/')}/wp-admin/post.php?post={page_id}&action=edit"
                print(f"\n✅ Mega Menu Code Page Created!")
                print(f"   📍 Edit page: {page_url}")
                print(f"   📋 Copy the code from this page and paste into your header widget")
                return True
            else:
                print(f"   ⚠️ Failed to create menu page: {response.status_code}")
                return False
    except Exception as e:
        print(f"   ⚠️ Error creating menu page: {e}")
        return False

def export_menu_as_file(b_data, structure, mode, hub_target_url=""):
    """Export mega menu as a downloadable HTML file for manual installation"""
    
    header_html = UniversalHeader.render(b_data, structure, mode, hub_target_url)
    
    # Create a standalone HTML file with just the menu
    menu_file_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mega Menu Export - {b_data.get('name', 'Website')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: #f5f5f5; 
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: #0073aa; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: white; padding: 30px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        pre {{
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.5;
            max-height: 500px;
            overflow-y: auto;
        }}
        button {{
            background: #0073aa;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            margin: 10px 0;
        }}
        button:hover {{ background: #005a87; }}
        .instructions {{
            background: #f0f8ff;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #0073aa;
        }}
        .preview {{
            border: 1px solid #ddd;
            border-radius: 8px;
            margin: 20px 0;
            overflow: hidden;
        }}
        .preview-title {{
            background: #f0f0f0;
            padding: 10px 15px;
            font-weight: bold;
            border-bottom: 1px solid #ddd;
        }}
        h1, h2, h3 {{ margin: 15px 0; }}
        .success {{
            background: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🍔 Mega Menu Export</h1>
            <p>Copy the code below and paste into your WordPress site</p>
        </div>
        <div class="content">
            <div class="success">
                ✅ Menu generated for: <strong>{b_data.get('name', 'Website')}</strong>
            </div>
            
            <div class="instructions">
                <h3>📋 Installation Instructions:</h3>
                <ol>
                    <li>Click the <strong>"Copy Code"</strong> button below</li>
                    <li>Go to WordPress Admin → Appearance → Widgets</li>
                    <li>Add a <strong>"Custom HTML"</strong> widget to your header area</li>
                    <li>Paste the code and save</li>
                    <li>Your mega menu is now live!</li>
                </ol>
            </div>
            
            <button onclick="copyToClipboard()">📋 Copy Code to Clipboard</button>
            <pre id="menu-code"><code>{escape(header_html)}</code></pre>
            
            <div class="preview">
                <div class="preview-title">🔍 Live Preview:</div>
                <div style="padding: 0;">
                    {header_html}
                </div>
            </div>
            
            <div class="instructions">
                <h3>💡 Need Help?</h3>
                <p>If the menu doesn't appear correctly, check that:</p>
                <ul>
                    <li>Your WordPress theme has a header widget area</li>
                    <li>Font Awesome 6 is loaded on your site</li>
                    <li>The code is pasted correctly (no missing characters)</li>
                </ul>
            </div>
        </div>
    </div>
    
    <script>
    function copyToClipboard() {{
        const code = document.getElementById('menu-code').innerText;
        navigator.clipboard.writeText(code).then(() => {{
            alert('✅ Menu code copied! Now paste it into a WordPress Custom HTML widget.');
        }});
    }}
    </script>
</body>
</html>'''
    
    # Save as file
    filename = f"mega_menu_{slugify(b_data.get('name', 'site'))}.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(menu_file_content)
    
    print(f"\n✅ Mega Menu exported to file: {filename}")
    print(f"   📁 Open this file in your browser to copy the menu code")
    print(f"   📋 Then paste into WordPress → Appearance → Widgets → Custom HTML")
    return filename

# ==============================================================================
# RESTORED FOOTER BUILDER FUNCTION 
# ==============================================================================
def build_enhanced_footer(b_data, structure):
    """Enhanced WordPress footer with strict Grid layout, AI colors, and 5-language support."""
    ui = b_data.get('ui', {})
    primary = b_data.get('primary', '#1A73E8')
    accent = b_data.get('accent', '#FFB300')
    name = b_data.get('name', 'Our Company')
    phone = b_data.get('phone', '')
    domain = b_data.get('domain', 'example.com')
    city = b_data.get('city', '')
    country = b_data.get('country', '')
    facebook = b_data.get('facebook', '#')
    twitter = b_data.get('twitter', '#')
    instagram = b_data.get('instagram', '#')
    linkedin = b_data.get('linkedin', '#')
    target_lang = b_data.get('target_lang', 'en')
    mode = b_data.get('mode', '3')
    
    # 🌍 5-LANGUAGE FULL TRANSLATION & RTL LOGIC
    if target_lang == 'ar':
        desc_text = "خدمات احترافية يمكنك الوثوق بها. مكرسون للتميز وإرضاء العملاء."
        rights_text = "جميع الحقوق محفوظة."
        services_title = "خدماتنا"
        contact_title = "اتصل بنا"
        dir_attr = "rtl"
        icon_margin = "margin-left: 10px;"
        chevron = "fa-chevron-left"
    elif target_lang == 'es':
        desc_text = "Servicios profesionales en los que puede confiar. Dedicados a la excelencia y la satisfacción del cliente."
        rights_text = "Todos los derechos reservados."
        services_title = "Servicios"
        contact_title = "Contáctenos"
        dir_attr = "ltr"
        icon_margin = "margin-right: 10px;"
        chevron = "fa-chevron-right"
    elif target_lang == 'fr':
        desc_text = "Des services professionnels de confiance. Dévoués à l'excellence et à la satisfaction du client."
        rights_text = "Tous droits réservés."
        services_title = "Services"
        contact_title = "Contactez-nous"
        dir_attr = "ltr"
        icon_margin = "margin-right: 10px;"
        chevron = "fa-chevron-right"
    elif target_lang == 'de':
        desc_text = "Professionelle Dienstleistungen, denen Sie vertrauen können. Exzellenz und Kundenzufriedenheit verpflichtet."
        rights_text = "Alle Rechte vorbehalten."
        services_title = "Dienstleistungen"
        contact_title = "Kontaktiere uns"
        dir_attr = "ltr"
        icon_margin = "margin-right: 10px;"
        chevron = "fa-chevron-right"
    else: # Default English
        desc_text = "Professional services you can trust. Dedicated to excellence and customer satisfaction."
        rights_text = "All rights reserved."
        services_title = "Services"
        contact_title = "Contact Us"
        dir_attr = "ltr"
        icon_margin = "margin-right: 10px;"
        chevron = "fa-chevron-right"
        
    # Generate Service Links dynamically
    services_links = ""
    if structure:
        for cat in list(structure.keys())[:5]:
            cat_url = validate_url("category", cat, mode)
            # AI Primary color applied to chevron icons
            services_links += f'<li style="margin-bottom: 12px;"><a href="{cat_url}" style="color: rgba(255,255,255,0.8); text-decoration: none; transition: 0.3s; display: flex; align-items: center;"><i class="fas {chevron}" style="color: {primary}; font-size: 0.8rem; {icon_margin}"></i> {clean_title(cat)}</a></li>'

    # Generate Social Links
    social_html = ""
    for icon, link in [('fa-facebook-f', facebook), ('fa-twitter', twitter), ('fa-instagram', instagram), ('fa-linkedin-in', linkedin)]:
        if link and link != '#':
            # AI Primary color applied directly to social icons
            social_html += f'<a href="{link}" style="width: 40px; height: 40px; border-radius: 50%; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); display: flex; align-items: center; justify-content: center; color: {primary}; text-decoration: none; transition: 0.3s;" onmouseover="this.style.background=\'{primary}\'; this.style.color=\'#fff\';" onmouseout="this.style.background=\'rgba(255,255,255,0.05)\'; this.style.color=\'{primary}\';"><i class="fab {icon}"></i></a>'

    return f'''
    <style>
        .wp-univ-footer {{
            background: #0f172a; 
            color: white;
            padding: 60px 0 20px;
            font-family: 'Outfit', sans-serif;
            direction: {dir_attr};
        }}
        .wp-univ-footer-grid {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            display: grid;
            /* 💎 STRICT 3-COLUMN DESKTOP FIX */
            grid-template-columns: 1.5fr 1fr 1fr;
            gap: 40px;
            margin-bottom: 40px;
        }}
        .wp-univ-footer-col h3 {{
            color: white;
            font-size: 1.3rem;
            margin-bottom: 25px;
            position: relative;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        /* AI Primary Color Underlines */
        .wp-univ-footer-col h3::after {{
            content: '';
            position: absolute;
            bottom: 0;
            {'right' if target_lang == 'ar' else 'left'}: 0;
            width: 50px;
            height: 2px;
            background: {primary};
        }}
        .wp-univ-footer-col ul {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .wp-univ-footer-col .contact-item {{
            display: flex;
            align-items: center;
            margin-bottom: 15px;
            color: rgba(255,255,255,0.8);
        }}
        /* AI Primary Color on Contact Icons */
        .wp-univ-footer-col .contact-item i {{
            color: {primary};
            {icon_margin}
            font-size: 1.1rem;
        }}
        /* 📱 MOBILE RESPONSIVE FIXES */
        @media (max-width: 991px) {{
            .wp-univ-footer-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
        @media (max-width: 768px) {{
            .wp-univ-footer-grid {{
                grid-template-columns: 1fr;
                text-align: center;
            }}
            .wp-univ-footer-col h3::after {{
                left: 50%;
                right: auto;
                transform: translateX(-50%);
            }}
            .wp-univ-footer-col .social-wrapper {{
                justify-content: center;
            }}
            .wp-univ-footer-col .contact-item,
            .wp-univ-footer-col ul li a {{
                justify-content: center;
            }}
        }}
    </style>

    <footer class="wp-univ-footer">
        <div class="wp-univ-footer-grid">
            
            <div class="wp-univ-footer-col">
                <h3 style="border:none; padding:0; margin-bottom:15px; font-size:1.8rem; color:{primary}; font-weight:800;">{name}</h3>
                <p style="color: rgba(255,255,255,0.7); line-height: 1.7; margin-bottom: 25px;">{desc_text}</p>
                <div class="social-wrapper" style="display: flex; gap: 15px;">
                    {social_html}
                </div>
            </div>
            
            <div class="wp-univ-footer-col">
                <h3>{services_title}</h3>
                <ul>
                    {services_links}
                </ul>
            </div>
            
            <div class="wp-univ-footer-col">
                <h3>{contact_title}</h3>
                <ul>
                    <li class="contact-item"><i class="fas fa-phone"></i> {phone}</li>
                    <li class="contact-item"><i class="fas fa-envelope"></i> info@{domain}</li>
                    <li class="contact-item"><i class="fas fa-map-marker-alt"></i> {city}{', ' + country if country else ''}</li>
                </ul>
            </div>
            
        </div>
        
        <div style="max-width: 1200px; margin: 0 auto; padding: 20px; border-top: 1px solid rgba(255,255,255,0.05); text-align: center; color: rgba(255,255,255,0.5); font-size: 0.9rem;">
            &copy; {datetime.now().year} {name}. {rights_text}
        </div>
    </footer>
    '''
def export_footer_as_page(wp_conf, b_data, structure):
    """
    Creates a dedicated WordPress page that contains the Footer HTML.
    This page can be used to copy the footer code once and reuse across all pages.
    """
    footer_html = build_enhanced_footer(b_data, structure)
    
    footer_page_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Footer Code - Copy and Paste</title>
        <style>
            body {{ font-family: sans-serif; padding: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .success {{ background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #28a745; }}
            pre {{ background: #1e1e1e; color: #d4d4d4; padding: 20px; border-radius: 8px; overflow-x: auto; }}
            button {{ background: #0073aa; color: white; border: none; padding: 12px 24px; border-radius: 5px; cursor: pointer; font-weight: bold; margin-bottom: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success"><strong>✅ Footer Generated!</strong> Copy the code below and paste it into a Custom HTML widget in your WordPress Footer area.</div>
            <button onclick="navigator.clipboard.writeText(document.getElementById('footer-code').innerText); alert('Copied!');">📋 Copy Footer Code</button>
            <pre id="footer-code"><code>{escape(footer_html)}</code></pre>
            <div style="margin-top:40px;"><h3>Live Preview:</h3>{footer_html}</div>
        </div>
    </body>
    </html>
    '''
    
    auth = base64.b64encode(f"{wp_conf['user']}:{wp_conf['pass']}".encode()).decode('utf-8')
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
    payload = {"title": "Footer Code (Copy This)", "content": footer_page_content, "slug": "footer-code", "status": "draft"}
    
    try:
        check_url = f"{wp_conf['url'].rstrip('/')}/wp-json/wp/v2/pages?slug=footer-code"
        check_response = requests.get(check_url, headers=headers, verify=False, timeout=30)
        if check_response.status_code == 200 and check_response.json():
            pid = check_response.json()[0]['id']
            requests.put(f"{wp_conf['url'].rstrip('/')}/wp-json/wp/v2/pages/{pid}", headers=headers, json=payload, verify=False)
            print(f"\n✅ Footer Code Page Updated!")
        else:
            requests.post(f"{wp_conf['url'].rstrip('/')}/wp-json/wp/v2/pages", headers=headers, json=payload, verify=False)
            print(f"\n✅ Footer Code Page Created!")
    except Exception as e:
        print(f"   ⚠️ Error creating footer page: {e}")
def export_global_css_as_page(wp_conf, b_data):
    """Creates a dedicated WordPress page containing the Global CSS."""
    css_content = get_enterprise_css(b_data)
    
    page_content = f'''
    <div style="background: #e8f0fe; padding: 25px; border-left: 5px solid #0073aa; margin-bottom: 20px;">
        <h3>✅ Global CSS Generated</h3>
        <p>Copy the code below and paste it into your WordPress Customizer (Appearance -> Customize -> Additional CSS) OR into a site-wide HTML widget.</p>
    </div>
    <pre style="background: #1e1e1e; color: #d4d4d4; padding: 20px; overflow-y: auto; max-height: 500px;"><code>{escape(css_content)}</code></pre>
    '''
    
    auth = base64.b64encode(f"{wp_conf['user']}:{wp_conf['pass']}".encode()).decode('utf-8')
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
    payload = {"title": "Global CSS Code (Copy This)", "content": page_content, "slug": "global-css-code", "status": "draft"}
    
    try:
        check_url = f"{wp_conf['url'].rstrip('/')}/wp-json/wp/v2/pages?slug=global-css-code"
        check_response = requests.get(check_url, headers=headers, verify=False, timeout=30)
        if check_response.status_code == 200 and check_response.json():
            pid = check_response.json()[0]['id']
            requests.put(f"{wp_conf['url'].rstrip('/')}/wp-json/wp/v2/pages/{pid}", headers=headers, json=payload, verify=False)
            print(f"\n✅ Global CSS Code Page Updated!")
        else:
            requests.post(f"{wp_conf['url'].rstrip('/')}/wp-json/wp/v2/pages", headers=headers, json=payload, verify=False)
            print(f"\n✅ Global CSS Code Page Created!")
    except Exception as e:
        print(f"   ⚠️ Error creating CSS page: {e}")

# ==============================================================================
# 📞 CONTACT PAGE BUILDER
# ==============================================================================
def build_contact_html(b_data):
    """Build the raw HTML for the Contact page matching the Home Page Hero aesthetic."""
    ui = b_data.get('ui', {})
    primary = b_data.get('primary', '#1e40af')
    accent = b_data.get('accent', '#d4af37')
    name = b_data.get('name', '')
    phone = b_data.get('phone', '')
    city = b_data.get('city', 'our city')
    industry = b_data.get('industry', 'professional')
    target_lang = b_data.get('target_lang', 'en')
    business_name = escape(b_data.get('name', ''))
    
    dir_attr = get_language_direction(target_lang)
    lang_code = target_lang[:2]

    hero_img = get_hosted_image(f"Friendly {industry} customer support representative smiling", "hero", industry, service_name="Contact Support")

    if target_lang == 'ar':
        hero_sub = f"تواصل معنا اليوم للحصول على خدمات الخبراء في {city}."
        msg_ph = "رسالة..."
        call_text = "أو اتصل بنا مباشرة"
        err_alert = "يرجى إدخال اسمك ورقم هاتفك"
        succ_msg = "جاري التحويل..."
        trust_signals = ["دعم على مدار الساعة", "استجابة سريعة", "خبراء معتمدون"]
    elif target_lang == 'es':
        hero_sub = f"Póngase en contacto con nosotros hoy para servicios expertos en {city}."
        msg_ph = "Mensaje..."
        call_text = "O Llámenos Directamente"
        err_alert = "Por favor, introduzca su nombre y número de teléfono"
        succ_msg = "Redirigiendo..."
        trust_signals = ["Soporte 24/7", "Respuesta Rápida", "Expertos Certificados"]
    elif target_lang == 'fr':
        hero_sub = f"Contactez-nous aujourd'hui pour des services experts à {city}."
        msg_ph = "Message..."
        call_text = "Ou Appelez-nous Directement"
        err_alert = "Veuillez remplir votre nom et votre numéro de téléphone"
        succ_msg = "Redirection..."
        trust_signals = ["Support 24/7", "Réponse Rapide", "Experts Certifiés"]
    elif target_lang == 'de':
        hero_sub = f"Kontaktieren Sie uns heute für Experten-Dienstleistungen in {city}."
        msg_ph = "Nachricht..."
        call_text = "Oder rufen Sie uns direkt an"
        err_alert = "Bitte geben Sie Ihren Namen und Ihre Telefonnummer ein"
        succ_msg = "Weiterleiten..."
        trust_signals = ["24/7 Support", "Schnelle Antwort", "Zertifizierte Experten"]
    else:
        hero_sub = f"Get in touch with us today for expert services in {city}."
        msg_ph = "Message..."
        call_text = "Or Call Us Directly"
        err_alert = "Please fill in your name and phone number"
        succ_msg = "Redirecting..."
        trust_signals = ["24/7 Support", "Fast Response", "Certified Experts"]

    signals_html = '<div class="hero-features" style="margin-top:20px;">'
    for sig in trust_signals:
        signals_html += f'<div class="hero-feature"><span class="iconify" data-icon="mdi:check-decagram" data-width="22" style="color: {accent}; margin-right: 8px;"></span> {sig}</div>'
    signals_html += '</div>'

    html = f'''
    <script>
    window.v360ContactConfig = window.v360ContactConfig || {{}};
    window.v360ContactConfig.phone = "{phone}";
    window.v360ContactConfig.whatsapp = "{b_data.get('whatsapp', '')}";
    window.v360ContactConfig.sheetUrl = "{b_data.get('google_sheet_url', '')}";
    window.v360ContactConfig.source = "{business_name} - Contact Form";
    
    window.handleContactLead = function(e, formId) {{
        try {{ if(e) e.preventDefault(); }} catch(err) {{}}
        
        var name = document.getElementById(formId + '-name')?.value || '';
        var phone = document.getElementById(formId + '-phone')?.value || '';
        var msg = document.getElementById(formId + '-msg')?.value || '';
        
        if (!name || !phone) {{
            alert('{err_alert}');
            return false;
        }}
        
        var form = document.getElementById(formId);
        var btn = form ? form.querySelector('button[type="submit"]') : null;
        var originalText = btn ? btn.innerHTML : '';
        
        if (btn) btn.innerHTML = '<span class="iconify" data-icon="mdi:check-circle" data-width="20" style="margin-right:8px;"></span> {succ_msg}';
        
        try {{
            if (window.v360ContactConfig.sheetUrl && window.v360ContactConfig.sheetUrl.length > 10) {{
                var data = new FormData();
                data.append('Source', window.v360ContactConfig.source);
                data.append('Name', name);
                data.append('Phone', phone);
                data.append('Service', 'General Inquiry');
                data.append('Message', msg);
                data.append('Date', new Date().toLocaleString());
                fetch(window.v360ContactConfig.sheetUrl, {{ method: 'POST', body: data, mode: 'no-cors' }}).catch(function(){{}});
            }}
        }} catch(sheetErr) {{}}
        
        try {{
            var whatsappNumber = String(window.v360ContactConfig.whatsapp).replace(/[^0-9]/g, '');
            var rawText = "New Lead from " + window.v360ContactConfig.source + ":\\n\\n*Name:* " + name + "\\n*Phone:* " + phone + "\\n*Message:* " + msg;
            var waUrl = "https://wa.me/" + whatsappNumber + "?text=" + encodeURIComponent(rawText);
            
            /* 💎 FIX: Safely force new tab redirect */
            window.open(waUrl, '_blank');
            
            setTimeout(function() {{
                if (form && typeof form.reset === 'function') form.reset();
                if (btn) btn.innerHTML = originalText;
            }}, 2000);
        }} catch(waErr) {{
            if (btn) btn.innerHTML = originalText;
        }}
        return false;
    }};
    </script>
    
    <div id="v360-wrapper" dir="{dir_attr}" class="lang-{lang_code}">
        <section class="hero" style="background-image: url('{hero_img}'); min-height: 600px; padding: 80px 0; background-position: center; background-size: cover; position: relative;">
            <div class="hero-overlay" style="position: absolute; inset: 0; background: linear-gradient(135deg, rgba(15,23,42,0.92) 0%, rgba(15,23,42,0.75) 100%);"></div>
            <div class="container hero-content" style="position: relative; z-index: 2; display: grid; grid-template-columns: 1fr 1fr; gap: 40px; align-items: center;">
                <div class="text-col">
                    <div class="hero-gold-badge" style="background: linear-gradient(135deg, {accent} 0%, #F5A623 100%); color: #000; padding: 8px 20px; border-radius: 30px; display: inline-block; font-weight: bold; margin-bottom: 20px;">
                        <i class="fas fa-headset"></i> {ui.get('get_in_touch', 'Get in Touch')}
                    </div>
                    <h1 class="hero-title" style="color: white; font-size: 3.5rem; font-weight: 800; line-height: 1.1; margin-bottom: 20px;">{ui.get('contact', 'Contact')} {name}</h1>
                    <p class="hero-sub" style="color: #cbd5e1; font-size: 1.2rem; line-height: 1.6;">{hero_sub}</p>
                    {signals_html}
                </div>
                
                <div class="form-col">
                    <div class="glass-card" style="background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 20px; padding: 40px; box-shadow: 0 20px 40px rgba(0,0,0,0.3);">
                        <h3 style="color: white; margin-bottom: 25px; text-align: center; font-size: 1.6rem;">{ui.get('send_message', 'Send Us a Message')}</h3>
                        <form id="contact-form" action="javascript:void(0);" onsubmit="window.handleContactLead(event, 'contact-form'); return false;">
                            <input type="text" id="contact-form-name" placeholder="{ui.get('name_ph', 'Your Name')}" required style="width: 100%; padding: 15px; margin-bottom: 15px; border: none; border-radius: 8px; background: rgba(255,255,255,0.9); font-family: inherit;">
                            <input type="tel" id="contact-form-phone" placeholder="{ui.get('phone_ph', 'Your Phone')}" required style="width: 100%; padding: 15px; margin-bottom: 15px; border: none; border-radius: 8px; background: rgba(255,255,255,0.9); font-family: inherit;">
                            <textarea id="contact-form-msg" placeholder="{msg_ph}" required style="width: 100%; padding: 15px; margin-bottom: 20px; border: none; border-radius: 8px; height: 120px; font-family: inherit; background: rgba(255,255,255,0.9);"></textarea>
                            <button type="submit" class="btn btn-primary" style="width: 100%; padding: 15px; font-size: 1.1rem; font-weight: bold; background: {primary}; color: white; border: none; border-radius: 8px; cursor: pointer; transition: 0.3s;">
                                {ui.get('send_message', 'Send Message')} <i class="fas fa-paper-plane" style="margin-left: 8px;"></i>
                            </button>
                        </form>
                    </div>
                </div>
            </div>
        </section>

        <section class="section" style="background: #f8fafc; padding: 80px 0;">
            <div class="container">
                <div class="infographic-grid">
                    <div class="infographic-item" style="background: white; padding: 40px 20px; border-radius: 15px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.05);">
                        <div style="width: 70px; height: 70px; background: {primary}15; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; color: {primary}; font-size: 2rem;">
                            <i class="fas fa-phone-alt"></i>
                        </div>
                        <h4 style="font-size: 1.3rem; margin-bottom: 10px; color: #0f172a;">{call_text.split(" ")[-1]}</h4>
                        <p><a href="tel:{phone}" style="color: #64748b; font-size: 1.1rem; text-decoration: none; font-weight: bold;">{phone}</a></p>
                    </div>
                    
                    <div class="infographic-item" style="background: white; padding: 40px 20px; border-radius: 15px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.05);">
                        <div style="width: 70px; height: 70px; background: #25D36615; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; color: #25D366; font-size: 2.2rem;">
                            <i class="fab fa-whatsapp"></i>
                        </div>
                        <h4 style="font-size: 1.3rem; margin-bottom: 10px; color: #0f172a;">WhatsApp</h4>
                        <p><a href="https://wa.me/{b_data.get('whatsapp', '')}" target="_blank" style="color: #64748b; font-size: 1.1rem; text-decoration: none; font-weight: bold;">Message Us</a></p>
                    </div>
                    
                    <div class="infographic-item" style="background: white; padding: 40px 20px; border-radius: 15px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.05);">
                        <div style="width: 70px; height: 70px; background: {accent}15; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; color: {accent}; font-size: 2rem;">
                            <i class="fas fa-map-marker-alt"></i>
                        </div>
                        <h4 style="font-size: 1.3rem; margin-bottom: 10px; color: #0f172a;">Location</h4>
                        <p style="color: #64748b; font-size: 1.1rem;">{city}, {b_data.get('country', '')}</p>
                    </div>
                </div>
            </div>
        </section>
    </div>
    '''
    return html

# ==============================================================================
# 📝 ABOUT PAGE BUILDER
# ==============================================================================
def build_about_html(b_data):
    """Builds a rich, highly professional About Us page matching the Hero style."""
    ui = b_data.get('ui', {})
    primary = b_data.get('primary', '#1e40af')
    accent = b_data.get('accent', '#d4af37')
    name = b_data.get('name', 'Our Company')
    industry = clean_title(b_data.get('industry', 'Services'))
    city = b_data.get('city', 'our area')
    target_lang = b_data.get('target_lang', 'en')
    
    dir_attr = get_language_direction(target_lang)
    lang_code = target_lang[:2]

    hero_img = get_hosted_image(f"Corporate headquarters or professional team for {industry}", "hero", industry, service_name="About Us Hero")
    story_img = get_hosted_image(f"Diverse team of professionals working together in {industry}", "zigzag", industry, service_name="Our Story")

    if target_lang == 'ar':
        title = f"نبذة عن {name}"
        sub = f"رائدون في التميز في مجال {industry} في {city}."
        story_title = "قصتنا"
        story_text = f"تأسست {name} برؤية واضحة: رفع معايير {industry} في {city}. نحن مكرسون لتقديم التميز وبناء علاقات طويلة الأمد مع عملائنا. يضم فريقنا من المحترفين المعتمدين سنوات من الخبرة والتزامًا ثابتاً بالجودة."
        mission_title = "مهمتنا ورؤيتنا"
        mission_text = f"مهمتنا هي تقديم خدمات {industry} من الدرجة الأولى تتجاوز توقعات العملاء من خلال الموثوقية والنزاهة والابتكار. نحن نهدف إلى أن نكون الشريك الأكثر ثقة للشركات والسكان في {city}."
        core_values = "قيمنا الأساسية"
    elif target_lang == 'es':
        title = f"Acerca de {name}"
        sub = f"Liderando la excelencia en {industry} en {city}."
        story_title = "Nuestra Historia"
        story_text = f"{name} se fundó con una visión clara: elevar los estándares de {industry} en {city}. Estamos dedicados a ofrecer excelencia y construir relaciones a largo plazo con nuestros clientes. Nuestro equipo aporta años de experiencia y un compromiso inquebrantable con la calidad."
        mission_title = "Nuestra Misión y Visión"
        mission_text = f"Nuestra misión es proporcionar servicios de {industry} de primer nivel que superen las expectativas del cliente a través de la confiabilidad, integridad e innovación. Nuestro objetivo es ser el socio más confiable en {city}."
        core_values = "Nuestros Valores"
    elif target_lang == 'fr':
        title = f"À propos de {name}"
        sub = f"Chef de file de l'excellence en {industry} à {city}."
        story_title = "Notre Histoire"
        story_text = f"{name} a été fondée avec une vision claire : élever les normes de {industry} à {city}. Nous sommes dévoués à l'excellence et à l'établissement de relations à long terme avec nos clients. Notre équipe apporte des années d'expérience et un engagement inébranlable envers la qualité."
        mission_title = "Notre Mission et Vision"
        mission_text = f"Notre mission est de fournir des services de {industry} de premier ordre qui dépassent les attentes des clients grâce à la fiabilité, l'intégrité et l'innovation."
        core_values = "Nos Valeurs"
    elif target_lang == 'de':
        title = f"Über {name}"
        sub = f"Führend in der {industry}-Exzellenz in {city}."
        story_title = "Unsere Geschichte"
        story_text = f"{name} wurde mit einer klaren Vision gegründet: die Standards für {industry} in {city} zu erhöhen. Wir haben es uns zur Aufgabe gemacht, Exzellenz zu liefern und langfristige Beziehungen zu unseren Kunden aufzubauen."
        mission_title = "Unsere Mission und Vision"
        mission_text = f"Unsere Mission ist es, erstklassige {industry}-Dienstleistungen anzubieten, die die Kundenerwartungen durch Zuverlässigkeit, Integrität und Innovation übertreffen."
        core_values = "Unsere Werte"
    else:
        title = f"About {name}"
        sub = f"Leading the way in {industry} excellence in {city}."
        story_title = "Our Story"
        story_text = f"{name} was founded with a clear vision: to elevate the standards of {industry} in {city}. We are dedicated to delivering excellence and building long-term relationships with our clients. Our team of certified professionals brings years of experience and an unwavering commitment to quality that sets us apart from the competition."
        mission_title = "Our Mission & Vision"
        mission_text = f"Our mission is to provide top-tier {industry} services that exceed customer expectations through reliability, integrity, and innovation. We aim to be the most trusted partner for businesses and residents throughout {city}."
        core_values = "Our Core Values"

    values_data = [
        {"title": "Integrity" if target_lang != 'ar' else "النزاهة", "desc": "Transparent pricing and honest communication." if target_lang != 'ar' else "أسعار شفافة وتواصل صادق.", "icon": "shield-check", "stat": "100%"},
        {"title": "Excellence" if target_lang != 'ar' else "التميز", "desc": "Uncompromising standards in every project." if target_lang != 'ar' else "معايير لا هوادة فيها في كل مشروع.", "icon": "star-circle", "stat": "A+"},
        {"title": "Innovation" if target_lang != 'ar' else "الابتكار", "desc": "Utilizing the latest industry techniques." if target_lang != 'ar' else "استخدام أحدث تقنيات الصناعة.", "icon": "lightbulb-on", "stat": "Modern"}
    ]

    values_html = ""
    for val in values_data:
        icon = val['icon'].replace('mdi:', '')
        values_html += f'''
        <div style="background: white; padding: 30px; border-radius: 15px; border: 1px solid #e2e8f0; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.03);">
            <div style="width: 60px; height: 60px; background: {primary}15; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px; color: {primary}; font-size: 1.8rem;">
                <span class="iconify" data-icon="mdi:{icon}"></span>
            </div>
            <h3 style="margin-bottom: 15px; font-size: 1.3rem; color: {primary};">{val['title']}</h3>
            <p style="color: #64748b; font-size: 0.95rem; line-height: 1.6;">{val['desc']}</p>
        </div>
        '''

    html = f'''
    <div id="v360-wrapper" dir="{dir_attr}" class="lang-{lang_code}">
        <section class="hero" style="background-image: url('{hero_img}'); min-height: 450px; padding: 80px 0; background-position: center; background-size: cover; position: relative;">
            <div class="hero-overlay" style="position: absolute; inset: 0; background: linear-gradient(135deg, rgba(15,23,42,0.85) 0%, rgba(15,23,42,0.65) 100%);"></div>
            <div class="container hero-content" style="position: relative; z-index: 2; text-align:center; display:block;">
                <h1 style="color: white; font-size: 3.5rem; font-weight: 800; margin-bottom:15px; line-height: 1.2;">{title}</h1>
                <p style="color: #cbd5e1; font-size: 1.2rem; max-width: 600px; margin: 0 auto;">{sub}</p>
            </div>
        </section>

        <section class="section" style="padding: 80px 0;">
            <div class="container">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 50px; align-items: center;">
                    <div>
                        <h2 style="font-size: 2.2rem; margin-bottom: 20px; color: {primary};">{story_title}</h2>
                        <div style="width: 60px; height: 4px; background: {accent}; margin-bottom: 30px; border-radius: 2px;"></div>
                        <p style="font-size: 1.1rem; line-height: 1.8; color: #475569; margin-bottom: 20px;">
                            {story_text}
                        </p>
                    </div>
                    <div>
                        <img src="{story_img}" style="width: 100%; border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.15);" alt="Our Story">
                    </div>
                </div>
            </div>
        </section>

        <section class="section" style="background: linear-gradient(135deg, {primary} 0%, #0f172a 100%); padding: 80px 0; text-align: center; color: white;">
            <div class="container" style="max-width: 800px;">
                <span class="iconify" data-icon="mdi:bullseye-arrow" data-width="60" style="color: {accent}; margin-bottom: 20px;"></span>
                <h2 style="font-size: 2.2rem; margin-bottom: 25px; color: white;">{mission_title}</h2>
                <p style="font-size: 1.25rem; line-height: 1.7; color: rgba(255,255,255,0.9);">
                    "{mission_text}"
                </p>
            </div>
        </section>

        <section class="section" style="padding: 80px 0; background: #f8fafc;">
            <div class="container">
                <h2 style="text-align: center; font-size: 2.2rem; margin-bottom: 50px; color: {primary};">{core_values}</h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 30px;">
                    {values_html}
                </div>
            </div>
        </section>
    </div>
    '''
    return html

# ==============================================================================
# 📝 BLOG PAGE BUILDER
# ==============================================================================
def build_blog_page_html(b_data, wp_url):
    primary = b_data.get('primary', '#1e40af')
    accent = b_data.get('accent', '#d4af37')
    industry = b_data.get('industry', 'Business')
    target_lang = b_data.get('target_lang', 'en')
    
    hero_img = get_hosted_image(f"Professional {industry} team researching and writing articles", "hero", industry, service_name="Company Blog")

    if target_lang == 'ar':
        title = "أحدث الأخبار والمقالات"
        sub = "ابق على اطلاع بأحدث الرؤى والأدلة."
        loading = "جاري تحميل المقالات..."
        no_posts = "لم يتم نشر أي مقالات بعد. عد قريباً!"
        read_more = "اقرأ المزيد"
        load_error = "تعذر تحميل المقالات."
        arrow = "fa-arrow-left"
    elif target_lang == 'es':
        title = "Nuestras Últimas Noticias y Artículos"
        sub = "Manténgase actualizado con información y guías."
        loading = "Cargando artículos..."
        no_posts = "Aún no se han publicado artículos. ¡Vuelve pronto!"
        read_more = "Leer Más"
        load_error = "No se pudieron cargar los artículos."
        arrow = "fa-arrow-right"
    elif target_lang == 'fr':
        title = "Nos Dernières Nouvelles et Articles"
        sub = "Restez informé avec des idées et des guides."
        loading = "Chargement des articles..."
        no_posts = "Aucun article publié pour le moment. Revenez bientôt !"
        read_more = "Lire la Suite"
        load_error = "Impossible de charger les articles."
        arrow = "fa-arrow-right"
    elif target_lang == 'de':
        title = "Unsere neuesten Nachrichten und Artikel"
        sub = "Bleiben Sie auf dem Laufenden mit Einblicken und Leitfäden."
        loading = "Artikel werden geladen..."
        no_posts = "Noch keine Artikel veröffentlicht. Schauen Sie bald wieder vorbei!"
        read_more = "Weiterlesen"
        load_error = "Artikel konnten nicht geladen werden."
        arrow = "fa-arrow-right"
    else:
        title = "Our Latest News & Articles"
        sub = "Stay updated with insights, guides, and industry news."
        loading = "Loading articles..."
        no_posts = "No articles published yet. Check back soon!"
        read_more = "Read More"
        load_error = "Unable to load articles."
        arrow = "fa-arrow-right"

    html = f'''
    <section class="hero" style="background-image: url('{hero_img}'); min-height: 400px; padding: 80px 0; background-position: center; background-size: cover; position: relative;">
        <div class="hero-overlay" style="position: absolute; inset: 0; background: linear-gradient(135deg, rgba(15,23,42,0.85) 0%, rgba(15,23,42,0.65) 100%);"></div>
        <div class="container hero-content" style="position: relative; z-index: 2; text-align:center; display:block;">
            <div class="hero-gold-badge" style="background: linear-gradient(135deg, {accent} 0%, #F5A623 100%); color: #000; padding: 8px 20px; border-radius: 30px; display: inline-block; font-weight: bold; margin-bottom: 20px;">
                <i class="fas fa-newspaper"></i> {title.split()[0]} Updates
            </div>
            <h1 style="color: white; font-size: 3.5rem; font-weight: 800; margin-bottom:15px; line-height: 1.2;">{title}</h1>
            <p style="color: #cbd5e1; font-size: 1.2rem; max-width: 600px; margin: 0 auto;">{sub}</p>
        </div>
    </section>
    
    <section class="section" style="padding: 80px 0; background: #f8fafc;">
        <div class="container">
            <div id="blog-container" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 30px;">
                <div style="text-align:center; width:100%; grid-column: 1 / -1; padding: 40px;">
                    <i class="fas fa-spinner fa-spin" style="font-size: 2.5rem; color: {primary}; margin-bottom:15px;"></i> 
                    <p style="color: #64748b; font-size: 1.1rem; font-weight: 500;">{loading}</p>
                </div>
            </div>
        </div>
    </section>

    <style>
        .v360-blog-card {{
            background: white;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
            border: 1px solid #e2e8f0;
            height: 100%;
        }}
        .v360-blog-card:hover {{
            transform: translateY(-8px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.1);
            border-color: {primary};
        }}
        .v360-blog-img-wrap {{
            height: 220px;
            overflow: hidden;
            position: relative;
        }}
        .v360-blog-img-wrap img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.5s ease;
        }}
        .v360-blog-card:hover .v360-blog-img-wrap img {{
            transform: scale(1.05);
        }}
        .v360-blog-content {{
            padding: 25px;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
        }}
        .v360-blog-title {{
            font-size: 1.4rem;
            color: #0f172a;
            margin-bottom: 15px;
            font-weight: 700;
            line-height: 1.3;
        }}
        .v360-blog-excerpt {{
            color: #64748b;
            font-size: 0.95rem;
            line-height: 1.6;
            margin-bottom: 25px;
            flex-grow: 1;
        }}
        .v360-blog-btn {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: {primary};
            font-weight: 700;
            text-decoration: none;
            transition: 0.2s;
            margin-top: auto;
        }}
        .v360-blog-btn:hover {{
            color: {accent};
            gap: 12px;
        }}
    </style>

    <script>
    document.addEventListener("DOMContentLoaded", function() {{
        const apiUrl = "{wp_url.rstrip('/')}/wp-json/wp/v2/posts?_embed&per_page=9";
        
        fetch(apiUrl)
            .then(response => response.json())
            .then(posts => {{
                const container = document.getElementById('blog-container');
                container.innerHTML = ''; 
                
                if (posts.length === 0) {{
                    container.innerHTML = '<p style="text-align:center; width:100%; grid-column: 1 / -1; font-size:1.2rem; color:#64748b;">{no_posts}</p>';
                    return;
                }}

                posts.forEach(post => {{
                    const postTitle = post.title.rendered;
                    const link = post.link;
                    const excerpt = post.excerpt.rendered.replace(/<[^>]*>?/gm, '').substring(0, 120) + '...';
                    
                    let imgUrl = 'https://images.unsplash.com/photo-1432821596592-e2c18b78144f?auto=format&fit=crop&w=800&q=80';
                    
                    if (post._embedded && post._embedded['wp:featuredmedia'] && post._embedded['wp:featuredmedia'][0].source_url) {{
                        imgUrl = post._embedded['wp:featuredmedia'][0].source_url;
                    }}

                    const dateObj = new Date(post.date);
                    /* 🛡️ FIX: Changed from // to block comment to survive minification */
                    const formattedDate = dateObj.toLocaleDateString('{"en-US" if target_lang != "ar" else "ar-EG"}', {{ month: 'short', day: 'numeric', year: 'numeric' }});

                    const cardHtml = `
                        <div class="v360-blog-card">
                            <div class="v360-blog-img-wrap">
                                <img src="${{imgUrl}}" alt="${{postTitle}}">
                            </div>
                            <div class="v360-blog-content">
                                <div style="font-size: 0.85rem; color: #94a3b8; font-weight: 600; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px;">
                                    <i class="far fa-calendar-alt"></i> ${{formattedDate}}
                                </div>
                                <h3 class="v360-blog-title">${{postTitle}}</h3>
                                <div class="v360-blog-excerpt">${{excerpt}}</div>
                                <a href="${{link}}" class="v360-blog-btn">
                                    {read_more} <i class="fas {arrow}"></i>
                                </a>
                            </div>
                        </div>
                    `;
                    container.innerHTML += cardHtml;
                }});
            }})
            .catch(error => {{
                document.getElementById('blog-container').innerHTML = '<div style="text-align:center; width:100%; grid-column: 1 / -1;"><i class="fas fa-exclamation-triangle" style="color:#ef4444; font-size:2rem; margin-bottom:15px;"></i><p style="color:#64748b;">{load_error}</p></div>';
                console.error('Error fetching posts:', error);
            }});
    }});
    </script>
    '''
    return html

# ==============================================================================
# 🧠 DYNAMIC STRUCTURE ENGINE
# ==============================================================================

@retry_operation(max_retries=3)
def analyze_structure_with_ai(raw_input, target_lang="en", mode="urls"):
    """Analyze input and create service hierarchy using AI. Now enforces output language."""
    fallback = {
        "General Services": {
            "description": "Comprehensive general services for all needs",
            "children": ["Service 1", "Service 2", "Service 3"],
            "sibling_relationships": {"Service 1": ["Service 2", "Service 3"]},
            "child_services": {"Service 1": ["Specialized Service A", "Specialized Service B"]}
        }
    }
    
    if not CLIENTS['openai']:
        return fallback

    ignore_keywords = ['cost', 'quote', 'contact', 'blog', 'project', 'about', 'terms', 'policy', 'privacy', 'login', 'signup']
    
    if mode == "urls":
        lines = detangle_urls(raw_input)
    else:
        lines = [line.strip() for line in raw_input.split('\n') if line.strip()]
        
    cleaned_lines = [l for l in lines if not any(bad in l.lower() for bad in ignore_keywords)]
    cleaned_input = "\n".join(list(set(cleaned_lines)))
    
    print(f"   ℹ️  Processing {len(cleaned_lines)} unique items...")

    # 🌍 MAP LANGUAGE FOR PROMPT (This was missing in your pasted code!)
    lang_names = {"en": "English", "ar": "Arabic", "es": "Spanish", "fr": "French", "de": "German"}
    full_lang_name = lang_names.get(target_lang, "English")

    system_prompt = "You are a Website Information Architect. Output must be valid JSON."
    
    # 🛑 PRO FIX: Forced the AI to write category descriptions in the target language!
    prompt = f"""
    Organize this service list into a logical hierarchy with relationships.
    
    INPUT: {cleaned_input}
    
    RULES:
    1. Group into EXACTLY 6 Logical Parent Categories
    2. Create sibling relationships
    3. Add child services where appropriate
    4. CRITICAL: You MUST categorize and include EVERY SINGLE service from the INPUT list.
    5. LANGUAGE LOCK: ALL "description" text fields MUST be written natively in {full_lang_name}. (The Category Names and Service Names should remain exactly as provided in the INPUT).
    
    RETURN JSON ONLY with this structure:
    {{
        "Category Name": {{
            "description": "Persuasive, action-oriented SEO description in {full_lang_name} highlighting the benefit (max 12 words). DO NOT start with 'Services related to'.",
            "children": ["Main Service 1", "Main Service 2"],
            "sibling_relationships": {{
                "Main Service 1": ["Main Service 2", "Main Service 3"]
            }},
            "child_services": {{
                "Main Service 1": ["Specialized Service A", "Specialized Service B"]
            }}
        }}
    }}
    """

    try:
        response = CLIENTS['openai'].chat.completions.create(
            model=Config.MODEL_HIGH_TIER,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        structure = clean_json_response(response.choices[0].message.content)
        if structure:
            global SERVICE_HIERARCHY
            SERVICE_HIERARCHY = structure
            return structure
        return fallback
    except Exception as e:
        print(f"   ⚠️ Structure Analysis Error: {e}")
        return fallback

def build_service_relationship_graph(structure):
    """Build relationship graph from service hierarchy."""
    graph = {}
    
    for category, data in structure.items():
        if not isinstance(data, dict): continue
        
        children = data.get('children', [])
        siblings_map = data.get('sibling_relationships', {})
        child_map = data.get('child_services', {})
        
        for service in children:
            graph[service.lower()] = {
                "category": category,
                "siblings": [s for s in children if s.lower() != service.lower()],
                "children": child_map.get(service, []),
                "parent": None
            }
            
            if service in siblings_map:
                graph[service.lower()]["siblings"] = list(set(graph[service.lower()]["siblings"] + siblings_map[service]))
            
            for child in graph[service.lower()]["children"]:
                graph[child.lower()] = {
                    "category": category,
                    "siblings": [s for s in graph[service.lower()]["children"] if s.lower() != child.lower()],
                    "children": [],
                    "parent": service
                }
                
    return graph

def get_service_relationships(service_name):
    """Get relationships for a specific service."""
    global SERVICE_HIERARCHY
    
    if not SERVICE_HIERARCHY:
        return {"category": "General", "siblings": [], "children": [], "parent": None}
    
    flat_graph = {}
    for cat, data in SERVICE_HIERARCHY.items():
        if not isinstance(data, dict): continue
        
        children = data.get('children', [])
        for svc in children:
            svc_lower = svc.lower()
            flat_graph[svc_lower] = {
                "category": cat,
                "siblings": [s for s in children if s.lower() != svc_lower],
                "children": data.get('child_services', {}).get(svc, []),
                "parent": None
            }
            
            for child in flat_graph[svc_lower]["children"]:
                child_lower = child.lower()
                flat_graph[child_lower] = {
                    "category": cat,
                    "siblings": [s for s in flat_graph[svc_lower]["children"] if s.lower() != child_lower],
                    "children": [],
                    "parent": svc
                }
    
    return flat_graph.get(service_name.lower(), {"category": "General", "siblings": [], "children": [], "parent": None})

# ==============================================================================
# 🔗 BACKLINK MANAGER
# ==============================================================================

class BacklinkManager:
    @staticmethod
    def create_devto_post(title, content, image_url, target_link):
        if not Config.GENERATE_BACKLINKS or not Config.DEVTO_API_KEY:
            return None

        url = "https://dev.to/api/articles"
        headers = {"api-key": Config.DEVTO_API_KEY, "Content-Type": "application/json"}
        
        markdown_body = f"""
![{title}]({image_url})

# {title}

{content}

**[👉 Click here for full service details]({target_link})**
"""
        
        payload = {
            "article": {
                "title": f"Guide: {title}",
                "published": True,
                "body_markdown": markdown_body,
                "main_image": image_url,
                "tags": ["business", "services", "guide"]
            }
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 201:
                print(f"   ✅ Dev.to Post Created")
                return True
        except Exception as e:
            print(f"   ⚠️ Dev.to Error: {e}")
        return False

    @staticmethod
    def create_blogger_post(title, content, image_url, target_link):
        if not Config.GENERATE_BACKLINKS or not os.path.exists('token.json'):
            return None

        try:
            creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/blogger'])
            service = build('blogger', 'v3', credentials=creds)

            if not Config.BLOGGER_ID:
                blogs = service.blogs().listByUser(userId='self').execute()
                if 'items' in blogs:
                    Config.BLOGGER_ID = blogs['items'][0]['id']
                else:
                    return None

            post_body = f"""
            <div style="text-align: center;">
                <img src="{image_url}" style="max-width: 100%; border-radius: 10px;">
            </div>
            <p>{content}</p>
            <p style="text-align: center;">
                <a href="{target_link}">👉 Click here for full guide</a>
            </p>
            """

            body = {"kind": "blogger#post", "title": f"Guide: {title}", "content": post_body}
            
            posts = service.posts()
            result = posts.insert(blogId=Config.BLOGGER_ID, body=body).execute()
            print(f"   ✅ Blogger Link Created")
            return True
        except Exception as e:
            print(f"   ⚠️ Blogger Error: {e}")
            return False

# ==============================================================================
# 🧠 ENHANCED SCHEMA GENERATOR
# ==============================================================================

def get_related_entities(service_name, industry, location, target_lang="en"):
    """Get related entities and keywords for enhanced SEO."""
    cache_key = f"entities_{service_name}_{industry}_{location}_{target_lang}"
    
    if cache_key in Config.ENTITY_CACHE:
        return Config.ENTITY_CACHE[cache_key]
    
    fallback = {
        "keywords": [f"{service_name} {location}", f"best {service_name}", f"professional {service_name}"],
        "entities": [f"{service_name} experts", f"{service_name} professionals"],
        "related_terms": [f"{service_name} near me", f"affordable {service_name}"]
    }

    if not CLIENTS['openai']:
        return fallback
    
    try:
        prompt = f"""
        Generate SEO-related entities and keywords for: "{service_name}"
        Industry: {industry}
        Location: {location}
        
        Return JSON:
        {{
            "keywords": ["keyword1", "keyword2", "keyword3"],
            "entities": ["entity1", "entity2"],
            "related_terms": ["term1", "term2"]
        }}
        """
        
        response = CLIENTS['openai'].chat.completions.create(
            model=Config.MODEL_HIGH_TIER,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.5
        )
        
        content = clean_json_response(response.choices[0].message.content)
        if content:
            Config.ENTITY_CACHE[cache_key] = content
            return content
    except Exception as e:
        print(f"   ⚠️ Entity generation error: {e}")
    
    Config.ENTITY_CACHE[cache_key] = fallback
    return fallback

def extract_top_keywords_from_schema(b_data, service_name, industry, location):
    """Extract top 3 keywords for SEO."""
    try:
        entities = get_related_entities(service_name, industry, location, b_data.get('target_lang', 'en'))
        keywords_list = entities.get("keywords", [])
        
        if keywords_list and len(keywords_list) >= 3:
            return keywords_list[:3]
        elif keywords_list:
            top_kw = keywords_list.copy()
            while len(top_kw) < 3:
                top_kw.append(service_name)
            return top_kw
        else:
            return [service_name, industry, location]
    except Exception as e:
        print(f"   ⚠️ Keyword extraction error: {e}")
        return [service_name, industry, location]

def get_dynamic_seo_data(service_name, city, state, country, industry, target_lang="en"):
    """Get dynamic SEO data including neighborhoods and keywords."""
    neighborhoods = []
    location_string = f"{city}, {state}, {country}".strip(', ')
    
    if CLIENTS['openai']:
        try:
            hood_prompt = f"""List 6-8 popular neighborhoods, districts, or areas in {location_string}. 
            Focus on residential and commercial areas. Return JSON: {{"neighborhoods": ["Area 1", "Area 2"]}}"""
            
            response = CLIENTS['openai'].chat.completions.create(
                model=Config.MODEL_LOW_TIER,
                messages=[{"role": "user", "content": hood_prompt}],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            data = clean_json_response(response.choices[0].message.content)
            if isinstance(data, dict) and 'neighborhoods' in data:
                neighborhoods = data['neighborhoods']
        except Exception as e:
            print(f"   ⚠️ Neighborhood API Error: {e}")

    if not neighborhoods or len(neighborhoods) < 3:
        if city:
            neighborhoods = [f"Central {city}", f"North {city}", f"South {city}", f"{city} Business District"]
        elif state:
            neighborhoods = [f"Central {state}", f"Northern {state}", f"Southern {state}"]
        else:
            neighborhoods = [f"Major Cities in {country}", f"Regional Hubs in {country}"]

    entities = get_related_entities(service_name, industry, location_string, target_lang)
    keywords = entities.get("keywords", [])
    
    if not keywords:
        keywords = [
            f"{clean_title(service_name)} in {location_string}",
            f"Best {clean_title(service_name)} {location_string}",
            f"Professional {clean_title(service_name)} services"
        ]
    
    return neighborhoods[:8], keywords, entities

def get_schema_type(industry):
    """Get appropriate Schema.org types based on industry for Local SEO."""
    if not industry:
        return ["LocalBusiness", "Organization"]
    
    ind = industry.lower()
    mapping = {
        'plumb': ['Plumber', 'HomeAndConstructionBusiness'],
        'electric': ['Electrician', 'HomeAndConstructionBusiness'],
        'dentist': ['Dentist', 'MedicalOrganization'],
        'law': ['Attorney', 'LegalService'],
        'hvac': ['HVACBusiness', 'HomeAndConstructionBusiness'],
        'seo': ['ProfessionalService', 'LocalBusiness'],
        'marketing': ['ProfessionalService', 'LocalBusiness'],
        'digital': ['ProfessionalService', 'LocalBusiness'],
        'roof': ['RoofingContractor', 'HomeAndConstructionBusiness'],
        'auto': ['AutoRepair', 'LocalBusiness'],
        'lock': ['Locksmith', 'HomeAndConstructionBusiness']
    }
    
    for keyword, schema_types in mapping.items():
        if keyword in ind:
            return schema_types
    return ["LocalBusiness", "Organization"]

def generate_hierarchical_schema(b_data, p_data, service_name, page_url, parent_category=None, is_child_page=False, parent_url=None):
    """Generate complete Schema.org markup with strict Google Rich Results compliance."""
    try:
        base_url = Config.WP_URL.rstrip('/')
        display_service_name = clean_title(service_name)
        schema_types = get_schema_type(b_data.get('industry', ''))
        primary_type = schema_types[0] if len(schema_types) > 0 else "LocalBusiness"
        secondary_type = schema_types[1] if len(schema_types) > 1 else "Organization"
        
        location_str = b_data.get('city') if b_data.get('city') else b_data.get('country')
        entities = get_related_entities(display_service_name, b_data.get('industry', ''), location_str, b_data.get('target_lang', 'en'))
        keywords = ", ".join(entities.get("keywords", [])[:10])
        
        image_url = p_data.get('image_url', p_data.get('hero_image', '')) if p_data else ""
        
        # 🛡️ Safe SEO Variables to prevent validation errors
        street_address = b_data.get('street_address', '')
        price_range = b_data.get('price_range', '$$')
        logo_val = b_data.get('logo_url') or image_url
        
        schema_graph = []
        
        # 1. Organization
        org_schema = {
            "@type": secondary_type,
            "@id": f"{base_url}/#organization",
            "name": b_data.get('name', ''),
            "url": f"{base_url}/",
            "description": f"Professional {b_data.get('industry', '')} services in {location_str}",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": b_data.get('city', ''),
                "addressRegion": b_data.get('state', ''),
                "addressCountry": b_data.get('country', '')
            }
        }
        if street_address:
            org_schema["address"]["streetAddress"] = street_address
        if logo_val:
            org_schema["logo"] = logo_val
            
        schema_graph.append(org_schema)
        
        # 2. LocalBusiness (Strictly adhering to Google Guidelines)
        local_biz = {
            "@type": primary_type,
            "@id": f"{page_url}#localbusiness",
            "name": b_data.get('name', ''),
            "description": clean_schema_text(p_data.get('meta_description', f"Professional {display_service_name} services")),
            "url": f"{base_url}/",
            "telephone": b_data.get('phone', ''),
            "priceRange": price_range,
            "address": {
                "@type": "PostalAddress",
                "addressLocality": b_data.get('city', ''),
                "addressRegion": b_data.get('state', ''),
                "addressCountry": b_data.get('country', '')
            },
            "keywords": keywords
        }

        # Dynamically map AI-generated reviews into the schema to prevent Google penalties
        if p_data and 'reviews' in p_data and p_data['reviews']:
            schema_reviews = []
            for rev in p_data['reviews']:
                schema_reviews.append({
                    "@type": "Review",
                    "author": {"@type": "Person", "name": rev.get('name', 'Customer')},
                    "reviewRating": {
                        "@type": "Rating",
                        "ratingValue": rev.get('rating', '5'),
                        "bestRating": "5"
                    },
                    "reviewBody": rev.get('txt', '')
                })
            local_biz["review"] = schema_reviews
            
            # Static 4.9 rating paired with a realistic, slightly randomized review count baseline
            local_biz["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": "4.9", 
                "reviewCount": str(len(schema_reviews) + 45), # Base 45 + the generated reviews
                "bestRating": "5",
                "worstRating": "1"
            }

        if street_address:
            local_biz["address"]["streetAddress"] = street_address
        if image_url:
            local_biz["image"] = image_url
            
        schema_graph.append(local_biz)
        
        # 3. Service
        schema_graph.append({
            "@type": "Service",
            "name": display_service_name,
            "description": clean_schema_text(p_data.get('intro', f"{display_service_name} services")),
            "provider": {"@id": f"{page_url}#localbusiness"},
            "areaServed": {"@type": "Place", "name": location_str},
            "serviceType": display_service_name,
            "keywords": keywords
        })
        
        # 4. BreadcrumbList (💎 PERFECT MATCH ROUTING APPLIED HERE)
        breadcrumbs = [{"@type": "ListItem", "position": 1, "name": "Home", "item": f"{base_url}/"}]
        position = 2
        if service_name.lower() != "home":
            if parent_category:
                if parent_url:
                    p_url = parent_url
                else:
                    # Dynamically calls validate_url so schema routing 100% matches Menu routing
                    cat_path = validate_url("category", parent_category, b_data.get('mode', '3'))
                    p_url = f"{base_url}{cat_path}"
                    
                breadcrumbs.append({"@type": "ListItem", "position": position, "name": clean_title(parent_category), "item": p_url})
                position += 1
                
            breadcrumbs.append({"@type": "ListItem", "position": position, "name": display_service_name, "item": page_url})
            
        schema_graph.append({"@type": "BreadcrumbList", "itemListElement": breadcrumbs})
        
        # 5. WebPage
        schema_graph.append({
            "@type": "WebPage",
            "@id": f"{page_url}#webpage",
            "url": page_url,
            "name": p_data.get('meta_title', display_service_name),
            "description": clean_schema_text(p_data.get('meta_description', '')),
            "datePublished": datetime.now().strftime("%Y-%m-%d"),
            "dateModified": datetime.now().strftime("%Y-%m-%d")
        })
        
        # 6. WebSite
        schema_graph.append({
            "@type": "WebSite",
            "@id": f"{base_url}/#website",
            "url": f"{base_url}/",
            "name": b_data.get('name', ''),
            "description": f"Professional {b_data.get('industry', '')} services in {location_str}",
            "publisher": {"@id": f"{base_url}/#organization"}
        })
        
        # 7. FAQPage
        if p_data and 'faqs' in p_data and p_data['faqs']:
            faq_entities = []
            for f in p_data['faqs'][:5]:
                question = f.get('q', f.get('question', ''))
                answer = f.get('a', f.get('answer', ''))
                if question and answer:
                    faq_entities.append({
                        "@type": "Question",
                        "name": question,
                        "acceptedAnswer": {"@type": "Answer", "text": answer[:200]}
                    })
            if faq_entities:
                schema_graph.append({
                    "@type": "FAQPage",
                    "@id": f"{page_url}#faqpage",
                    "mainEntity": faq_entities
                })

        return json.dumps({"@context": "https://schema.org", "@graph": schema_graph}, indent=2)
        
    except Exception as e:
        print(f"   ⚠️ Schema Generation Error: {e}")
        return json.dumps({
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": b_data.get('name', ''),
            "url": Config.WP_URL
        })
# ==============================================================================
# 🧠 ENHANCED CONTENT ENGINE
# ==============================================================================

@retry_operation(max_retries=3)
def generate_sub_services(b_data, main_service):
    """Generate 6+ related sub-services for Mode 1."""
    if not CLIENTS['openai']:
        return [f"Strategic {main_service} Planning", f"Executive {main_service} Management",
                f"Analytics & {main_service} Reporting", f"{main_service} Audit & Optimization",
                f"Advanced {main_service} Techniques", f"{main_service} ROI Maximization"]
    
    target_lang = b_data.get('target_lang', 'en')
    lang_names = {"en": "English", "ar": "Arabic", "es": "Spanish", "fr": "French", "de": "German"}
    full_lang_name = lang_names.get(target_lang, "English")

    try:
        prompt = f"""
        Generate 6 SPECIFIC, REALISTIC sub-services for: "{main_service}"
        Industry: {b_data.get('industry')}
        Location: {b_data.get('city', b_data.get('country'))}

        CRITICAL LANGUAGE RULE: Every sub-service name MUST be written natively in {full_lang_name}.
        Do NOT return English if {full_lang_name} is different.

        Return JSON: {{"sub_services": ["service1", "service2", ...]}}
        """
        
        response = CLIENTS['openai'].chat.completions.create(
            model=Config.MODEL_LOW_TIER,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        content = clean_json_response(response.choices[0].message.content)
        if content and 'sub_services' in content and len(content['sub_services']) >= 6:
            return content['sub_services'][:6]
    except Exception as e:
        print(f"   ⚠️ Sub-service generation error: {e}")
    
    if target_lang == 'ar':
        return [f"خدمة {main_service} المتخصصة {i+1}" for i in range(6)]
    return [f"Professional {main_service} - Service {i+1}" for i in range(6)]

@retry_operation(max_retries=3)
def generate_service_faqs(b_data, service_name, category):
    """
    💎 AEO-OPTIMIZED FAQ ENGINE: Generates 'People Also Ask' style content.
    Forces factual, objective answers (Pricing, Timeframes) to win Perplexity/ChatGPT 
    extractions, while injecting LSI keywords for Google Traditional SEO.
    """
    cache_key = f"faqs_{service_name}_{category}_{b_data.get('target_lang', 'en')}"
    if cache_key in SERVICE_FAQS_CACHE:
        return SERVICE_FAQS_CACHE[cache_key]
    
    city = b_data.get('city', '')
    location = city if city else b_data.get('country', '')
    target_lang = b_data.get('target_lang', 'en')
    clean_srv = clean_title(service_name) if service_name else "services"
    industry = b_data.get('industry', 'service')

    # 🌍 MAP LANGUAGE FOR PROMPT
    lang_names = {"en": "English", "ar": "Arabic", "es": "Spanish", "fr": "French", "de": "German"}
    full_lang_name = lang_names.get(target_lang, "English")

    fallback_faqs = [
        {"q": f"How much does {clean_srv} cost in {location}?", "a": f"The cost for {clean_srv} depends on the scope of work, but we provide transparent, upfront pricing before any job begins in {location}."},
        {"q": f"How quickly can you respond to {clean_srv} requests?", "a": "Emergency service is typically available within 60 minutes, while standard appointments are scheduled within 24 hours."},
        {"q": f"Are you licensed and insured for {clean_srv} work?", "a": "Yes, all our professionals are fully licensed, bonded, and insured to ensure complete safety and compliance."},
        {"q": f"How long does a typical {clean_srv} job take?", "a": "Most standard jobs are completed within 2 to 4 hours, though complex projects may require a full day or more."},
        {"q": f"Do you offer warranties on your {clean_srv} work?", "a": "Yes, all work comes with a comprehensive warranty covering both parts and labor for your peace of mind."}
    ]

    if not CLIENTS['openai']: return fallback_faqs
    
    # 1. FETCH LSI KEYWORDS FOR TRADITIONAL SEO INJECTION
    entities = get_related_entities(service_name, industry, location, target_lang)
    lsi_terms = entities.get('related_terms', [])[:3]
    
    lsi_instruction = f"TRADITIONAL SEO RULE: You MUST naturally weave these exact long-tail phrases into the Questions or Answers: {', '.join(lsi_terms)}" if lsi_terms else ""

    # Niche-specific tone (medical = reassuring, trades = practical, etc.)
    _niche = b_data.get('niche_engine')
    tone_instruction = _niche.get_faq_tone_instruction() if _niche and hasattr(_niche, 'get_faq_tone_instruction') else "Be professional and clear."
    
    # 2. THE HYBRID AEO/SEO PROMPT
    prompt = f"""
    You are an elite AEO (Answer Engine Optimization) and SEO Architect.
    Generate EXACTLY 5 "People Also Ask" (PAA) style FAQ questions and answers for {clean_srv} services in {location}.
    CONTEXT: {industry} industry, {category} category.
    LANGUAGE: {full_lang_name}
    
    CRITICAL AEO RULES (To win Perplexity, Gemini, and ChatGPT extractions):
    1. HOT TOPICS ONLY: Questions MUST focus on what humans actually worry about: Pricing/Costs, Timeframes/Speed, and Specific Troubleshooting/Process details.
    2. BE OBJECTIVE & FACTUAL: Answers MUST be direct and factual. Absolutely NO marketing fluff (Do not say "Call our amazing team today!"). 
    3. GIVE ESTIMATES: Include realistic, estimated cost ranges or precise timeframes (e.g., "typically takes 2-4 hours", or "costs vary based on X and Y, usually starting around...").
    
    TONE INSTRUCTION: {tone_instruction}
    
    {lsi_instruction}
    
    RETURN JSON FORMAT ONLY: {{"faqs": [{{"q": "Question 1", "a": "Answer 1"}}, ...]}}
    """
    
    try:
        print(f"   🧠 Generating AEO-Optimized FAQs for {clean_srv[:20]}...")
        # Claude-first (best AEO logic), OpenAI fallback
        content = call_claude_json(prompt)
        if not content and CLIENTS.get('openai'):
            response = CLIENTS['openai'].chat.completions.create(
                model=Config.MODEL_HIGH_TIER,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.6,
                max_tokens=800
            )
            content = clean_json_response(response.choices[0].message.content)
        if content and 'faqs' in content and len(content['faqs']) >= 3:
            final_faqs = content['faqs'][:5]
            SERVICE_FAQS_CACHE[cache_key] = final_faqs
            return final_faqs
    except Exception as e:
        print(f"   ⚠️ AEO FAQ Generation Error: {e}")
    
    SERVICE_FAQS_CACHE[cache_key] = fallback_faqs
    return fallback_faqs
def generate_zigzag_content_with_links(b_data, service_name, category, is_child_page=False, related_services=None, page_seed=None):
    """Generate zigzag section content, inject secondary keywords, and add PERFECT localized internal links."""
    seed = page_seed if page_seed else service_name
    cache_key = f"zigzag_links_{service_name}_{category}_{is_child_page}_{seed}"
    
    if cache_key in ZIGZAG_CONTENT_CACHE:
        return ZIGZAG_CONTENT_CACHE[cache_key]
    
    location = b_data.get('city', '') or b_data.get('country', '')
    mode = b_data.get('mode', '3')
    target_lang = b_data.get('target_lang', 'en')
    
    base_path = Config.SERVICE_BASE_PATH
    if not base_path.startswith('/'): base_path = '/' + base_path
    if not base_path.endswith('/'): base_path = base_path + '/'

    # 🌍 MAP LANGUAGE FOR PROMPT
    lang_names = {"en": "English", "ar": "Arabic", "es": "Spanish", "fr": "French", "de": "German"}
    full_lang_name = lang_names.get(target_lang, "English")

    # FETCH SECONDARY KEYWORDS FOR ZIGZAG INJECTION
    entities = get_related_entities(service_name, b_data.get('industry', ''), location, target_lang)
    secondary_keywords = entities.get("keywords", [])[1:4] 
    sec_kw_instruction = f"SEO CRITICAL: Naturally weave these secondary keywords into the text: {', '.join(secondary_keywords)}" if secondary_keywords else ""
    
    random_seed = random.randint(1, 1000)
    
    if CLIENTS['openai']:
        url_map_str = ""
        link_instruction = ""
        
        # 🛑 PRO FIX: Conditionally ask AI for links ONLY if allowed by Config
        if Config.GENERATE_INTERNAL_LINKS and related_services:
            for svc in related_services[:3]:
                perfect_url = validate_url('service', svc, mode)
                url_map_str += f"- Service Name: '{svc}' -> EXACT URL TO USE: {perfect_url}\n"
            
            link_instruction = f"""
            3. INCLUDE 2-3 NATURAL INTERNAL LINKS. 
               Write standard HTML <a> tags directly in the text. 
               For the clickable text of the link, TRANSLATE the service name into native {full_lang_name}. 
               For the href attribute, you MUST use the exact URL provided below.
            """
        else:
            url_map_str = "None. Do not link to anything."
            link_instruction = "3. CRITICAL: DO NOT include any HTML links (<a> tags) or URLs in the description."
        
        prompt = f"""
        You are an elite conversion copywriter for a {b_data.get('industry')} business in {location}.
        Write a RICH, DETAILED zigzag section for this specific service: {clean_title(service_name)}
        UNIQUE SEED: {random_seed}
        TARGET LANGUAGE: {full_lang_name}

        WRITING RULES:
        1. LENGTH: Write exactly 3 full paragraphs (minimum 150 words total). Separate paragraphs with <br><br>.
        2. PARAGRAPH 1: What is this service, who needs it, what problem does it solve in {location}?
        3. PARAGRAPH 2: How do we do it differently? What technique, tool, or guarantee sets us apart?
        4. PARAGRAPH 3: What result/benefit/peace of mind does the customer get afterward?
        5. Use <strong> tags on 2-3 key phrases that show expertise or urgency.
        6. Start with a DIRECT HOOK — the customer's pain point or a surprising fact. NOT "In today's world" or "Professional services".
        7. Weave these semantic keywords naturally: {', '.join(secondary_keywords)}
        8. {("Plain prose only — do NOT include any <a href> links." if not (Config.GENERATE_INTERNAL_LINKS and related_services) else "Weave 2-3 internal links using ONLY the exact URLs provided below; translate the clickable text into native " + full_lang_name + ".")}
        9. BANNED FILLER (instant rejection): "Our experienced team provides customized solutions", "We use the latest technology", "premium materials for lasting results".
        10. Include at least ONE specific realistic number: a price range, timeframe, count, or percentage relevant to {location}.
        11. AUTO-ADAPT tone: medical/dental = reassuring; trades/repair = urgent and practical; beauty/luxury = aspirational; professional services = authoritative. Follow Problem → Agitate → Solution flow.
        12. ALL text MUST be written natively in {full_lang_name}.

        RETURN JSON ONLY:
        {{
            "title": "Catchy 4-6 word title specific to {clean_title(service_name)} in {full_lang_name}",
            "description": "3 rich paragraphs separated by <br><br> in {full_lang_name}"
        }}

        AVAILABLE SERVICES TO LINK TO (USE THESE EXACT URLS FOR THE HREF):
        {url_map_str}
        """
        
        try:
            # Claude-first (richer copy), OpenAI fallback
            content = call_claude_json(prompt)
            if not content:
                response = CLIENTS['openai'].chat.completions.create(
                    model=Config.MODEL_LOW_TIER,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.9
                )
                content = clean_json_response(response.choices[0].message.content)
            if content and 'title' in content and 'description' in content:
                desc = content['description'].strip()
                
                # Absolute fail-safe: Strip URLs from AI text if links are disabled just in case AI disobeys
                if not Config.GENERATE_INTERNAL_LINKS:
                    desc = re.sub(r'<a\b[^>]*>(.*?)</a>', r'\1', desc, flags=re.IGNORECASE)
                elif base_path == "/":
                    # Absolute fail-safe: If AI still forced a /services/ path, strip it out if base_path is "/"
                    desc = re.sub(r'href=[\'"](?:https?://[^/]+)?/services/([^\'"]+)[\'"]', r'href="/\1"', desc)
                
                # Ensure minimum length with Localized additional sentences
                sentences = desc.split('. ')
                if len(sentences) < 6:
                    if target_lang == 'ar':
                        additional = [
                            f"يتوفر أخصائيو {clean_title(service_name)} لدينا للمكالمات الطارئة في {location}.",
                            f"نحن نقدم تقديرات مجانية لجميع المشاريع.",
                            f"رضا العملاء هو أولويتنا القصوى.",
                            f"اتصل بفريقنا اليوم لمناقشة احتياجاتك."
                        ]
                    elif target_lang == 'es':
                        additional = [
                            f"Nuestros especialistas en {clean_title(service_name)} están disponibles 24/7 en {location}.",
                            f"Ofrecemos presupuestos gratuitos para todos los proyectos.",
                            f"La satisfacción del cliente es nuestra máxima prioridad.",
                            f"Póngase en contacto con nuestro equipo hoy mismo."
                        ]
                    elif target_lang == 'fr':
                        additional = [
                            f"Nos spécialistes en {clean_title(service_name)} sont disponibles 24/7 à {location}.",
                            f"Nous fournissons des devis gratuits pour tous les projets.",
                            f"La satisfaction du client est notre priorité absolue.",
                            f"Contactez notre équipe dès aujourd'hui."
                        ]
                    elif target_lang == 'de':
                        additional = [
                            f"Unsere {clean_title(service_name)}-Spezialisten sind in {location} rund um die Uhr verfügbar.",
                            f"Wir bieten kostenlose Kostenvoranschläge für alle Projekte.",
                            f"Kundenzufriedenheit steht bei uns an erster Stelle.",
                            f"Kontaktieren Sie unser Team noch heute."
                        ]
                    else:
                        additional = [
                            f"Our {clean_title(service_name)} specialists are available 24/7 for emergency calls in {location}.",
                            f"We provide free estimates and competitive pricing for all projects.",
                            f"Customer satisfaction is our top priority with every service we deliver.",
                            f"Contact our team today to discuss your needs."
                        ]
                    desc += " " + " ".join(additional[:6-len(sentences)])
                
                content['title'] = strip_markdown(content['title'])
                content['description'] = desc
                ZIGZAG_CONTENT_CACHE[cache_key] = content
                return content
        except Exception as e:
            print(f"   ⚠️ Zigzag Content Error: {e}")
    
    # 🌍 MULTI-LANGUAGE FALLBACK IF API FAILS
    if target_lang == 'ar':
        lines = [
            f"خدمات {clean_title(service_name)} احترافية في {location}.",
            f"يقدم فريقنا ذو الخبرة حلولاً مخصصة لجميع احتياجاتك.",
            f"نستخدم أحدث التقنيات والمواد المتميزة لنتائج تدوم طويلاً.",
            f"جميع الأعمال مدعومة بضمان الرضا بنسبة 100٪.",
            f"خدمات الطوارئ متاحة على مدار الساعة.",
            f"اتصل بنا اليوم للحصول على استشارة مجانية."
        ]
        explore_txt = "استكشف خدمات"
        and_txt = "و"
        title_txt = f"حلول {clean_title(service_name)} المتميزة"
    elif target_lang == 'es':
        lines = [
            f"Servicios profesionales de {clean_title(service_name)} en {location}.",
            f"Nuestro equipo experto ofrece soluciones personalizadas.",
            f"Utilizamos la última tecnología y materiales de primera calidad.",
            f"Todo el trabajo está respaldado por nuestra garantía de satisfacción.",
            f"Servicios de emergencia disponibles 24/7.",
            f"Contáctenos hoy para una consulta gratuita."
        ]
        explore_txt = "Explore nuestros servicios de"
        and_txt = "y"
        title_txt = f"Soluciones expertas en {clean_title(service_name)}"
    elif target_lang == 'fr':
        lines = [
            f"Services professionnels de {clean_title(service_name)} à {location}.",
            f"Notre équipe expérimentée fournit des solutions personnalisées.",
            f"Nous utilisons les dernières technologies et des matériaux de qualité.",
            f"Tous nos travaux sont garantis à 100 %.",
            f"Services d'urgence disponibles 24/7.",
            f"Contactez-nous dès aujourd'hui pour une estimation gratuite."
        ]
        explore_txt = "Découvrez nos services de"
        and_txt = "et"
        title_txt = f"Solutions expertes en {clean_title(service_name)}"
    elif target_lang == 'de':
        lines = [
            f"Professionelle {clean_title(service_name)} Dienstleistungen in {location}.",
            f"Unser erfahrenes Team bietet maßgeschneiderte Lösungen.",
            f"Wir verwenden neueste Technologien und hochwertige Materialien.",
            f"Alle Arbeiten sind durch unsere Zufriedenheitsgarantie abgesichert.",
            f"Notdienste sind rund um die Uhr verfügbar.",
            f"Kontaktieren Sie uns heute für eine kostenlose Beratung."
        ]
        explore_txt = "Entdecken Sie unsere"
        and_txt = "und"
        title_txt = f"Expertenlösungen für {clean_title(service_name)}"
    else:
        lines = [
            f"Professional {clean_title(service_name)} services in {location}.",
            f"Our experienced team provides customized solutions for all your needs.",
            f"We use the latest technology and premium materials for lasting results.",
            f"All work is backed by our 100% satisfaction guarantee.",
            f"Emergency services available 24/7 for urgent needs.",
            f"Contact us today for a free consultation and estimate."
        ]
        explore_txt = "Explore our"
        and_txt = "and"
        title_txt = f"Expert {clean_title(service_name)} Solutions"
    
    if related_services and Config.GENERATE_INTERNAL_LINKS:
        link1 = related_services[0] if len(related_services) > 0 else "Services"
        link2 = related_services[1] if len(related_services) > 1 else "Solutions"
        lines.append(f"{explore_txt} <a href='{validate_url('service', link1, mode)}' rel='dofollow'>{clean_title(link1)}</a> {and_txt} <a href='{validate_url('service', link2, mode)}' rel='dofollow'>{clean_title(link2)}</a>.")
    
    fallback = {
        "title": title_txt,
        "description": " ".join(lines)
    }
    ZIGZAG_CONTENT_CACHE[cache_key] = fallback
    return fallback
def generate_seo_meta_description(b_data, service_name, keywords, industry, location):
    """Generates an SEO-optimized meta description."""
    kw_str = ", ".join(keywords[:3]) if keywords else service_name
    fallback = f"Top-rated {clean_title(service_name)} in {location}. Expert {industry} professionals specializing in {kw_str}. Call us today!"

    if CLIENTS.get('openai'):
        try:
            prompt = f"""
            Write a high-converting, SEO-optimized meta description (under 160 characters) for a {industry} business page.
            Service: {service_name}
            Location: {location}
            Keywords to include naturally: {kw_str}
            Return ONLY the text of the description.
            """
            response = CLIENTS['openai'].chat.completions.create(
                model=Config.MODEL_HIGH_TIER,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=100
            )
            desc = response.choices[0].message.content.strip().strip('"\'')
            if len(desc) > 20:
                return desc
        except Exception as e:
            print(f"   ⚠️ Meta description generation failed: {e}")
    
    return fallback
def build_how_it_works_section(b_data):
    """Renders the 4-step 'How It Works' band from b_data['design_spec']."""
    spec = b_data.get('design_spec', {})
    steps = spec.get('how_it_works', [])
    target_lang = b_data.get('target_lang', 'en')
    primary = b_data.get('primary', '#1A73E8')

    if not steps or len(steps) < 4:
        return ""

    titles = {"en": "How It Works", "ar": "كيف نعمل؟", "es": "Cómo Funciona",
              "fr": "Comment Ça Marche", "de": "Wie Es Funktioniert"}
    title = titles.get(target_lang, titles["en"])

    cards = ""
    for i, step in enumerate(steps[:4]):
        cards += f'''
        <div style="background:white; border-radius:16px; padding:28px 22px;
                    box-shadow:0 4px 20px rgba(0,0,0,0.07); border:1px solid #e2e8f0;
                    text-align:center;">
            <div style="width:48px; height:48px; background:{primary}; border-radius:50%;
                        display:flex; align-items:center; justify-content:center;
                        font-size:1.3rem; margin:0 auto 14px; color:white;
                        font-weight:800; box-shadow:0 4px 12px rgba(0,0,0,0.15);">
                {i+1}
            </div>
            <div style="font-size:1.8rem; margin-bottom:10px;">{step.get('emoji','✅')}</div>
            <h4 style="font-size:1.05rem; margin-bottom:10px; color:#0f172a; font-weight:700;">
                {step.get('title','')}
            </h4>
            <p style="color:#64748b; font-size:0.9rem; line-height:1.6;">
                {step.get('desc','')}
            </p>
        </div>'''

    return f'''
    <section class="section" style="background:#f8fafc;">
        <div class="container">
            <h2 style="text-align:center; margin-bottom:50px; font-size:2.2rem; color:var(--primary);">{title}</h2>
            <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:24px;">{cards}</div>
        </div>
    </section>'''


def generate_page_dna(b_data: dict) -> dict:
    """One Claude call per site — site-unique section order for home/category/service.
    Two same-niche sites get different layouts. Safe fallback if Claude fails."""
    fallback = {
        "home_section_order":     ["services_grid", "process_steps", "why_choose", "reviews", "areas", "internal_links", "faq"],
        "category_section_order": ["intro_block", "services_grid", "why_choose", "faq"],
        "service_section_order":  ["intro_block", "zigzag_siblings", "why_choose", "reviews", "faq"],
        "intro_style":            "centered",
        "services_display":       "mixed",
        "faq_position":           "bottom",
    }
    if not CLIENTS.get('claude'):
        return fallback

    industry   = b_data.get("industry", "business")
    city       = b_data.get("city") or b_data.get("country", "")
    site_seed  = b_data.get("site_seed", 0)
    niche_obj  = b_data.get("niche_engine")
    niche_label = getattr(niche_obj, "label", "general") if niche_obj else "general"

    prompt = f"""You are a web architect. Design a UNIQUE section order for this site.

BUSINESS: {industry} in {city}
NICHE: {niche_label}
UNIQUENESS SEED: {site_seed}

IMPORTANT: Use the seed to vary your choices. Two sites with different seeds
MUST produce different layouts. Do not always put "why_choose" first.

home_section_order: shuffle these (keep all 7, vary the order):
["services_grid","process_steps","why_choose","reviews","areas","internal_links","faq"]

category_section_order: choose 4 from:
["intro_block","services_grid","why_choose","faq","reviews"]

service_section_order: choose 5 from:
["intro_block","zigzag_siblings","why_choose","reviews","faq","areas"]

intro_style: pick ONE of: centered, left_aligned, split_with_stats
services_display: pick ONE of: grid, zigzag, mixed
faq_position: pick ONE of: bottom, after_why_choose

Return ONLY valid JSON, no markdown:
{{
    "home_section_order": [...],
    "category_section_order": [...],
    "service_section_order": [...],
    "intro_style": "...",
    "services_display": "...",
    "faq_position": "..."
}}"""

    try:
        print(f"\n🧬 Generating PAGE_DNA for {industry} (seed: {site_seed})...")
        result = call_claude_json(prompt)
        if result and "home_section_order" in result:
            for k, v in fallback.items():
                if k not in result:
                    result[k] = v
            print(f"   ✅ PAGE_DNA: home starts with [{result['home_section_order'][0]}]")
            return result
    except Exception as e:
        print(f"   ⚠️ PAGE_DNA generation failed: {e}")
    return fallback


def generate_design_spec(b_data):
    """One Claude call that defines hero_title, hero_sub, trust_badge, how_it_works,
    services_intro, why_choose_intro for the whole site. Cached in b_data['design_spec']."""

    name     = b_data.get('name', 'Our Company')
    industry = b_data.get('industry', 'Service')
    city     = b_data.get('city') or b_data.get('country', 'your area')
    phone    = b_data.get('phone', '')
    services = b_data.get('flat_services_list', [])[:8]
    target_lang = b_data.get('target_lang', 'en')

    lang_names = {"en": "English", "ar": "Arabic", "es": "Spanish", "fr": "French", "de": "German"}
    lang_name = lang_names.get(target_lang, "English")

    fallback_steps = {
        "ar": [
            {"emoji": "📞", "title": "اتصل أو احجز", "desc": f"تواصل معنا 24/7 لأي احتياج في {city}."},
            {"emoji": "🔍", "title": "تشخيص مجاني", "desc": "نفحص المشكلة مجاناً قبل تقديم أي سعر."},
            {"emoji": "💰", "title": "سعر واضح مسبقاً", "desc": "سعر ثابت بدون مفاجآت."},
            {"emoji": "✅", "title": "عمل مضمون", "desc": "ننجز العمل من أول مرة مع ضمان شامل."},
        ],
    }
    default_steps = fallback_steps.get(target_lang, [
        {"emoji": "📞", "title": "Call or Book", "desc": f"Reach us 24/7 for any {industry.lower()} need in {city}."},
        {"emoji": "🔍", "title": "Free Diagnosis", "desc": "A specialist inspects the problem at no charge before quoting."},
        {"emoji": "💰", "title": "Upfront Quote", "desc": "Fixed price — no hidden charges, ever."},
        {"emoji": "✅", "title": "Guaranteed Work", "desc": "We complete the job right the first time."},
    ])

    fallback = {
        "hero_title": f"Expert {industry} in {city}",
        "hero_sub": f"Fast, reliable service — licensed professionals reaching {city} in 60 minutes",
        "trust_badge": f"#1 Rated in {city}",
        "how_it_works": default_steps,
        "services_intro": f"Explore our professional {industry.lower()} services across {city}.",
        "why_choose_intro": f"Why {city} residents choose {name}",
    }
    if target_lang == 'ar':
        fallback.update({
            "hero_title": f"خبراء {industry} الموثوقون في {city}",
            "hero_sub": f"خدمة سريعة واحترافية — نصل إليك خلال 60 دقيقة في {city}",
            "trust_badge": f"#1 موثوق في {city}",
            "services_intro": f"اكتشف خدمات {industry} الاحترافية في {city}.",
            "why_choose_intro": f"لماذا يختارنا أهل {city}؟",
        })

    if not CLIENTS.get('claude'):
        return fallback

    services_str = ", ".join(services) if services else industry
    _seed = b_data.get('site_seed', 0)
    headline_styles = [
        "BENEFIT-LED: lead with the strongest outcome",
        "URGENCY-LED: lead with speed/response time",
        "TRUST-LED: lead with social proof/rating",
        "PROBLEM-LED: open with the customer's pain",
    ]
    chosen_style = headline_styles[_seed % 4]

    prompt = f"""You are an elite conversion copywriter designing a local service website.

UNIQUENESS SEED: {_seed}
MANDATORY HEADLINE STYLE for hero_title: {chosen_style}

BUSINESS:
- Name: {name}
- Industry: {industry}
- City / Area: {city}
- Phone: {phone}
- Key services: {services_str}

OUTPUT LANGUAGE: {lang_name}

RULES:
1. hero_title: 5-8 words MAX. ONE H1. Must contain the top search keyword + city.
   No "Professional Services" filler, no year.
2. hero_sub: max 15 words. Mention speed/reliability/guarantee.
3. trust_badge: 3-5 words, e.g. "#1 Rated in {city}".
4. how_it_works: EXACTLY 4 steps specific to {industry}. Titles max 3 words,
   descs max 18 words, mention {city} in at least one. Emojis in order: 📞 🔍 💰 ✅
5. services_intro: one sentence (max 20 words).
6. why_choose_intro: 4-6 words heading.

Return ONLY valid JSON:
{{
    "hero_title": "string", "hero_sub": "string", "trust_badge": "string",
    "how_it_works": [
        {{"emoji":"📞","title":"string","desc":"string"}},
        {{"emoji":"🔍","title":"string","desc":"string"}},
        {{"emoji":"💰","title":"string","desc":"string"}},
        {{"emoji":"✅","title":"string","desc":"string"}}
    ],
    "services_intro": "string", "why_choose_intro": "string"
}}"""

    try:
        print(f"\n🎯 Generating DESIGN_SPEC for {name} ({industry}, {city})...")
        spec = call_claude_json(prompt, "You are a conversion copywriter. Output only valid JSON.")
        if not spec or 'hero_title' not in spec:
            return fallback
        hiw = spec.get('how_it_works', [])
        while len(hiw) < 4:
            hiw.append(default_steps[len(hiw)])
        spec['how_it_works'] = hiw[:4]
        spec['hero_title'] = re.sub(r'\s*\b20\d{2}\b\s*', '', spec['hero_title']).strip(' -—|:')
        print(f"   ✅ DESIGN_SPEC ready: \"{spec['hero_title']}\"")
        return spec
    except Exception as e:
        print(f"   ⚠️ DESIGN_SPEC generation error: {e}")
        return fallback
def generate_evergreen_title(service_name, business_name, current_year):
    """Generates an evergreen SEO title tag."""
    clean_srv = clean_title(service_name)
    if business_name and business_name.lower() in clean_srv.lower():
        return f"{clean_srv} in {current_year}"
    return f"{clean_srv} in {current_year} | {business_name}"

@retry_operation(max_retries=3)
def generate_page_content(b_data, page_type, active_service_name=None, parent_service=None, sibling_services=None, child_services=None, sub_services=None):
    """Generate complete page content using AI with 3-Tier Keyword Strategy and dynamic language support."""
    
    city = b_data.get('city', '')
    location = city if city else b_data.get('country', '')
    industry = b_data.get('industry', '')
    clean_service_name = clean_title(active_service_name) if active_service_name else industry
    # 👇 THE ONE-LINE FIX: Strips "Service(s)" from the end before generating content
    clean_service_name = re.sub(r'(?i)\s+services?$', '', clean_service_name).strip()
    target_lang = b_data.get('target_lang', 'en')
    current_year = datetime.now().year

    random_seed = random.randint(1, 10000)
    
    # =========================================================
    # 💎 NEW 3-TIER SEO KEYWORD INTEGRATION
    # =========================================================
    keyword_tiers = extract_keyword_tiers(b_data, clean_service_name, industry, location, target_lang)
    high_intent_kw = ", ".join(keyword_tiers.get('high_intent', [])[:3])
    semantic_kw = ", ".join(keyword_tiers.get('semantic', [])[:3])
    local_time_kw = ", ".join(keyword_tiers.get('local_time', [])[:3])
    all_keywords_str = f"{high_intent_kw}, {semantic_kw}, {local_time_kw}"
    
    # Generate Time-Sensitive SEO Meta Data
    evergreen_title = generate_seo_title_with_year(clean_service_name, location, b_data.get('name', ''), current_year)
    seo_meta_description = f"Top-rated {clean_service_name} in {location}. Expert {industry} professionals specializing in {high_intent_kw}. Call us today!"

    # Standard language mapping for the AI prompt
    lang_names = {"en": "ENGLISH", "ar": "ARABIC", "es": "SPANISH", "fr": "FRENCH", "de": "GERMAN"}
    full_lang_name = lang_names.get(target_lang, "ENGLISH")

    # Resilient language fallbacks for structural items
    standard_why_choose_us = [
        {
            "title": "Expert Team" if target_lang != 'ar' else "فريق خبير", 
            "desc": f"Certified professionals with extensive training in {clean_service_name}. Our team undergoes continuous education to stay ahead of industry trends and deliver cutting-edge solutions for your business in {location}.", 
            "icon": "user-tie", 
            "stat": "10+ Years"
        },
        {
            "title": "Quality Guarantee" if target_lang != 'ar' else "ضمان الجودة", 
            "desc": f"Every {clean_service_name} project is backed by our comprehensive satisfaction guarantee. We stand behind our work and ensure that you receive the highest quality results, or we'll make it right - no questions asked.", 
            "icon": "shield-alt", 
            "stat": "100%"
        },
        {
            "title": "Fast Response" if target_lang != 'ar' else "استجابة سريعة", 
            "desc": f"Time is critical when you need {clean_service_name} services. Our team responds within 60 minutes for urgent requests and works efficiently to minimize disruption to your business operations in {location}.", 
            "icon": "clock", 
            "stat": "60 Min"
        }
    ]

    neighborhoods, _, _ = get_dynamic_seo_data(clean_service_name, city, b_data.get('state', ''), b_data.get('country', ''), industry, target_lang)
    faqs = generate_service_faqs(b_data, active_service_name or industry, parent_service or "General")

    defaults = {
        "hero_title": f"Professional {clean_service_name} Services",
        "hero_sub": f"Serving {location} with excellence and reliability",
        "trust_signals": ["Satisfaction Guaranteed", "Free Quotes", "Fast Turnaround"] if target_lang != 'ar' else ["ضمان الرضا", "عروض أسعار مجانية", "استجابة سريعة"],
        "intro": f"Expert {clean_service_name} services in {location}. We specialize in {high_intent_kw}. Our team of certified professionals delivers exceptional results with a focus on quality and customer satisfaction.",
        "why_choose_us": standard_why_choose_us,
        "reviews": [
            {"name": "Ahmed S.", "txt": f"I was really stressed about finding a good {industry} company, but these guys were amazing. The {clean_service_name} was done perfectly.", "rating": "5"},
            {"name": "Mike T.", "txt": f"Hands down the best {clean_service_name} in {location}. They showed up on time and didn't try to upsell me.", "rating": "5"},
            {"name": "David C.", "txt": f"Highly recommend! If you need professional {clean_service_name} done right the first time, call them.", "rating": "4.9"}
        ],
        "faqs": faqs,
        "areas_served": neighborhoods,
        "meta_title": evergreen_title,
        "meta_description": seo_meta_description,
        "meta_keywords": all_keywords_str
    }

    if not CLIENTS['openai']:
        return defaults
    
    primary_keyword = (keyword_tiers.get('high_intent') or [clean_service_name])[0]

    prompt = f"""
    You are an elite SEO Copywriter and Conversion Rate Optimization (CRO) expert.
    Create UNIQUE, highly persuasive {page_type} page content for {clean_service_name} in {location}.

    BUSINESS CONTEXT:
    - Industry: {industry}
    - Primary Service: {clean_service_name}
    - Target Location: {location}
    - Target Language: {full_lang_name}
    - Random Seed: {random_seed}

    LANGUAGE LOCK: Every text value (except JSON keys and mdi icons) MUST be written natively in {full_lang_name}. Output native characters, NOT unicode escapes. Keep JSON keys in English.

    HERO H1 RULES (the `hero_title` is the H1):
    - 5-8 words MAXIMUM. NO year. NO HTML tags.
    - Format: "[Action/Benefit] [Specific Service] [City]" — e.g. "Same-Day Fridge Repair Dubai" or "Dubai's Trusted AC Experts".
    - MUST contain the primary keyword: "{primary_keyword}".
    - DO NOT just concatenate industry + city. DO NOT use "We provide..." sentence structure. Write a real headline a human would say.

    INTRO RULES:
    - Maximum 55 words TOTAL, split into exactly 2 short paragraphs separated by <br><br>.
    - First sentence states what you do and where. Second sentence mentions "{primary_keyword}" naturally.
    - NO `#`, `<h1>`, `<h2>` tags. NO filler like "In today's competitive world" or "As a leading provider".
    - Naturally weave in semantic keywords: [{semantic_kw}].

    WHY CHOOSE US RULES (exactly 3 cards):
    - Each `title` is a 2-3 word UNIQUE benefit — NOT "Expert Team", NOT "Quality Guarantee".
    - Each `desc` is 40-60 words, SPECIFIC to this {industry} business in {location}, includes ONE concrete number, ZERO generic filler.
    - `stat` is a short proof point (e.g. "12+ Years", "100%", "60 Min").
    - `icon` is a valid Material Design Icon (e.g. "mdi:shield-check", "mdi:clock-fast").

    REVIEWS RULES (exactly 3):
    - Culturally accurate names for {location}. Each review max 25 words, sounds like a real human.
    - Weave in keywords naturally from: [{local_time_kw}].

    META: Meta Title (~60 chars) + Meta Description (~150 chars) embedding keywords from: [{high_intent_kw}].

    RETURN ONLY VALID JSON MATCHING THIS EXACT FORMAT:
    {{
        "meta_title": "string (~60 chars in {full_lang_name}, keyword + location)",
        "hero_title": "string (5-8 word H1 in {full_lang_name}, contains '{primary_keyword}', NO year, NO HTML)",
        "hero_sub": "string (Compelling subheadline in {full_lang_name} mentioning {location})",
        "trust_signals": ["signal 1", "signal 2", "signal 3"],
        "intro": "string (max 55 words, 2 paragraphs split by <br><br>, includes '{primary_keyword}')",
        "process": ["Step 1", "Step 2", "Step 3", "Step 4"],
        "why_choose_us": [
            {{"title": "2-3 word UNIQUE benefit", "desc": "40-60 words specific to {industry} in {location} with ONE number", "icon": "mdi:icon-name", "stat": "short stat"}},
            {{"title": "string", "desc": "string", "icon": "mdi:icon-name", "stat": "string"}},
            {{"title": "string", "desc": "string", "icon": "mdi:icon-name", "stat": "string"}}
        ],
        "reviews": [
            {{"name": "localized name", "txt": "max 25 words with a high-intent keyword", "rating": "5.0"}},
            {{"name": "localized name", "txt": "max 25 words with a semantic keyword", "rating": "4.9"}},
            {{"name": "localized name", "txt": "max 25 words with a local/time keyword", "rating": "5.0"}}
        ],
        "faqs": [
            {{"q": "question in {full_lang_name} about {clean_service_name} in {location}", "a": "factual answer in {full_lang_name}"}},
            {{"q": "string", "a": "string"}},
            {{"q": "string", "a": "string"}},
            {{"q": "string", "a": "string"}},
            {{"q": "string", "a": "string"}}
        ]
    }}
    """
    try:
        print(f"   📝 Generating {page_type} content for {clean_service_name} in {full_lang_name}...")
        
        # 💎 CLAUDE-FIRST (repo standard): pehle Claude try karo
        content = call_claude_json(prompt)
        if not content and CLIENTS.get('openai'):
            response = CLIENTS['openai'].chat.completions.create(
                model=Config.MODEL_HIGH_TIER,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.85
            )
            content = clean_json_response(response.choices[0].message.content)
        
        if content:
            # FORCE-STRIP any year from H1 (AI often ignores negative prompts)
            if 'hero_title' in content:
                content['hero_title'] = re.sub(r'\s*\b20\d{2}\b\s*', '', content['hero_title']).strip(' -—|:')

            # Stricter why_choose_us validation — accept AI only if well-formed
            _wcu = content.get('why_choose_us')
            if not (isinstance(_wcu, list) and len(_wcu) >= 3 and
                    all(isinstance(x, dict) and x.get('title') and len(str(x.get('desc', ''))) > 30 for x in _wcu[:3])):
                content['why_choose_us'] = standard_why_choose_us

            if 'faqs' not in content or len(content['faqs']) < 3:
                content['faqs'] = faqs
            if 'areas_served' not in content:
                content['areas_served'] = neighborhoods

            # 💎 SEO FIX: Use AI-generated Meta Title, fallback to Evergreen if AI fails
            if 'meta_title' not in content or len(content['meta_title']) < 10:
                content['meta_title'] = evergreen_title
            content['meta_description'] = seo_meta_description
            content['meta_keywords'] = all_keywords_str

            # 🌟 NATURAL KEYWORD REWRITE: if intro missed the primary keyword, rewrite with Claude
            try:
                _top_kw = keyword_tiers.get('high_intent', [])
                if content.get('intro') and _top_kw and _top_kw[0].lower() not in content['intro'].lower():
                    print(f"   🔄 Intro missed primary keyword — rewriting naturally with Claude...")
                    _rw_prompt = f"""Rewrite this intro so it naturally includes the exact phrase: '{_top_kw[0]}'.
Do NOT force it with colons. Make it flow in the first or second sentence.
Keep it SHORT (max 55 words). Language: {full_lang_name}.

Original:
{content['intro']}

Return ONLY JSON: {{"intro": "rewritten text"}}"""
                    _rw = call_claude_json(_rw_prompt, "You are an expert SEO editor. Return ONLY JSON.")
                    if _rw and _rw.get('intro'):
                        content['intro'] = _rw['intro']
                        print(f"     ✨ Keyword woven into intro.")
            except Exception as _rwe:
                print(f"     ⚠️ Intro rewrite skipped: {_rwe}")

            return content
    except Exception as e:
        print(f"   ⚠️ Content Generation Error: {e}")
    
    return defaults
# ==============================================================================
# 🏗️ COMPONENT BUILDERS (FULLY SYNCED WITH STATIC VERSION)
# ==============================================================================

def get_smart_hero_options(b_data, full_list):
    """Uses GPT-4o to pick the top 7 services for dropdown safely."""
    global HERO_DROPDOWN_CACHE
    if HERO_DROPDOWN_CACHE:
        return HERO_DROPDOWN_CACHE
    
    if not full_list or len(full_list) <= 7 or not CLIENTS.get('openai'):
        # Fallback: remove duplicates and return up to 7
        HERO_DROPDOWN_CACHE = list(dict.fromkeys(full_list))[:7]
        return HERO_DROPDOWN_CACHE
    
    try:
        prompt = f"""
        I have a list of services for a {b_data.get('industry')} business.
        Select exactly 7 "High-Intent" services for a "Get a Quote" dropdown menu.
        If there are fewer than 7 high-intent services, just fill the rest of the 7 spots with the next best options from the list.
        
        FULL LIST: {json.dumps(full_list)}
        
        RETURN EXACTLY THIS JSON FORMAT:
        {{
            "selected_services": ["Service 1", "Service 2", "Service 3", "Service 4", "Service 5", "Service 6", "Service 7"]
        }}
        """
        response = CLIENTS['openai'].chat.completions.create(
            model=Config.MODEL_LOW_TIER,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        data = clean_json_response(response.choices[0].message.content)
        
        if data and "selected_services" in data and isinstance(data["selected_services"], list):
            HERO_DROPDOWN_CACHE = data["selected_services"][:7]
            return HERO_DROPDOWN_CACHE
            
    except Exception as e:
        print(f"   ⚠️ AI Dropdown selection failed: {e}")
    
    # Ultimate fallback
    HERO_DROPDOWN_CACHE = list(dict.fromkeys(full_list))[:7]
    return HERO_DROPDOWN_CACHE

def build_enhanced_hero(b_data, title, sub, hero_img_url, service_list=None, trust_signals=None):
    """Build hero with translated dropdowns, robust WhatsApp redirects, and UX feedback."""
    ui = b_data.get('ui', {})
    city_display = b_data.get('city') or b_data.get('country')
    target_lang = b_data.get('target_lang', 'en')
    business_name = escape(b_data.get('name', ''))
    # 🛡️ FIX: Create a separate unescaped variable specifically for JS injection
    business_name_js = b_data.get('name', '').replace('"', '\\"').replace("'", "\\'") 
    defaults = ["Satisfaction Guaranteed", "Free Quotes", "Fast Turnaround"] if target_lang != 'ar' else ["ضمان الرضا", "عروض أسعار مجانية", "استجابة سريعة"]
    trust_signals = trust_signals or defaults
    
    if target_lang == 'ar':
        err_alert = "يرجى ملء جميع الحقول"
        success_msg = "جاري التحويل..."
        placeholders = {"name": "الاسم", "phone": "رقم الهاتف", "service": "اختر الخدمة"}
    elif target_lang == 'es':
        err_alert = "Por favor, complete todos los campos"
        success_msg = "Redirigiendo..."
        placeholders = {"name": "Nombre", "phone": "Teléfono", "service": "Seleccionar Servicio"}
    elif target_lang == 'fr':
        err_alert = "Veuillez remplir tous les champs"
        success_msg = "Redirection..."
        placeholders = {"name": "Nom", "phone": "Téléphone", "service": "Sélectionner un Service"}
    elif target_lang == 'de':
        err_alert = "Bitte füllen Sie alle Felder aus"
        success_msg = "Weiterleiten..."
        placeholders = {"name": "Name", "phone": "Telefon", "service": "Service Auswählen"}
    else:
        err_alert = "Please fill in all fields"
        success_msg = "Redirecting..."
        placeholders = {"name": "Name", "phone": "Phone", "service": "Select Service"}
    
    signals_html = '<div class="hero-features">'
    for sig in trust_signals[:3]:
        signals_html += f'<div class="hero-feature"><span class="iconify" data-icon="mdi:star-circle" data-width="22" style="color: var(--gold-primary); margin-right: 8px;"></span> {sig}</div>'
    signals_html += '</div>'
    
    raw_services = service_list or b_data.get('flat_services_list', [])
    import json
    smart_services = get_smart_hero_options(b_data, raw_services)
    
    translated_services = smart_services
    if target_lang != 'en' and CLIENTS.get('openai'):
        try:
            lang_names = {"ar": "Arabic", "es": "Spanish", "fr": "French", "de": "German"}
            t_lang = lang_names.get(target_lang, "English")
            t_prompt = f"Translate this exact list of services into {t_lang}. Return ONLY JSON matching this format: {{\"translated\": [\"trans1\", \"trans2\"]}}. Here is the list: {json.dumps(smart_services)}"
            t_resp = CLIENTS['openai'].chat.completions.create(
                model=Config.MODEL_LOW_TIER,
                messages=[{"role": "user", "content": t_prompt}],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            t_data = clean_json_response(t_resp.choices[0].message.content)
            if t_data and "translated" in t_data and len(t_data["translated"]) == len(smart_services):
                translated_services = t_data["translated"]
        except Exception as e:
            print(f"   ⚠️ Dropdown translation failed: {e}")

    options_html = ""
    for orig_val, display_val in zip(smart_services, translated_services):
        options_html += f'<option value="{orig_val}">{clean_title(display_val)}</option>'
    options_html += f'<option value="Other">{ui.get("other_services", "Other Services")}</option>'
    
    return f'''
    <section class="hero" style="background-image: url('{hero_img_url}');">
        <div class="hero-overlay"></div>
        <div class="container hero-content">
            <div class="text-col">
                <div class="hero-gold-badge">
                    <span class="iconify" data-icon="mdi:crown" data-width="20" style="margin-right:8px;"></span> {ui.get('rated', '#1 Rated in')} {city_display}
                </div>
                <h1 class="hero-title">{strip_markdown(title)}</h1>
                <p class="hero-sub">{strip_markdown(sub)}</p>
                
                {signals_html}
                
                <div class="btn-group">
                    <a href="tel:{b_data.get('phone', '')}" class="btn btn-call">
                        <span class="iconify" data-icon="mdi:phone-in-talk" data-width="22"></span> {ui.get('call_now', 'Call Now')}
                    </a>
                    <a href="https://wa.me/{b_data.get('whatsapp', '')}" target="_blank" class="btn btn-whatsapp">
                        <span class="iconify" data-icon="mdi:whatsapp" data-width="22"></span> {ui.get('whatsapp', 'WhatsApp Quote')}
                    </a>
                </div>
            </div>
            <div class="form-col">
                <div class="glass-card v360-hero-wrapper">
                    <h3 style="text-align:center; margin-bottom:20px; font-size:1.5rem; display:flex; align-items:center; justify-content:center; gap:8px;">
                        <span class="iconify" data-icon="mdi:clipboard-text-outline" data-width="26" style="color:var(--gold-secondary);"></span> {ui.get('get_quote', 'Free Quote')}
                    </h3>
                    
                    <div>
                        <input type="text" class="v360-name" placeholder="{placeholders['name']}" style="width:100%; padding:14px; margin-bottom:15px; border-radius:10px; border:1px solid #cbd5e1; background:white;">
                        <input type="tel" class="v360-phone" placeholder="{placeholders['phone']}" style="width:100%; padding:14px; margin-bottom:15px; border-radius:10px; border:1px solid #cbd5e1; background:white;">
                        <select class="v360-svc" style="width:100%; padding:14px; margin-bottom:20px; border-radius:10px; border:1px solid #cbd5e1; background:white;">
                            <option value="" disabled selected>{placeholders['service']}</option>
                            {options_html}
                        </select>
                        <button type="button" onclick="window.handleHeroLead(this)" class="btn btn-submit v360-submit-btn" style="background:var(--primary); color:white; border:none; border-radius:10px; cursor:pointer; width:100%; padding:15px; font-size:1.1rem; font-weight:700; transition:all 0.3s;">
    {ui.get('submit_btn', 'Get Quote')} <span class="iconify" data-icon="mdi:arrow-right" data-width="20"></span>
                             </button>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <script>
    window.handleHeroLead = function(btn) {{
        var wrapper = btn.closest(".v360-hero-wrapper");
        if (!wrapper) {{ return; }}
        
        var nameField = wrapper.querySelector(".v360-name");
        var phoneField = wrapper.querySelector(".v360-phone");
        var svcField = wrapper.querySelector(".v360-svc");
        
        var name = nameField ? nameField.value.trim() : "";
        var phone = phoneField ? phoneField.value.trim() : "";
        var service = svcField ? svcField.value : "";
        
        if (!name || !phone || !service) {{
            alert("{err_alert}");
            return;
        }}
        
        var originalText = btn.innerHTML;
        btn.innerHTML = '<span class="iconify" data-icon="mdi:check-circle" data-width="20" style="margin-right:8px;"></span> {success_msg}';
        
        var sheetUrl = "{b_data.get('google_sheet_url', '')}";
        if (sheetUrl && sheetUrl.length > 10) {{
            try {{
                var data = new FormData();
                data.append("Source", "{business_name_js} - Hero Form");
                data.append("Name", name);
                data.append("Phone", phone);
                data.append("Service", service);
                data.append("Date", new Date().toLocaleString());
                fetch(sheetUrl, {{ method: "POST", body: data, mode: "no-cors" }}).catch(function(){{}});
            }} catch(err) {{}}
        }}
        
        try {{
            var whatsappNumber = "{b_data.get('whatsapp', '')}".replace(/[^0-9]/g, "");
            
            /* FIX: We use %0A for newlines to prevent Python from creating literal line breaks in the HTML */
            var message = "New Lead from {business_name_js} - Hero Form:%0A%0A";
            message += "*Name:* " + encodeURIComponent(name) + "%0A";
            message += "*Phone:* " + encodeURIComponent(phone) + "%0A";
            message += "*Service:* " + encodeURIComponent(service);
            
            var waUrl = "https://wa.me/" + whatsappNumber + "?text=" + message;
            
            /* 💎 FIX: Safely force new tab redirect, works securely in Elementor & Mobile */
            window.open(waUrl, '_blank');
            
            /* Reset form fields asynchronously */
            setTimeout(function() {{
                if (nameField) nameField.value = "";
                if (phoneField) phoneField.value = "";
                if (svcField) svcField.value = "";
                btn.innerHTML = originalText;
            }}, 2500);
            
        }} catch(waErr) {{
            btn.innerHTML = originalText;
        }}
    }};
    </script>
    '''
def generate_grid_descriptions(items, industry, city, target_lang):
    """Generate highly professional, SEO-optimized descriptions for grid items using keywords."""
    if not CLIENTS.get('openai') or not items:
        return {}
    
    # Map the two supported languages for the AI prompt
    lang_name = {"ar": "Arabic", "es": "Spanish", "fr": "French", "de": "German"}.get(target_lang, "English")
    
    prompt = f"""
    You are an elite SEO copywriter. Write a highly persuasive, professional 2-sentence description (max 20 words each) for the following {industry} services in {city}.
    Language: {lang_name}
    
    CRITICAL SEO INSTRUCTION: For each service, naturally weave in a 'High-Intent' or 'Local' keyword (e.g., 'Top-rated [service] in {city}', 'Affordable [service] solutions'). Do not sound robotic.
    
    SERVICES: {', '.join(items)}
    
    Return EXACTLY this JSON format:
    {{
        "Service 1": "Highly professional keyword-rich description in {lang_name}...",
        "Service 2": "Highly professional keyword-rich description in {lang_name}..."
    }}
    """
    try:
        response = CLIENTS['openai'].chat.completions.create(
            model=Config.MODEL_LOW_TIER,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        return clean_json_response(response.choices[0].message.content) or {}
    except Exception as e:
        print(f"   ⚠️ Grid description generation error: {e}")
        return {}

def build_dynamic_layout_section(b_data, items, section_title, page_type, page_name, limit=6, url_type="service"):
    """
    Builds a dynamic layout mixing Grids and Zigzags perfectly based on item count.
    """
    if not items: return ""

    items_to_process = items[:limit]
    count = len(items_to_process)
    target_lang = b_data.get('target_lang', 'en')
    
    lang_prefixes = {'ar': 'المزيد حول ', 'es': 'Más ', 'fr': 'Plus de ', 'de': 'Mehr '}
    more_prefix = lang_prefixes.get(target_lang, "More ")
    secondary_title = f"{more_prefix}{section_title}"
    is_child = (page_type == "child")

    if count == 1 or count == 2:
        return build_zigzag_section(b_data, items_to_process, section_title, limit, is_child_page=is_child, url_type=url_type)
    elif count == 3:
        return build_grid_section(b_data, items_to_process, section_title, limit=3, url_type=url_type)
    elif count == 4:
        html = build_grid_section(b_data, items_to_process[:3], section_title, limit=3, url_type=url_type)
        html += build_zigzag_section(b_data, items_to_process[3:], secondary_title, limit=1, is_child_page=is_child, url_type=url_type)
        return html
    elif count == 5:
        html = build_grid_section(b_data, items_to_process[:3], section_title, limit=3, url_type=url_type)
        html += build_zigzag_section(b_data, items_to_process[3:], secondary_title, limit=2, is_child_page=is_child, url_type=url_type)
        return html
    elif count >= 6:
        html = build_grid_section(b_data, items_to_process[:3], section_title, limit=3, url_type=url_type)
        html += build_zigzag_section(b_data, items_to_process[3:6], secondary_title, limit=3, is_child_page=is_child, url_type=url_type)
        return html
        
    return ""

def build_grid_section(b_data, items, section_title, limit=6, url_type="service"):
    """Builds a properly spaced grid layout section with SEO-rich, dynamically AI-generated descriptions."""
    if not items: return ""
        
    mode = b_data.get('mode', '3')
    ui = b_data.get('ui', {})
    target_lang = b_data.get('target_lang', 'en')
    city_display = b_data.get('city') if b_data.get('city') else b_data.get('country')
    industry = b_data.get('industry', 'professional')
    
    items_to_process = items[:limit]
    
    # 💎 RESTORED: Batch AI Generation with Language Support
    dynamic_descriptions = generate_grid_descriptions(items_to_process, industry, city_display, target_lang)
    
    html = f'''
    <section class="section">
        <div class="container" style="max-width: 1400px; margin: 0 auto; padding: 0 20px;">
            <h2 style="text-align:center; margin-bottom:50px; font-size:2.2rem; color:var(--primary);">
                {section_title}
            </h2>
            <div class="service-grid">
    '''
    
    for item in items_to_process:
        img = get_hosted_image(item, "grid", industry, service_name=item)
        
        # 💎 MODE 1 FIX: sub-service pages don't exist → route CTA to pre-filled WhatsApp (no 404)
        if mode == "1":
            from urllib.parse import quote as _q
            _wa  = b_data.get('whatsapp', '')
            _msg = _q(f"Hi! I need {clean_title(item)} in {city_display}. Please send me a quote.")
            link = f"https://wa.me/{_wa}?text={_msg}"
            btn_text = ui.get('get_quote', 'Get Quote')
        elif Config.GENERATE_INTERNAL_LINKS:
            link = validate_url(url_type, item, mode)
            btn_text = ui.get('learn_more', 'Learn More')
        else:
            link = "#v360-wrapper"
            btn_text = ui.get('get_quote', 'Get Quote')
        
        # Inject AI Text or use the MULTI-LANGUAGE fallback!
        if item in dynamic_descriptions and dynamic_descriptions[item]:
            description = dynamic_descriptions[item]
        else:
            # 🛡️ RESTORED PRESERVED LANGUAGES: Multi-lingual fallback templates
            entities = get_related_entities(item, industry, city_display, target_lang)
            keywords = entities.get("keywords", [])
            related_terms = entities.get("related_terms", [])
            
            kw1 = keywords[1] if len(keywords) > 1 else industry
            kw2 = related_terms[0] if len(related_terms) > 0 else "custom solutions"
            item_clean = clean_title(item)
            
            if target_lang == 'ar':
                ar_templates = [
                    f"ارتقِ بتجربتك مع حلول {item_clean} المتميزة في {city_display}. نحن نضمن لك أفضل النتائج في {kw1}.",
                    f"هل تبحث عن {kw2}؟ يقدم فريقنا المتخصص في {city_display} خدمات {item_clean} بأعلى معايير الجودة.",
                    f"نقدم خدمات {item_clean} مخصصة لتلبية احتياجاتك في {city_display}، مع التركيز التام على {kw1}."
                ]
                description = random.choice(ar_templates)
            elif target_lang == 'es':
                es_templates = [
                    f"Soluciones destacadas de {item_clean} en {city_display}. Desde {kw1} hasta {kw2}, garantizamos calidad.",
                    f"¿Buscas {kw1}? Nuestro equipo de {item_clean} en {city_display} ofrece resultados excepcionales y {kw2}.",
                    f"Mejora tu experiencia con nuestros servicios de {item_clean}. Nos especializamos en {kw2} en todo {city_display}."
                ]
                description = random.choice(es_templates)
            elif target_lang == 'fr':
                fr_templates = [
                    f"Solutions de {item_clean} de premier ordre à {city_display}. De {kw1} à {kw2}, nous garantissons la qualité.",
                    f"Vous cherchez {kw1} ? Notre équipe de {item_clean} à {city_display} offre des résultats exceptionnels.",
                    f"Améliorez votre expérience avec nos services de {item_clean}. Nous sommes spécialisés dans {kw2} à {city_display}."
                ]
                description = random.choice(fr_templates)
            elif target_lang == 'de':
                de_templates = [
                    f"Erstklassige {item_clean}-Lösungen in {city_display}. Von {kw1} bis {kw2} garantieren wir Qualität.",
                    f"Suchen Sie {kw1}? Unser {item_clean}-Team in {city_display} liefert außergewöhnliche Ergebnisse.",
                    f"Verbessern Sie Ihre Erfahrung mit unseren {item_clean}-Diensten. Wir sind spezialisiert auf {kw2} in {city_display}."
                ]
                description = random.choice(de_templates)
            else:
                en_templates = [
                    f"Top-rated {item_clean} solutions in {city_display}. From {kw1} to {kw2}, we deliver reliable results.",
                    f"Looking for {kw1}? Our {item_clean} team in {city_display} guarantees exceptional service, including {kw2}.",
                    f"Enhance your project with our professional {item_clean}. We specialize in {kw2} throughout {city_display}."
                ]
                description = random.choice(en_templates)

        _niche = b_data.get('niche_engine')
        card_variant = getattr(_niche, 'card_variant', 'image_top') if _niche else 'image_top'
        extra_class = f" cv-{card_variant}" if card_variant != "image_top" else ""

        html += f'''
        <div class="service-card{extra_class}">
            <div class="service-card-img">
                <img src="{img}" loading="lazy" alt="{clean_title(item)}">
            </div>
            <div class="service-card-content">
                <h3>{clean_title(item)}</h3>
                <div class="v360-desc-text">{description}</div>
                <a href="{link}" class="btn btn-primary" style="align-self: flex-start; width: 100%; border-radius: 50px;">
                    <i class="fas fa-arrow-right"></i> {btn_text}
                </a>
            </div>
        </div>
        '''
    
    html += '</div></div></section>'
    return html
def build_zigzag_section(b_data, items, section_title, limit=6, is_child_page=False, current_service=None, is_category_page=False, category_name=None, url_type="service"):
    """Build zigzag layout section with clean CSS classes and safe URL routing."""
    if not items: return ""
    
    ui = b_data.get('ui', {})
    target_lang = b_data.get('target_lang', 'en')
    mode = b_data.get('mode', '3')
    
    html = f'''
    <section class="section">
        <div class="container">
            <h2 style="text-align:center; margin-bottom:50px; font-size:2.2rem; color:var(--primary);">
                {section_title}
            </h2>
    '''
    
    for i, item in enumerate(items[:limit]):
        rev = "reverse" if i % 2 != 0 else ""
        relationships = get_service_relationships(item)
        category = relationships.get('category', 'General')
        img = get_hosted_image(item, "zigzag", b_data.get('industry', ''), is_category=False, service_name=item)
        
        related_services = relationships.get('siblings', [])[:3]
        if not related_services and Config.GENERATE_INTERNAL_LINKS:
            if mode == "1" and current_service and item == current_service:
                related_services = generate_sub_services(b_data, current_service)[:3]
            else:
                flat_list = b_data.get('flat_services_list', [])
                if flat_list and len(flat_list) > 1:
                    pool = [s for s in flat_list if s != item]
                    related_services = random.sample(pool, min(len(pool), 3))
        
        page_seed = f"{item}_{i}_{random.randint(1,1000)}"
        zigzag_content = generate_zigzag_content_with_links(
            b_data, item, category, is_child_page, related_services=related_services, page_seed=page_seed
        )
        
        raw_title = zigzag_content.get('title', clean_title(item))
        title_text = escape(raw_title)
        desc_text = zigzag_content.get('description', '')
        
        # Ensure 6 lines
        sentences = desc_text.split('. ')
        if len(sentences) < 6:
            additional = [f"Professional {clean_title(item)} support.", f"Available 24/7.", f"Call for estimates."]
            desc_text = '. '.join(sentences + additional[:6-len(sentences)])
        
        bullet_points = ""
        for line in desc_text.split('. ')[:6]:
            if line.strip():
                bullet_points += f'<span class="service-line">{line.strip().rstrip(".")}.</span>'
        
        # 💎 MODE 1 FIX: zigzag items = sub-services on SAME page → WhatsApp route (no 404)
        if mode == "1":
            from urllib.parse import quote as _q
            _wa  = b_data.get('whatsapp', '')
            _msg = _q(f"Hi! I'm interested in {clean_title(item)}. Please share details and price.")
            link = f"https://wa.me/{_wa}?text={_msg}"
            btn_text = ui.get('get_quote', 'Get Quote')
            btn_class = "btn-primary"
            btn_disabled = ''
        elif not Config.GENERATE_INTERNAL_LINKS:
            link = "#v360-wrapper"
            btn_text = ui.get('get_quote', 'Get Quote')
            btn_class = "btn-primary"
            btn_disabled = ''
        elif is_child_page and title_text.lower() == clean_title(current_service or "").lower():
            link = "#"
            btn_text = ui.get('current_svc', 'Current Service')
            btn_class = "btn-primary"
            btn_disabled = 'style="opacity:0.7; cursor:default;"'
        else:
            link = validate_url(url_type, item, mode)
            btn_text = ui.get('learn_more', 'Learn More')
            btn_class = "btn-primary"
            btn_disabled = ''
        
        html += f'''
        <div class="zigzag-item {rev}">
            <div class="zigzag-content">
                <h3>{title_text}</h3>
                <div class="service-description">{bullet_points}</div>
                <a href="{link}" class="btn {btn_class}" {btn_disabled}>
                    <i class="fas fa-arrow-right"></i> {btn_text}
                </a>
            </div>
            <div class="zigzag-img-wrap">
                <img src="{img}" class="zigzag-img" loading="lazy" alt="{title_text}">
            </div>
        </div>
        '''
    
    html += '</div></section>'
    return html 
def build_infographic_section(features, b_data):
    """Build infographic/why choose us section - With P-Tag Avoidance for WP & Iconify Integration."""
    ui = b_data.get('ui', {})
    target_lang = b_data.get('target_lang', 'en')
    
    # 🌍 FULL MULTI-LANGUAGE FALLBACKS FOR "WHY CHOOSE US"
    if not features or len(features) == 0:
        if target_lang == 'ar':
            features = [
                {"title": "فريق خبير", "desc": "متخصصون معتمدون يتمتعون بتدريب مكثف. يخضع فريقنا للتعليم المستمر لمواكبة اتجاهات الصناعة.", "icon": "mdi:account-tie", "stat": "10+ سنوات"},
                {"title": "مواد عالية الجودة", "desc": "نحن نستخدم فقط المواد الممتازة لنتائج دائمة. يتم إكمال كل مشروع بمستلزمات عالية الجودة.", "icon": "mdi:trophy", "stat": "ممتاز"},
                {"title": "استجابة سريعة", "desc": "خدمات الطوارئ متاحة 24/7. عندما تحتاج إلى مساعدة، يستجيب فريقنا في غضون 60 دقيقة.", "icon": "mdi:clock-outline", "stat": "24/7"}
            ]
        elif target_lang == 'es':
            features = [
                {"title": "Equipo Experto", "desc": "Profesionales certificados con amplia formación. Nuestro equipo se capacita continuamente.", "icon": "mdi:account-tie", "stat": "10+ Años"},
                {"title": "Materiales Premium", "desc": "Utilizamos solo materiales de primera calidad para resultados duraderos en cada proyecto.", "icon": "mdi:trophy", "stat": "Premium"},
                {"title": "Respuesta Rápida", "desc": "Servicios de emergencia 24/7. Nuestro equipo responde en menos de 60 minutos.", "icon": "mdi:clock-outline", "stat": "24/7"}
            ]
        elif target_lang == 'fr':
            features = [
                {"title": "Équipe d'Experts", "desc": "Des professionnels certifiés avec une formation approfondie. Notre équipe se forme en continu.", "icon": "mdi:account-tie", "stat": "10+ Ans"},
                {"title": "Matériaux de Qualité", "desc": "Nous n'utilisons que des matériaux de qualité supérieure pour des résultats durables.", "icon": "mdi:trophy", "stat": "Premium"},
                {"title": "Réponse Rapide", "desc": "Services d'urgence disponibles 24/7. Notre équipe intervient en moins de 60 minutes.", "icon": "mdi:clock-outline", "stat": "24/7"}
            ]
        elif target_lang == 'de':
            features = [
                {"title": "Experten-Team", "desc": "Zertifizierte Profis mit umfassender Ausbildung. Unser Team bildet sich ständig weiter.", "icon": "mdi:account-tie", "stat": "10+ Jahre"},
                {"title": "Hochwertige Materialien", "desc": "Wir verwenden nur Premium-Materialien für dauerhafte Ergebnisse bei jedem Projekt.", "icon": "mdi:trophy", "stat": "Premium"},
                {"title": "Schnelle Reaktion", "desc": "Notdienste 24/7 verfügbar. Unser Team reagiert innerhalb von 60 Minuten.", "icon": "mdi:clock-outline", "stat": "24/7"}
            ]
        else:
            features = [
                {"title": "Expert Team", "desc": "Certified professionals with extensive training. Our team undergoes continuous education.", "icon": "mdi:account-tie", "stat": "10+ Years"},
                {"title": "Quality Materials", "desc": "We use only premium materials for lasting results. Every project is completed with top-grade supplies.", "icon": "mdi:trophy", "stat": "Premium"},
                {"title": "Fast Response", "desc": "Emergency services available 24/7. When you need help, our team responds within 60 minutes.", "icon": "mdi:clock-outline", "stat": "24/7"}
            ]
            
    display_features = features[:3]
    
    html = '<section class="section"><div class="container">'
    html += f'<h2 style="text-align: center; margin-bottom: 50px; color: var(--primary); font-size: 2.2rem;">{ui.get("why_choose_us", "Why Choose Us?")}</h2>'
    html += '<div class="infographic-grid">'
    
    for feature in display_features:
        icon_name = feature.get('icon', 'mdi:star-circle')
        icon_name = icon_name.replace('fa-', '').replace('fas ', '').replace('fab ', '')
        if not icon_name.startswith('mdi:'):
            icon_name = f"mdi:{icon_name}"
            
        title = strip_markdown(feature.get('title', 'Expert Service'))
        desc = strip_markdown(feature.get('desc', 'Professional quality work.'))
        stat = strip_markdown(feature.get('stat', ''))
        
        html += f'''
        <div class="infographic-item">
            <div class="infographic-icon">
                <span class="iconify" data-icon="{icon_name}" data-width="40" data-height="40"></span>
            </div>
            <div class="infographic-number">{stat}</div>
            <h3>{title}</h3>
            <div class="v360-desc-text">{desc}</div>
        </div>
        '''
    
    html += '</div></div></section>'
    return html

def build_internal_links_section(b_data, service_name, page_type="child"):
    """Build internal links section for SEO using uniform, mobile-friendly horizontal cards."""
    mode = b_data.get('mode', '3')
    
    # 💎 STRICT FIX: If internal links are disabled, kill this entire section instantly.
    if not Config.GENERATE_INTERNAL_LINKS:
        return ""
    
    global SERVICE_HIERARCHY
    city_display = b_data.get('city') if b_data.get('city') else b_data.get('country')
    target_lang = b_data.get('target_lang', 'en')
    ui = b_data.get('ui', {})
    industry = clean_title(b_data.get('industry', 'Services'))

    # 🌍 RTL Arrow Logic mapped to a guaranteed MDI icon
    arrow_icon = "mdi:arrow-left" if target_lang == 'ar' else "mdi:arrow-right"
    text_align = "right" if target_lang == 'ar' else "left"

    if page_type == "home" and SERVICE_HIERARCHY:
        # 🌍 DYNAMIC MULTI-LANGUAGE TITLES
        if target_lang == 'ar':
            section_title = f"استكشف فئات {industry}"
            section_desc = f"تصفح جميع فئات خدمات {industry} الشاملة لدينا"
            services_plural = "خدمات"
            available_text_template = "{count} {services} متاحة"
        elif target_lang == 'es':
            section_title = f"Explora Nuestras Categorías de {industry}"
            section_desc = "Explora nuestras categorías integrales de servicios"
            services_plural = "servicios"
            available_text_template = "{count} {services} disponibles"
        elif target_lang == 'fr':
            section_title = f"Explorez Nos Catégories de {industry}"
            section_desc = "Parcourez nos catégories complètes de services"
            services_plural = "services"
            available_text_template = "{count} {services} disponibles"
        elif target_lang == 'de':
            section_title = f"Entdecken Sie Unsere {industry}-Kategorien"
            section_desc = "Durchsuchen Sie unsere umfassenden Servicekategorien"
            services_plural = "Dienstleistungen"
            available_text_template = "{count} {services} verfügbar"
        else:
            section_title = f"Explore Our {industry} Categories"
            section_desc = f"Browse our comprehensive {industry} service categories"
            services_plural = "services"
            available_text_template = "{count} {services} available"
        
        html = '<section class="section"><div class="container">'
        html += f'<div style="background:linear-gradient(135deg, #f8fafc 0%, white 100%); border-radius:20px; padding:40px; border: 1px solid #eef2ff;">'
        html += f'<h3 style="margin-bottom:25px; color:var(--primary); font-size:1.8rem; display:flex; align-items:center; gap:10px;"><span class="iconify" data-icon="mdi:sitemap" data-width="30"></span> {section_title}</h3>'
        html += f'<p style="color:var(--text-gray); margin-bottom:30px;">{section_desc}.</p>'
        
        # 🛑 PRO FIX: Strict grid layout that handles mobile gracefully (minmax 280px)
        html += '<div class="internal-links-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">'
        
        for cat_name, cat_data in list(SERVICE_HIERARCHY.items())[:6]:
            if isinstance(cat_data, dict) and 'children' in cat_data:
                description = cat_data.get('description', f'Professional {clean_title(cat_name)} services')
                cat_link = validate_url("category", cat_name, mode)
                children_count = len(cat_data.get('children', []))
                
                available_text = available_text_template.format(count=children_count, services=services_plural)
                cat_icon = get_dynamic_icon(cat_name) 
                
                # 💎 FIX: Bulletproof Flexbox layout. Icon left, Arrow right. Text correctly flows underneath heading.
                html += f'''
                <div class="pro-internal-link" style="position: relative; display: flex; align-items: flex-start; background: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eef2ff; box-shadow: 0 4px 15px rgba(0,0,0,0.03); gap: 16px; width: 100%; transition: all 0.3s ease;">
                    <a href="{cat_link}" style="position: absolute; inset: 0; z-index: 10;"></a>
                    
                    <div class="pro-link-icon" style="width: 50px; height: 50px; border-radius: 12px; background: rgba(26, 115, 232, 0.08); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                        <span class="iconify" data-icon="{cat_icon}" data-width="26" style="color: var(--primary);"></span>
                    </div>
                    
                    <div class="pro-link-text" style="flex-grow: 1; min-width: 0; text-align: {text_align}; padding-top: 2px;">
                        <h3 style="margin: 0 0 6px 0; font-size: 1.1rem; color: #0f172a; font-weight: 700; line-height: 1.3;">{clean_title(cat_name)}</h3>
                        <p style="margin: 0; font-size: 0.9rem; color: #64748b; line-height: 1.5;">
                            <span style="display: inline-block; background: #f0fdf4; color: #16a34a; padding: 2px 8px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; margin-right: 6px; margin-bottom: 4px;">{available_text}</span>
                            {description}
                        </p>
                    </div>
                    
                    <div class="pro-link-arrow" style="flex-shrink: 0; display: flex; align-items: center; height: 50px;">
                        <span class="iconify" data-icon="{arrow_icon}" data-width="20" style="color: #cbd5e1;"></span>
                    </div>
                </div>
                '''
        
        html += '</div></div></div></section>'
        return html
    
    elif service_name:
        relationships = get_service_relationships(service_name)
        category = relationships.get('category', 'Services')
        siblings = relationships.get('siblings', [])
        children = relationships.get('children', [])
        
        if mode == "1":
            siblings = generate_sub_services(b_data, service_name)
            category = f"{clean_title(service_name)} Services"
        
        if not siblings and not children:
            return ""
        
        html = '<section class="section"><div class="container">'
        html += '<div style="background:linear-gradient(135deg, #f8fafc 0%, white 100%); border-radius:20px; padding:40px; border: 1px solid #eef2ff;">'
        
        if children:
            if target_lang == 'ar':
                child_title = f"خدمات {clean_title(service_name)} المتخصصة"
            else:
                child_title = f"Specialized {clean_title(service_name)} Services"
            
            html += f'<h3 style="margin-bottom:25px; color:var(--primary); font-size:1.6rem; display:flex; align-items:center; gap:10px;"><span class="iconify" data-icon="mdi:arrow-down-right" data-width="28"></span> {child_title}</h3>'
            html += '<div class="internal-links-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom:40px;">'
            
            for child in children[:6]:
                child_link = validate_url("service", child, mode)
                child_icon = get_dynamic_icon(child)
                
                # 💎 FIX: Identical structure for Specialized Services
                html += f'''
                <div class="pro-internal-link" style="position: relative; display: flex; align-items: flex-start; background: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eef2ff; box-shadow: 0 4px 15px rgba(0,0,0,0.03); gap: 16px; width: 100%; transition: all 0.3s ease;">
                    <a href="{child_link}" style="position: absolute; inset: 0; z-index: 10;"></a>
                    
                    <div class="pro-link-icon" style="width: 50px; height: 50px; border-radius: 12px; background: rgba(26, 115, 232, 0.08); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                        <span class="iconify" data-icon="{child_icon}" data-width="26" style="color: var(--primary);"></span>
                    </div>
                    
                    <div class="pro-link-text" style="flex-grow: 1; min-width: 0; text-align: {text_align}; display: flex; flex-direction: column; justify-content: center; min-height: 50px;">
                        <h3 style="margin: 0; font-size: 1.05rem; color: #0f172a; font-weight: 600; line-height: 1.3;">{clean_title(child)}</h3>
                    </div>
                    
                    <div class="pro-link-arrow" style="flex-shrink: 0; display: flex; align-items: center; height: 50px;">
                        <span class="iconify" data-icon="{arrow_icon}" data-width="20" style="color: #cbd5e1;"></span>
                    </div>
                </div>
                '''
            html += '</div>'
        
        if siblings:
            category_clean = category.replace(" Services", "").strip()
            if target_lang == 'ar':
                sibling_title = f"خدمات {clean_title(category_clean)} الأخرى"
            else:
                sibling_title = f"Other {clean_title(category_clean)} Services"

            html += f'<h3 style="margin-bottom:25px; color:var(--primary); font-size:1.6rem; display:flex; align-items:center; gap:10px;"><span class="iconify" data-icon="mdi:view-grid-plus-outline" data-width="28"></span> {sibling_title}</h3>'
            html += '<div class="internal-links-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">'
            
            for sibling in siblings[:6]:
                if sibling.lower() != service_name.lower():
                    sibling_link = validate_url("service", sibling, mode)
                    sibling_icon = get_dynamic_icon(sibling)
                    
                    # 💎 FIX: Identical structure for Other Services
                    html += f'''
                    <div class="pro-internal-link" style="position: relative; display: flex; align-items: flex-start; background: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eef2ff; box-shadow: 0 4px 15px rgba(0,0,0,0.03); gap: 16px; width: 100%; transition: all 0.3s ease;">
                        <a href="{sibling_link}" style="position: absolute; inset: 0; z-index: 10;"></a>
                        
                        <div class="pro-link-icon" style="width: 50px; height: 50px; border-radius: 12px; background: rgba(26, 115, 232, 0.08); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                            <span class="iconify" data-icon="{sibling_icon}" data-width="26" style="color: var(--primary);"></span>
                        </div>
                        
                        <div class="pro-link-text" style="flex-grow: 1; min-width: 0; text-align: {text_align}; display: flex; flex-direction: column; justify-content: center; min-height: 50px;">
                            <h3 style="margin: 0; font-size: 1.05rem; color: #0f172a; font-weight: 600; line-height: 1.3;">{clean_title(sibling)}</h3>
                        </div>
                        
                        <div class="pro-link-arrow" style="flex-shrink: 0; display: flex; align-items: center; height: 50px;">
                            <span class="iconify" data-icon="{arrow_icon}" data-width="20" style="color: #cbd5e1;"></span>
                        </div>
                    </div>
                    '''
            html += '</div>'
        
        html += '</div></div></section>'
        return html
    return ""
def build_areas_served(b_data, neighborhoods):
    """Build areas served section with full language support, Iconify, and Anchor ID."""
    if not neighborhoods:
        return ""
    
    ui = b_data.get('ui', {})
    city_display = b_data.get('city') if b_data.get('city') else b_data.get('country')
    target_lang = b_data.get('target_lang', 'en')
    industry = clean_title(b_data.get('industry', 'services'))
    
    # 🌍 FULL MULTI-LANGUAGE TRANSLATIONS
    if target_lang == 'ar':
        subtext = f"نقدم خدمات {industry} احترافية في جميع الأحياء الرئيسية."
        footer_text = "نخدم جميع المناطق المحيطة - اتصل لمعرفة التوافر!"
        area_icon_margin = "margin-left:5px;" 
    elif target_lang == 'es':
        subtext = f"Proporcionando servicios profesionales de {industry} en los principales vecindarios."
        footer_text = "Sirviendo a todas las áreas circundantes - ¡Llame para disponibilidad!"
        area_icon_margin = "margin-right:5px;"
    elif target_lang == 'fr':
        subtext = f"Fourniture de services professionnels de {industry} dans tous les grands quartiers."
        footer_text = "Desservant toutes les zones environnantes - Appelez pour la disponibilité !"
        area_icon_margin = "margin-right:5px;"
    elif target_lang == 'de':
        subtext = f"Bereitstellung professioneller {industry}-Dienstleistungen in allen wichtigen Stadtteilen."
        footer_text = "Wir bedienen alle umliegenden Gebiete - Rufen Sie uns für die Verfügbarkeit an!"
        area_icon_margin = "margin-right:5px;"
    else:
        subtext = f"Providing professional {industry} services across all major neighborhoods."
        footer_text = "Serving all surrounding areas - Call for availability!"
        area_icon_margin = "margin-right:5px;"

    # 🛑 PRO FIX: Added id="locations" so the Mega Menu link scrolls smoothly to this exact spot
    html = f'''
    <section class="section" id="locations">
        <div class="container" style="text-align:center;">
            <h2 style="margin-bottom:20px; font-size:2rem; color:var(--primary);">{ui.get('areas_served_in', 'Areas We Serve in')} {city_display}</h2>
            <p style="color:var(--text-gray); margin-bottom:40px; font-size:1.1rem;">
                {subtext}
            </p>
            <div style="display:flex; flex-wrap:wrap; gap:12px; justify-content:center;">
    '''
    
    for area in neighborhoods[:12]:
        # 🌟 FIXED: Use Iconify for the map markers in the pills!
        html += f'<div style="background:white; border:1px solid #e2e8f0; padding:10px 22px; border-radius:50px; font-size:0.9rem; color:var(--text-gray); font-weight:500; box-shadow:0 2px 5px rgba(0,0,0,0.02); display:flex; align-items:center;"><span class="iconify" data-icon="mdi:map-marker" data-width="18" style="color:var(--primary); {area_icon_margin}"></span> {area}</div>'
    
    html += f'''
            </div>
            <p style="margin-top:30px; color:var(--text-gray); font-size:0.95rem; display:flex; align-items:center; justify-content:center; gap:8px;">
                <span class="iconify" data-icon="mdi:truck-fast-outline" data-width="24"></span> {footer_text}
            </p>
        </div>
    </section>
    '''
    return html
def build_testimonials_section(b_data, reviews, neighborhoods):
    """Build testimonials section displaying AI-generated reviews with dynamic locations and multi-language support."""
    if not reviews:
        return ""
        
    city = b_data.get('city', 'our area')
    target_lang = b_data.get('target_lang', 'en')
    
    # 🌍 DYNAMIC MULTI-LANGUAGE TRANSLATIONS
    if target_lang == 'ar':
        title_text = f"ماذا يقول عملاؤنا في {city}"
        sub_text = "آراء حقيقية من عملائنا المحليين"
        verified_text = "عميل موثوق في"
    elif target_lang == 'es':
        title_text = f"Lo que dicen nuestros clientes en {city}"
        sub_text = "Comentarios reales de nuestros clientes locales"
        verified_text = "Cliente verificado en"
    elif target_lang == 'fr':
        title_text = f"Ce que disent nos clients à {city}"
        sub_text = "De vrais retours de nos clients locaux"
        verified_text = "Client vérifié à"
    elif target_lang == 'de':
        title_text = f"Was unsere Kunden in {city} sagen"
        sub_text = "Echtes Feedback von unseren lokalen Kunden"
        verified_text = "Verifizierter Kunde in"
    else:
        title_text = f"What Our {city} Clients Say"
        sub_text = "Real feedback from our local customers"
        verified_text = "Verified Customer in"

    html = f'''
    <section class="section">
        <div class="container">
            <h2 style="text-align:center; margin-bottom:15px; font-size:2.2rem; color:var(--primary);">
                {title_text}
            </h2>
            <p style="text-align:center; color:var(--text-gray); margin-bottom:40px; font-size:1.1rem;">
                {sub_text}
            </p>
            <div class="service-grid">
    '''
    
    for rev in reviews:
        name = escape(rev.get('name', 'Customer'))
        text = escape(rev.get('txt', 'Great service!'))
        
        # 🎯 DYNAMIC LOCATION INJECTION: Pick a random neighborhood, fallback to city
        random_location = random.choice(neighborhoods) if neighborhoods else city
        
        # Generate 5 Iconify stars
        stars_html = '<span class="iconify" data-icon="mdi:star" style="color:var(--gold-primary); font-size:1.3rem;"></span>' * 5
        
        html += f'''
        <div style="background:white; padding:30px; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.05); border:1px solid #eef2ff; display:flex; flex-direction:column; height:100%;">
            <div style="margin-bottom:15px;">
                {stars_html}
            </div>
            <p style="font-style:italic; color:var(--text-gray); line-height:1.7; margin-bottom:20px; flex-grow:1; font-size:0.95rem;">
                "{text}"
            </p>
            <div style="border-top:1px solid #f1f5f9; padding-top:15px;">
                <strong style="color:var(--text-dark); display:block; font-size:1.05rem;">{name}</strong>
                <span style="color:var(--primary); font-size:0.85rem;">{verified_text} {escape(random_location)}</span>
            </div>
        </div>
        '''
        
    html += '''
            </div>
        </div>
    </section>
    '''
    return html
def build_faq_section(faqs, service_name, b_data=None):
    """Build FAQ section safely centered with long-tail SEO fallbacks and multi-language support."""
    ui = b_data.get('ui', {}) if b_data else {}
    target_lang = b_data.get('target_lang', 'en') if b_data else 'en'
    
    # Extract variables for Long-Tail Keyword injection
    city = b_data.get('city', '') if b_data else ''
    location = city if city else (b_data.get('country', '') if b_data else '')
    clean_srv = clean_title(service_name) if service_name else "services"
    
    # If AI fails to generate, use these heavily SEO-optimized Long-Tail fallbacks
    if not faqs or len(faqs) < 5:
        if target_lang == 'ar':
            faqs = [
                {"q": f"ما هي المناطق التي تخدمونها لخدمات {clean_srv} في {location}؟", "a": f"نحن نقدم تغطية شاملة لجميع خدمات {clean_srv} في جميع أنحاء {location} والمناطق المجاورة."},
                {"q": f"ما مدى سرعة استجابتكم لطلبات {clean_srv} الطارئة؟", "a": "خدمة الطوارئ متاحة للوصول إليك خلال 60 دقيقة، والخدمات العادية خلال 24 ساعة."},
                {"q": f"هل أنتم مرخصون ومؤمنون للقيام بأعمال {clean_srv}؟", "a": "نعم، جميع الفنيين لدينا مرخصون ومؤمنون بالكامل لضمان سلامتك."},
                {"q": f"ما الذي يميز خدمات {clean_srv} الخاصة بكم عن الآخرين؟", "a": "نحن نجمع بين الخبرة، والمواد عالية الجودة، والتركيز على إرضاء العملاء في كل مشروع."},
                {"q": f"هل تقدمون ضمانات على إصلاحات وأعمال {clean_srv}؟", "a": "نعم، جميع أعمالنا تأتي مع ضمان شامل لراحة بالك."}
            ]
        elif target_lang == 'es':
            faqs = [
                {"q": f"¿Qué áreas atienden para los servicios de {clean_srv} en {location}?", "a": f"Brindamos cobertura completa para {clean_srv} en todo {location} y áreas circundantes."},
                {"q": f"¿Qué tan rápido pueden responder a emergencias de {clean_srv}?", "a": "El servicio de emergencia está disponible en 60 minutos, el estándar en 24 horas."},
                {"q": f"¿Están licenciados y asegurados para trabajos de {clean_srv}?", "a": "Sí, todos nuestros técnicos están completamente licenciados y asegurados."},
                {"q": f"¿Qué hace diferente a su servicio de {clean_srv}?", "a": "Combinamos experiencia, materiales de calidad y un servicio enfocado en el cliente."},
                {"q": f"¿Ofrecen garantías en el trabajo de {clean_srv}?", "a": "Sí, todo el trabajo viene con una garantía integral."}
            ]
        elif target_lang == 'fr':
            faqs = [
                {"q": f"Quelles zones desservez-vous pour les services de {clean_srv} à {location} ?", "a": f"Nous offrons une couverture complète pour {clean_srv} dans tout {location} et ses environs."},
                {"q": f"À quelle vitesse pouvez-vous intervenir pour une urgence de {clean_srv} ?", "a": "Service d'urgence disponible sous 60 minutes, standard sous 24 heures."},
                {"q": f"Êtes-vous agréés et assurés pour les travaux de {clean_srv} ?", "a": "Oui, tous nos techniciens sont entièrement agréés et assurés."},
                {"q": f"Qu'est-ce qui différencie votre service de {clean_srv} ?", "a": "Nous allions expertise, matériaux de qualité et service axé sur le client."},
                {"q": f"Offrez-vous des garanties pour les réparations de {clean_srv} ?", "a": "Oui, tous nos travaux sont assortis d'une garantie complète."}
            ]
        elif target_lang == 'de':
            faqs = [
                {"q": f"Welche Gebiete bedienen Sie für {clean_srv} in {location}?", "a": f"Wir bieten umfassende {clean_srv}-Dienstleistungen in ganz {location} und Umgebung an."},
                {"q": f"Wie schnell können Sie bei {clean_srv}-Notfällen reagieren?", "a": "Notdienst innerhalb von 60 Minuten, Standard innerhalb von 24 Stunden."},
                {"q": f"Sind Sie für {clean_srv}-Arbeiten lizenziert und versichert?", "a": "Ja, alle unsere Techniker sind voll lizenziert und versichert."},
                {"q": f"Was unterscheidet Ihren {clean_srv}-Service?", "a": "Wir kombinieren Fachwissen, hochwertige Materialien und kundenorientierten Service."},
                {"q": f"Bieten Sie Garantien für {clean_srv}-Reparaturen?", "a": "Ja, alle Arbeiten sind mit einer umfassenden Garantie versehen."}
            ]
        else:
            faqs = [
                {"q": f"What areas do you serve for {clean_srv} in {location}?", "a": f"We provide comprehensive {clean_srv} service coverage throughout {location} and surrounding areas."},
                {"q": f"How quickly can you respond to {clean_srv} emergencies?", "a": "Emergency service available within 60 minutes, standard within 24 hours."},
                {"q": f"Are you licensed and insured for {clean_srv} work?", "a": "Yes, all our technicians are fully licensed and insured for your peace of mind."},
                {"q": f"What makes your {clean_srv} service different?", "a": "We combine expertise, premium quality materials, and customer-focused service."},
                {"q": f"Do you offer warranties on {clean_srv} repairs?", "a": "Yes, all our work comes with a comprehensive warranty."}
            ]
    
    faqs = faqs[:5]
    
    # 🔥 PERFECT CENTERING FIX: Using display: flex and align-items: center ensures it never sticks to the left.
    html = f'''
    <section class="section">
        <div class="container" style="max-width:850px; margin: 0 auto !important; display: flex; flex-direction: column; align-items: center;">
            <h2 style="text-align:center; margin-bottom:40px; font-size:2rem; color:var(--primary); width: 100%;">{ui.get('faq', 'Frequently Asked Questions')}</h2>
            
            <div style="width: 100%;">
    '''
    
    for f in faqs:
        question = strip_markdown(f.get('q', f.get('question', 'Question')))
        answer = strip_markdown(f.get('a', f.get('answer', 'Professional service.')))
        
        # MODERN UI: Uses chevron-down and smooth transitions
        html += f'''
        <div style="margin-bottom:15px; background:white; border-radius:12px; overflow:hidden; border:1px solid #e2e8f0; box-shadow:0 4px 15px rgba(0,0,0,0.03);">
            <div onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'block' ? 'none' : 'block'; this.querySelector('i').className = this.nextElementSibling.style.display === 'block' ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" 
                 style="padding:22px 25px; cursor:pointer; font-weight:600; display:flex; justify-content:space-between; align-items:center; background:#f8fafc; color:var(--text-dark); transition: background 0.3s;">
                {question} <i class="fas fa-chevron-down" style="color:var(--primary); font-size: 0.9rem;"></i>
            </div>
            <div style="padding:0 25px 25px; display:none; color:var(--text-gray); border-top:1px solid #f1f5f9; padding-top:20px; line-height:1.7; font-size: 0.95rem;">{answer}</div>
        </div>
        '''
    
    more_qs_text = ui.get('more_qs', 'Have more questions? Call us anytime!')
    
    html += f'''
            </div> <p style="text-align:center; margin-top:35px; color:#64748b; font-size:1rem; font-weight: 500;">
                <i class="fas fa-comment-alt" style="color: var(--gold-secondary); margin-right: 8px;"></i> {more_qs_text}
            </p>
        </div>
    </section>
    '''
    return html
# 🎨 5. CSS ENGINE WITH 3-COLUMN DESKTOP LAYOUT (FIXED)
# ==============================================================================
def get_enterprise_css(b_data):
    """
    Ultimate Elementor-Proof CSS with DYNAMIC RTL (ARABIC) SUPPORT.
    Deeply scoped to #v360-wrapper to prevent WordPress theme conflicts.
    """
    is_rtl = b_data.get('is_rtl', False)
    
    niche_profile = b_data.get('niche_profile', NICHE_PROFILES["general"])
    heading_font = niche_profile.get('font_primary', 'Outfit')

    # 🎨 Section background alternation — site_seed rotates the offset
    _seed = b_data.get('site_seed', 0)
    _offset = _seed % 4
    _sec0 = get_section_bg(niche_profile, 0 + _offset)
    _sec1 = get_section_bg(niche_profile, 1 + _offset)
    _sec2 = get_section_bg(niche_profile, 2 + _offset)
    _sec3 = get_section_bg(niche_profile, 3 + _offset)
    _bg_n1, _bg_n2, _bg_n3, _bg_n4 = "4n+1", "4n+2", "4n+3", "4n+4"
    _extra_font = niche_font_import(niche_profile)
    _font_import_url = "https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800"
    if _extra_font:
        _font_import_url += _extra_font
    _font_import_url += "&display=swap"

    css = f"""
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="{_font_import_url}" rel="stylesheet">
    <script src="https://code.iconify.design/3/3.1.0/iconify.min.js"></script>
    
    <!-- 🛑 SEO FIX: Physically remove the theme's duplicate H1 so Google only sees the Hero H1 -->
    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            var badH1s = document.querySelectorAll('h1.entry-title, header.entry-header h1, .page-title, .elementor-page-title');
            badH1s.forEach(function(h1) {{
                if(!h1.classList.contains('hero-title')) {{ h1.remove(); }}
            }});
        }});
    </script>

    <style>
        /* Outfit loaded via <link> above; niche heading font applied below */
        #v360-wrapper h1, #v360-wrapper h2, #v360-wrapper h3, #v360-wrapper .hero-title {{
            font-family: '{heading_font}', 'Outfit', sans-serif !important;
        }}
        
        /* 🛑 CRITICAL FIX: Kill Horizontal Scrolling globally */
        html, body {{
            overflow-x: hidden !important;
            width: 100% !important;
            max-width: 100vw !important;
            margin: 0 !important;
            padding: 0 !important;
        }}

        /* 🛑 MODE 1 FUNNEL HEADER GAP FIX:
           Neutralize theme header/content top spacing that sits ABOVE the
           sticky funnel header (which lives outside #v360-wrapper). */
        body {{
            padding-top: 0 !important;
        }}
        #content, #primary, #main, .site-main, .site-content,
        .entry-content, .ast-container, .elementor-section-wrap,
        header.site-header, #masthead, .site-header,
        .elementor-location-header {{
            margin: 0 !important;
            padding: 0 !important;
            min-height: 0 !important;
        }}
        [id^="univ-header-"][id$="-funnel"] {{
            margin-top: 0 !important;
            top: 0 !important;
        }}

        /* ===== MASTER WRAPPER ===== */
        #v360-wrapper {{
            display: block !important;
            font-family: 'Outfit', sans-serif !important; 
            color: #0f172a !important; 
            line-height: 1.6 !important; 
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
            overflow-x: hidden !important;
            
            /* Core Brand Colors */
            --primary: {b_data.get('primary', '#1A73E8')};
            --secondary: {b_data.get('secondary', '#34A853')};
            --accent: {b_data.get('accent', '#FFB300')};
            --gold-primary: #FFD700;
            --gold-secondary: #D4AF37;
            --gold-light: #FFF8DC;
            --text-dark: #0f172a; 
            --text-gray: #64748b; 
            --light-bg: #f8fafc; 
            --white: #ffffff;
        }}

        #v360-wrapper * {{ 
            box-sizing: border-box !important; 
        }}

        /* 🛑 HOLLOW RECTANGLE FIX: Nuke WordPress Theme [data-icon] Hijacking */
        #v360-wrapper .iconify::before,
        #v360-wrapper .iconify::after,
        #v360-wrapper [data-icon]::before,
        #v360-wrapper [data-icon]::after {{
            content: none !important;
            display: none !important;
        }}
        
        #v360-wrapper .iconify svg {{
            display: inline-block !important;
            vertical-align: middle !important;
        }}
        
        #v360-wrapper *:not(i):not(.iconify) {{
            font-family: 'Outfit', sans-serif !important; 
        }}
        
        #v360-wrapper i.fas, #v360-wrapper i.fa {{
            font-family: "Font Awesome 6 Free" !important;
            font-weight: 900 !important;
        }}
        
        /* Headings */
        #v360-wrapper h1, #v360-wrapper h2, #v360-wrapper h3, #v360-wrapper h4 {{ 
            font-weight: 700 !important; 
            color: var(--text-dark) !important; 
            margin-top: 0 !important;
            word-wrap: break-word !important;
            line-height: 1.2 !important;
        }}

        /* 🛑 AGGRESSIVE FIX: Nuke Hello Elementor & Default Theme Titles (Fixes Double H1) */
        .entry-title, .page-title, h1.entry-title, .elementor-widget-theme-post-title, 
        .elementor-page-title, header.site-header, .site-main > header {{
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }}
        
        #v360-wrapper img {{
            max-width: 100% !important;
            height: auto !important;
            display: block !important;
        }}
        
        /* ===== BASE STRUCTURE ===== */
        #v360-wrapper .container {{ 
            max-width: 1200px !important; 
            margin: 0 auto !important; 
            padding: 0 20px !important; 
            width: 100% !important;
            display: block !important;
            box-sizing: border-box !important;
        }}

        #content, #primary, #main, .site-inner, 
        .site-main, .site-content, .page-content, .entry-content, 
        .ast-container, .elementor-section-wrap, .elementor-widget-wrap,
        .widget, .widget-area {{
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }}
        #v360-wrapper {{
            /* 🛑 THE ELEMENTOR NEGATIVE MARGIN FIX */
            margin-top: -20px !important; 
            padding-top: 0 !important;
            max-width: 100vw !important;
            overflow-x: hidden !important;
            position: relative !important;
            z-index: 10 !important;
        }}
        /* 🛑 EXPLICIT FIX: Eliminates the small white gap with the header */
        #v360-wrapper .hero {{
            margin-top: 0 !important;
            padding-top: 0 !important;
            top: 0 !important;
        }}
        
        #v360-wrapper .section {{ 
            padding: 30px 0 !important; 
            margin: 0 !important;
            position: relative !important;
            background: var(--white) !important;
            display: block !important;
            width: 100% !important;
        }}
        
        #v360-wrapper .bg-gray {{ background-color: var(--light-bg) !important; }}

        /* ── SECTION ALTERNATING BACKGROUNDS (niche bg_pattern + site_seed offset) ── */
        #v360-wrapper .section:nth-of-type({_bg_n1}) {{ background: {_sec0} !important; }}
        #v360-wrapper .section:nth-of-type({_bg_n2}) {{ background: {_sec1} !important; }}
        #v360-wrapper .section:nth-of-type({_bg_n3}) {{ background: {_sec2} !important; }}
        #v360-wrapper .section:nth-of-type({_bg_n4}) {{ background: {_sec3} !important; }}
        
        /* ===== HERO SECTION ===== */
        #v360-wrapper .hero {{ 
            position: relative !important; 
            padding: 20px 0 60px 0 !important; 
            margin-top: 0 !important;
            background-size: cover !important; 
            background-position: center !important; 
            color: white !important; 
            min-height: 550px !important;
            display: flex !important;
            align-items: center !important;
            margin-bottom: 0px !important;
            width: 100% !important;
        }}
        
        #v360-wrapper .hero-overlay {{ 
            position: absolute !important; 
            inset: 0 !important; 
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.88) 0%, rgba(15, 23, 42, 0.65) 100%) !important; 
            z-index: 1 !important;
        }} 
        
        #v360-wrapper .hero-content {{ 
            position: relative !important; 
            z-index: 2 !important; 
            display: grid !important; 
            grid-template-columns: 1.2fr 1fr !important; 
            gap: 40px !important; 
            align-items: center !important;
            width: 100% !important;
        }}
        
        #v360-wrapper .hero-gold-badge {{
            background: linear-gradient(135deg, var(--gold-primary) 0%, var(--gold-secondary) 100%) !important;
            color: #1e293b !important;
            padding: 10px 24px !important;
            border-radius: 40px !important;
            font-weight: 800 !important;
            display: inline-block !important;
            margin-bottom: 20px !important;
            font-size: 1rem !important;
            box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3) !important;
        }}
        
        #v360-wrapper .hero-gold-badge i {{ margin-right: 8px !important; color: #1e293b !important; }}
        
        #v360-wrapper .hero-title {{ 
            font-size: clamp(2.5rem, 5vw, 3.8rem) !important; 
            line-height: 1.1 !important; 
            margin-bottom: 15px !important; 
            font-weight: 800 !important;
            color: white !important;
            text-shadow: 0 2px 5px rgba(0,0,0,0.3) !important;
        }}
        
        #v360-wrapper .hero-sub {{
            font-size: 1.2rem !important;
            line-height: 1.5 !important;
            margin-bottom: 25px !important;
            color: rgba(255, 255, 255, 0.95) !important;
            font-weight: 400 !important;
        }}
        
        #v360-wrapper .hero-features {{ display: flex !important; flex-wrap: wrap !important; gap: 20px !important; margin-bottom: 30px !important; }}
        #v360-wrapper .hero-feature {{ display: flex !important; align-items: center !important; gap: 8px !important; font-size: 1rem !important; font-weight: 500 !important; color: rgba(255,255,255,0.9) !important; }}
        #v360-wrapper .hero-feature i {{ color: var(--gold-primary) !important; font-size: 1.1rem !important; }}
        
        /* ===== BUTTONS ===== */
        #v360-wrapper .btn-group {{ display: flex !important; gap: 15px !important; flex-wrap: wrap !important; }}
        
        #v360-wrapper .btn {{ 
            padding: 14px 28px !important; border-radius: 8px !important; font-weight: 700 !important; 
            text-decoration: none !important; transition: all 0.3s ease !important; 
            display: inline-flex !important; align-items: center !important; justify-content: center !important;
            gap: 10px !important; border: none !important; cursor: pointer !important; font-size: 1rem !important; 
            color: white !important; text-align: center !important; min-height: 50px !important; min-width: 150px !important;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1) !important;
        }}
        
        #v360-wrapper .btn-primary {{ background: var(--primary) !important; }}
        #v360-wrapper .btn-call {{ background: #1e40af !important; }}
        #v360-wrapper .btn-whatsapp {{ background: #25D366 !important; }}
        
        #v360-wrapper .btn-submit {{ 
            width: 100% !important; justify-content: center !important; padding: 15px !important;
            font-size: 1.1rem !important; font-weight: 700 !important; background: var(--primary) !important;
            color: #fff !important; box-shadow: 0 4px 10px rgba(0,0,0,0.1) !important; border-radius: 8px !important;
            border: none !important; cursor: pointer !important; margin-top: 10px !important;
        }}
        
        #v360-wrapper .btn-submit i {{ color: #fff !important; }}
        #v360-wrapper .btn:hover, #v360-wrapper .btn-submit:hover {{ transform: translateY(-2px) !important; filter: brightness(1.05) !important; box-shadow: 0 8px 20px rgba(0,0,0,0.15) !important; }}
        
        /* Glass Card Form (IOS ZOOM FIX APPLIED) */
        #v360-wrapper .glass-card {{ 
            background: rgba(255, 255, 255, 0.98) !important; backdrop-filter: blur(12px) !important; 
            border: 1px solid rgba(255, 255, 255, 0.3) !important; padding: 35px !important; 
            border-radius: 12px !important; box-shadow: 0 10px 30px rgba(0,0,0,0.15) !important; 
            width: 100% !important; display: block !important; box-sizing: border-box !important;
        }}
        
        #v360-wrapper .glass-card h3 {{ color: #1e293b !important; font-size: 1.6rem !important; margin-bottom: 20px !important; text-align: center !important; }}
        #v360-wrapper .glass-card h3 i {{ color: var(--gold-secondary) !important; margin-right: 10px !important; }}
        
        #v360-wrapper .glass-card input, #v360-wrapper .glass-card select, #v360-wrapper .glass-card textarea {{
            width: 100% !important; padding: 14px 16px !important; margin-bottom: 15px !important; 
            border-radius: 8px !important; border: 1px solid #e2e8f0 !important; 
            font-size: 16px !important; /* CRITICAL: Prevents iOS Zoom */
            background: #f8fafc !important; color: var(--text-dark) !important; outline: none !important; 
            box-shadow: none !important; height: auto !important; min-height: 48px !important; box-sizing: border-box !important;
        }}
        #v360-wrapper .glass-card input:focus, #v360-wrapper .glass-card select:focus {{ border-color: var(--primary) !important; background: white !important; }}

        /* ===== BULLETPROOF CSS GRID ===== */
        #v360-wrapper .service-grid, 
        #v360-wrapper .infographic-grid {{
            display: grid !important; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)) !important;
            gap: 30px !important; 
            margin-top: 20px !important; 
            width: 100% !important;
        }}

        #v360-wrapper .internal-links-grid {{
            display: grid !important; 
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)) !important;
            gap: 20px !important; 
            margin-top: 20px !important; 
            width: 100% !important;
        }}
        
        #v360-wrapper .service-card, 
        #v360-wrapper .infographic-item, 
        #v360-wrapper .internal-link-card {{
            width: 100% !important; 
            background: white !important; 
            border-radius: 12px !important; 
            overflow: hidden !important; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.05) !important; 
            border: 1px solid #eef2ff !important; 
            display: flex !important; 
            flex-direction: column !important; 
            height: 100% !important; 
            transition: all 0.3s ease !important;
        }}
        
        #v360-wrapper .service-card:hover, 
        #v360-wrapper .infographic-item:hover, 
        #v360-wrapper .internal-link-card:hover {{
            transform: translateY(-4px) !important; 
            box-shadow: 0 10px 25px rgba(0,0,0,0.08) !important; 
            border-color: var(--primary) !important; 
        }}
        
        #v360-wrapper .service-card-img {{ height: 200px !important; overflow: hidden !important; width: 100% !important; }}
        #v360-wrapper .service-card-img img {{ width: 100% !important; height: 100% !important; object-fit: cover !important; object-position: center center !important; transition: transform 0.5s ease !important; }}
        #v360-wrapper .service-card:hover img {{ transform: scale(1.05) !important; }}
        #v360-wrapper .service-card-content {{ padding: 25px !important; flex-grow: 1 !important; display: flex !important; flex-direction: column !important; }}
        #v360-wrapper .service-card h3 {{ font-size: 1.3rem !important; margin-bottom: 12px !important; color: var(--primary) !important; }}
        
        /* Infographic Specifics */
        #v360-wrapper .infographic-item {{ padding: 30px 25px !important; align-items: center !important; text-align: center !important; background: #f8fafc !important; border: none !important; }}
        #v360-wrapper .infographic-icon {{
            width: 70px !important; height: 70px !important; background: rgba(26, 115, 232, 0.1) !important; 
            border-radius: 12px !important; display: flex !important; align-items: center !important; justify-content: center !important; 
            margin: 0 auto 20px !important; font-size: 2rem !important; color: var(--primary) !important; flex-shrink: 0 !important;
        }}
        #v360-wrapper .infographic-number {{
            font-size: 2rem !important; font-weight: 800 !important; color: var(--text-dark) !important; margin-bottom: 5px !important; line-height: 1 !important;
        }}
        #v360-wrapper .infographic-item h4 {{ margin: 10px 0 10px 0 !important; color: var(--primary) !important; font-size: 1.2rem !important; line-height: 1.3 !important; }}
        
        /* Safe Text Wrappers */
        #v360-wrapper .v360-desc-text {{ color: var(--text-gray) !important; font-size: 0.95rem !important; line-height: 1.6 !important; margin: 0 0 15px 0 !important; flex-grow: 1 !important; display: block !important; text-align: left !important; }}
        #v360-wrapper .infographic-item .v360-desc-text {{ text-align: center !important; margin: 0 !important; }}

        /* ===== ZIGZAG SECTION ===== */
        #v360-wrapper .zigzag-item {{ display: flex !important; align-items: center !important; gap: 50px !important; margin-bottom: 60px !important; width: 100% !important; }}
        #v360-wrapper .zigzag-item:last-child {{ margin-bottom: 0 !important; }}
        #v360-wrapper .zigzag-item.reverse {{ flex-direction: row-reverse !important; }}
        #v360-wrapper .zigzag-content, #v360-wrapper .zigzag-img-wrap {{ flex: 1 !important; width: 100% !important; }}
        #v360-wrapper .zigzag-img {{ width: 100% !important; border-radius: 16px !important; height: 380px !important; object-fit: cover !important; object-position: center center !important; box-shadow: 0 10px 25px rgba(0,0,0,0.08) !important; transition: transform 0.5s ease !important; }}
        #v360-wrapper .zigzag-img:hover {{ transform: scale(1.02) !important; }}
        #v360-wrapper .zigzag-content h3 {{ font-size: 1.8rem !important; margin-bottom: 20px !important; color: var(--primary) !important; line-height: 1.2 !important; }}
        #v360-wrapper .service-description {{ display: flex !important; flex-direction: column !important; gap: 10px !important; margin-bottom: 25px !important; }}
        #v360-wrapper .service-line {{ position: relative !important; padding-left: 25px !important; font-size: 0.95rem !important; color: var(--text-gray) !important; line-height: 1.6 !important; display: block !important; margin-bottom: 6px !important; }}
        #v360-wrapper .service-line:before {{ content: "✓" !important; color: var(--gold-secondary) !important; font-weight: bold !important; position: absolute !important; left: 0 !important; font-size: 1.1rem !important; }}

        /* ===== PRO HORIZONTAL ACTION CARDS (Internal Links) ===== */
        #v360-wrapper .internal-links-section {{ background: linear-gradient(135deg, #f8fafc 0%, white 100%) !important; border-radius: 16px !important; padding: 40px !important; margin: 20px 0 !important; border: 1px solid #eef2ff !important; box-shadow: 0 4px 15px rgba(0,0,0,0.04) !important; width: 100% !important; box-sizing: border-box !important; }}
        
        #v360-wrapper .pro-internal-link {{
            display: flex !important;
            align-items: center !important;
            background: white !important;
            padding: 18px 20px !important;
            border-radius: 12px !important;
            border: 1px solid #eef2ff !important;
            box-shadow: 0 4px 15px rgba(0,0,0,0.03) !important;
            text-decoration: none !important;
            transition: all 0.3s ease !important;
            gap: 15px !important;
            width: 100% !important;
            box-sizing: border-box !important;
        }}
        #v360-wrapper .pro-internal-link:hover {{
            transform: translateY(-3px) !important;
            border-color: var(--primary) !important;
            box-shadow: 0 10px 25px rgba(0,0,0,0.08) !important;
        }}
        #v360-wrapper .pro-link-icon {{
            width: 50px !important;
            height: 50px !important;
            border-radius: 12px !important;
            background: rgba(26, 115, 232, 0.08) !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            flex-shrink: 0 !important;
            color: var(--primary) !important;
        }}
        #v360-wrapper .pro-link-text {{
            flex-grow: 1 !important;
            text-align: left !important;
        }}
        #v360-wrapper .pro-link-text h3 {{
            margin: 0 0 6px 0 !important;
            font-size: 1.15rem !important;
            color: var(--text-dark) !important;
            font-weight: 700 !important;
        }}
        #v360-wrapper .pro-link-text p {{
            margin: 0 !important;
            font-size: 0.9rem !important;
            color: var(--text-gray) !important;
            line-height: 1.4 !important;
        }}
        #v360-wrapper .pro-link-arrow {{
            color: #cbd5e1 !important;
            font-size: 1.1rem !important;
            transition: all 0.3s ease !important;
            flex-shrink: 0 !important;
        }}
        #v360-wrapper .pro-internal-link:hover .pro-link-arrow {{
            color: var(--primary) !important;
            transform: translateX(3px) !important;
        }}

        /* ===== FAQ SECTION ===== */
        #v360-wrapper .faq-item {{ margin-bottom: 15px !important; background: white !important; border-radius: 12px !important; overflow: hidden !important; border: 1px solid #e2e8f0 !important; box-shadow: 0 2px 10px rgba(0,0,0,0.02) !important; display: block !important; }}
        #v360-wrapper .faq-question {{ padding: 20px 25px !important; cursor: pointer !important; font-weight: 600 !important; display: flex !important; justify-content: space-between !important; align-items: center !important; background: #fafcff !important; font-size: 1.05rem !important; color: var(--text-dark) !important; transition: all 0.2s !important; }}
        #v360-wrapper .faq-question:hover {{ background: #f8fafc !important; }}
        #v360-wrapper .faq-answer {{ padding: 0 25px 25px !important; display: none; color: var(--text-gray) !important; border-top: 1px solid #f1f5f9 !important; padding-top: 20px !important; line-height: 1.6 !important; font-size: 0.95rem !important; }}

        /* ===== PILLS ===== */
        #v360-wrapper .pill-container {{ display: flex !important; flex-wrap: wrap !important; gap: 10px !important; justify-content: center !important; }}
        #v360-wrapper .pill {{ background: white !important; border: 1px solid #e2e8f0 !important; padding: 10px 20px !important; border-radius: 50px !important; font-size: 0.9rem !important; color: var(--text-gray) !important; transition: all 0.3s !important; font-weight: 500 !important; }}
        #v360-wrapper .pill:hover {{ background: var(--light-bg) !important; border-color: var(--primary) !important; color: var(--primary) !important; transform: translateY(-2px) !important; }}

        /* ==========================================================================
        📱 MOBILE RESPONSIVENESS - STRICTLY ENFORCED
        ========================================================================== */
        @media (max-width: 1024px) {{
            #v360-wrapper .service-grid, 
            #v360-wrapper .infographic-grid, 
            #v360-wrapper .internal-links-grid {{
                grid-template-columns: repeat(2, 1fr) !important;
                gap: 20px !important;
            }}
        }}
        
        @media (max-width: 768px) {{ 
            #v360-wrapper .section {{ padding: 30px 0 !important; }}
            
            /* Strict Hero Stacking */
            #v360-wrapper .hero {{ padding: 40px 0 60px !important; min-height: auto !important; background-position: center 25% !important; }}
            #v360-wrapper .hero-content {{ display: flex !important; flex-direction: column !important; gap: 35px !important; }} 
            #v360-wrapper .text-col {{ text-align: center !important; order: 1 !important; width: 100% !important; display: block !important; box-sizing: border-box !important; }}
            #v360-wrapper .form-col {{ order: 2 !important; width: 100% !important; display: block !important; box-sizing: border-box !important; }}
            #v360-wrapper .hero-features {{ justify-content: center !important; }}
            #v360-wrapper .btn-group {{ justify-content: center !important; flex-direction: column !important; }}
            #v360-wrapper .btn {{ width: 100% !important; max-width: 300px !important; margin: 0 auto !important; }}
            #v360-wrapper .hero-title {{ font-size: 2rem !important; }} 
            
            /* Strict Zigzag Stacking */
            #v360-wrapper .zigzag-item, #v360-wrapper .zigzag-item.reverse {{ flex-direction: column !important; gap: 30px !important; margin-bottom: 45px !important; width: 100% !important; }}
            #v360-wrapper .zigzag-img {{ height: 260px !important; order: 1 !important; }}
            #v360-wrapper .zigzag-content {{ text-align: center !important; order: 2 !important; width: 100% !important; box-sizing: border-box !important; }}
            #v360-wrapper .zigzag-content .service-line {{ text-align: left !important; padding-left: 28px !important; }}
            
            /* Strict 1-Column Stacking for Mobile (GRID FIX) */
            #v360-wrapper .service-grid, 
            #v360-wrapper .infographic-grid, 
            #v360-wrapper .internal-links-grid {{
                grid-template-columns: 1fr !important;
                gap: 20px !important;
            }}
            #v360-wrapper .service-card, 
            #v360-wrapper .infographic-item, 
            #v360-wrapper .internal-link-card {{
                width: 100% !important;
                max-width: 100% !important;
                box-sizing: border-box !important;
            }}
            #v360-wrapper .glass-card {{ padding: 25px 20px !important; width: 100% !important; box-sizing: border-box !important; }}
            #v360-wrapper .hero-gold-badge {{ margin: 0 auto 20px auto !important; display: inline-block !important; }}
            #v360-wrapper .internal-links-section {{ padding: 25px 20px !important; margin: 25px 0 !important; width: 100% !important; box-sizing: border-box !important; }}
            
            /* CRITICAL: MOBILE TOP BAR FIXES */
            #v360-wrapper .hide-on-mobile {{ display: none !important; }}
            #v360-wrapper .center-on-mobile {{ width: 100% !important; justify-content: center !important; text-align: center !important; }}
            #v360-wrapper .top-bar-inner {{ justify-content: center !important; }}
            #v360-wrapper .top-bar-left {{ width: 100% !important; justify-content: center !important; }}
        }}
        
        @media (max-width: 480px) {{
            #v360-wrapper .hero-title {{ font-size: 1.8rem !important; }}
            #v360-wrapper .zigzag-content h3 {{ font-size: 1.5rem !important; }}
            #v360-wrapper .zigzag-img {{ height: 220px !important; }}
            #v360-wrapper .btn {{ padding: 12px 20px !important; min-width: 140px !important; font-size: 0.9rem !important; }}
            #v360-wrapper .infographic-icon {{ width: 60px !important; height: 60px !important; font-size: 1.4rem !important; margin-bottom: 15px !important; }}
            #v360-wrapper .infographic-number {{ font-size: 2rem !important; }}
            #v360-wrapper .infographic-item h4 {{ font-size: 1.2rem !important; }}
            #v360-wrapper .pill {{ padding: 8px 16px !important; font-size: 0.85rem !important; }}
            
            /* 💎 MOBILE SAFE-ZONE FOR PRO ACTION CARDS (Prevents Text Shattering) */
            #v360-wrapper .pro-internal-link {{
                padding: 15px 12px !important;
                gap: 12px !important;
            }}
            #v360-wrapper .pro-link-icon {{
                width: 45px !important;
                height: 45px !important;
            }}
            #v360-wrapper .pro-link-text h3 {{
                font-size: 1rem !important;
            }}
        }}
    </style>
    """
    
    if is_rtl:
        css += """
        <style>
        /* ==========================================================================
        🌍 ARABIC (RTL) ALIGNMENT OVERRIDES
        ========================================================================== */
        #v360-wrapper {
            direction: rtl !important;
            text-align: right !important;
        }
        
        #v360-wrapper .text-col,
        #v360-wrapper .service-card-content,
        #v360-wrapper .internal-link-card,
        #v360-wrapper .faq-question {
            text-align: right !important;
        }

        #v360-wrapper .v360-desc-text {
            text-align: right !important;
        }
        #v360-wrapper .infographic-item .v360-desc-text {
            text-align: center !important;
        }

        #v360-wrapper .zigzag-content,
        #v360-wrapper .service-line {
            text-align: right !important;
        }
        
        /* Flip Arrows & Chevrons */
        #v360-wrapper .fa-arrow-right, 
        #v360-wrapper .fa-chevron-right { 
            transform: scaleX(-1) !important; 
        }
        
        /* Fix Bullet Points for Zigzag */
        #v360-wrapper .service-line { 
            padding-left: 0 !important; 
            padding-right: 28px !important; 
        }
        #v360-wrapper .service-line:before { 
            left: auto !important; 
            right: 0 !important; 
        }
        
        /* Fix Button & Badge Icon Margins */
        #v360-wrapper .hero-feature i,
        #v360-wrapper .btn i,
        #v360-wrapper .hero-gold-badge i,
        #v360-wrapper .glass-card h3 i { 
            margin-right: 0 !important; 
            margin-left: 10px !important; 
        }
        
        /* Move FAQ Plus/Minus Icon to the left */
        #v360-wrapper .faq-question {
            flex-direction: row-reverse !important;
        }

        /* 💎 PRO INTERNAL LINKS ARABIC FIXES */
        #v360-wrapper .pro-link-text {
            text-align: right !important;
        }
        #v360-wrapper .pro-internal-link:hover .pro-link-arrow {
            transform: translateX(-3px) !important;
        }
        
        /* Mobile Centering Override */
        @media (max-width: 768px) {
            #v360-wrapper .text-col,
            #v360-wrapper .zigzag-content {
                text-align: center !important;
            }
            #v360-wrapper .service-line {
                text-align: right !important;
            }
            #v360-wrapper .v360-desc-text {
                text-align: center !important;
            }
        }
        </style>
        """
    return css
def assemble_enhanced_page_without_header(b_data, content_data, page_type="child", service_name=None, siblings=None, parent_category=None, pre_generated_img=None, structure=None):
    """Assemble complete page WITHOUT header AND WITHOUT footer, safely scoped for Elementor."""
    
    # 🌟 CRITICAL FIX: Inject CSS directly into the wrapper so it loads instantly in WordPress
    html = get_enterprise_css(b_data)

    if b_data.get('mode') == "1":
        html += UniversalHeader.render(b_data, None, "1", "")
    
    # 🛡️ DYNAMIC LANGUAGE DIRECTION INJECTION (Handles Arabic/Hebrew/Urdu RTL automatically)
    dir_attr = get_language_direction(b_data.get('target_lang', 'en'))
    lang_code = b_data.get('target_lang', 'en')[:2]
    target_lang = b_data.get('target_lang', 'en')
    
    # 🌐 100% PERFECT CANONICAL ROUTING FOR HREFLANG
    mode_val = b_data.get('mode', '3')
    if page_type == "home":
        canonical_path = validate_url("home", None, mode_val)
    elif page_type == "parent":
        canonical_path = validate_url("category", service_name, mode_val)
    else:
        canonical_path = validate_url("service", service_name, mode_val)

    base_url = Config.WP_URL.rstrip('/')
    full_canonical = f"{base_url}{canonical_path}"

    html += f'<link rel="alternate" hreflang="{lang_code}" href="{full_canonical}">\n'
    html += f'<link rel="alternate" hreflang="x-default" href="{full_canonical}">\n'

    html += f'<div id="v360-wrapper" dir="{dir_attr}" class="lang-{lang_code}">\n'
    title = strip_markdown(content_data.get('hero_title', f"Expert {clean_title(service_name) if service_name else 'Services'}"))
    sub = strip_markdown(content_data.get('hero_sub', f"Professional & Reliable in {b_data.get('city', '')}"))
    
    if pre_generated_img:
        hero_img = pre_generated_img
    else:
        hero_img = get_hosted_image(service_name or b_data.get('industry', ''), "hero", b_data.get('industry', ''), service_name=service_name)
    
    # 1. HERO SECTION
    html += build_enhanced_hero(b_data, title, sub, hero_img, b_data.get('flat_services_list'), content_data.get('trust_signals'))

    if b_data.get('mode') != "1":
        niche = b_data.get('niche_engine')
        if niche:
            html += niche.get_extra_sections(content_data, service_name)

    # ===== MODE 1 — UNIVERSAL LANDING ENGINE =====
    if b_data.get('mode') == "1" and page_type == "child" and service_name:
        sub_services = generate_sub_services(b_data, service_name)
        body_html = build_mode1_landing_page(
            b_data=b_data, service_name=service_name, sub_services=sub_services,
            content_data=content_data, call_claude_json=call_claude_json,
            build_zigzag_section=build_zigzag_section,
            build_grid_section=build_grid_section,
            build_infographic_section=build_infographic_section,
            build_areas_served=build_areas_served,
            build_faq_section=build_faq_section,
        )
        html += body_html
        html += '</div>'
        return html
    # ===== END MODE 1 =====

    # 2. INTRO PARAGRAPH
    if content_data.get('intro'):
        html += f'''
        <section class="section">
            <div class="container" style="max-width:900px; text-align:center;">
                <div style="font-size:1.2rem; color:#475569; line-height:1.8;">{strip_markdown(content_data.get('intro', ''))}</div>
            </div>
        </section>
        '''

    if page_type == "home":
        # 1. Gather all primary items
        primary_items = []
        is_category_list = False
        
        if structure and isinstance(structure, dict):
            primary_items = list(structure.keys())
            is_category_list = True
        
        if not primary_items:
            primary_items = b_data.get('flat_services_list', [])
            
        # 💎 URL FIX: Determine if the homepage grid should link to Categories or Services
        home_url_type = "category" if is_category_list else "service"
            
        # 🌍 5-LANGUAGE TRANSLATIONS
        if target_lang == 'ar':
            core_title, zig_title = "خدماتنا الأساسية", "حلول مخصصة لك"
        elif target_lang == 'es':
            core_title, zig_title = "Nuestros Servicios Principales", "Soluciones Expertas Adaptadas para Ti"
        elif target_lang == 'fr':
            core_title, zig_title = "Nos Services Principaux", "Des Solutions Expertes Sur Mesure"
        elif target_lang == 'de':
            core_title, zig_title = "Unsere Hauptdienstleistungen", "Maßgeschneiderte Expertenlösungen"
        else:
            core_title, zig_title = "Our Core Services", "Expert Solutions Tailored For You"
            
        # Get secondary items (to fill zigzags if we run out of primary items)
        flat_list = b_data.get('flat_services_list', [])
        secondary_items = [s for s in flat_list if s not in primary_items]

        # 🧬 PAGE_DNA: site-unique layout blueprint
        _dna = b_data.get('page_dna', {})
        _services_display = _dna.get("services_display", "mixed")
        _home_order = _dna.get("home_section_order",
                               ["services_grid", "process_steps", "why_choose", "reviews", "areas", "internal_links", "faq"])
        _faq_pos = _dna.get("faq_position", "bottom")

        # ── Renderer for the services block (honors services_display) ──
        def _render_services_block():
            grid_items = []
            zigzag_items = []
            total_primary = len(primary_items)

            if _services_display == "grid":
                # Pure grid — up to 9 items
                return build_grid_section(b_data, (primary_items + secondary_items)[:9],
                                          core_title, limit=9, url_type=home_url_type)
            elif _services_display == "zigzag":
                # Pure zigzag — up to 6 items
                return build_zigzag_section(b_data, (primary_items + secondary_items)[:6],
                                            core_title, limit=6, is_child_page=False, url_type="service")

            # "mixed" — the perfect 1-10 math (default)
            if total_primary <= 2:
                grid_items = []
                zigzag_items = (primary_items + secondary_items)[:4]
            elif 3 <= total_primary < 6:
                grid_items = primary_items[:3]
                zigzag_items = (primary_items[3:] + secondary_items)[:4]
            else:
                grid_items = primary_items[:6]
                zigzag_items = (primary_items[6:] + secondary_items)[:4]

            _h = ""
            if grid_items:
                _h += build_grid_section(b_data, grid_items, core_title, limit=len(grid_items), url_type=home_url_type)
            if zigzag_items:
                _h += build_zigzag_section(b_data, zigzag_items, zig_title, limit=len(zigzag_items), is_child_page=False, url_type="service")
            return _h

        # ── Section renderers keyed by DNA names ──
        def _render_home_section(name):
            if name == "services_grid":
                return _render_services_block()
            elif name == "why_choose":
                if content_data.get('why_choose_us'):
                    return build_infographic_section(content_data.get('why_choose_us', [])[:3], b_data)
                return ""
            elif name == "reviews":
                if content_data.get('reviews'):
                    _areas = content_data.get('areas_served', [b_data.get('city', '')])
                    return build_testimonials_section(b_data, content_data.get('reviews', []), _areas)
                return ""
            elif name == "areas":
                if content_data.get('areas_served'):
                    return build_areas_served(b_data, content_data.get('areas_served', []))
                return ""
            elif name == "process_steps":
                return build_how_it_works_section(b_data)
            elif name == "internal_links":
                return build_internal_links_section(b_data, "home", "home")
            elif name == "faq":
                # FAQ handled separately via faq_position — skip inline unless DNA forces it here
                return ""
            return ""

        # ── Render home in DNA order (skip faq here, place it per faq_position) ──
        _faq_html = ""
        if content_data.get('faqs'):
            _faq_html = build_faq_section(content_data.get('faqs'), None, b_data)

        for _sec in _home_order:
            if _sec == "faq":
                continue  # placed via faq_position below
            html += _render_home_section(_sec)
            # Insert FAQ right after why_choose if DNA requests it
            if _faq_pos == "after_why_choose" and _sec == "why_choose":
                html += _faq_html
                _faq_html = ""  # consumed

        # Any remaining FAQ goes at the bottom
        if _faq_html:
            html += _faq_html

        _home_dna_rendered = True
        
    elif page_type == "parent":
        # 🌍 5-LANGUAGE TRANSLATIONS FOR CATEGORY PAGES
        if target_lang == 'ar':
            services_title = f"خدمات {clean_title(service_name)} الشاملة"
        elif target_lang == 'es':
            services_title = f"Servicios Completos de {clean_title(service_name)}"
        elif target_lang == 'fr':
            services_title = f"Services Complets de {clean_title(service_name)}"
        elif target_lang == 'de':
            services_title = f"Komplette {clean_title(service_name)} Dienstleistungen"
        else:
            services_title = f"Complete {clean_title(service_name)} Services"
            
        if siblings and len(siblings) > 0:
            # 💎 PERFECT ROUTING: Force url_type="service" for children of this category
            html += build_dynamic_layout_section(b_data, siblings[:6], services_title, "parent", f"parent_{slugify(service_name)}", url_type="service")
            
        if content_data.get('why_choose_us'):
            html += build_infographic_section(content_data.get('why_choose_us', [])[:3], b_data)
        
    else: # Child page
        # 🌍 5-LANGUAGE TRANSLATIONS FOR CHILD PAGES
        parent_name_clean = clean_title(parent_category) if parent_category else b_data.get('industry', '')
        
        if target_lang == 'ar':
            related_title = f"خدمات {parent_name_clean} ذات الصلة"
        elif target_lang == 'es':
            related_title = f"Servicios Relacionados con {parent_name_clean}"
        elif target_lang == 'fr':
            related_title = f"Services Liés à {parent_name_clean}"
        elif target_lang == 'de':
            related_title = f"Verwandte {parent_name_clean} Dienstleistungen"
        else:
            related_title = f"Related {parent_name_clean} Services"

        if siblings and len(siblings) > 0:
            # 💎 PERFECT ROUTING: Force url_type="service"
            html += build_dynamic_layout_section(b_data, siblings[:6], related_title, "child", f"child_{slugify(service_name)}", url_type="service")
            
        if content_data.get('why_choose_us'):
            html += build_infographic_section(content_data.get('why_choose_us', [])[:3], b_data)
            
        html += build_internal_links_section(b_data, service_name, "child")

    # 7 & 8. AREAS SERVED + REVIEWS — order varies per business (niche_engine section-order)
    areas_html = build_areas_served(b_data, content_data.get('areas_served', [])) if content_data.get('areas_served') else ""
    reviews_html = ""
    if content_data.get('reviews'):
        areas_list = content_data.get('areas_served', [b_data.get('city', '')])
        reviews_html = build_testimonials_section(b_data, content_data.get('reviews', []), areas_list)

    section_order = get_section_order(b_data)
    for sec in section_order:
        if sec == "areas":
            html += areas_html
        elif sec == "reviews":
            html += reviews_html
        # "why_choose" already placed earlier in each branch — position kept as-is  
        
    # 9. FAQS — home page already placed its FAQ via PAGE_DNA faq_position
    if content_data.get('faqs') and not (page_type == "home" and 'page_dna' in b_data):
        html += build_faq_section(content_data.get('faqs'), service_name, b_data)
    
    html += '</div>'
    return html
# ==============================================================================
# 📤 WORDPRESS PUBLISHER (WITHOUT HEADER)
# ==============================================================================

@retry_operation(max_retries=3, delay=5)
def get_existing_page_content(page_id, wp_conf):
    """Fetch existing page content from WordPress."""
    url = f"{wp_conf['url'].rstrip('/')}/wp-json/wp/v2/pages/{page_id}"
    auth = base64.b64encode(f"{wp_conf['user']}:{wp_conf['pass']}".encode()).decode('utf-8')
    headers = {"Authorization": f"Basic {auth}", "User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=20)
        if response.status_code == 200:
            data = response.json()
            return {
                "id": data['id'],
                "title": data['title']['rendered'],
                "slug": data['slug'],
                "content": data['content']['rendered'],
                "link": data['link']
            }
        return None
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")
        raise e

@retry_operation(max_retries=4, delay=5)
def publish_to_wp_without_header(title, slug, content, parent_id=0, wp_conf=None, update_id=None, meta_data=None):
    """Publish page to WordPress WITHOUT header - safely handles connections."""
    
    parts = re.split(r'(<(?:textarea|pre|script)[\s\S]*?</(?:textarea|pre|script)>)', content)
    result = []
    for part in parts:
        if part.startswith('<textarea') or part.startswith('<pre') or part.startswith('<script'):
            result.append(part)
        else:
            result.append(re.sub(r'\n\s*', ' ', part)) 
    content = ''.join(result)
    
    # 🟢 THE FIX: Wrap the minified output in Gutenberg HTML block tags
    # This stops WordPress from injecting `<p></p>` and breaking your grids/icons!
    safe_gutenberg_content = f"<!-- wp:html -->\n{content}\n<!-- /wp:html -->"
    
    if not wp_conf:
        print(f"   ⚠️ No WordPress configuration")
        return 0
    
    url = f"{wp_conf['url'].rstrip('/')}/wp-json/wp/v2/pages"
    auth = base64.b64encode(f"{wp_conf['user']}:{wp_conf['pass']}".encode()).decode('utf-8')
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    payload = {
        "title": title,
        "content": safe_gutenberg_content,
        "slug": slug,
        "status": "publish",
        "parent": parent_id, 
        "meta": {
            "_elementor_hide_title": "yes",       # Hides duplicate H1 in Elementor
            "ast-title-bar-display": "disabled",  # Hides duplicate H1 in Astra
            "ocean_disable_title": "yes"          # Hides duplicate H1 in OceanWP
        }
    }
    
    
    if meta_data:
        if meta_data.get('meta_title'):
            payload["meta"]["rank_math_title"] = meta_data["meta_title"]
        if meta_data.get('meta_description'):
            payload["meta"]["rank_math_description"] = meta_data["meta_description"]
        if meta_data.get('meta_keywords'):
            payload["meta"]["rank_math_focus_keyword"] = meta_data["meta_keywords"]
    
    try:
        if update_id:
            response = requests.put(f"{url}/{update_id}", headers=headers, json=payload, verify=False, timeout=30)
            if response.status_code == 200:
                print(f"   🔄 Updated Page: {title} with proper SEO tags")
                return update_id
            return 0
        
        check = requests.get(f"{url}?slug={slug}", headers=headers, verify=False, timeout=30)
        if check.status_code == 200 and check.json():
            pid = check.json()[0]['id']
            response = requests.put(f"{url}/{pid}", headers=headers, json=payload, verify=False, timeout=30)
            if response.status_code == 200:
                print(f"   🔄 Updated Page: {title} (ID: {pid}) with proper SEO tags")
                return pid
            return 0
        else:
            response = requests.post(url, headers=headers, json=payload, verify=False, timeout=30)
            if response.status_code == 201:
                pid = response.json()['id']
                print(f"   ✅ Created Page: {title} (ID: {pid}) with proper SEO tags")
                return pid
            else:
                print(f"   ❌ WP Error: {response.status_code} - {response.text}")
                return 0
    except Exception as e:
        print(f"   ❌ Connection Failed: {str(e)[:100]}")
        raise e

# ==============================================================================
# 🎮 MAIN EXECUTION
# ==============================================================================

def run_generator():
    """Main execution function — GitHub Actions compatible (config.json driven)."""
    import json as _json

    # ── CONFIG.JSON LOAD ──────────────────────────────────────────────────────
    _cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if not os.path.exists(_cfg_path):
        print("\n❌ config.json not found! Repo me config.json rakho.")
        sys.exit(1)

    with open(_cfg_path, "r", encoding="utf-8") as _f:
        cfg = _json.load(_f)

    print("\n📋 CONFIG LOADED FROM config.json")
    print("-" * 40)

    # ── WORDPRESS TARGET (URL/User config se, Password sirf Secret se) ────────
    wp_url_cfg  = cfg.get("wordpress_url", "").strip()
    wp_user_cfg = cfg.get("wordpress_user", "").strip()
    wp_pass_cfg = cfg.get("wordpress_app_password", "").strip()
    if wp_url_cfg:  Config.WP_URL  = wp_url_cfg
    if wp_user_cfg: Config.WP_USER = wp_user_cfg
    if wp_pass_cfg: Config.WP_APP_PASSWORD = wp_pass_cfg

    if not Config.WP_URL or not Config.WP_USER or not Config.WP_APP_PASSWORD:
        print("\n❌ WordPress credentials missing!")
        print("   wordpress_url + wordpress_user → config.json me")
        print("   WP_APP_PASSWORD → GitHub Secret me (ya local export)")
        sys.exit(1)

    if not Config.WP_URL.startswith("http"):
        Config.WP_URL = "https://" + Config.WP_URL
    if not Config.WP_URL.endswith("/"):
        Config.WP_URL += "/"
    Config.SITE_URL = Config.WP_URL
    print(f"✅ WordPress Target: {Config.WP_URL} (user: {Config.WP_USER})")

    wp_conf = {"url": Config.WP_URL, "user": Config.WP_USER, "pass": Config.WP_APP_PASSWORD}

    # ── 🛡️ WORDPRESS CONNECTION PRE-CHECK (resource-saving) ──────────────────
    print("\n🔌 Testing WordPress connection...")
    try:
        _auth = base64.b64encode(f"{wp_conf['user']}:{wp_conf['pass']}".encode()).decode('utf-8')
        _headers = {"Authorization": f"Basic {_auth}", "User-Agent": "Mozilla/5.0"}
        _check_url = f"{wp_conf['url'].rstrip('/')}/wp-json/wp/v2/users/me"
        _resp = requests.get(_check_url, headers=_headers, verify=False, timeout=15)
        if _resp.status_code == 200:
            _user_data = _resp.json()
            print(f"   ✅ Connected to WordPress as: {_user_data.get('name', wp_conf['user'])}")
        else:
            print(f"   ❌ WordPress connection FAILED — Status {_resp.status_code}")
            print(f"   Response: {_resp.text[:200]}")
            print("\n❌ ABORTING — fix WP_URL/WP_USER/WP_APP_PASSWORD before running again.")
            sys.exit(1)
    except Exception as e:
        print(f"   ❌ WordPress connection ERROR: {e}")
        print("\n❌ ABORTING — check WP_URL is reachable and credentials are correct.")
        sys.exit(1)
    # ── END PRE-CHECK ──────────────────────────────────────────────────────────

    # ── 🌐 LANGUAGE (5-LANGUAGE SYSTEM: en / ar / es / fr / de) ───────────────
    lang_input = cfg.get("language", "en").strip().lower()
    if lang_input in ["no", ""]:
        lang_input = "en"
    if lang_input not in ["en", "ar", "es", "fr", "de"]:
        print(f"⚠️ Unknown language '{lang_input}' — defaulting to English")
        lang_input = "en"

    UI_DICT = {
        "en": {
            "home": "Home", "services": "Services", "contact": "Contact",
            "blog": "Blog", "locations": "Locations", "about": "About",
            "get_quote": "Get Quote", "call_now": "Call Now",
            "free_quote": "Free Quote", "send_message": "Send Message",
            "why_choose_us": "Why Choose Us?", "faq": "Frequently Asked Questions",
            "areas_served": "Areas We Serve", "learn_more": "Learn More",
            "dir": "ltr", "current_svc": "Current Service", "more_qs": "Have more questions? Call us anytime!",
            "rated": "#1 Rated in", "areas_served_in": "Areas We Serve in",
            "submit_btn": "Get Quote", "service_ph": "Select Service",
            "name_ph": "Name", "phone_ph": "Phone", "other_services": "Other Services",
            "whatsapp": "WhatsApp Quote", "get_in_touch": "Get in Touch"
        },
        "ar": {
            "home": "الرئيسية", "services": "خدماتنا", "contact": "اتصل بنا",
            "blog": "المدونة", "locations": "المواقع", "about": "من نحن",
            "get_quote": "احصل على عرض سعر", "call_now": "اتصل الآن",
            "free_quote": "عرض سعر مجاني", "send_message": "إرسال رسالة",
            "why_choose_us": "لماذا تختارنا؟", "faq": "الأسئلة الشائعة",
            "areas_served": "المناطق التي نخدمها", "learn_more": "اعرف المزيد",
            "dir": "rtl", "current_svc": "الخدمة الحالية", "more_qs": "لديك أسئلة أخرى؟ اتصل بنا في أي وقت!",
            "rated": "الأعلى تقييمًا في", "areas_served_in": "المناطق التي نخدمها في",
            "submit_btn": "احصل على عرض سعر", "service_ph": "اختر الخدمة",
            "name_ph": "الاسم", "phone_ph": "رقم الهاتف", "other_services": "خدمات أخرى",
            "whatsapp": "واتساب", "get_in_touch": "تواصل معنا"
        },
        "es": {
            "home": "Inicio", "services": "Servicios", "contact": "Contacto",
            "blog": "Blog", "locations": "Ubicaciones", "about": "Nosotros",
            "get_quote": "Obtener Cotización", "call_now": "Llamar Ahora",
            "free_quote": "Cotización Gratis", "send_message": "Enviar Mensaje",
            "why_choose_us": "¿Por Qué Elegirnos?", "faq": "Preguntas Frecuentes",
            "areas_served": "Áreas de Servicio", "learn_more": "Saber Más",
            "dir": "ltr", "current_svc": "Servicio Actual", "more_qs": "¿Más preguntas? ¡Llámanos!",
            "rated": "Mejor valorado en", "areas_served_in": "Áreas que servimos en",
            "submit_btn": "Obtener Cotización", "service_ph": "Seleccionar Servicio",
            "name_ph": "Nombre", "phone_ph": "Teléfono", "other_services": "Otros Servicios",
            "whatsapp": "WhatsApp", "get_in_touch": "Contáctenos"
        },
        "fr": {
            "home": "Accueil", "services": "Services", "contact": "Contact",
            "blog": "Blog", "locations": "Emplacements", "about": "À Propos",
            "get_quote": "Obtenir un Devis", "call_now": "Appelez Maintenant",
            "free_quote": "Devis Gratuit", "send_message": "Envoyer un Message",
            "why_choose_us": "Pourquoi Nous Choisir ?", "faq": "Questions Fréquentes",
            "areas_served": "Zones Desservies", "learn_more": "En Savoir Plus",
            "dir": "ltr", "current_svc": "Service Actuel", "more_qs": "D'autres questions ? Appelez-nous !",
            "rated": "Le mieux noté à", "areas_served_in": "Zones desservies à",
            "submit_btn": "Obtenir un Devis", "service_ph": "Sélectionner un Service",
            "name_ph": "Nom", "phone_ph": "Téléphone", "other_services": "Autres Services",
            "whatsapp": "WhatsApp", "get_in_touch": "Contactez-nous"
        },
        "de": {
            "home": "Startseite", "services": "Dienstleistungen", "contact": "Kontakt",
            "blog": "Blog", "locations": "Standorte", "about": "Über Uns",
            "get_quote": "Angebot Einholen", "call_now": "Jetzt Anrufen",
            "free_quote": "Kostenloses Angebot", "send_message": "Nachricht Senden",
            "why_choose_us": "Warum Wir?", "faq": "Häufig Gestellte Fragen",
            "areas_served": "Einzugsgebiete", "learn_more": "Mehr Erfahren",
            "dir": "ltr", "current_svc": "Aktueller Service", "more_qs": "Weitere Fragen? Rufen Sie an!",
            "rated": "Am besten bewertet in", "areas_served_in": "Unsere Einzugsgebiete in",
            "submit_btn": "Angebot Einholen", "service_ph": "Service Auswählen",
            "name_ph": "Name", "phone_ph": "Telefon", "other_services": "Andere Dienstleistungen",
            "whatsapp": "WhatsApp", "get_in_touch": "Kontaktieren Sie uns"
        }
    }
    ui_translations = UI_DICT[lang_input]
    is_rtl = (ui_translations.get("dir") == "rtl")
    print(f"✅ Language: {lang_input.upper()} ({'RTL' if is_rtl else 'LTR'})")

    # ── BUSINESS INPUTS ───────────────────────────────────────────────────────
    name     = cfg.get("business_name", "Global Services").strip() or "Global Services"
    industry = cfg.get("industry", "General").strip() or "General"
    country  = cfg.get("country", "UAE").strip()
    state    = cfg.get("state", "").strip()
    city     = cfg.get("city", "").strip() or "Major Cities"
    phone    = cfg.get("phone", "+971501234567").strip()
    clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace("+", "")
    print(f"✅ Business: {name} | {industry} | {city}, {country}")

    # ── SOCIAL LINKS ──────────────────────────────────────────────────────────
    facebook  = cfg.get("facebook",  "#")
    twitter   = cfg.get("twitter",   "#")
    instagram = cfg.get("instagram", "#")
    linkedin  = cfg.get("linkedin",  "#")
    youtube   = cfg.get("youtube",   "#")

    # ── MODE ──────────────────────────────────────────────────────────────────
    mode_input = str(cfg.get("mode", "3")).strip()
    print(f"✅ Mode: {mode_input}")

    # ── IMAGE MODEL ───────────────────────────────────────────────────────────
    img_choice = str(cfg.get("image_model", "1")).strip()
    if img_choice == "2":
        Config.IMAGE_MODEL, Config.LOGO_MODEL, Config.PHOTO_MODEL = "openai", "openai", "openai"
    elif img_choice == "3":
        Config.IMAGE_MODEL, Config.LOGO_MODEL, Config.PHOTO_MODEL = "replicate", "replicate", "replicate"
    else:
        Config.IMAGE_MODEL, Config.LOGO_MODEL, Config.PHOTO_MODEL = "hybrid", "openai", "replicate"
    print(f"✅ Image Model: {Config.IMAGE_MODEL.upper()}")

    # ── LINKING SETTINGS ──────────────────────────────────────────────────────
    Config.GENERATE_INTERNAL_LINKS = cfg.get("internal_links", "yes").strip().lower() in ["yes", "y", ""]
    Config.GENERATE_BACKLINKS      = cfg.get("backlinks", "no").strip().lower() in ["yes", "y"]
    print(f"✅ Internal Links: {Config.GENERATE_INTERNAL_LINKS} | Backlinks: {Config.GENERATE_BACKLINKS}")

    # ── AI BRAND COLORS ───────────────────────────────────────────────────────
    colors = {"primary": "#1e40af", "secondary": "#0f766e", "accent": "#16a34a"}
    ai_colors = call_claude_json(
        f"Generate 3 VIBRANT, high-contrast hex colors for a {industry} business. "
        f"Return JSON with keys: primary, secondary, accent."
    )
    if not ai_colors and CLIENTS.get('openai'):
        try:
            c_resp = CLIENTS['openai'].chat.completions.create(
                model=Config.MODEL_LOW_TIER,
                messages=[{"role": "user", "content": f"Generate 3 VIBRANT hex colors for a {industry} business. Return JSON keys: primary, secondary, accent."}],
                response_format={"type": "json_object"}, temperature=0.3
            )
            ai_colors = clean_json_response(c_resp.choices[0].message.content)
        except Exception as e:
            print(f"   ⚠️ Color Error: {e}")
    if ai_colors and isinstance(ai_colors, dict):
        colors.update(ai_colors)
    print(f"   🎨 Colors: {colors}")

    # ── LOGO (sirf Mode 3) ────────────────────────────────────────────────────
    logo_url = ""
    if mode_input == "3":
        print("\n🖼️ Generating Business Logo...")
        logo_url = generate_logo({"name": name, "industry": industry, "city": city,
                                  "country": country, "primary": colors['primary'],
                                  "accent": colors['accent']}) or ""
    else:
        print("\nℹ️ Skipping Logo Generation (Not in Full Website Mode)")

    # ── B_DATA ────────────────────────────────────────────────────────────────
    import hashlib as _hashlib
    _site_seed_src = f"{name}{industry}{city}{country}".lower().strip()
    _site_seed = int(_hashlib.md5(_site_seed_src.encode()).hexdigest()[:8], 16)

    b_data = {
        "site_seed": _site_seed,
        "name": name, "city": city, "state": state, "country": country,
        "industry": industry, "phone": phone, "whatsapp": clean_phone,
        "primary": colors['primary'], "secondary": colors['secondary'], "accent": colors['accent'],
        "mode": mode_input,
        "domain": name.lower().replace(' ', '') + '.com',
        "google_sheet_url": Config.GOOGLE_SHEET_URL,
        "flat_services_list": [],
        "logo_url": logo_url,
        "facebook": facebook, "twitter": twitter, "instagram": instagram,
        "linkedin": linkedin, "youtube": youtube,
        "ui": ui_translations,
        "target_lang": lang_input,
        "is_rtl": is_rtl,
        "lang_mode": lang_input,
        "generated_pages": []
    }

    # ── 🎨 NICHE-AWARE DESIGN PROFILE (variety per business: fonts, trust items, etc.) ──
    print("\n🎨 Generating niche design profile...")
    niche = NicheEngine(b_data, claude_caller=call_claude_json)
    b_data['niche_engine'] = niche
    niche_slug = niche.slug
    niche_profile = niche.profile
    b_data['niche_slug'] = niche_slug
    b_data['niche_profile'] = niche_profile

    tok = _get_business_tokens(b_data)
    p = niche_profile["palette"]
    b_data['primary'] = _hue_shift(p["primary"], tok["hue_shift"])
    b_data['secondary'] = _hue_shift(p["secondary"], tok["hue_shift"] + tok["secondary_extra"])
    b_data['accent'] = p["accent"]

    print(f"   ✅ Niche: {niche_slug} | Heading Font: {niche_profile.get('font_primary')} | Label: {niche_profile.get('label')}")

    # 🎯 DESIGN SPEC — coordinated hero/how-it-works content for entire site
    b_data['design_spec'] = generate_design_spec(b_data)

    # ── H1 KEYWORD GUARANTEE: force primary keyword into the hero H1 ──
    _loc = b_data.get("city") or b_data.get("country", "")
    _ind = b_data.get("industry", "")
    _kw_check = extract_keyword_tiers(b_data, _ind, _ind, _loc, b_data.get("target_lang", "en"))
    _primary_kw = (_kw_check.get("high_intent") or [None])[0]
    if _primary_kw:
        _h1 = b_data['design_spec'].get("hero_title", "")
        if _primary_kw.lower() not in _h1.lower():
            _words = _primary_kw.title().split()[:3]
            b_data['design_spec']["hero_title"] = f"{' '.join(_words)} — {_loc}".strip(" —")
            print(f"   ⚡ H1 keyword fixed: \"{b_data['design_spec']['hero_title']}\"")

    # 🧬 PAGE_DNA — site-unique layout blueprint (one Claude call)
    b_data['page_dna'] = generate_page_dna(b_data)

    # ── 🛑 LANGUAGE ROUTING (Menu links ↔ Published slugs PERFECT MATCH) ──────
    Config.SERVICE_BASE_PATH = "/"
    lang_slug_prefix = f"{lang_input}-" if lang_input != "en" else ""
    if lang_input != "en":
        Config.LANG_PREFIX = f"/{lang_input}-".rstrip('/')
    else:
        Config.LANG_PREFIX = ""

    # ==========================================================================
    # MODE 1 — CONTENT INJECTOR
    # ==========================================================================
    if mode_input == "1":
        print("\n💉 MODE 1: CONTENT INJECTOR")
        target_id = str(cfg.get("target_page_id", "")).strip()
        if not target_id.isdigit():
            print("❌ config.json me 'target_page_id' (number) zaroori hai for Mode 1.")
            sys.exit(1)

        existing_page = get_existing_page_content(target_id, wp_conf)
        if not existing_page:
            print("❌ Target page nahi mili — Page ID check karein.")
            sys.exit(1)
        print(f"   ✅ Found: {existing_page['title']}")

        service_name = cfg.get("main_service", "").strip() or existing_page['title']
        b_data['flat_services_list'] = [service_name]

        print(f"   🧠 Generating sub-services for Grid/Zigzag layout...")
        mode_1_siblings = generate_sub_services(b_data, service_name)

        content_data = generate_page_content(b_data, "child", service_name)
        if content_data:
            page_content = assemble_enhanced_page_without_header(
                b_data, content_data, page_type="child",
                service_name=service_name, siblings=mode_1_siblings
            )
            schema = generate_hierarchical_schema(
                b_data, content_data, service_name,
                f"{wp_conf['url'].rstrip('/')}/{lang_slug_prefix}{slugify(service_name)}/"
            )
            page_content += f'\n<script type="application/ld+json">{schema}</script>'

            meta_html  = f'<meta name="description" content="{content_data.get("meta_description", "")}">\n'
            meta_html += f'<meta name="keywords" content="{content_data.get("meta_keywords", "")}">\n'
            final_content = existing_page['content'] + "\n" + meta_html + page_content

            publish_to_wp_without_header(existing_page['title'], existing_page['slug'],
                                         final_content, wp_conf=wp_conf,
                                         update_id=int(target_id), meta_data=content_data)

    # ==========================================================================
    # MODE 2 — HUB MODE
    # ==========================================================================
    elif mode_input == "2":
        print("\n🔗 MODE 2: HUB MODE")
        entered_id  = str(cfg.get("hub_page_id", "")).strip()
        hub_page_id = int(entered_id) if entered_id.isdigit() else 0

        if hub_page_id != 0:
            hub_page = get_existing_page_content(hub_page_id, wp_conf)
            if hub_page:
                Config.SERVICE_BASE_PATH = f"/{hub_page['slug']}/"
                print(f"   ✅ Base path dynamically set to: {Config.SERVICE_BASE_PATH}")

        inp = cfg.get("sub_services", "").strip()
        services_list = [s.strip() for s in inp.split(',') if s.strip()]
        if not services_list:
            print("❌ config.json me 'sub_services' (comma separated) zaroori hai for Mode 2.")
            sys.exit(1)
        b_data['flat_services_list'] = services_list

        for service in services_list:
            print(f"\n📄 Generating: {service}...")
            hero_img = get_hosted_image(service, "hero", industry, service_name=service)
            content_data = generate_page_content(b_data, "child", service)
            wp_id = 0
            if content_data:
                siblings = [s for s in services_list if s != service]
                page_content = assemble_enhanced_page_without_header(
                    b_data, content_data, page_type="child", service_name=service,
                    siblings=siblings, pre_generated_img=hero_img
                )
                safe_url = f"{wp_conf['url'].rstrip('/')}{validate_url('service', service, mode_input)}"
                schema = generate_hierarchical_schema(b_data, content_data, service, safe_url)
                page_content += f'\n<script type="application/ld+json">{schema}</script>'

                wp_id = publish_to_wp_without_header(
                    clean_title(service), f"{lang_slug_prefix}{slugify(service)}",
                    page_content, parent_id=hub_page_id, wp_conf=wp_conf, meta_data=content_data
                )

                if wp_id and Config.GENERATE_BACKLINKS and hero_img:
                    live_link = safe_url
                    social_desc = content_data.get('intro', '')[:300]
                    BacklinkManager.create_devto_post(f"Expert Guide: {clean_title(service)}", social_desc, hero_img, live_link)
                    BacklinkManager.create_blogger_post(f"New Guide: {clean_title(service)}", social_desc, hero_img, live_link)
            time.sleep(Config.API_DELAY)

    # ==========================================================================
    # MODE 3 — FULL WEBSITE
    # ==========================================================================
    elif mode_input == "3":
        print("\n🏗️ MODE 3: FULL WEBSITE")
        raw_svc = cfg.get("services_mode3", "").strip()
        lines   = [s.strip() for s in raw_svc.split(",") if s.strip()]
        if not lines:
            print("❌ config.json me 'services_mode3' (comma separated) zaroori hai for Mode 3.")
            sys.exit(1)

        unique_lines = list(set(lines))
        raw_in = "\n".join(unique_lines)
        in_mode = "urls" if any('http' in l for l in unique_lines) else "services"
        structure = analyze_structure_with_ai(raw_in, target_lang=lang_input, mode=in_mode)

        flat_ai = []
        for k, v in structure.items():
            if isinstance(v, dict) and "children" in v:
                flat_ai.extend(v["children"])
        orig_lower = {s.lower(): s for s in unique_lines if 'http' not in s}
        ai_lower   = [s.lower() for s in flat_ai]
        missing    = [orig_lower[k] for k in orig_lower if k not in ai_lower]
        if missing:
            cats = list(structure.keys()) or ["General Services"]
            for i, item in enumerate(missing):
                cat = cats[i % len(cats)]
                if isinstance(structure.get(cat), dict):
                    structure[cat].setdefault("children", []).append(item)

        flat = []
        for k, v in structure.items():
            if isinstance(v, dict) and 'children' in v:
                flat.extend(v['children'])
        b_data['flat_services_list'] = list(set(flat))
        print(f"✅ {len(structure)} categories | {len(b_data['flat_services_list'])} services")

        # ── HOMEPAGE ──────────────────────────────────────────────────────────
        print(f"\n🏠 Generating Homepage...")
        home_content = generate_page_content(b_data, "home")
        if home_content:
            home_html = assemble_enhanced_page_without_header(b_data, home_content, "home", "Home", structure=structure)
            schema = generate_hierarchical_schema(b_data, home_content, "Home", wp_conf['url'])
            home_html += f'\n<script type="application/ld+json">{schema}</script>'
            home_slug = f"{lang_slug_prefix}home" if lang_slug_prefix else "home"
            publish_to_wp_without_header("Home", home_slug, home_html, wp_conf=wp_conf, meta_data=home_content)

        # ── CATEGORIES + CHILD SERVICES ───────────────────────────────────────
        for category, data in structure.items():
            if not isinstance(data, dict):
                continue
            print(f"\n📂 Generating Category: {category}...")
            cat_content = generate_page_content(b_data, "parent", category, sub_services=data.get('children', []))
            if not cat_content:
                continue
            cat_html = assemble_enhanced_page_without_header(b_data, cat_content, "parent", category,
                                                             siblings=data.get('children', []), structure=structure)
            cat_full_url = f"{wp_conf['url'].rstrip('/')}{validate_url('category', category, mode_input)}"
            schema = generate_hierarchical_schema(b_data, cat_content, category, cat_full_url)
            cat_html += f'\n<script type="application/ld+json">{schema}</script>'

            cat_slug  = f"{lang_slug_prefix}{slugify(category)}"
            parent_id = publish_to_wp_without_header(clean_title(category), cat_slug, cat_html,
                                                     wp_conf=wp_conf, meta_data=cat_content)

            for service in data.get('children', []):
                print(f"   📄 Generating: {service}...")
                hero_img = get_hosted_image(service, "hero", industry, service_name=service)
                rel = get_service_relationships(service)
                child_content = generate_page_content(b_data, "child", service, parent_service=category,
                                                      sibling_services=rel.get('siblings', []),
                                                      child_services=rel.get('children', []))
                if child_content:
                    child_html = assemble_enhanced_page_without_header(b_data, child_content, "child", service,
                                                                       siblings=rel.get('siblings', []),
                                                                       parent_category=category,
                                                                       pre_generated_img=hero_img,
                                                                       structure=structure)
                    child_full_url = f"{wp_conf['url'].rstrip('/')}{validate_url('service', service, mode_input)}"
                    schema = generate_hierarchical_schema(b_data, child_content, service, child_full_url,
                                                          parent_category=category, is_child_page=True,
                                                          parent_url=cat_full_url)
                    child_html += f'\n<script type="application/ld+json">{schema}</script>'

                    service_slug = slugify(service)
                    wp_id = publish_to_wp_without_header(clean_title(service), service_slug, child_html,
                                                         parent_id=parent_id, wp_conf=wp_conf,
                                                         meta_data=child_content)

                    if wp_id and Config.GENERATE_BACKLINKS and hero_img:
                        social_desc = child_content.get('intro', '')[:300]
                        BacklinkManager.create_devto_post(f"Expert Guide: {clean_title(service)}", social_desc, hero_img, child_full_url)
                        BacklinkManager.create_blogger_post(f"New Guide: {clean_title(service)}", social_desc, hero_img, child_full_url)
                    time.sleep(Config.API_DELAY)

        # ── WIDGET EXPORTS ─────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("🍔 GENERATING WIDGET CODES (MENU, FOOTER & CSS)")
        print("=" * 60)
        export_mega_menu_as_page(wp_conf, b_data, structure, mode_input)
        export_footer_as_page(wp_conf, b_data, structure)
        export_global_css_as_page(wp_conf, b_data)

        # ── CORE PAGES (Contact / About / Blog) — 5-language titles ──────────
        target_lang = lang_input
        dir_attr  = get_language_direction(target_lang)
        lang_code = target_lang[:2]

        core_titles = {
            "en": ("Contact Us", "About Us", "Blog"),
            "ar": ("اتصل بنا", "من نحن", "المدونة"),
            "es": ("Contacto", "Sobre Nosotros", "Blog"),
            "fr": ("Contact", "À Propos", "Blog"),
            "de": ("Kontakt", "Über Uns", "Blog"),
        }
        contact_title, about_title, blog_title = core_titles.get(target_lang, core_titles["en"])

        print(f"\n📄 Generating Contact Page...")
        contact_content = f"{get_enterprise_css(b_data)}\n{build_contact_html(b_data)}"
        safe_contact_url = f"{wp_conf['url'].rstrip('/')}/{lang_slug_prefix}contact/"
        contact_content += f'\n<script type="application/ld+json">{generate_hierarchical_schema(b_data, {}, contact_title, safe_contact_url)}</script>'
        publish_to_wp_without_header(contact_title, f"{lang_slug_prefix}contact", contact_content, wp_conf=wp_conf)

        print(f"\n📄 Generating About Page...")
        about_content = f"{get_enterprise_css(b_data)}\n{build_about_html(b_data)}"
        safe_about_url = f"{wp_conf['url'].rstrip('/')}/{lang_slug_prefix}about/"
        about_content += f'\n<script type="application/ld+json">{generate_hierarchical_schema(b_data, {}, about_title, safe_about_url)}</script>'
        publish_to_wp_without_header(about_title, f"{lang_slug_prefix}about", about_content, wp_conf=wp_conf)

        print(f"\n📄 Generating Blog Page...")
        blog_html = build_blog_page_html(b_data, wp_conf['url'])
        full_blog_content = f'''
        {get_enterprise_css(b_data)}
        <div id="v360-wrapper" dir="{dir_attr}" class="lang-{lang_code}">
            {blog_html}
        </div>
        '''
        safe_blog_url = f"{wp_conf['url'].rstrip('/')}/{lang_slug_prefix}blog/"
        full_blog_content += f'\n<script type="application/ld+json">{generate_hierarchical_schema(b_data, {}, blog_title, safe_blog_url)}</script>'
        publish_to_wp_without_header(blog_title, f"{lang_slug_prefix}blog", full_blog_content, wp_conf=wp_conf)

    # ── DONE ──────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(" ✅ WORDPRESS SITE GENERATION COMPLETE!")
    print(" 🌐 Website: " + wp_conf['url'])
    print("\n 🍔 NEXT STEPS:")
    print(" 1. WP Admin → Pages → 'Mega Menu Code', 'Footer Code', 'Global CSS Code' (Drafts)")
    print(" 2. Code copy karein → Appearance → Widgets → Custom HTML me paste karein")
    print(" 3. Menu/Footer ab har page par flawlessly show honge!")
    print("=" * 60)
# ==============================================================================
# 🚀 SCRIPT ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    try:
        run_generator()
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

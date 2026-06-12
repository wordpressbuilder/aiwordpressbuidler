import requests
import base64
import cloudinary
import cloudinary.uploader
import openai
import anthropic  # <-- ADD THIS
import replicate
import json
import random
import sys
from html import escape
import re
import os
import time
from niche_engine import NicheEngine
from mode1_landing_engine import build_mode1_landing_page
import functools
import shutil
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
print(" 🚀 UNIVERSAL STATIC SITE GENERATOR V6.0 - COMPLETE FIXED VERSION")
print(" 💎 ALL ISSUES FIXED: Meta Tags, Mobile Form, Why Choose Us, Menu Text")
print(" 💎 ENHANCED SEO: Related Keywords, Entities, Rich Snippets")
print(" 💎 MOBILE HERO: Form ALWAYS visible - 100% guaranteed with short placeholders")
print(" 💎 WHY CHOOSE US: All cards have EQUAL, rich descriptive content")
print(" 💎 MENU TEXT: Properly shortened to 2-3 words max")
print(" 💎 INTERNAL LINKS: Perfect formatting with proper URLs")
print(" 💎 SCHEMA: Enhanced with LocalBusiness, Service, FAQ, Review, and more")
print("=" * 80)

class Config:
    # ---------------------------------------------------------
    # ⚠️ REPLACE THESE WITH YOUR ACTUAL API KEYS BEFORE RUNNING
    # ---------------------------------------------------------
    OPENAI_API_KEY        = os.environ.get("OPENAI_API_KEY", "")
    REPLICATE_API_TOKEN   = os.environ.get("REPLICATE_API_TOKEN", "")
    ANTHROPIC_API_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL          = "claude-opus-4-6"
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY    = os.environ.get("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")
    
    # 🌍 MASTER LOCATIONS LIST (Grouped by Country)
    LOCATIONS = []
    
    # IMAGE MODEL SELECTION (Set at runtime)
    IMAGE_MODEL = "hybrid"  # default, will be set by user input
    PHOTO_MODEL = "replicate"
    LOGO_MODEL = "openai"
    # RATE LIMIT PROTECTION
    REPLICATE_REQUEST_DELAY = 15  # Seconds between Replicate requests to prevent 429
    
    # STATIC SITE CONFIGURATION
    OUTPUT_FOLDER = "static_website"
    
    # DATA TRACKING
    GOOGLE_SHEET_URL = "https://script.google.com/macros/s/AKfycbwfulMr_zpU10c7oHkcCC7oG-35KRM53KkFbG0qViaqvmkthZF9mnXHW0CoNEtwTl-g/exec"
    
    # 🔗 BACKLINK SETTINGS
    DEVTO_API_KEY = os.environ.get("DEVTO_API_KEY", "")
    BLOGGER_ID = None
    
    # 🔗 [NEW] DYNAMIC PATH SETTING
    # Default is "/services/", but Mode 2 will change this automatically to "/sialkot-seo/" etc.
    SERVICE_BASE_PATH = "/services/" 
    
    # 🔥 ADDED: GLOBAL LANGUAGE PREFIX ROUTING
    LANG_PREFIX = ""
    
    # SETTINGS
    MODEL_HIGH_TIER = "gpt-5.4"
    MODEL_LOW_TIER  = "gpt-5.4-mini"
    API_DELAY = 2
    MAX_RETRIES = 3
    IMAGE_QUALITY = 90
    SITE_URL = "https://example.com"  # Auto-overwritten at runtime from user input
    # BACKLINK & INTERNAL LINKS CONTROLS
    GENERATE_BACKLINKS = True
    GENERATE_INTERNAL_LINKS = True
    
    # LOGO SETTINGS
    LOGO_URL = ""
    LOGO_WIDTH = "200"
    LOGO_HEIGHT = "80"
    
    # HUB MODE TARGET URL
    HUB_TARGET_URL = ""
    
    # SOCIAL MEDIA LINKS
    SOCIAL_LINKS = {
        "facebook": "",
        "twitter": "",
        "instagram": "",
        "linkedin": "",
        "youtube": "",
        "pinterest": ""
    }
    
    # IMPORTANT FOOTER LINKS - REMOVED Careers, Terms, Privacy (only essential)
    FOOTER_LINKS = {
        "About Us": "/pages/about.html",
        "Services": "/services/",
        "Contact": "/pages/contact.html",
        "Blog": "/blog/",
        "Sitemap": "/sitemap.xml"
    }
    
    # ENTITY CACHE FOR RELATED KEYWORDS
    ENTITY_CACHE = {}

    # 🆕 VISION INSPECTOR RETRY LIMIT (5 tries then fallback)
    VISION_MAX_RETRIES = 5
# ==============================================================================
# 🛠️ HELPER FUNCTIONS - MUST BE DEFINED FIRST
# ==============================================================================
def strip_markdown(text):
    """Remove markdown formatting from text."""
    if not isinstance(text, str):
        return text
    text = re.sub(r'\*\*|__|##|###|---', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    return text.strip()

def clean_json_response(raw_text):
    """Clean and parse JSON from AI response."""
    try:
        if not raw_text:
            return None
            
        # 1. Strip markdown code blocks
        clean_text = re.sub(r'```json\s*', '', raw_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'```', '', clean_text)
        
        # 2. Isolate the JSON object
        start = clean_text.find('{')
        end = clean_text.rfind('}') + 1
        
        if start != -1 and end != 0:
            json_str = clean_text[start:end]
            
            # 3. Safely parse the JSON directly (OpenAI JSON mode guarantees valid syntax)
            return json.loads(json_str.strip())
            
        return None
        
    except Exception as e:
        print(f"   ⚠️ JSON Parsing Error: {e}")
        return None
def call_claude_json(prompt, system_prompt="You are an elite SEO copywriter. Always output valid JSON."):
    """Helper function to call Claude and return parsed JSON.
    RESILIENT: 4 attempts with growing delay (3s/6s/9s) — survives net blips,
    rate limits, and overloaded errors. SDK adds 2 internal retries per attempt."""
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

def optimize_cloudinary(url, width=320):
    """Cloudinary URL mein delivery transformation inject karta hai:
    chhoti width + f_auto (WebP/AVIF) + q_auto:eco = 95% chhota file."""
    if not url or "res.cloudinary.com" not in url or "/upload/" not in url:
        return url
    if "f_auto" in url or "w_" in url.split("/upload/")[1][:30]:
        return url  # already optimized
    return url.replace("/upload/", f"/upload/w_{width},f_auto,q_auto:eco/", 1)

# 🌐 GLOBAL TRANSLATION CACHE
GLOBAL_TRANSLATIONS = {}

def clean_title(text, b_data=None):
    """Clean and title case text - with Global Translation Support."""
    if not text:
        return ""
    text_str = str(text).replace("-", " ").replace("_", " ").strip()

    # 🌐 INTERCEPT AND TRANSLATE
    if text_str.lower() in GLOBAL_TRANSLATIONS:
        return strip_markdown(GLOBAL_TRANSLATIONS[text_str.lower()])

    text_str = strip_markdown(text_str)
    words = text_str.split()
    title_words = []
    for word in words:
        if word.isupper() and len(word) > 1:
            title_words.append(word)
        else:
            title_words.append(word.title())
    return " ".join(title_words)
import re

def get_dynamic_icon(text):
    """
    Automatically assigns a highly relevant MDI (Iconify) Icon based on the service name.
    Uses strict word boundaries to prevent substring overlap (e.g., 'auto' vs 'automation').
    """
    if not text:
        return "mdi:briefcase-check-outline" # Universal fallback
        
    t = str(text).lower()
    
    # Dictionary mapping regex patterns to MDI icons
    mapping = {
        # Appliance Repair
        r'\b(fridge|refrigerator|freezer|cooler|ice)\b': 'mdi:fridge',
        r'\b(wash(er|ing)?|laundry|dryer)\b': 'mdi:washing-machine',
        r'\b(dish(washer)?|plate)\b': 'mdi:dishwasher',
        r'\b(oven|stove|cooker|range|hob)\b': 'mdi:stove',
        
        # HVAC & Air
        r'\b(ac|air condition(ing|er)?|hvac|vent|duct|heating|furnace)\b': 'mdi:air-conditioner',
        r'\b(gas|leak)\b': 'mdi:gas-cylinder',
        
        # Home Trades & Contracting
        r'\b(plumb(er|ing)?|pipe|water|drain|toilet)\b': 'mdi:water',
        r'\b(elect(ric|rician)?|light(ing)?|wire|wiring|power)\b': 'mdi:lightning-bolt',
        r'\b(roof(ing|er)?|gutter)\b': 'mdi:home-roof',
        r'\b(paint(er|ing)?)\b': 'mdi:format-paint',
        r'\b(build(er|ing)?|construct(ion)?|contractor|remodel(ing)?|renovat(ion)?)\b': 'mdi:hammer-screwdriver',
        r'\b(handyman|fix|repair)\b': 'mdi:tools',
        r'\b(lock(smith)?|key|secur(ity)?)\b': 'mdi:lock',
        r'\b(glass|window)\b': 'mdi:window-closed',
        
        # Cleaning & Maintenance
        r'\b(clean(ing|er)?|maid|janitor(ial)?|sweep|sanitiz(e|ation))\b': 'mdi:broom',
        r'\b(pest|bug|insect|exterminat(or|ion)?)\b': 'mdi:bug',
        r'\b(pool|swim(ming)?)\b': 'mdi:pool',
        
        # Outdoor & Moving
        r'\b(lawn|landscape|tree|garden(ing)?|yard)\b': 'mdi:tree',
        r'\b(mov(ing|er)?|pack(ing|er)?|relocat(ion)?)\b': 'mdi:truck-fast',
        r'\b(garage|door)\b': 'mdi:garage',
        
        # Automotive
        r'\b(auto|car|mechanic|tow(ing)?|vehicle)\b': 'mdi:car-wrench',
        
        # B2B, Digital & Tech
        r'\b(seo|market(ing)?|digital|web|software|app|tech|cyber)\b': 'mdi:bullseye-arrow',
        r'\b(consult(ing|ant)?|advisor|finance|account(ing|ant)?|tax)\b': 'mdi:chart-line',
        
        # Health, Medical & Beauty
        r'\b(medic(al)?|doctor|clinic|hospital|health)\b': 'mdi:hospital-box',
        r'\b(dent(al|ist)?|teeth|tooth)\b': 'mdi:tooth',
        r'\b(beauty|salon|spa|hair|nail|massage)\b': 'mdi:content-cut',
        r'\b(gym|fitness|workout|train(ing|er)?)\b': 'mdi:dumbbell',
        
        # Real Estate & Legal
        r'\b(real estate|property|realtor)\b': 'mdi:home-city',
        r'\b(law(yer)?|attorney|legal)\b': 'mdi:scale-balance',
        
        # Events & Hospitality
        r'\b(cater(ing)?|food|restaurant|chef)\b': 'mdi:silverware-fork-knife',
        r'\b(event|party|wed(ding)?|photo(graphy)?)\b': 'mdi:camera'
    }
    
    # Check the text against our patterns
    for pattern, icon in mapping.items():
        if re.search(pattern, t):
            return icon
            
    # Universal fallback for any unmapped business/service
    return "mdi:briefcase-check-outline"
def shorten_menu_text(text, max_words=2):
    """Shorten menu text for cleaner display - FIXED to 2-3 words max."""
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text
    # Keep the most important words (usually first 2-3)
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

def get_unique_folder_name(base_name="static_website"):
    """Generate unique folder name with timestamp to prevent overwrites."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_name = f"{base_name}_{timestamp}"
    return unique_name

def validate_url(url_type, slug, mode, pages_list=None):
    """Validate that a URL exists or will exist in the site - 100% LANGUAGE AWARE (CLEAN URLS)."""
    
    # 1. Grab the absolute language prefix from global config (e.g., "/en" or "/ar")
    lang_prefix = getattr(Config, 'LANG_PREFIX', "")
    
    # 2. Get the dynamic base path
    base_path = Config.SERVICE_BASE_PATH
    
    # Ensure base_path starts and ends with /
    if not base_path.startswith('/'): base_path = '/' + base_path
    if not base_path.endswith('/'): base_path = base_path + '/'

    # 3. CRITICAL SAFETY NET: If we have a language selected, but the base_path 
    # lost it during Hub Mode setup, force it back in!
    if lang_prefix and not base_path.startswith(f"{lang_prefix}/"):
        base_path = f"{lang_prefix}{base_path}"

    if url_type == "home":
        # Mode 2 Hubs treat the Index as the "Home" of that Silo
        if mode == "2":
            return base_path
        return f"{lang_prefix}/" if lang_prefix else "/"
        
    elif url_type == "services_index":
        return base_path
        
    elif url_type == "categories_index":
        return f"{lang_prefix}/categories" if lang_prefix else "/categories"
        
    elif url_type == "contact":
        return f"{lang_prefix}/pages/contact" if lang_prefix else "/pages/contact"
        
    elif url_type == "about":
        return f"{lang_prefix}/pages/about" if lang_prefix else "/pages/about"
        
    elif url_type == "blog":
        return f"{lang_prefix}/blog" if lang_prefix else "/blog"
        
    elif url_type == "service" and slug:
        # For service pages, use the full base_path which is guaranteed to have the language
        # STRIPPED .html for clean URLs
        return f"{base_path}{slugify(slug)}"
        
    elif url_type == "category" and slug:
        # STRIPPED .html for clean URLs
        return f"{lang_prefix}/categories/{slugify(slug)}" if lang_prefix else f"/categories/{slugify(slug)}"
        
    else:
        return "#"
# ==============================================================================
# 🔄 RETRY DECORATOR - DEFINED BEFORE USE
# ==============================================================================
def retry_operation(max_retries=3, delay=2):
    """Decorator for retrying operations on failure."""
    def decorator(func):
        @functools.wraps(func)
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
    
    # 1. OpenAI Initialization
    if hasattr(Config, 'OPENAI_API_KEY') and Config.OPENAI_API_KEY and "sk-" in Config.OPENAI_API_KEY:
        try:
            clients['openai'] = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
            print("✅ OpenAI Client Initialized")
        except Exception as e:
            print(f"⚠️ OpenAI Error: {e}")
            clients['openai'] = None
    else:
        clients['openai'] = None
        print("⚠️ OpenAI API Key missing.")
    # 1.5 Anthropic Initialization
    if hasattr(Config, 'ANTHROPIC_API_KEY') and Config.ANTHROPIC_API_KEY and "sk-ant" in Config.ANTHROPIC_API_KEY:
        try:
            clients['claude'] = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
            print("✅ Anthropic (Claude) Client Initialized")
        except Exception as e:
            print(f"⚠️ Anthropic Error: {e}")
            clients['claude'] = None
    else:
        clients['claude'] = None
        print("⚠️ Anthropic API Key missing.")
    # 2. Replicate Initialization
    replicate_token = getattr(Config, 'REPLICATE_API_TOKEN', None)
    if replicate_token and "r8_" in replicate_token:
        os.environ["REPLICATE_API_TOKEN"] = replicate_token
        try:
            clients['replicate'] = True
            print("✅ Replicate API Configured")
        except Exception as e:
            print(f"⚠️ Replicate Test Failed: {e}")
            clients['replicate'] = False
    else:
        clients['replicate'] = False
        print("⚠️ Replicate API Token missing.")

    # 3. Cloudinary Initialization
    try:
        if hasattr(Config, 'CLOUDINARY_CLOUD_NAME') and Config.CLOUDINARY_CLOUD_NAME:
            cloudinary.config(
                cloud_name=Config.CLOUDINARY_CLOUD_NAME,
                api_key=Config.CLOUDINARY_API_KEY,
                api_secret=Config.CLOUDINARY_API_SECRET,
                secure=True
            )
            print("✅ Cloudinary Configured")
            clients['cloudinary'] = True
        else:
            print("⚠️ Cloudinary keys missing. Images will use placeholders.")
            clients['cloudinary'] = False
    except Exception as e:
        print(f"⚠️ Cloudinary Error: {e}")
        clients['cloudinary'] = False
        
    return clients

# ==============================================================================
# 🌍 GLOBAL STATE & CACHE INITIALIZATION
# ==============================================================================
CLIENTS = init_clients()

# Data Caches (Saves API costs by remembering previous results)
IMAGE_CACHE = {} 
ZIGZAG_CONTENT_CACHE = {}
CATEGORY_IMAGE_CACHE = {}
SERVICE_FAQS_CACHE = {}
LAYOUT_STYLES_CACHE = {}

# 🆕 NEW: Stores the Top 7 services for the Hero Form (Prevents overflow)
HERO_DROPDOWN_CACHE = []  

# Structure & Progress Tracking
SERVICE_HIERARCHY = {}
GENERATED_PAGES_LIST = ['index.html']
LAST_REPLICATE_REQUEST = 0  # For rate limiting

# ==============================================================================
# 🎨 ENHANCED LOGO GENERATION - WITH MULTIPLE FORMATS AND STYLES
# ==============================================================================
@retry_operation(max_retries=2)
def generate_logo(b_data, output_folder=""):
    """
    ADVANCED AI LOGO GENERATOR: 
    Supports Replicate (FLUX) and OpenAI (GPT-Image-2/DALL-E 3).
    """
    logo_url = ""
    business_name = b_data.get('name', 'Company')
    industry = b_data.get('industry', 'Business')
    
    primary_color = b_data.get('primary', '#1A73E8')
    accent_color = b_data.get('accent', '#FFB300')
    
    # Base prompt used for both models
    pro_logo_prompt = (
        f"A premium, modern minimalist corporate logo for a {industry} company named '{business_name}'. "
        f"Design style: Flat vector graphic, clean geometric lines, highly professional. "
        f"Color palette: Strictly uses {primary_color} as the primary color and {accent_color} as the secondary accent. "
        f"Background: Pure solid white background. "
        f"CRITICAL: No 3D effects, no shadows, no physical mockups, no gradients. Perfectly centered."
    )
    
    # ==========================================
    # OPTION 1: REPLICATE (FLUX) - Budget/Testing
    # ==========================================
    if Config.LOGO_MODEL == "replicate" and CLIENTS.get('replicate'):
        try:
            print(f"   🎨 Generating Budget Logo with Replicate (FLUX)...")
            # Rate limit protection
            global LAST_REPLICATE_REQUEST
            elapsed = time.time() - LAST_REPLICATE_REQUEST
            if elapsed < Config.REPLICATE_REQUEST_DELAY:
                time.sleep(Config.REPLICATE_REQUEST_DELAY - elapsed)

            output = replicate.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": pro_logo_prompt + " minimalist vector icon.",
                    "aspect_ratio": "1:1",
                    "output_format": "png",
                    "output_quality": 90
                }
            )
            LAST_REPLICATE_REQUEST = time.time()

            if output:
                image_source = str(output[0]) if isinstance(output, list) else output
                
                # Upload to Cloudinary
                if image_source and CLIENTS.get('cloudinary'):
                    res = cloudinary.uploader.upload(
                        image_source,
                        folder="static_website/logos",
                        public_id=f"logo_flux_{slugify(business_name)}_{int(time.time())}",
                        quality=90,
                        format="png"
                    )
                    logo_url = res.get('secure_url')
                    print(f"   ✅ FLUX Logo uploaded: {logo_url[:50]}...")
                    return logo_url
        except Exception as e:
            print(f"   ⚠️ Replicate Logo Failed: {e}. Falling back to GPT...")

    # ==========================================
    # OPTION 2: OPENAI (GPT/DALL-E) - Production
    # ==========================================
    if not logo_url and CLIENTS.get('openai'):
        # --- ATTEMPT A: gpt-image-2 ---
        try:
            print(f"   🎨 Generating PRO Logo with gpt-image-2...")
            response = CLIENTS['openai'].images.generate(
                model="gpt-image-2",
                prompt=pro_logo_prompt,
                size="1024x1024",
                quality="high",
                n=1,
                output_format="png"
            )
            
            if response and response.data:
                data_obj = response.data[0]
                img_data = None
                
                if hasattr(data_obj, 'b64_json') and data_obj.b64_json:
                    import tempfile
                    image_bytes = base64.b64decode(data_obj.b64_json)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        tmp.write(image_bytes)
                        img_data = tmp.name
                elif hasattr(data_obj, 'url') and data_obj.url:
                    img_data = data_obj.url

                if img_data and CLIENTS.get('cloudinary'):
                    res = cloudinary.uploader.upload(
                        img_data,
                        folder="static_website/logos",
                        public_id=f"logo_gpt_{slugify(business_name)}_{int(time.time())}",
                        quality=90,
                        format="png",
                        transformation=[{"width": 480, "crop": "limit"},
                                        {"quality": "auto:eco"},
                                        {"fetch_format": "auto"}]
                    )
                    logo_url = res.get('secure_url')
                    print(f"   ✅ GPT-Image-2 Logo uploaded: {logo_url[:50]}...")
                    return logo_url
                    
        except Exception as e:
            print(f"   ⚠️ gpt-image-2 failed: {e}. Trying DALL-E 3 fallback...")

        # --- ATTEMPT B: dall-e-3 (FALLBACK) ---
        if not logo_url:
            try:
                print(f"   🎨 Generating PRO Logo with dall-e-3...")
                response = CLIENTS['openai'].images.generate(
                    model="dall-e-3",
                    prompt=pro_logo_prompt,
                    size="1024x1024",
                    n=1,
                    response_format="b64_json"
                )
                
                if response and response.data:
                    image_bytes = base64.b64decode(response.data[0].b64_json)
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        tmp.write(image_bytes)
                        img_data = tmp.name
                    
                    if CLIENTS.get('cloudinary'):
                        res = cloudinary.uploader.upload(
                            img_data,
                            folder="static_website/logos",
                            public_id=f"logo_dalle_{slugify(business_name)}_{int(time.time())}",
                            quality=90,
                            format="png"
                        )
                        logo_url = res.get('secure_url')
                        return logo_url
            except Exception as e:
                print(f"   ⚠️ dall-e-3 failed: {e}")

    # ==========================================
    # ULTIMATE FALLBACK: FontAwesome Icon
    # ==========================================
    if not logo_url:
        industry_lower = industry.lower()
        icon_name = "fas fa-tools"
        if any(x in industry_lower for x in ['plumb', 'pipe']): icon_name = "fas fa-wrench"
        elif any(x in industry_lower for x in ['elect', 'light']): icon_name = "fas fa-bolt"
        elif any(x in industry_lower for x in ['hvac', 'heat', 'cool', 'ac']): icon_name = "fas fa-wind"
        logo_url = icon_name
        print(f"   ℹ️ Using FontAwesome fallback: {icon_name}")
        
    return logo_url
# ==============================================================================
# 🆕 MODE 2 INTERNAL LINKS GENERATOR
# ==============================================================================
def generate_mode2_internal_links(b_data, current_service, all_services):
    """Generate beautiful internal links section for Mode 2 pages - WITH RTL ICONIFY SUPPORT."""
    if not Config.GENERATE_INTERNAL_LINKS or len(all_services) <= 1:
        return ""
    
    siblings = [s for s in all_services if s != current_service]
    if not siblings:
        return ""
    
    city_display = b_data.get('city') if b_data.get('city') else b_data.get('country')
    mode = b_data.get('mode', '3')
    target_lang = b_data.get('target_lang', 'en')
    ui = b_data.get('ui', {})
    
    # 🌍 RTL Arrow Logic mapped to a guaranteed MDI icon
    arrow_icon = "mdi:arrow-left" if target_lang == 'ar' else "mdi:arrow-right"
    text_align = "right" if target_lang == 'ar' else "left"
    
    # Language-aware section titles
    if target_lang == 'ar':
        section_title = f"جميع خدمات {b_data.get('industry', 'التسويق الرقمي')}"
        description = f"استكشف مجموعتنا الكاملة من الخدمات الاحترافية في {city_display}. تم تصميم كل خدمة لتحقيق أقصى النتائج لعملك."
        learn_more = "اعرف المزيد"
        professional_text = "خدمات احترافية"
    else:
        section_title = f"Our Complete {b_data.get('industry', 'Digital Marketing')} Services"
        description = f"Explore our full range of professional services in {city_display}. Each service is tailored to deliver maximum results for your business."
        learn_more = "Learn More"
        professional_text = "Professional"
    
    html = '<section class="internal-links-section"><div class="container">'
    html += f'''
        <h3 style="margin-bottom: 25px; color: var(--primary); font-size: 1.8rem; display:flex; align-items:center; gap:10px;">
            <span class="iconify" data-icon="mdi:link-variant" data-width="28"></span> {section_title}
        </h3>
        <p style="color: var(--text-gray); margin-bottom: 30px; font-size: 1.1rem;">
            {description}
        </p>
        <div class="internal-links-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">
    '''
    
    for sibling in siblings[:6]:
        link = validate_url("service", sibling, mode)
        sibling_icon = get_dynamic_icon(sibling)
        
        if target_lang == 'ar':
            service_text = f"لـ {clean_title(sibling)}"
        else:
            service_text = f"for {clean_title(sibling)}"
        
        html += f'''
        <a href="{link}" class="pro-internal-link" rel="dofollow" style="position: relative; display: flex; align-items: flex-start; background: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eef2ff; box-shadow: 0 4px 15px rgba(0,0,0,0.03); gap: 16px; width: 100%; transition: all 0.3s ease; text-decoration: none;">
            <div class="pro-link-icon" style="width: 50px; height: 50px; border-radius: 12px; background: rgba(26, 115, 232, 0.08); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                <span class="iconify" data-icon="{sibling_icon}" data-width="26" style="color: var(--primary);"></span>
            </div>
            
            <div class="pro-link-text" style="flex-grow: 1; min-width: 0; text-align: {text_align}; display: flex; flex-direction: column; justify-content: center; min-height: 50px;">
                <h4 style="margin: 0; font-size: 1.05rem; color: #0f172a; font-weight: 600; line-height: 1.3;">{clean_title(sibling)}</h4>
                <p style="margin: 0; font-size: 0.9rem; color: #64748b; line-height: 1.5; padding-top: 4px;">
                    {professional_text} {service_text}
                </p>
                <span style="display:inline-block; margin-top:8px; color:var(--primary); font-weight:600; font-size:0.85rem; display:flex; align-items:center; gap:5px;">
                    {learn_more} <span class="iconify" data-icon="{arrow_icon}" data-width="14"></span>
                </span>
            </div>
        </a>
        '''
    
    html += '</div></div></section>'
    return html
# ==============================================================================
# 🆕 MODE 1 SUB-SERVICES GENERATOR - ENHANCED
# ==============================================================================
@retry_operation(max_retries=3)
def generate_sub_services(b_data, main_service):
    """Generate 6 related sub-services for Mode 1 using AI."""

    # ── NEW: If the user supplied their own list, always return it ──
    custom = b_data.get('mode1_custom_subs', [])
    if custom:
        return custom          # skip AI entirely, return exact user list

    cache_key = f"sub_services_{main_service}"
    
    # Enhanced fallback with more specific options
    if not CLIENTS['openai']:
        industry = b_data.get('industry', '').lower()
        main_lower = main_service.lower()
        
        # PPC/Advertising specific
        if 'ppc' in main_lower or 'advertising' in main_lower or 'ad' in main_lower:
            return [
                "Google Ads Campaign Management",
                "Facebook & Instagram Advertising",
                "Shopping Ads Optimization",
                "Display Network Advertising", 
                "Remarketing Strategy Development",
                "Conversion Rate Optimization"
            ]
        # SEO specific
        elif 'seo' in main_lower or 'search' in main_lower:
            return [
                "Keyword Research & Analysis",
                "On-Page SEO Optimization",
                "Technical SEO Audit",
                "Link Building Strategy",
                "Local SEO Optimization",
                "SEO Performance Reporting"
            ]
        # Social Media specific
        elif 'social' in main_lower:
            return [
                "Social Media Strategy",
                "Content Creation & Curation",
                "Community Management",
                "Paid Social Advertising",
                "Influencer Marketing",
                "Social Analytics & Reporting"
            ]
        # Web Development specific
        elif 'web' in main_lower or 'develop' in main_lower:
            return [
                "Custom Website Design",
                "E-commerce Development",
                "CMS Integration",
                "Responsive Mobile Design",
                "Website Maintenance",
                "Performance Optimization"
            ]
        # Electrical specific
        elif 'elect' in main_lower:
            return [
                "24/7 Power Restoration",
                "Circuit Breaker Repair",
                "Emergency Lighting Installation",
                "Faulty Wiring Repair",
                "Generator Connection Services",
                "Electrical Safety Inspections"
            ]
        else:
            return [
                f"Strategic {main_service} Planning",
                f"Executive {main_service} Management",
                f"Analytics & {main_service} Reporting",
                f"{main_service} Audit & Optimization",
                f"Advanced {main_service} Techniques",
                f"{main_service} ROI Maximization"
            ]
    
    try:
        prompt = f"""
        Generate 6 SPECIFIC, REALISTIC sub-services for the main service: "{main_service}"
        Industry: {b_data.get('industry')}
        Location: {b_data.get('city', b_data.get('country'))}
        
        Requirements:
        - Return EXACTLY 6 sub-services
        - Must be specific, not generic
        - Should be actual related services customers need
        - Each sub-service should be 2-4 words
        - Format as JSON array of strings
        
        Example for "PPC Advertising":
        ["Google Ads Campaign Management", "Facebook & Instagram Ads", 
         "Shopping Ads Optimization", "Display Network Advertising", 
         "Remarketing Strategy", "Conversion Rate Optimization"]
        
        Return ONLY JSON: {{"sub_services": ["service1", "service2", ...]}}
        """
        
        response = CLIENTS['openai'].chat.completions.create(
            model=Config.MODEL_LOW_TIER,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} 
        )
        
        content = clean_json_response(response.choices[0].message.content)
        if content and 'sub_services' in content and len(content['sub_services']) >= 6:
            return content['sub_services'][:6]
    except Exception as e:
        print(f"   ⚠️ Sub-service generation error: {e}")
    
    # Ultimate fallback
    return [f"Professional {main_service} - Service {i+1}" for i in range(6)]

# ==============================================================================
# 🔗 BACKLINK MANAGER (DEV.TO + BLOGGER)
# ==============================================================================
class BacklinkManager:
    @staticmethod
    def create_devto_post(title, content, image_url, target_link):
        """Creates a post on Dev.to pointing to your new website."""
        if not Config.GENERATE_BACKLINKS:
            return None
        if not Config.DEVTO_API_KEY:
            print("   ⚠️ Dev.to API Key missing.")
            return None

        url = "https://dev.to/api/articles"
        headers = {
            "api-key": Config.DEVTO_API_KEY,
            "Content-Type": "application/json"
        }
        
        markdown_body = f"""
![{title}]({image_url})

# {title}

{content}

## Need Professional Help?

**[👉 Click here to get the best {title} services]({target_link})**
"""
        
        payload = {
            "article": {
                "title": f"Guide: {title}",
                "published": True,
                "body_markdown": markdown_body,
                "main_image": image_url,
                "tags": ["business", "services", "guide", "professional"]
            }
        }

        try:
            print(f"   🤖 Posting to Dev.to...")
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 201:
                data = response.json()
                print(f"   ✅ Dev.to Post Created: {data.get('url')}")
                return True
            else:
                print(f"   ❌ Dev.to Failed ({response.status_code})")
                return False
        except Exception as e:
            print(f"   ⚠️ Dev.to Error: {e}")
            return False

    @staticmethod
    def create_blogger_post(title, content, image_url, target_link):
        """Creates a post on Blogger with a backlink."""
        if not Config.GENERATE_BACKLINKS:
            return None
        if not os.path.exists('token.json'):
            return None

        try:
            creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/blogger'])
            service = build('blogger', 'v3', credentials=creds)

            if not Config.BLOGGER_ID:
                blogs = service.blogs().listByUser(userId='self').execute()
                if 'items' in blogs:
                    Config.BLOGGER_ID = blogs['items'][0]['id']
                else:
                    print("   ❌ No Blog found.")
                    return None

            post_body = f"""
            <div style="text-align: center; margin-bottom: 20px;">
                <img src="{image_url}" style="max-width: 100%; border-radius: 10px;">
            </div>
            <p>{content}</p>
            <p style="text-align: center; font-weight: bold; font-size: 1.2em; margin-top: 30px;">
                <a href="{target_link}">👉 Click here to read the full guide on {title}</a>
            </p>
            """

            body = {
                "kind": "blogger#post",
                "title": f"Guide: {title}",
                "content": post_body
            }

            print(f"   🅱️  Posting to Blogger...")
            posts = service.posts()
            result = posts.insert(blogId=Config.BLOGGER_ID, body=body).execute()
            print(f"   ✅ Blogger Link Created: {result.get('url')}")
            return True

        except Exception as e:
            print(f"   ❌ Blogger Error: {e}")
            return False

# ==============================================================================
# 🗂️ STATIC SITE FOLDER STRUCTURE
# ==============================================================================
def create_folder_structure():
    """Creates the complete folder structure for the static site."""
    
    # Generate unique folder name with timestamp
    unique_folder = get_unique_folder_name(Config.OUTPUT_FOLDER)
    Config.OUTPUT_FOLDER = unique_folder
    
    if os.path.exists(Config.OUTPUT_FOLDER):
        shutil.rmtree(Config.OUTPUT_FOLDER)
    
    os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)
    
    folders = [
        'css', 'js', 'images', 'images/services', 'images/categories', 
        'images/hero', 'images/logos', 'pages', 'services', 'categories', 'blog',
        'assets', 'assets/icons', 'assets/fonts'
    ]
    
    for folder in folders:
        os.makedirs(os.path.join(Config.OUTPUT_FOLDER, folder), exist_ok=True)
    
    print(f"✅ Created folder structure in {Config.OUTPUT_FOLDER}/")
    return Config.OUTPUT_FOLDER

# ==============================================================================
# 🎨 SEO-SAFE LAYOUT SWITCHING ENGINE
# ==============================================================================
def get_layout_style(page_type, page_name):
    """
    Forces a 3:1 ratio favoring Zigzag over Grid for better SEO and UX.
    Zigzag = 75% chance | Grid = 25% chance
    """
    cache_key = f"{page_type}_{page_name}"
    if cache_key in LAYOUT_STYLES_CACHE:
        return LAYOUT_STYLES_CACHE[cache_key]
    
    # 💎 THE 3:1 RATIO FIX:
    layout_pool = ['zigzag', 'zigzag', 'zigzag', 'grid']
    layout_type = random.choice(layout_pool)
    
    LAYOUT_STYLES_CACHE[cache_key] = layout_type
    return layout_type
# ==============================================================================
# 🖼️ IMAGE ENGINE - WITH CONTEXT-AWARE SERVICE DEMONSTRATIONS
# ==============================================================================
def is_important_page(page_name, page_type):
    """Determine if a page is important enough to use GPT for image generation."""
    important_pages = ['index', 'home', 'hero', 'logo', 'about', 'contact']
    important_services = ['plumbing', 'electrical', 'hvac', 'roofing', 'seo', 'marketing']
    
    page_lower = page_name.lower()
    
    # Check if it's a main page
    if any(imp in page_lower for imp in important_pages):
        return True
    
    # Check if it's an important service
    if any(service in page_lower for service in important_services):
        return True
    
    # Type-based importance
    if page_type in ['hero', 'logo']:
        return True
    
    return False

# ==============================================================================
# 🖼️ PERFECT UNIVERSAL IMAGE ENGINE V12 (PRO ENVIRONMENT SPLIT + VISION INSPECTOR)
# ==============================================================================
VISUAL_CONTEXT_CACHE = {}

def detect_business_context(industry, service_name="", context_mode="hero"):
    """UNIVERSAL VISUAL DIRECTOR: Uses AI to dynamically generate hyper-specific, relevant constraints."""
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

    if not CLIENTS.get('openai'): return fallback

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
        response = CLIENTS['openai'].chat.completions.create(
            model=Config.MODEL_LOW_TIER, 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"} ,
            max_completion_tokens=300
        )
        context = clean_json_response(response.choices[0].message.content)
        if context and "subject" in context:
            VISUAL_CONTEXT_CACHE[cache_key] = context
            return context
    except Exception as e:
        print(f"   ⚠️ Visual Context Generation Error: {e}")

    return fallback

def validate_image_content(image_url, service_name, context_dict):
    """THE VISION INSPECTOR: Uses GPT-4o Vision to literally count fingers and verify anatomy."""
    if not CLIENTS.get('openai'): return True 
    
    try:
        subject = context_dict.get('subject', 'professional')
        prompt = f"""You are a strict Quality Assurance Inspector for commercial photography. 
        Analyze this generated image for a '{service_name}' business. 
        
        CHECK ONLY FOR THESE FATAL ERRORS (ignore everything else):
        1. MISSING LIMBS: Clearly missing arms/legs, or amputee-like when they shouldn't be.
        2. FACELESS MONSTER: Face is melted, smeared, or distorted into a monster (a face turned away or partly cropped is FINE).
        3. SEVERE HAND MUTATION: Extra arms, three+ hands, fused/merged hands, or floating limbs.
        4. PHONE/TABLET: Holding or showing a glowing smartphone or tablet.
        
        IMPORTANT: Do NOT reject for missing uniforms, missing name patches, missing safety glasses,
        missing gloves, attire choices, or whether the person is "interacting" with equipment.
        Those are NOT errors. Only reject for the 4 fatal anatomy/object errors above.
        
        If ANY of those 4 fatal errors exist, reply EXACTLY with: INVALID - [Specific Reason].
        Otherwise reply EXACTLY with: VALID.
        """

        response = CLIENTS['openai'].chat.completions.create(
            model=Config.MODEL_LOW_TIER, 
            messages=[{
                "role": "user", 
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }],
            max_completion_tokens=50 
        )
        
        result = response.choices[0].message.content.strip().upper()
        if "INVALID" in result:
            print(f"   ❌ Vision Inspector Rejected: {result}")
            return False
            
        return True
    except Exception as e:
        return True 

def get_composition_and_culture(target_lang="en", context_mode="hero"):
    cultural = "modern Middle Eastern setting, Dubai/UAE professional attire" if target_lang == 'ar' else "modern, professional setting, diverse team, high quality"
    compositions = {
        "hero": "8k ultra HD, hyper-realistic, wide cinematic shot, shallow depth of field, professional lighting",
        "grid": "4k professional architectural photography, medium shot, clear flattering light",
        "zigzag": "8k cinematic quality, photorealistic, wide environmental shot, natural bright lighting"
    }
    return cultural, compositions.get(context_mode, compositions["hero"])


@retry_operation(max_retries=3)
def get_hosted_image(prompt_text, context_mode="hero", industry="General", is_category=False, service_name="", category_name="", target_lang="en"):
    """PERFECT IMAGE GENERATOR V12 - Natural Language Prompting for FLUX and DALL-E"""
    service_clean = clean_title(service_name or prompt_text)
    cache_key_base = service_name if service_name else prompt_text
    cache_key = f"{cache_key_base}_{industry}_{target_lang}_{Config.IMAGE_MODEL}_{context_mode}".lower()
    
    if cache_key in IMAGE_CACHE: return IMAGE_CACHE[cache_key]
    if is_category and cache_key_base in CATEGORY_IMAGE_CACHE: return CATEGORY_IMAGE_CACHE[cache_key_base]

    use_gpt = (Config.IMAGE_MODEL in ["gpt", "openai", "hybrid"])
    
    context = detect_business_context(industry, service_clean, context_mode) 
    cultural, comp = get_composition_and_culture(target_lang, context_mode)
    
    # Simple fallback for keywords if entities aren't imported perfectly yet
    img_keywords = f"professional {industry}"
    
    full_prompt = (
        f"A {comp} commercial photography shot. {cultural}. "
        f"The main focus is {context.get('subject', service_clean)}. "
        f"They are {context.get('action', 'standing naturally')} in {context.get('environment', 'a professional setting')}. "
        f"Framing: {context.get('framing', 'wide shot')}. Visual themes: {img_keywords}. "
        f"Extremely high quality, realistic lighting, pristine, no digital screens."
    )

    # --- NEW: ADD IMAGE MOOD FROM NICHE ---
    mood_suffix = getattr(Config, 'IMAGE_MOOD_SUFFIX', '')
    if mood_suffix:
        full_prompt = full_prompt.rstrip() + " " + mood_suffix
    # --------------------------------------
    
    final_image_url = None
    for attempt in range(Config.VISION_MAX_RETRIES):
        temp_image_url = None
        try:
            if use_gpt and CLIENTS.get('openai'):
                size = "1536x1024" if context_mode == "hero" else "1024x1024"
                response = CLIENTS['openai'].images.generate(
                    model="gpt-image-2",
                    prompt=full_prompt,
                    size=size,
                    quality="high" if context_mode == "hero" else "medium",
                    n=1,
                    output_format="png"
                )
                if response and response.data:
                    data_obj = response.data[0]
                    # gpt-image-2 returns b64_json by default
                    if hasattr(data_obj, 'b64_json') and data_obj.b64_json:
                        import tempfile
                        import base64
                        image_bytes = base64.b64decode(data_obj.b64_json)
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                        temp_file.write(image_bytes)
                        temp_file.close()
                        temp_image_url = temp_file.name
                    elif hasattr(data_obj, 'url') and data_obj.url:
                        temp_image_url = data_obj.url

            elif CLIENTS.get('replicate'):
                global LAST_REPLICATE_REQUEST
                elapsed = time.time() - LAST_REPLICATE_REQUEST
                if elapsed < Config.REPLICATE_REQUEST_DELAY: 
                    time.sleep(Config.REPLICATE_REQUEST_DELAY - elapsed)
                    
                aspect = "16:9" if context_mode == "hero" else "1:1"
                # 🔧 FIX: Cleanly executes FLUX run
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

            if temp_image_url:
                if context_mode == "hero":
                    if validate_image_content(temp_image_url, service_clean, context):
                        final_image_url = temp_image_url
                        break
                    else:
                        print(f"   🔁 Hero inspection failed (attempt {attempt+1}/{Config.VISION_MAX_RETRIES})")
                        full_prompt += " Ensure flawless photorealism, correct human anatomy, no devices."
                        # On the final attempt, accept the image anyway (fallback) instead of losing it
                        if attempt == Config.VISION_MAX_RETRIES - 1:
                            print(f"   ⚠️ Inspector exhausted — accepting last image as fallback.")
                            final_image_url = temp_image_url
                            break
                else:
                    final_image_url = temp_image_url
                    break
        except Exception as e:
            # 🔧 FIX: Catches all errors cleanly and moves to the next attempt
            print(f"   ⚠️ Image Generation Attempt Failed: {e}")
            pass

    if final_image_url and CLIENTS.get('cloudinary'):
        try:
            public_id = f"svc_{int(time.time())}_{random.randint(100,999)}"
            width = 1280 if context_mode == "hero" else 640
            res = cloudinary.uploader.upload(
                final_image_url, 
                folder="static_website/services", 
                public_id=public_id, 
                transformation=[
                    {"width": width, "crop": "limit"}, 
                    {"quality": "auto:good"}, 
                    {"fetch_format": "auto"}, 
                    {"dpr": "auto"}
                ]
            )
            final_image_url = res.get('secure_url', final_image_url)
        except Exception:
            final_image_url = None  
            
    if not final_image_url:
        fallback_list = ["https://images.unsplash.com/photo-1581578731548-c64695cc6952?auto=format&fit=crop&w=1200&q=80"]
        final_image_url = random.choice(fallback_list)

    IMAGE_CACHE[cache_key] = final_image_url
    if is_category: 
        CATEGORY_IMAGE_CACHE[cache_key_base] = final_image_url
        
    return final_image_url

# ==============================================================================
# 🏙️ UNIVERSAL HEADER SYSTEM - FINAL SAAS VERSION (4-COL MEGA MENU) WITH FULL RTL SUPPORT
# ==============================================================================
class UniversalHeader:
    """Generates a simplified universal header that won't conflict with styles.css - With full RTL support"""
    
    @staticmethod
    def generate_root_id():
        """Generate a unique root ID for the header."""
        return f"univ-header-{random.randint(10000, 99999)}"
    
    @staticmethod
    def get_translated_text(b_data, key, default):
        """Get translated text based on language setting."""
        ui = b_data.get('ui', {})
        return ui.get(key, default)
    
    @staticmethod
    def generate_contact_items(b_data):
        """Generate contact items for topbar with language support."""
        items = []
        ui = b_data.get('ui', {})
        
        # Email
        email = f"info@{b_data.get('domain', 'example.com')}"
        items.append({
            "icon": "fa-envelope",
            "text": email,
            "url": f"mailto:{email}"
        })
        
        # Phone
        phone = b_data.get('phone', '+1234567890')
        display_phone = phone
        if phone.startswith('+'):
            display_phone = phone
        items.append({
            "icon": "fa-phone-alt",
            "text": display_phone,
            "url": f"tel:{phone}"
        })
        
        # Location (if city exists)
        city = b_data.get('city', '')
        country = b_data.get('country', '')
        if city:
            location = f"{city}, {country}" if country else city
            items.append({
                "icon": "fa-map-marker-alt",
                "text": location[:30],
                "url": "#"
            })
        
        return items
    
    @staticmethod
    def generate_social_items(b_data):
        """Generate social media items."""
        items = []
        social_platforms = ['facebook', 'twitter', 'instagram', 'linkedin', 'youtube', 'pinterest']
        social_icons = {
            'facebook': 'fab fa-facebook-f',
            'twitter': 'fab fa-twitter',
            'instagram': 'fab fa-instagram',
            'linkedin': 'fab fa-linkedin-in',
            'youtube': 'fab fa-youtube',
            'pinterest': 'fab fa-pinterest-p'
        }
        
        for platform in social_platforms:
            url = b_data.get(platform, '')
            if url and url != '#':
                items.append({
                    "icon": social_icons.get(platform, f'fa-{platform}'),
                    "url": url
                })
        
        # Default items if none provided
        if not items:
            items = [
                {"icon": "fab fa-facebook-f", "url": "#"},
                {"icon": "fab fa-twitter", "url": "#"},
                {"icon": "fab fa-instagram", "url": "#"},
                {"icon": "fab fa-linkedin-in", "url": "#"}
            ]
        
        return items[:4]
    
    @staticmethod
    def generate_desktop_menu_items(b_data, structure, mode, hub_target_url=""):
        """Generate desktop menu items including Dynamic Locations and nested Contact."""
        items = []
        ui = b_data.get('ui', {})
        is_rtl = b_data.get('is_rtl', False)
        
        primary_color = b_data.get('primary', '#1A73E8').lstrip('#')
        accent_color = b_data.get('accent', '#F9AB00').lstrip('#')
        
        # 1. Home
        items.append({
            "type": "link", 
            "title": UniversalHeader.get_translated_text(b_data, 'home', 'Home'), 
            "url": validate_url("home", None, mode),
            "icon": "fa-home", 
            "has_dropdown": False
        })
        
        # 2. Services
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
                "title": UniversalHeader.get_translated_text(b_data, 'related_svc', 'Related Services'), 
                "links": [{
                    "title": shorten_menu_text(clean_title(svc), 3), 
                    "url": validate_url("service", svc, mode)
                } for svc in generate_sub_services(b_data, main)[:10]]
            }]
            items.append(services_item)
            
        elif mode == "2":
            if hub_target_url: 
                services_item["url"] = hub_target_url
            
            all_services = b_data.get('flat_services_list', [])
            num_services = len(all_services)
            
            if num_services > 0:
                # 🧮 ROUND-ROBIN DISTRIBUTION FOR MODE 2
                if num_services <= 5:
                    num_cols = 1
                elif num_services <= 10:
                    num_cols = 2
                elif num_services <= 15:
                    num_cols = 3
                else:
                    num_cols = 4
                    
                columns_data = [[] for _ in range(num_cols)]
                
                # Deal items evenly across columns
                for i, svc in enumerate(all_services):
                    col_index = i % num_cols
                    columns_data[col_index].append(svc)
                    
                services_item["dropdown_type"] = "mega" 
                
                for i, col_items in enumerate(columns_data):
                    if not col_items: continue
                    
                    # ULTIMATE FIX: Industry-Aware Column Titles for ANY Business
                    industry_name = clean_title(b_data.get('industry', 'Professional'))
                    
                    en_titles = [
                        "Our Core Services", 
                        "Specialized Solutions", 
                        f"Additional {industry_name} Services", 
                        "Explore More"
                    ]
                    
                    ar_titles = [
                        "خدماتنا الأساسية", 
                        "حلول متخصصة", 
                        f"خدمات {industry_name} إضافية", 
                        "استكشف المزيد"
                    ]
                    
                    titles_list = ar_titles if b_data.get('target_lang') == 'ar' else en_titles
                    fallback_title = titles_list[i] if i < len(titles_list) else f"More Services {i+1}"
                    
                    col_title = UniversalHeader.get_translated_text(b_data, f'col_{i}', fallback_title)
                    
                    services_item["columns"].append({
                        "title": col_title,
                        "links": [{
                            "title": shorten_menu_text(clean_title(svc), 3), 
                            "url": validate_url("service", svc, mode)
                        } for svc in col_items]
                    })
            items.append(services_item)
        elif mode == "3" and structure:
            # 🧮 5x2x5 DYNAMIC ROUND-ROBIN MEGA MENU LOGIC
            sorted_categories = sorted(
                structure.items(), 
                key=lambda item: len(item[1].get('children', [])) if isinstance(item[1], dict) else 0, 
                reverse=True
            )
            
            top_categories = sorted_categories[:10]
            num_cats = len(top_categories)
            
            if num_cats > 0:
                num_cols = min(num_cats, 5)
                columns_data = [[] for _ in range(num_cols)]
                
                for i, (category, data) in enumerate(top_categories):
                    col_index = i % num_cols
                    columns_data[col_index].append((category, data))
                
                grid_width = min(num_cols * 260, 1300)
                dropdown_position = "right: 0;" if is_rtl else "left: 0;"
                
                mega_html = f"""
                <div class="mega-menu-content" style="position:absolute; top:100%; {dropdown_position} margin: 0 auto; width: {grid_width}px; max-width: 90vw; background:white; box-shadow:0 10px 40px rgba(0,0,0,0.15); border-radius:12px; padding:30px; opacity:0; visibility:hidden; transition:0.3s; z-index:1000; border-top:3px solid #{accent_color}; display:grid; grid-template-columns:repeat({num_cols}, 1fr); gap:30px; text-align:{'right' if is_rtl else 'left'};">
                """
                
                for col_cats in columns_data:
                    mega_html += "<div>"
                    for category, data in col_cats:
                        if isinstance(data, dict):
                            sorted_children = sorted(data.get('children', []), key=len)[:5]
                            
                            if sorted_children:
                                cat_title = shorten_menu_text(clean_title(category), 3)
                                cat_url = validate_url("category", category, mode)
                                
                                mega_html += f'<a href="{cat_url}" style="display:block; color:#{primary_color}; font-size:0.95rem; font-weight:700; margin-bottom:12px; text-transform:uppercase; padding-bottom:5px; border-bottom:2px solid #{accent_color}; text-decoration:none;">{cat_title}</a>'
                                
                                for child in sorted_children:
                                    child_url = validate_url("service", child, mode)
                                    child_title = shorten_menu_text(clean_title(child), 3)
                                    padding_dir = 'paddingRight' if is_rtl else 'paddingLeft'
                                    
                                    mega_html += f'<a href="{child_url}" style="display:block; padding:5px 0; color:#64748b; font-size:0.85rem; text-decoration:none; transition:0.2s;" onmouseenter="this.style.color=\'#{primary_color}\'; this.style.{padding_dir}=\'5px\'" onmouseleave="this.style.color=\'#64748b\'; this.style.{padding_dir}=\'0\'">{child_title}</a>'
                                
                                mega_html += '<div style="margin-bottom: 20px;"></div>'
                    mega_html += "</div>"
                mega_html += "</div>"
                
                services_text = UniversalHeader.get_translated_text(b_data, 'services', 'Services')
                
                services_item = {
                    "type": "html_block",
                    "html": f"""
                    <div class="mega-menu-trigger" style="position:relative;">
                        <a href="{validate_url('services_index', None, mode)}" style="display:flex; align-items:center; gap:5px; color:#{primary_color}; font-weight:600; text-decoration:none; padding:8px 12px; font-size:15px;">
                            <i class="fas fa-tools" style="color:#{accent_color};"></i> {services_text} <i class="fas fa-chevron-down" style="font-size:11px;"></i>
                        </a>
                        {mega_html}
                    </div>
                    """
                }
            
            # 🛑 FIX APPLIED HERE: Indented 12 spaces to stay inside 'elif mode == "3"'
            items.append(services_item)
        
        # 3. CATEGORIES (replaces Locations — your business has one location, categories are more useful)
        if mode == "3" and structure:
            cat_links = [{
                "title": shorten_menu_text(clean_title(cat), 3),
                "url": validate_url("category", cat, mode)
            } for cat in list(structure.keys())[:10]]

            if cat_links:
                items.append({
                    "type": "dropdown",
                    "title": UniversalHeader.get_translated_text(b_data, 'categories', 'Categories'),
                    "url": validate_url("categories_index", None, mode),
                    "icon": "fa-th-large",
                    "has_dropdown": True,
                    "dropdown_type": "standard",
                    "columns": [{
                        "title": UniversalHeader.get_translated_text(b_data, 'explore_cat', 'Categories'),
                        "links": cat_links
                    }]
                })
        
        # 4. Blog — Mode 2 hub mein SKIP (hub existing site mein drop hota hai,
        # /blog parent site ka concern hai → yahan link = 404 risk)
        if mode != "2":
            items.append({
                "type": "link", 
                "title": UniversalHeader.get_translated_text(b_data, 'blog', 'Blog'), 
                "url": validate_url("blog", None, mode),
                "icon": "fa-newspaper", 
                "has_dropdown": False
            })

        # 5. Contact
        if mode == "2":
            # Hub mode: /pages/contact generate nahi hota — direct phone (zero 404)
            items.append({
                "type": "link",
                "title": UniversalHeader.get_translated_text(b_data, 'contact', 'Contact'),
                "url": f"tel:{b_data.get('phone', '')}",
                "icon": "fa-phone-alt",
                "has_dropdown": False
            })
        else:
            items.append({
                "type": "dropdown", 
                "title": UniversalHeader.get_translated_text(b_data, 'contact', 'Contact'), 
                "url": validate_url("contact", None, mode),
                "icon": "fa-phone-alt", 
                "has_dropdown": True, 
                "dropdown_type": "standard",
                "columns": [{
                    "title": UniversalHeader.get_translated_text(b_data, 'get_quote', 'Get in Touch'),
                    "links": [
                        {"title": UniversalHeader.get_translated_text(b_data, 'contact', 'Contact Us'), "url": validate_url("contact", None, mode)},
                        {"title": UniversalHeader.get_translated_text(b_data, 'about', 'About Us'), "url": validate_url("about", None, mode)}
                    ]
                }]
            })
        
        return items
    @staticmethod
    def generate_mobile_menu_items(b_data, structure, mode, hub_target_url=""):
        """Generate mobile menu items with Dynamic Locations placeholder - With RTL support."""
        items = []
        
        # Colors for the raw HTML block
        primary = b_data.get('primary', '#1A73E8')
        accent = b_data.get('accent', '#F9AB00')
        ui = b_data.get('ui', {})
        
        # Home
        items.append({
            "type": "standalone", 
            "title": UniversalHeader.get_translated_text(b_data, 'home', 'Home'), 
            "url": validate_url("home", None, mode), 
            "icon": "fa-home"
        })
        
        # Services Logic
        if mode == "3" and structure:
            # Sync mobile sorting with desktop (Top 10 max)
            sorted_categories = sorted(
                structure.items(), 
                key=lambda item: len(item[1].get('children', [])) if isinstance(item[1], dict) else 0, 
                reverse=True
            )[:10]
            
            for category, data in sorted_categories:
                if isinstance(data, dict) and data.get('children'):
                    # Limit to top 7 on mobile to prevent endless scrolling
                    sorted_children = sorted(data.get('children', []), key=len)[:7]
                    
                    if sorted_children:
                        items.append({
                            "type": "accordion", 
                            "title": shorten_menu_text(clean_title(category), 2), 
                            "icon": "fa-folder-open",
                            "url": validate_url("category", category, mode),
                            "links": [{
                                "title": shorten_menu_text(clean_title(child), 3), 
                                "url": validate_url("service", child, mode)
                            } for child in sorted_children]
                        })
        elif mode == "1":
            services = b_data.get('flat_services_list', [])
            if services:
                main = services[0]
                sub = generate_sub_services(b_data, main)
                items.append({
                    "type": "accordion", 
                    "title": shorten_menu_text(clean_title(main), 2), 
                    "icon": "fa-tools",
                    "url": validate_url("service", main, mode),
                    "links": [{
                        "title": shorten_menu_text(clean_title(svc), 3), 
                        "url": validate_url("service", svc, mode)
                    } for svc in [main] + sub[:15]]
                })
        # Explicit logic for Mode 2 to show MORE than 12 items
        elif mode == "2":
            services = b_data.get('flat_services_list', [])
            if services:
                items.append({
                    "type": "grid", 
                    "title": UniversalHeader.get_translated_text(b_data, 'services', 'Our Services'), 
                    "icon": "fa-tools",
                    "url": hub_target_url if hub_target_url else validate_url("services_index", None, mode),
                    "links": [{
                        "title": shorten_menu_text(clean_title(svc), 3), 
                        "url": validate_url("service", svc, mode)
                    } for svc in services[:30]]
                })
        
        # CATEGORIES INDEX LINK (replaces Locations accordion)
        if mode == "3" and structure:
            items.append({
                "type": "standalone",
                "title": UniversalHeader.get_translated_text(b_data, 'categories', 'Categories'),
                "url": validate_url("categories_index", None, mode),
                "icon": "fa-th-large"
            })

        # Contact & Blog — Mode 2 hub: contact = tel link, blog SKIP
        if mode == "2":
            items.append({
                "type": "standalone",
                "title": UniversalHeader.get_translated_text(b_data, 'contact', 'Contact'),
                "url": f"tel:{b_data.get('phone', '')}",
                "icon": "fa-phone-alt"
            })
        else:
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
    def generate_mobile_cta_buttons(b_data):
        """Generate mobile CTA buttons with translated text."""
        buttons = []
        ui = b_data.get('ui', {})
        
        # Call button
        buttons.append({
            "url": f"tel:{b_data.get('phone', '')}",
            "text": UniversalHeader.get_translated_text(b_data, 'call_now', 'Call Now'),
            "icon": "fas fa-phone-alt",
            "bg_color": "#2563eb"
        })
        
        # WhatsApp button - FIXED ICON
        whatsapp = b_data.get('whatsapp', '')
        if whatsapp:
            buttons.append({
                "url": f"https://wa.me/{whatsapp}",
                "text": UniversalHeader.get_translated_text(b_data, 'whatsapp', 'WhatsApp'),
                "icon": "fab fa-whatsapp",
                "bg_color": "#25D366"
            })
        
       # Quote button — Mode 2 mein contact page nahi hota → WhatsApp pe
        _q_mode = b_data.get('mode', '3')
        _q_url = (f"https://wa.me/{b_data.get('whatsapp', '')}"
                  if _q_mode == "2" else validate_url("contact", None, _q_mode))
        buttons.append({
            "url": _q_url,
            "text": UniversalHeader.get_translated_text(b_data, 'get_quote', 'Get Quote'),
            "icon": "fas fa-file-invoice-dollar",
            "bg_color": "#d4af37"
        })
        
        return buttons
    
    @staticmethod
    def render(b_data, structure=None, mode="3", hub_target_url=""):
        """Render simplified universal header that won't conflict with styles.css - With full RTL support"""
        
        root_id = UniversalHeader.generate_root_id()
        
        # Get RTL status
        is_rtl = b_data.get('is_rtl', False)
        ui = b_data.get('ui', {})
        
        # SIMPLIFIED CONFIG - MATCHES styles.css
        # 🆕 Pull font from niche engine if available
        _niche_obj  = b_data.get('niche_engine')
        _niche_font = _niche_obj.profile.get('font_primary', 'Outfit') if _niche_obj else 'Outfit'
        _safe_fonts = ['Outfit','Poppins','Inter','Merriweather',
                       'Playfair Display','Cormorant Garamond','Barlow Condensed']
        if _niche_font not in _safe_fonts:
            _niche_font = 'Outfit'
        _font_weight_str = f"{_niche_font}:wght@400;500;600;700"

        simple_config = {
            "ids": {
                "ROOT_ID": root_id,
                "HOME_URL": validate_url("home", None, mode)
            },
            "fonts": {
                "PRIMARY_FONT": _font_weight_str,
                "SECONDARY_FONT": _font_weight_str
            },
            "colors": {
                "PRIMARY_COLOR": b_data.get('primary', '#005B96').lstrip('#'),
                "ACCENT_COLOR": b_data.get('accent', '#F5A623').lstrip('#'),
                "SECONDARY_COLOR": "0f172a",
                "GRAY_LIGHT": "64748b",
                "MOBILE_BG": "f8fafc",
                "OVERLAY_COLOR": "rgba(15, 23, 42, 0.85)",
                "OVERLAY_BLUR": "4",
            },
            "sizing": {
                "LOGO_MAX_WIDTH": "180",
                "LOGO_MAX_HEIGHT": "60",
                "LOGO_MARGIN": "20",
                "HEADER_MIN_HEIGHT": "80",
                "MOBILE_LOGO_WIDTH": "150",
                "MOBILE_LOGO_MAX_HEIGHT": "50",
                "container": {
                    "CONTAINER_WIDTH": "95",
                    "MAX_CONTAINER_WIDTH": "1400",
                    "CONTAINER_PADDING": "20",
                }
            },
            "topbar": {
                "TOPBAR_ENABLED": "true",
                "TOPBAR_FONT_SIZE": "13",
                "TOPBAR_PADDING": "8",
                "CONTACT_GAP": "20",
                "SOCIAL_GAP": "15",
            },
            "menu": {
                "MENU_GAP": "20",
                "MENU_FONT_SIZE": "15",
                "MENU_FONT_WEIGHT": "600",
                "MENU_TEXT_TRANSFORM": "none",
                "MENU_LETTER_SPACING": "0",
                "MENU_LINK_PADDING_V": "8",
                "MENU_LINK_PADDING_H": "12",
            }
        }
        
        # Generate contact, social, logo, menu items
        contact_items = UniversalHeader.generate_contact_items(b_data)
        social_items = UniversalHeader.generate_social_items(b_data)
        
        # Build contact items HTML with classes for mobile control
        contact_items_html = ""
        for item in contact_items:
            # Add specific class to control visibility on mobile
            mobile_class = ""
            if "envelope" in item['icon']:
                mobile_class = "univ-email" # Keep visible
            elif "phone" in item['icon']:
                mobile_class = "univ-phone" # Hide on mobile
            elif "map" in item['icon']:
                mobile_class = "univ-location" # Hide on mobile
            
            # Adjust for RTL
            icon_margin = "margin-left:8px;" if is_rtl else "margin-right:8px;"
                
            contact_items_html += f"""
            <a href="{item['url']}" class="{mobile_class}" style="display:flex; align-items:center; gap:8px; color:#94a3b8; text-decoration:none; font-size:13px;">
                <i class="fas {item['icon']}" style="color:#{simple_config['colors']['ACCENT_COLOR']}; {icon_margin}"></i>
                <span>{item['text']}</span>
            </a>"""
        
        # Build social items HTML
        social_items_html = ""
        for i, item in enumerate(social_items):
            # Only show first 3 on mobile
            mobile_class = ""
            if i >= 3:
                mobile_class = "univ-social-hidden-mobile"
                
            social_items_html += f"""
            <a href="{item['url']}" class="{mobile_class}" style="color:#94a3b8; font-size:14px; text-decoration:none;" target="_blank" rel="noopener noreferrer">
                <i class="{item['icon']}"></i>
            </a>"""
        
        # Logo content (INSIDE def render)
        logo_url = b_data.get('logo_url', '')
        is_font_awesome = logo_url.startswith('fas ') or logo_url.startswith('fa-') or logo_url.startswith('fab ')
        
        if is_font_awesome:
            logo_content = f'<i class="{logo_url}" style="font-size:32px; color:#{simple_config["colors"]["ACCENT_COLOR"]};"></i>'
            logo_text = f'<span style="font-family:Outfit,sans-serif; font-size:1.3rem; font-weight:700; color:#{simple_config["colors"]["PRIMARY_COLOR"]};">{b_data.get("name", "")}</span>'
        elif logo_url:
            # 💎 OPTIMIZED LOGO: Cloudinary w_320 + f_auto + q_auto = ~15KB WebP
            # width/height attributes = zero layout shift (CLS fix)
            _logo_src = optimize_cloudinary(logo_url, 320)
            logo_content = f'<img src="{_logo_src}" alt="{b_data.get("name", "")} Logo" width="260" height="85" style="height:auto; width:100%; max-width:260px; max-height:85px; min-width:160px; object-fit:contain; display:block;">'
            logo_text = ""
        else:
            logo_content = ""
            logo_text = f'<span style="font-family:Outfit,sans-serif; font-size:1.3rem; font-weight:700; color:#{simple_config["colors"]["PRIMARY_COLOR"]};">{b_data.get("name", "")}</span>'
        # Generate desktop menu items
        desktop_items = UniversalHeader.generate_desktop_menu_items(b_data, structure, mode, hub_target_url)
        desktop_menu_html = ""
        
        # NEW DESKTOP LOOP (HANDLES HTML BLOCKS)
        for item in desktop_items:
            # CHECK FOR CUSTOM HTML BLOCK
            if item.get("type") == "html_block":
                desktop_menu_html += item["html"]
                continue

            if item["has_dropdown"] and item.get("columns"):
                # 💎 DYNAMIC MATH: Auto-detects columns
                col_count = len(item["columns"])
                if col_count == 0: col_count = 1
                grid_width = min(col_count * 260, 1300) # Max 1300px
                
                # 💎 PERFECT CENTERING MATH: Centers relative to the entire screen width
                dropdown_position = f"left: 0; right: 0; margin: 0 auto; width: {grid_width}px; max-width: 90vw;"
                
                desktop_menu_html += f"""
                <div class="mega-menu-trigger">
                    <a href="{item['url']}" style="display:flex; align-items:center; gap:5px; color:#{simple_config['colors']['PRIMARY_COLOR']}; font-weight:600; text-decoration:none; padding:8px 12px; font-size:15px;">
                        <i class="fas {item['icon']}" style="color:#{simple_config['colors']['ACCENT_COLOR']};"></i> {item['title']} <i class="fas fa-chevron-down" style="font-size:11px;"></i>
                    </a>
                    <div class="mega-menu-content" style="position:absolute; top:100%; {dropdown_position} background:white; box-shadow:0 10px 40px rgba(0,0,0,0.15); border-radius:12px; padding:30px; opacity:0; visibility:hidden; transition:0.3s; z-index:1000; border-top:3px solid #{simple_config['colors']['ACCENT_COLOR']}; display:grid; grid-template-columns:repeat({col_count}, 1fr); gap:30px; text-align:{'right' if is_rtl else 'left'};">
                        """
                for col in item["columns"]:
                    desktop_menu_html += f"""
                        <div>
                            <h4 style="color:#{simple_config['colors']['PRIMARY_COLOR']}; font-size:0.9rem; font-weight:700; margin-bottom:15px; text-transform:uppercase; padding-bottom:8px; border-bottom:2px solid #{simple_config['colors']['ACCENT_COLOR']};">{col['title']}</h4>"""
                    for link in col.get("links", [])[:10]: # Max 10 items
                        link_padding = "padding-right:5px;" if is_rtl else "padding-left:5px;"
                        desktop_menu_html += f"""
                            <a href="{link['url']}" style="display:block; padding:6px 0; color:#64748b; font-size:0.9rem; text-decoration:none; transition:0.2s;" onmouseenter="this.style.color='#{simple_config['colors']['PRIMARY_COLOR']}'; this.style.{'paddingRight' if is_rtl else 'paddingLeft'}='5px'" onmouseleave="this.style.color='#64748b'; this.style.{'paddingRight' if is_rtl else 'paddingLeft'}='0'">{link['title']}</a>"""
                    desktop_menu_html += "</div>"
                desktop_menu_html += "</div></div>"
            else:
                # Simple link
                desktop_menu_html += f"""
                <div class="mega-menu-trigger" style="position:relative;">
                    <a href="{item['url']}" style="display:flex; align-items:center; gap:5px; color:#{simple_config['colors']['PRIMARY_COLOR']}; font-weight:600; text-decoration:none; padding:8px 12px; font-size:15px;">
                        <i class="fas {item['icon']}" style="color:#{simple_config['colors']['ACCENT_COLOR']};"></i> {item['title']}
                    </a>
                </div>"""

        # Generate mobile menu items
        mobile_items = UniversalHeader.generate_mobile_menu_items(b_data, structure, mode, hub_target_url)
        mobile_menu_html = ""

        # NEW MOBILE LOOP (HANDLES HTML RAW)
        for item in mobile_items:
            # CHECK FOR CUSTOM HTML RAW
            if item.get("type") == "html_raw":
                mobile_menu_html += item["html"]
                continue

            if item["type"] in ["accordion", "grid"]:
                 mobile_menu_html += f"""
                <div class="univ-accordion-btn" style="border:1px solid #e2e8f0; border-radius:8px; overflow:hidden;">
                    <div class="univ-acc-head" onclick="toggleUnivAcc(this)" style="padding:15px; display:flex; justify-content:space-between; align-items:center; cursor:pointer; background:#f8fafc; font-weight:600; color:#{simple_config['colors']['PRIMARY_COLOR']};">
                        <div style="display:flex; align-items:center; gap:12px;">
                            <i class="fas {item['icon']}" style="color:#{simple_config['colors']['ACCENT_COLOR']};"></i>
                            <span>{item['title']}</span>
                        </div>
                        <i class="fas fa-chevron-down" style="color:#cbd5e1; transition:0.3s;"></i>
                    </div>
                    <div class="univ-acc-body" style="max-height:0; overflow:hidden; transition:0.3s; display:grid; grid-template-columns:repeat(2,1fr); gap:8px; padding:0 10px; text-align:{'right' if is_rtl else 'left'};">
                """
                 for link in item["links"][:8]:
                    mobile_menu_html += f"""
                        <a href="{link['url']}" style="display:block; padding:10px; border:1px solid #e2e8f0; border-radius:6px; text-align:center; color:#475569; font-size:0.9rem; text-decoration:none; background:white;">{link['title']}</a>"""
                 mobile_menu_html += "</div></div>"
            else:
                 mobile_menu_html += f"""
                <a href="{item['url']}" style="display:block; padding:15px; border:1px solid #e2e8f0; border-radius:8px; background:white; color:#{simple_config['colors']['PRIMARY_COLOR']}; font-weight:600; text-decoration:none; text-align:{'right' if is_rtl else 'left'};">
                    <i class="fas {item['icon']}" style="margin-right:12px; margin-left:12px; color:#{simple_config['colors']['ACCENT_COLOR']};"></i>
                    {item['title']}
                </a>"""
        
        # Generate mobile CTA buttons
        mobile_ctas = UniversalHeader.generate_mobile_cta_buttons(b_data)
        mobile_cta_html = ""
        
        for cta in mobile_ctas:
            mobile_cta_html += f"""
            <a href="{cta['url']}" style="display:block; padding:15px; background:{cta['bg_color']}; color:white; text-align:center; font-weight:600; text-decoration:none; border-radius:8px; margin-top:10px; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <i class="{cta['icon']}"></i> {cta['text']}
            </a>"""
        
        # Get translated text for the CTA button
        get_quote_text = UniversalHeader.get_translated_text(b_data, 'get_quote', 'Get Quote')
        # Mode 2: contact page exist nahi karta → CTA WhatsApp pe
        cta_url = (f"https://wa.me/{b_data.get('whatsapp', '')}"
                   if mode == "2" else validate_url('contact', None, mode))
        
        # Determine header layout direction
        header_direction = "rtl" if is_rtl else "ltr"
        
        # ===== SIMPLIFIED HTML - INLINE STYLES ONLY =====
        html = f"""<div id="{root_id}" style="width:100%; display:block; background:white; box-shadow:0 2px 10px rgba(0,0,0,0.05); font-family:'Outfit', sans-serif; direction: {header_direction};">
        
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
            
            <div style="background:#0f172a; color:#94a3b8; padding:8px 0; font-size:13px;">
                <div style="max-width:1400px; margin:0 auto; padding:0 20px; display:flex; justify-content:space-between; align-items:center;">
                    <div style="display:flex; gap:20px;">
                        {contact_items_html}
                    </div>
                    <div style="display:flex; gap:15px;">
                        {social_items_html}
                    </div>
                </div>
            </div>
            
            <header style="position: relative; display:flex; align-items:center; justify-content:space-between; max-width:1400px; margin:0 auto; padding:15px 20px; background:white;">
                <a href="{simple_config['ids']['HOME_URL']}" style="display:flex; align-items:center; gap:10px; text-decoration:none;">
                    {logo_content}
                    {logo_text}
                </a>
                
                <nav style="display:flex; align-items:center; gap:25px; margin: 0 auto;">
                    {desktop_menu_html}
                    
                    <a href="{cta_url}" 
                       style="background:linear-gradient(135deg, #{simple_config['colors']['ACCENT_COLOR']} 0%, #{simple_config['colors']['PRIMARY_COLOR']} 100%);
                              color:white; padding:12px 28px; border-radius:50px; font-weight:600; 
                              text-decoration:none; display:inline-flex; align-items:center; gap:8px;
                              box-shadow:0 4px 15px rgba(0,0,0,0.2); transition:all 0.3s ease;
                              border:none; font-size:0.95rem; cursor:pointer;">
                        <i class="fas fa-file-invoice-dollar"></i> {get_quote_text}
                    </a>
                </nav>
                
                <button id="{root_id}-mobile-toggle" 
                        style="display:none; background:none; border:none; font-size:24px; cursor:pointer; color:#{simple_config['colors']['PRIMARY_COLOR']}; padding:10px;">
                    <i class="fas fa-bars"></i>
                </button>
            </header>
            
            <div id="{root_id}-overlay" style="position:fixed; inset:0; background:rgba(15,23,42,0.85); backdrop-filter:blur(4px); z-index:100000; opacity:0; visibility:hidden; transition:0.3s;"></div>
            <div id="{root_id}-drawer" style="position:fixed; top:0; {'right' if is_rtl else 'right'}: -100%; width:85%; max-width:400px; height:100vh; background:white; z-index:100001; transition:0.4s cubic-bezier(0.19,1,0.22,1); box-shadow:{'-10px' if not is_rtl else '10px'} 0 30px rgba(0,0,0,0.1); overflow-y:auto; direction: {header_direction};">
                <div style="padding:25px; border-bottom:1px solid #e2e8f0; display:flex; justify-content:space-between; align-items:center; background:#f8fafc; position:sticky; top:0; z-index:10;">
                    <h3 style="font-size:1.2rem; color:#{simple_config['colors']['PRIMARY_COLOR']}; font-weight:700; margin:0;">{UniversalHeader.get_translated_text(b_data, 'menu', 'Menu')}</h3>
                    <button id="{root_id}-close-btn" style="background:none; border:none; font-size:28px; cursor:pointer; color:#{simple_config['colors']['PRIMARY_COLOR']};">&times;</button>
                </div>
                <div style="padding:25px 25px 150px;">
                    <div style="display:flex; flex-direction:column; gap:15px;">
                        {mobile_menu_html}
                        <div style="margin-top:20px; display:flex; flex-direction:column; gap:10px;">
                            {mobile_cta_html}
                        </div>
                    </div>
                </div>
            </div>
            
            <style>
                /* Dropdown hover styles */
                #{root_id} .mega-menu-content {{
                    opacity: 0;
                    visibility: hidden;
                    transition: opacity 0.2s, visibility 0.2s;
                }}
                #{root_id} .mega-menu-trigger:hover .mega-menu-content {{
                    opacity: 1 !important;
                    visibility: visible !important;
                }}
                
                /* Fix Dynamic Locations dropdown */
                #{root_id} div[style*="position:relative;"]:hover > div[style*="position:absolute; top:100%;"] {{
                    opacity: 1 !important;
                    visibility: visible !important;
                }}
                
                /* Mobile responsive */
                @media (max-width: 1150px) {{
                    #{root_id} nav {{
                        display: none !important;
                    }}
                    #{root_id} #{root_id}-mobile-toggle {{
                        display: block !important;
                    }}
                }}
                
                /* 💎 MOBILE LOGO SIZING FIX 💎 */
                @media (max-width: 768px) {{
                    #{root_id} header img {{
                        max-width: 180px !important;
                        min-width: 140px !important;
                        max-height: 60px !important;
                        object-fit: contain !important;
                    }}
                }}
                
                /* MOBILE TOP BAR FIXES - Email left, 3 social icons right */
                @media (max-width: 768px) {{
                    .univ-phone, .univ-location {{
                        display: none !important;
                    }}
                    .univ-social-hidden-mobile {{
                        display: none !important;
                    }}
                    /* Ensure the email is visible and has space */
                    .univ-email span {{
                        display: inline !important;
                    }}
                }}
                
                /* RTL Specific Mobile Fixes */
                @media (max-width: 768px) {{
                    [dir="rtl"] .univ-email i {{
                        margin-left: 8px;
                        margin-right: 0;
                    }}
                }}
                
                /* Accordion active state */
                #{root_id} .univ-accordion-btn.active .univ-acc-head {{
                    background: #{simple_config['colors']['PRIMARY_COLOR']} !important;
                    color: white !important;
                }}
                #{root_id} .univ-accordion-btn.active .univ-acc-head i {{
                    color: white !important;
                }}
                #{root_id} .univ-accordion-btn.active .univ-acc-head .fa-chevron-down {{
                    transform: rotate(180deg);
                }}
                #{root_id} .univ-accordion-btn.active .univ-acc-body {{
                    max-height: 500px !important;
                    padding: 10px !important;
                }}
                
                /* Fix for hidden dropdowns */
                #{root_id} div[style*="position:relative;"] {{
                    position: relative !important;
                }}
                
                /* RTL specific dropdown positioning */
                #{root_id}[dir="rtl"] div[style*="position:absolute; top:100%;"] {{
                    left: auto;
                    right: 0;
                }}
            </style>
            
            <script>
            (function() {{
                const root = document.getElementById('{root_id}');
                const trigger = root.querySelector('#{root_id}-mobile-toggle');
                const closeBtn = root.querySelector('#{root_id}-close-btn');
                const overlay = root.querySelector('#{root_id}-overlay');
                const drawer = root.querySelector('#{root_id}-drawer');
                const isRTL = {str(is_rtl).lower()};
                
                function openMenu() {{
                    document.body.classList.add('univ-mobile-active');
                    drawer.style.right = isRTL ? 'auto' : '0';
                    drawer.style.left = isRTL ? '0' : 'auto';
                    overlay.style.opacity = '1';
                    overlay.style.visibility = 'visible';
                    document.body.style.overflow = 'hidden';
                }}
                
                function closeMenu() {{
                    document.body.classList.remove('univ-mobile-active');
                    drawer.style.right = isRTL ? 'auto' : '-100%';
                    drawer.style.left = isRTL ? '-100%' : 'auto';
                    overlay.style.opacity = '0';
                    overlay.style.visibility = 'hidden';
                    document.body.style.overflow = '';
                }}
                
                if(trigger) trigger.addEventListener('click', openMenu);
                if(closeBtn) closeBtn.addEventListener('click', closeMenu);
                if(overlay) overlay.addEventListener('click', closeMenu);
                
                // Escape key
                document.addEventListener('keydown', function(e) {{
                    if (e.key === 'Escape' && document.body.classList.contains('univ-mobile-active')) {{
                        closeMenu();
                    }}
                }});
                
                // Window resize
                window.addEventListener('resize', function() {{
                    if (window.innerWidth > 1150 && document.body.classList.contains('univ-mobile-active')) {{
                        closeMenu();
                    }}
                }});
                
                // Accordion toggle
                window.toggleUnivAcc = function(head) {{
                    const btn = head.parentElement;
                    const body = btn.querySelector('.univ-acc-body');
                    btn.classList.toggle('active');
                    if(btn.classList.contains('active')) {{
                        body.style.maxHeight = body.scrollHeight + 'px';
                    }} else {{
                        body.style.maxHeight = null;
                    }}
                }};
                
                // Keep mobile accordions closed by default, ONLY open main services tab if it exists
                window.addEventListener('load', function() {{
                    const mainServiceIcon = root.querySelector('.univ-accordion-btn .fa-tools');
                    if(mainServiceIcon) {{
                        const head = mainServiceIcon.closest('.univ-acc-head');
                        if(head) {{
                            const btn = head.parentElement;
                            const body = btn.querySelector('.univ-acc-body');
                            btn.classList.add('active');
                            if(body) body.style.maxHeight = body.scrollHeight + 'px';
                        }}
                    }}
                    
                    // Add hover effects to CTA button
                    const cta = root.querySelector('a[href*="contact"]');
                    if(cta && cta.style.background.includes('linear-gradient')) {{
                        cta.addEventListener('mouseenter', function() {{
                            this.style.transform = 'translateY(-3px)';
                            this.style.boxShadow = '0 6px 20px rgba(0,0,0,0.25)';
                            this.style.filter = 'brightness(1.1)';
                        }});
                        cta.addEventListener('mouseleave', function() {{
                            this.style.transform = 'translateY(0)';
                            this.style.boxShadow = '0 4px 15px rgba(0,0,0,0.2)';
                            this.style.filter = 'brightness(1)';
                        }});
                    }}
                }});
            }})();
            </script>
        </div>"""
        if mode == "1":
            # ══════════════════════════════════════════════════════════════
            # 💎 MODE 1 PRO HEADER — Beautiful sticky anchor-link menu
            # Zero 404: har link ISI page ke section pe scroll karta hai.
            # Menu items b_data['_m1_anchors'] se aate hain (Claude ke
            # chosen sections ke mutabiq) — jo section nahi, wo menu mein nahi.
            # ══════════════════════════════════════════════════════════════
            anchors_present = b_data.get('_m1_anchors', ['services', 'faq', 'contact'])
            target_lang = b_data.get('target_lang', 'en')

            if target_lang == 'ar':
                m1_labels = {"services": "خدماتنا", "pricing": "الأسعار",
                             "reviews": "آراء العملاء", "faq": "الأسئلة الشائعة",
                             "contact": "اتصل بنا"}
                menu_word   = "القائمة"
                urgency_txt = "⚡ خدمة طوارئ 24/7 — استجابة سريعة"
            else:
                m1_labels = {"services": "Services", "pricing": "Pricing",
                             "reviews": "Reviews", "faq": "FAQ", "contact": "Contact"}
                menu_word   = "Menu"
                urgency_txt = "⚡ 24/7 Emergency Service — Fast Response"

            m1_icons = {"services": "fa-tools", "pricing": "fa-tags",
                        "reviews": "fa-star", "faq": "fa-question-circle",
                        "contact": "fa-phone-alt"}

            menu_order = [k for k in ["services", "pricing", "reviews", "faq", "contact"]
                          if k in anchors_present]
            if "contact" not in menu_order:
                menu_order.append("contact")

            _pc = simple_config['colors']['PRIMARY_COLOR']
            _ac = simple_config['colors']['ACCENT_COLOR']

            desktop_nav = ""
            drawer_nav  = ""
            for key in menu_order:
                desktop_nav += f'''
                <a href="#{key}" class="m1-nav-link" style="color:#{_pc}; font-weight:600; text-decoration:none; padding:8px 10px; font-size:15px; display:inline-flex; align-items:center; gap:6px; border-radius:8px; transition:background 0.2s;">
                    <i class="fas {m1_icons[key]}" style="color:#{_ac}; font-size:13px;"></i> {m1_labels[key]}
                </a>'''
                drawer_nav += f'''
                <a href="#{key}" class="m1-drawer-link" style="display:flex; align-items:center; gap:12px; padding:15px; border:1px solid #e2e8f0; border-radius:10px; background:white; color:#{_pc}; font-weight:600; text-decoration:none;">
                    <i class="fas {m1_icons[key]}" style="color:#{_ac};"></i> {m1_labels[key]}
                </a>'''

            funnel_header_html = f"""
<div id="{root_id}-funnel" style="width:100%; font-family:'Outfit',sans-serif; position:sticky; top:0; z-index:9999; direction:{header_direction};">

    <!-- Top urgency strip -->
    <div style="background:#0C2340; color:#E8F4FD; padding:7px 20px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; border-bottom:2px solid #1D9E75;">
        <div style="display:flex; align-items:center; gap:8px;">
            <span style="width:8px; height:8px; border-radius:50%; background:#5DCAA5; display:inline-block; animation:upulse 2s infinite;"></span>
            <span style="font-size:12px; font-weight:600;">{urgency_txt}</span>
        </div>
        <div style="display:flex; gap:8px;">
            <a href="tel:{b_data.get('phone','')}" style="background:#1D9E75; color:#E1F5EE; padding:5px 14px; border-radius:20px; font-size:11px; font-weight:700; text-decoration:none; white-space:nowrap;">📞 {b_data.get('phone','')}</a>
            <a href="https://wa.me/{b_data.get('whatsapp','')}" target="_blank" style="background:#25D366; color:white; padding:5px 14px; border-radius:20px; font-size:11px; font-weight:700; text-decoration:none; white-space:nowrap;">💬 WhatsApp</a>
        </div>
    </div>

    <!-- Main header row with MENU -->
    <div style="background:white; box-shadow:0 2px 10px rgba(0,0,0,0.08);">
        <div style="max-width:1200px; margin:0 auto; padding:10px 20px; display:flex; justify-content:space-between; align-items:center; gap:16px;">
            <a href="#top" style="display:flex; align-items:center; gap:10px; text-decoration:none; flex-shrink:0;">
                {logo_content}
                {logo_text}
            </a>

            <nav class="m1-desktop-nav" style="display:flex; align-items:center; gap:4px;">
                {desktop_nav}
                <a href="#contact" style="margin-{'right' if is_rtl else 'left'}:10px; display:inline-flex; align-items:center; gap:7px; background:linear-gradient(135deg, #{_ac} 0%, #{_pc} 100%); color:white; padding:11px 24px; border-radius:50px; font-weight:700; text-decoration:none; font-size:0.9rem; box-shadow:0 4px 12px rgba(0,0,0,0.2);">
                    <i class="fas fa-file-invoice-dollar"></i> {get_quote_text}
                </a>
            </nav>

            <div style="display:flex; gap:8px; align-items:center;">
                <a href="tel:{b_data.get('phone','')}" class="m1-phone-pill" style="display:inline-flex; align-items:center; gap:7px; background:#{_pc}; color:white; padding:10px 18px; border-radius:50px; font-weight:700; text-decoration:none; font-size:0.85rem; box-shadow:0 4px 12px rgba(0,0,0,0.2);">
                    <i class="fas fa-phone-alt"></i><span class="funnel-phone-text">{b_data.get('phone','')}</span>
                </a>
                <button id="{root_id}-m1-toggle" style="display:none; background:none; border:none; font-size:24px; cursor:pointer; color:#{_pc}; padding:8px;">
                    <i class="fas fa-bars"></i>
                </button>
            </div>
        </div>
    </div>

    <!-- Mobile drawer -->
    <div id="{root_id}-m1-overlay" style="position:fixed; inset:0; background:rgba(15,23,42,0.85); backdrop-filter:blur(4px); z-index:100000; opacity:0; visibility:hidden; transition:0.3s;"></div>
    <div id="{root_id}-m1-drawer" style="position:fixed; top:0; right:-100%; width:85%; max-width:380px; height:100vh; background:#f8fafc; z-index:100001; transition:0.4s cubic-bezier(0.19,1,0.22,1); box-shadow:-10px 0 30px rgba(0,0,0,0.1); overflow-y:auto; direction:{header_direction};">
        <div style="padding:22px; border-bottom:1px solid #e2e8f0; display:flex; justify-content:space-between; align-items:center; background:white; position:sticky; top:0;">
            <h3 style="font-size:1.15rem; color:#{_pc}; font-weight:700; margin:0;">{menu_word}</h3>
            <button id="{root_id}-m1-close" style="background:none; border:none; font-size:28px; cursor:pointer; color:#{_pc};">&times;</button>
        </div>
        <div style="padding:22px; display:flex; flex-direction:column; gap:12px;">
            {drawer_nav}
            <a href="tel:{b_data.get('phone','')}" style="display:block; padding:15px; background:#{_pc}; color:white; text-align:center; font-weight:700; text-decoration:none; border-radius:10px; margin-top:8px;">
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
#{root_id}-funnel .m1-nav-link:hover {{ background:#f1f5f9; }}
@media (max-width:991px) {{
    #{root_id}-funnel .m1-desktop-nav {{ display:none !important; }}
    #{root_id}-funnel #{root_id}-m1-toggle {{ display:block !important; }}
}}
@media (max-width:600px) {{
    #{root_id}-funnel .funnel-phone-text {{ display:none !important; }}
}}
@keyframes upulse{{
    0%{{box-shadow:0 0 0 0 rgba(93,202,165,.7)}}
    70%{{box-shadow:0 0 0 8px rgba(93,202,165,0)}}
    100%{{box-shadow:0 0 0 0 rgba(93,202,165,0)}}
}}
</style>

<script>
(function() {{
    var toggle  = document.getElementById('{root_id}-m1-toggle');
    var drawer  = document.getElementById('{root_id}-m1-drawer');
    var overlay = document.getElementById('{root_id}-m1-overlay');
    var closeB  = document.getElementById('{root_id}-m1-close');
    function openM()  {{ drawer.style.right='0'; overlay.style.opacity='1'; overlay.style.visibility='visible'; document.body.style.overflow='hidden'; }}
    function closeM() {{ drawer.style.right='-100%'; overlay.style.opacity='0'; overlay.style.visibility='hidden'; document.body.style.overflow=''; }}
    if(toggle)  toggle.addEventListener('click', openM);
    if(closeB)  closeB.addEventListener('click', closeM);
    if(overlay) overlay.addEventListener('click', closeM);
    if(drawer)  drawer.querySelectorAll('a[href^="#"]').forEach(function(a) {{ a.addEventListener('click', closeM); }});
}})();
</script>
"""
            return funnel_header_html

        return html
        
        
# 🧠 DYNAMIC STRUCTURE ENGINE
# ==============================================================================
@retry_operation(max_retries=3)
def analyze_structure_with_ai(raw_input, mode="urls", target_lang="en"):
    """Analyze input and create service hierarchy using AI - OPTIMIZED FOR MASSIVE LISTS."""
    fallback = {
        "General Services": {
            "description": "Comprehensive general services for all needs",
            "children": ["Service 1", "Service 2", "Service 3"]
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
    
    unique_lines = list(set(cleaned_lines))
    cleaned_input = "\n".join(unique_lines)
    
    print(f"   ℹ️  Processing {len(unique_lines)} unique items...")

    system_prompt = "You are a Website Information Architect. Output must be valid JSON."
    
    lang_instruction = "Arabic (Use native Arabic script)" if target_lang == 'ar' else "English"
    
    prompt = f"""
    Organize this service list into a logical hierarchy.
    
    INPUT DATA: 
    {cleaned_input}
    
    RULES:
    1. Group into EXACTLY 6 to 8 Logical Parent Categories based on the industry.
    2. URL CRITICAL: The 'Category Name' (the JSON Key) MUST ALWAYS be written in ENGLISH. Do not translate the category name.
    3. TRANSLATION: For each category, provide a brief 1-sentence description written in {lang_instruction}.
    4. Place EVERY SINGLE input item into the 'children' array of its most relevant category.
    5. CRITICAL: You MUST categorize and include EVERY SINGLE service from the INPUT list.
    
    RETURN JSON ONLY with this exact structure:
    {{
        "English Category Name": {{
            "description": "Brief category description in {lang_instruction}",
            "children": ["Service 1", "Service 2", "Service 3"]
        }}
    }}
    """

    try:
        response = CLIENTS['openai'].chat.completions.create(
            model=Config.MODEL_HIGH_TIER,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"} 
        )
        
        structure = clean_json_response(response.choices[0].message.content)
        
        if structure:
            # 🔥 THE SAFETY NET: Catch Lazy AI Dropping Items! 🔥
            flat_ai = []
            for k, v in structure.items():
                if isinstance(v, dict) and 'children' in v:
                    flat_ai.extend(v['children'])
                elif isinstance(v, list):
                    flat_ai.extend(v)
            
            original_items_lower = {s.lower(): s for s in unique_lines}
            ai_items_lower = [s.lower() for s in flat_ai]
            missing_items = [original_items_lower[key] for key in original_items_lower if key not in ai_items_lower]
            
            if missing_items:
                print(f"   ⚠️ AI got lazy and dropped {len(missing_items)} items. Python is forcing them back in...")
                
                categories = list(structure.keys())
                if not categories:
                    cat_name = "General Services"
                    cat_desc = "خدمات شاملة" if target_lang == 'ar' else "Comprehensive services"
                    categories = [cat_name]
                    structure[cat_name] = {"description": cat_desc, "children": []}
                
                for i, missing_item in enumerate(missing_items):
                    cat = categories[i % len(categories)]
                    if isinstance(structure[cat], dict):
                        if 'children' not in structure[cat]:
                            structure[cat]['children'] = []
                        structure[cat]['children'].append(missing_item)
            
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

def extract_keyword_tiers(b_data, service_name, industry, location, target_lang="en"):
    """3-tier SEO keywords — Claude-powered, real search-intent based. Cached per service."""
    cache_key = f"keyword_tiers_{service_name}_{industry}_{location}_{target_lang}"
    if cache_key in Config.ENTITY_CACHE: return Config.ENTITY_CACHE[cache_key]

    current_year = datetime.now().year
    fallback = {
        "high_intent": [f"{service_name} {location}".lower(), f"best {service_name} {location}".lower(),
                        f"emergency {service_name} near me".lower()],
        "semantic": [f"{service_name} cost", f"professional {service_name} service",
                     f"{service_name} maintenance"],
        "local_time": [f"{service_name} {location} {current_year}".lower(),
                       f"24/7 {service_name} {location}".lower()]
    }

    lang_name = "Arabic (native script)" if target_lang == 'ar' else "English"
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
                model=Config.MODEL_LOW_TIER,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"})
            content = clean_json_response(response.choices[0].message.content)
            if content and content.get('high_intent'):
                Config.ENTITY_CACHE[cache_key] = content
                return content
        except Exception:
            pass

    Config.ENTITY_CACHE[cache_key] = fallback
    return fallback
# ==============================================================================
# 🧠 ENHANCED SCHEMA GENERATOR WITH ENTITIES AND KEYWORDS
# ==============================================================================
def get_related_entities(service_name, industry, location, target_lang="en"):
    """Get related entities and keywords for enhanced SEO with Multi-Language Support."""
    cache_key = f"entities_{service_name}_{industry}_{location}_{target_lang}"
    
    if cache_key in Config.ENTITY_CACHE:
        return Config.ENTITY_CACHE[cache_key]
    
    lang_instruction = "Arabic (RTL)" if target_lang == 'ar' else "English"
    
    if target_lang == 'ar':
        fallback = {
            "keywords": [f"{service_name} {location}", f"افضل {service_name}", f"خدمات {service_name} احترافية"],
            "entities": [f"خبراء {service_name}", f"متخصصون في {service_name}"],
            "related_terms": [f"{service_name} بالقرب مني", f"{service_name} بأسعار مناسبة"]
        }
    else:
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
        TARGET LANGUAGE: {lang_instruction}
        
        Return JSON with:
        1. keywords: 8-10 specific long-tail keywords in the TARGET LANGUAGE
        2. entities: 5-7 related business entities in the TARGET LANGUAGE
        3. related_terms: 5-7 common search phrases customers use in the TARGET LANGUAGE
        
        Format:
        {{
            "keywords": ["keyword1", "keyword2", ...],
            "entities": ["entity1", "entity2", ...],
            "related_terms": ["term1", "term2", ...]
        }}
        """
        
        response = CLIENTS['openai'].chat.completions.create(
            model=Config.MODEL_LOW_TIER,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} 
        )
        
        content = clean_json_response(response.choices[0].message.content)
        if content:
            Config.ENTITY_CACHE[cache_key] = content
            return content
    except Exception as e:
        print(f"   ⚠️ Entity generation error: {e}")
    
    Config.ENTITY_CACHE[cache_key] = fallback
    return fallback

# ==============================================================================
# 🔑 KEYWORD EXTRACTION FOR SCHEMA SYNC - SEO OPTIMIZATION
# ==============================================================================
def extract_top_keywords_from_schema(b_data, service_name, industry, location):
    """Extract top 3 keywords from schema entities for SEO synchronization."""
    try:
        # Get related entities which contain keywords
        entities = get_related_entities(
            service_name, 
            industry, 
            location, 
            b_data.get('target_lang', 'en')
        )
        
        # Extract keywords list
        keywords_list = entities.get("keywords", [])
        
        # If we have keywords, return top 3
        if keywords_list and len(keywords_list) >= 3:
            return keywords_list[:3]
        elif keywords_list:
            # Pad with service name if less than 3
            top_kw = keywords_list.copy()
            while len(top_kw) < 3:
                top_kw.append(service_name)
            return top_kw
        else:
            # Fallback keywords
            return [service_name, industry, location]
            
    except Exception as e:
        print(f"   ⚠️ Keyword extraction error: {e}")
        return [service_name, industry, location]

# ==============================================================================
# 📍 DYNAMIC SEO DATA GENERATOR - WITH KEYWORD SYNC
# ==============================================================================
def get_dynamic_seo_data(service_name, city, state, country, industry, target_lang="en"):
    """Get dynamic SEO data including neighborhoods and keywords - With full language support."""
    neighborhoods = []
    location_string = f"{city}, {state}, {country}".strip(', ')
    
    if CLIENTS['openai']:
        try:
            print(f"   📍 Fetching Neighborhoods for {location_string}...")
            
            lang_instruction = "Arabic" if target_lang == 'ar' else "English"
            hood_prompt = f"""List 6-8 popular neighborhoods, districts, or areas in {location_string}. 
            Focus on residential and commercial areas. ALL VALUES MUST BE IN {lang_instruction}.
            Return JSON: {{"neighborhoods": ["Area 1", "Area 2"]}}"""
            
            response = CLIENTS['openai'].chat.completions.create(
                model=Config.MODEL_LOW_TIER,
                messages=[{"role": "user", "content": hood_prompt}],
                response_format={"type": "json_object"} 
            )
            data = clean_json_response(response.choices[0].message.content)
            if isinstance(data, dict) and 'neighborhoods' in data:
                neighborhoods = data['neighborhoods']
        except Exception as e:
            print(f"   ⚠️ Neighborhood API Error: {e}")

    if not neighborhoods or len(neighborhoods) < 3:
        if target_lang == 'ar':
            neighborhoods = [f"وسط {city}", f"شمال {city}", f"جنوب {city}", f"المنطقة التجارية في {city}"] if city else [f"المدن الرئيسية في {country}"]
        else:
            if city:
                neighborhoods = [f"Central {city}", f"North {city}", f"South {city}", f"{city} Business District"]
            elif state:
                neighborhoods = [f"Central {state}", f"Northern {state}", f"Southern {state}"]
            else:
                neighborhoods = [f"Major Cities in {country}", f"Regional Hubs in {country}"]

    # Pass the target language to the entities function
    entities = get_related_entities(service_name, industry, location_string, target_lang)
    
    keywords = entities.get("keywords", [])
    if not keywords:
        if target_lang == 'ar':
            keywords = [f"{clean_title(service_name)} في {location_string}", f"افضل {clean_title(service_name)} {location_string}"]
        else:
            keywords = [
                f"{clean_title(service_name)} in {location_string}",
                f"Best {clean_title(service_name)} {location_string}",
                f"Professional {clean_title(service_name)} services",
                f"Affordable {clean_title(service_name)} near me",
                f"Top Rated {clean_title(service_name)} {city if city else country}"
            ]
    
    return neighborhoods[:8], keywords, entities

# ==============================================================================
# 🏷️ SCHEMA TYPE DETECTOR
# ==============================================================================
import re

def get_schema_type(industry):
    """Get appropriate Schema.org types using strict word boundaries to prevent substring errors."""
    if not industry:
        return ["LocalBusiness", "Organization"]
    
    ind = industry.lower()
    
    # \b ensures we only match whole words or specific prefixes. 
    # No more "auto" in "automation" or "law" in "lawn"
    mapping = {
        r'\bplumb': ['Plumber', 'HomeAndConstructionBusiness'],
        r'\belectric': ['Electrician', 'HomeAndConstructionBusiness'],
        r'\bdentist': ['Dentist', 'MedicalOrganization'],
        r'\blaw\b': ['Attorney', 'LegalService'], 
        r'\blawyer': ['Attorney', 'LegalService'],
        r'\battorney': ['Attorney', 'LegalService'],
        r'\bhvac\b': ['HVACBusiness', 'HomeAndConstructionBusiness'],
        r'\broof': ['RoofingContractor', 'HomeAndConstructionBusiness'],
        r'\bpaint': ['HousePainter', 'HomeAndConstructionBusiness'],
        r'\bclean': ['CleaningService', 'HomeAndConstructionBusiness'],
        r'\blocksmith': ['Locksmith', 'HomeAndConstructionBusiness'],
        r'\bmedic': ['MedicalClinic', 'MedicalOrganization'],
        r'\bdoctor': ['Physician', 'MedicalOrganization'],
        r'\bauto\b': ['AutoRepair', 'AutomotiveBusiness'],
        r'\bmechanic': ['AutoRepair', 'AutomotiveBusiness'],
        r'\bcar\b': ['AutoRepair', 'AutomotiveBusiness'],
        r'\bseo\b': ['ProfessionalService', 'LocalBusiness'],
        r'\bmarket': ['ProfessionalService', 'LocalBusiness'],
        r'\bdigital': ['ProfessionalService', 'LocalBusiness'],
        r'\bweb\b': ['WebDesignAgency', 'Organization'],
        r'\bconsult': ['ConsultingAgency', 'Organization'],
        r'\bsoftware': ['SoftwareCompany', 'Organization'],
        r'\bhealth': ['HealthClub', 'SportsActivityLocation'],
        r'\bfitness': ['ExerciseGym', 'SportsActivityLocation'],
        r'\bgym\b': ['ExerciseGym', 'SportsActivityLocation'],
        r'\bbeauty': ['BeautySalon', 'HealthAndBeautyBusiness'],
        r'\bsalon': ['BeautySalon', 'HealthAndBeautyBusiness'],
        r'\bspa\b': ['HealthAndBeautyBusiness', 'BeautySalon'],
        r'\bconstruct': ['HomeAndConstructionBusiness', 'ConstructionCompany'],
        r'\bhome\b': ['HomeAndConstructionBusiness', 'LocalBusiness']
    }
    
    for pattern, schema_types in mapping.items():
        if re.search(pattern, ind):
            return schema_types
            
    return ["LocalBusiness", "Organization"]
# ==============================================================================
# 🧠 ENHANCED SCHEMA GENERATOR - WITH KEYWORD SYNC & ABSOLUTE URL FIX
# ==============================================================================
def generate_hierarchical_schema(b_data, p_data, service_name, page_url, parent_category=None, is_child_page=False, parent_url=None):
    """Generate complete Schema.org markup with hierarchy, entities, and keywords - With absolute CLEAN URLs."""
    try:
        # 🔧 FIX: Guarantee an absolute base URL even if Config.SITE_URL is empty
        base_url = Config.SITE_URL.rstrip('/')
        if not base_url or not base_url.startswith('http'):
            domain = b_data.get('domain', 'yourdomain.com')
            base_url = f"https://{domain}"

        # 🟢 THE FIX: Grab the language prefix (e.g., '/en')
        lang_prefix = ""
        lang_mode = b_data.get('lang_mode', 'no')
        if lang_mode != "no":
            lang_prefix = f"/{lang_mode}"

        # 🟢 THE FIX: Create a base URL that includes the language for page-specific schema
        lang_base_url = f"{base_url}{lang_prefix}"
            
        # 🔧 FIX: Ensure page_url is absolute, has lang, and matches canonical exactly
        if not page_url.startswith('http'):
            # Strip any duplicate lang prefix before rebuilding
            _stripped = page_url
            if lang_prefix and _stripped.startswith(lang_prefix):
                _stripped = _stripped[len(lang_prefix):]
            _stripped = _stripped.lstrip('/')
            # Strip .html to match Netlify clean URLs
            if _stripped.endswith('index.html'):
                _stripped = _stripped[:-10]
            elif _stripped.endswith('.html'):
                _stripped = _stripped[:-5]
            _stripped = _stripped.rstrip('/')
            page_url = f"{lang_base_url}/{_stripped}" if _stripped else f"{lang_base_url}/"
            
        # 🟢 THE FIX: Strip .html for Schema to match canonical and sitemap
        if page_url.endswith('index.html'):
            page_url = page_url.replace('index.html', '')
        elif page_url.endswith('.html'):
            page_url = page_url[:-5]
        # FIX: Home page root must keep trailing slash
        # rstrip('/') on "https://domain.com/" gives "https://domain.com" — mismatch with canonical
        if page_url.rstrip('/') == lang_base_url:
            page_url = lang_base_url + "/"  # restore trailing slash for root only
        else:
            page_url = page_url.rstrip('/')
        if not page_url:
            page_url = lang_base_url + "/"
            
        # 🔧 FIX: Ensure parent_url is absolute if provided AND clean
        if parent_url:
            if not parent_url.startswith('http'):
                clean_parent_url = parent_url.replace(lang_prefix, "", 1).lstrip('/')
                parent_url = f"{lang_base_url}/{clean_parent_url}"
            if parent_url.endswith('index.html'):
                parent_url = parent_url.replace('index.html', '')
            elif parent_url.endswith('.html'):
                parent_url = parent_url[:-5]
            parent_url = parent_url.rstrip('/')

        display_service_name = clean_title(service_name)
        schema_types = get_schema_type(b_data.get('industry', ''))
        primary_type = schema_types[0] if len(schema_types) > 0 else "LocalBusiness"
        secondary_type = schema_types[1] if len(schema_types) > 1 else "Organization"
        
        location_str = b_data.get('city') if b_data.get('city') else b_data.get('country')
        target_lang = b_data.get('target_lang', 'en')
        
        # 💎 SEO FIX: Extract 3-Tier Keywords for Schema
        keyword_tiers = extract_keyword_tiers(b_data, display_service_name, b_data.get('industry', ''), location_str, target_lang)
        high_intent = keyword_tiers.get('high_intent', [])
        semantic = keyword_tiers.get('semantic', [])
        local_time = keyword_tiers.get('local_time', [])
        
        # Combine them all for maximum Schema context
        all_schema_keywords = high_intent + semantic + local_time
        keywords = ", ".join(all_schema_keywords[:10]) if all_schema_keywords else display_service_name
        review_objects = []
        if p_data and 'reviews' in p_data and isinstance(p_data['reviews'], list):
            for r in p_data['reviews'][:3]:
                if isinstance(r, dict):
                    # 💎 FIX: Safely extract floats even if AI returns "5/5" or string text
                    try:
                        match = re.search(r'\d+(\.\d+)?', str(r.get('rating', '5')))
                        r_val = float(match.group()) if match else 5.0
                    except Exception:
                        r_val = 5.0
                        
                    review_objects.append({
                        "@type": "Review",
                        # 💎 FIX: Required by GSC to prevent "Missing itemReviewed" warning
                        "itemReviewed": {
                            "@type": primary_type,
                            "name": b_data.get('name', display_service_name)
                        },
                        "author": {"@type": "Person", "name": r.get('name', 'Satisfied Customer')},
                        "reviewRating": {"@type": "Rating", "ratingValue": r_val, "bestRating": 5},
                        "reviewBody": r.get('txt', 'Excellent service!')[:100],
                        "datePublished": datetime.now().strftime("%Y-%m-%d")
                    })

        image_url = p_data.get('image_url', p_data.get('hero_image', '')) if p_data else ""

        service_areas = []
        if p_data and 'areas_served' in p_data:
            for area in p_data['areas_served'][:5]:
                service_areas.append({"@type": "City", "name": area})

        schema_graph = []
        
        # Organization
        schema_graph.append({
            "@type": secondary_type,
            "@id": f"{base_url}/#organization",
            "name": b_data.get('name', ''),
            "url": f"{base_url}/",
            "logo": b_data.get('logo_url', image_url or ""),
            "description": f"Professional {b_data.get('industry', '')} services in {location_str}",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": b_data.get('city', ''),
                # CRITICAL SCHEMA FIX: Region cannot be a city. Fall back to state or blank.
                "addressRegion": b_data.get('state', ''),
                "addressCountry": b_data.get('country', '')
            },
            "contactPoint": {
                "@type": "ContactPoint",
                "telephone": b_data.get('phone', ''),
                "contactType": "customer service",
                "areaServed": location_str
            }
        })
        
        # LocalBusiness
        local_biz = {
            "@type": primary_type,
            "@id": f"{page_url}/#localbusiness",
            "name": b_data.get('name', ''),
            "description": p_data.get('meta_description', f"Professional {display_service_name} services"),
            "url": f"{base_url}/",
            "telephone": b_data.get('phone', ''),
            "priceRange": "$$",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": b_data.get('city', ''),
                # Use state if provided, otherwise leave blank to prevent invalid city duplicates
                "addressRegion": b_data.get('state', '') if b_data.get('state') else b_data.get('country', ''),
                "addressCountry": b_data.get('country', '')
            },
            "areaServed": service_areas,
            "keywords": keywords
        }
        if image_url:
            local_biz["image"] = image_url
        # 💎 GOOGLE POLICY: self-serving review/aggregateRating REMOVED (manual action risk).
        # Reviews page par visible rehte hain — sirf schema se hataya gaya.
        # 💎 ENTITY BOOST: sameAs + opening hours + service catalog
        _socials = [b_data.get(k, '') for k in ['facebook', 'twitter', 'instagram', 'linkedin', 'youtube']]
        _socials = [s for s in _socials if s and s != '#' and len(s) > 5]
        if _socials:
            local_biz["sameAs"] = _socials
        local_biz["openingHoursSpecification"] = {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            "opens": "00:00",
            "closes": "23:59"
        }
        _cat_svcs = b_data.get('flat_services_list', [])[:8]
        if _cat_svcs:
            local_biz["hasOfferCatalog"] = {
                "@type": "OfferCatalog",
                "name": f"{b_data.get('industry', '')} Services",
                "itemListElement": [
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": clean_title(_s)}}
                    for _s in _cat_svcs
                ]
            }
        schema_graph.append(local_biz)
        
        # Service
        schema_graph.append({
            "@type": "Service",
            "name": b_data.get('name', display_service_name), # Uses business name or service name
            "description": p_data.get('intro', f"{display_service_name} services")[:150],
            # MUST EXACTLY MATCH THE ID DEFINED EARLIER
            "provider": {"@id": f"{page_url}/#localbusiness"},
            "areaServed": {"@type": "Place", "name": location_str},
            "serviceType": display_service_name,
            "keywords": keywords
        })
        # BreadcrumbList
        breadcrumbs = [{"@type": "ListItem", "position": 1, "name": "Home", "item": f"{base_url}/"}]
        position = 2
        if service_name.lower() != "home":
            if parent_category:
                p_url = parent_url if parent_url else f"{lang_base_url}/{slugify(parent_category)}"
                breadcrumbs.append({"@type": "ListItem", "position": position, "name": clean_title(parent_category), "item": p_url})
                position += 1
            breadcrumbs.append({"@type": "ListItem", "position": position, "name": display_service_name, "item": page_url})
        schema_graph.append({"@type": "BreadcrumbList", "itemListElement": breadcrumbs})
        
        # WebPage
        schema_graph.append({
            "@type": "WebPage",
            "@id": f"{page_url}/#webpage",
            "url": page_url,
            "name": p_data.get('meta_title', display_service_name),
            "description": p_data.get('meta_description', ''),
            "isPartOf": {"@id": f"{base_url}/#website"},
            "datePublished": datetime.now().strftime("%Y-%m-%d"),
            "dateModified": datetime.now().strftime("%Y-%m-%d")
        })
        
        # WebSite
        schema_graph.append({
            "@type": "WebSite",
            "@id": f"{base_url}/#website",
            "url": f"{base_url}/",
            "name": b_data.get('name', ''),
            "description": f"Professional {b_data.get('industry', '')} services in {location_str}",
            "publisher": {"@id": f"{base_url}/#organization"}
        })
        
        # FAQ - ALWAYS LAST in schema graph
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
                    "@id": f"{page_url}/#faqpage",
                    "mainEntity": faq_entities
                })

        return json.dumps({"@context": "https://schema.org", "@graph": schema_graph}, indent=2, ensure_ascii=False)
        
    except Exception as e:
        print(f"   ⚠️ Schema Generation Error: {e}")
        
        # 🔧 FIX: Ensure the ultimate fallback also resolves the empty base_url issue
        fallback_base = Config.SITE_URL.rstrip('/')
        if not fallback_base or not fallback_base.startswith('http'):
            fallback_base = f"https://{b_data.get('domain', 'yourdomain.com')}"
            
        if not page_url.startswith('http'):
            page_url = f"{fallback_base}/{page_url.lstrip('/')}"
            
        if page_url.endswith('index.html'):
            page_url = page_url.replace('index.html', '')
        elif page_url.endswith('.html'):
            page_url = page_url[:-5]
            
        return json.dumps({
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "@id": f"{fallback_base}/#organization",
            "name": b_data.get('name', ''),
            "url": f"{fallback_base}/",
            "logo": b_data.get('logo_url', '')
        })
# 🧠 ENHANCED CONTENT ENGINE - WITH RICH WHY CHOOSE US (EQUAL CONTENT)
# ==============================================================================
@retry_operation(max_retries=3)
def generate_service_faqs(b_data, service_name, category):
    """
    💎 AEO-OPTIMIZED FAQ ENGINE: Generates 'People Also Ask' style content in English and Arabic.
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

    # 🌍 MAP LANGUAGE FOR PROMPT (English & Arabic Only)
    lang_names = {"en": "English", "ar": "Arabic"}
    full_lang_name = lang_names.get(target_lang, "English")

    # 🌍 2-LANGUAGE FALLBACKS
    if target_lang == 'ar':
        fallback_faqs = [
            {"q": f"ما تكلفة خدمات {clean_srv} في {location}؟", "a": f"تعتمد التكلفة على حجم العمل، لكننا نقدم تسعيرًا شفافًا ومقدمًا قبل البدء بأي عمل في {location}."},
            {"q": f"ما مدى سرعة استجابتكم لطلبات {clean_srv}؟", "a": "خدمة الطوارئ متاحة عادةً خلال 60 دقيقة، بينما تتم جدولة المواعيد العادية خلال 24 ساعة."},
            {"q": f"هل أنتم مرخصون ومؤمنون لأعمال {clean_srv}؟", "a": "نعم، جميع المهنيين لدينا مرخصون ومؤمنون بالكامل لضمان السلامة والامتثال التام."},
            {"q": f"كم يستغرق عمل {clean_srv} النموذجي؟", "a": "تكتمل معظم الأعمال القياسية خلال ساعتين إلى 4 ساعات، رغم أن المشاريع المعقدة قد تتطلب يومًا كاملاً أو أكثر."},
            {"q": f"هل تقدمون ضمانات على أعمالكم؟", "a": "نعم، جميع أعمالنا تأتي مع ضمان شامل يغطي قطع الغيار والعمالة لراحة بالك."}
        ]
    else:
        fallback_faqs = [
            {"q": f"How much does {clean_srv} cost in {location}?", "a": f"The cost for {clean_srv} depends on the scope of work, but we provide transparent, upfront pricing before any job begins in {location}."},
            {"q": f"How quickly can you respond to {clean_srv} requests?", "a": "Emergency service is typically available within 60 minutes, while standard appointments are scheduled within 24 hours."},
            {"q": f"Are you licensed and insured for {clean_srv} work?", "a": "Yes, all our professionals are fully licensed, bonded, and insured to ensure complete safety and compliance."},
            {"q": f"How long does a typical {clean_srv} job take?", "a": "Most standard jobs are completed within 2 to 4 hours, though complex projects may require a full day or more."},
            {"q": f"Do you offer warranties on your {clean_srv} work?", "a": "Yes, all work comes with a comprehensive warranty covering both parts and labor for your peace of mind."}
        ]

    if not CLIENTS.get('openai'): return fallback_faqs
    
    # 1. FETCH LSI KEYWORDS FOR TRADITIONAL SEO INJECTION
    entities = get_related_entities(service_name, industry, location, target_lang)
    lsi_terms = entities.get('related_terms', [])[:3]
    
    lsi_instruction = f"TRADITIONAL SEO RULE: You MUST naturally weave these exact long-tail phrases into the Questions or Answers: {', '.join(lsi_terms)}" if lsi_terms else ""
    
    # --- FIX FOR YELLOW LINES: Define Tone Variable SAFELY outside the string ---
    niche = b_data.get('niche_engine')
    tone_instruction = niche.get_faq_tone_instruction() if niche else "Be professional and clear."
    # ----------------------------------------------------------------------------
    
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
        content = call_claude_json(prompt)
        if content and 'faqs' in content and len(content['faqs']) >= 3:
            final_faqs = content['faqs'][:5]
            SERVICE_FAQS_CACHE[cache_key] = final_faqs
            return final_faqs
    except Exception as e:
        print(f"   ⚠️ AEO FAQ Generation Error: {e}")
    
    SERVICE_FAQS_CACHE[cache_key] = fallback_faqs
    return fallback_faqs
@retry_operation(max_retries=3)
def generate_zigzag_content_with_links(b_data, service_name, category, is_child_page=False, related_services=None, page_seed=None):
    """Generate zigzag section content with internal links - With full language support & SEO Keywords."""
    
    seed = page_seed if page_seed else service_name
    cache_key = f"zigzag_links_{service_name}_{category}_{is_child_page}_{seed}_{b_data.get('target_lang', 'en')}"
    
    if cache_key in ZIGZAG_CONTENT_CACHE:
        return ZIGZAG_CONTENT_CACHE[cache_key]
    
    city = b_data.get('city', '')
    location = city if city else b_data.get('country', '')
    mode = b_data.get('mode', '3')
    target_lang = b_data.get('target_lang', 'en')
    
    # Mode 1 NEVER forces internal links — respect the user toggle
    should_use_links = Config.GENERATE_INTERNAL_LINKS

    # Ensure base_path exists for the AI prompt
    base_path = Config.SERVICE_BASE_PATH
    if not base_path.startswith('/'): base_path = '/' + base_path
    if not base_path.endswith('/'): base_path = base_path + '/'

    if not (CLIENTS.get('claude') or CLIENTS.get('openai')):
        if target_lang == 'ar':
            lines = [
                f"خدمات {clean_title(service_name)} احترافية في {location}.",
                f"يقدم فريقنا ذو الخبرة حلولاً مخصصة لجميع احتياجات {clean_title(service_name)} الخاصة بك.",
                f"نستخدم أحدث التقنيات والمواد عالية الجودة لنتائج تدوم طويلاً.",
                f"جميع الأعمال مدعومة بضمان رضا 100%.",
                f"خدمات الطوارئ متاحة 24/7 لاحتياجات {clean_title(service_name)} العاجلة.",
                f"اتصل بنا اليوم للحصول على استشارة مجانية وتقدير."
            ]
        else:
            lines = [
                f"Professional {clean_title(service_name)} services in {location}.",
                f"Our experienced team provides customized solutions for all your {clean_title(service_name)} needs.",
                f"We use the latest technology and premium materials for lasting results.",
                f"All work is backed by our 100% satisfaction guarantee.",
                f"Emergency services available 24/7 for urgent {clean_title(service_name)} needs.",
                f"Contact us today for a free consultation and estimate."
            ]
        
        if related_services and should_use_links:
            link1 = related_services[0] if len(related_services) > 0 else "Our Services"
            link2 = related_services[1] if len(related_services) > 1 else "Other Services"
            if target_lang == 'ar':
                lines.append(f"استكشف خدمات <a href='{validate_url('service', link1, mode)}' rel='dofollow'>{clean_title(link1)}</a> و <a href='{validate_url('service', link2, mode)}' rel='dofollow'>{clean_title(link2)}</a> للحصول على حلول متكاملة.")
            else:
                lines.append(f"Explore our <a href='{validate_url('service', link1, mode)}' rel='dofollow'>{clean_title(link1)}</a> and <a href='{validate_url('service', link2, mode)}' rel='dofollow'>{clean_title(link2)}</a> services for complete solutions.")
        
        content = {
            "title": f"Expert {clean_title(service_name)} Solutions" if target_lang == 'en' else f"حلول {clean_title(service_name)} الخبيرة",
            "description": " ".join(lines)
        }
        ZIGZAG_CONTENT_CACHE[cache_key] = content
        return content

    related_links = ""
    if related_services and len(related_services) >= 2 and should_use_links:
        related_links = "Related services: " + ", ".join([f"<a href='{validate_url('service', svc, mode)}' rel='dofollow'>{clean_title(svc)}</a>" for svc in related_services[:3]])
    
    random_seed = random.randint(1, 1000)
    
    # 🌟 NEW: Fetch Semantic Keywords for Zigzag Body Content
    keyword_tiers = extract_keyword_tiers(b_data, service_name, b_data.get('industry', ''), location, target_lang)
    semantic_keywords = keyword_tiers.get("semantic", [])[:3] 
    sec_kw_instruction = f"SEO CRITICAL: Naturally weave these semantic keywords into the text: {', '.join(semantic_keywords)}" if semantic_keywords else ""
    
    # 🌟 ULTIMATE ZIGZAG PROMPT — RICH CONTENT, NO LINKS IN MODE 1
    is_mode1 = (b_data.get('mode') == '1')
    
    prompt = f"""
    You are an elite conversion copywriter for a {b_data.get('industry')} business in {location}.
    Write a RICH, DETAILED zigzag section for this specific service: {clean_title(service_name)}
    UNIQUE SEED: {random_seed}
    TARGET LANGUAGE: {"Arabic (RTL)" if target_lang == 'ar' else "English"}
    
    WRITING RULES:
    1. LENGTH: Write exactly 3 full paragraphs (minimum 150 words total). Each paragraph minimum 2 sentences.
       Separate with <br><br>.
    2. PARAGRAPH 1: What is this service, who needs it, what problem does it solve in {location}?
    3. PARAGRAPH 2: How do we do it differently? What technique, tool, or guarantee sets us apart?
    4. PARAGRAPH 3: What happens after we finish? Result, benefit, peace of mind for the customer.
    5. Use <strong> tags on 2-3 key phrases that show expertise or urgency.
    6. Start with a DIRECT HOOK — not "In today's world" or "Professional services".
       Start with the customer's pain point or a surprising fact about {clean_title(service_name)}.
    7. KEYWORDS to weave naturally: {', '.join(semantic_keywords)}
    8. {"Do NOT include any <a href> links. Plain prose only." if (is_mode1 or not should_use_links) else "Weave 2-3 internal links using: <a href='" + base_path + "service-name'>Service Name</a>"}
    9. BANNED FILLER (instant rejection): "Our experienced team provides customized solutions", "We use the latest technology", "premium materials for lasting results". Never use template filler.
    10. Each section MUST open with a DIFFERENT hook pattern: a real pain-scenario, a surprising statistic, or a question the customer actually asks. No two sections may start the same way.
    11. Include at least ONE specific realistic number: a price range, timeframe, count, or percentage relevant to the target city.
    12. AUTO-ADAPT tone to the industry: medical/dental = reassuring and gentle, trades/repair = urgent and practical, beauty/luxury = aspirational, professional services = authoritative. Follow Problem, Agitate, Solution flow.
    13. ALL text in {"ARABIC" if target_lang == 'ar' else "ENGLISH"}.
    
    RETURN EXACTLY:
    {{
        "title": "Catchy 4-6 word title — specific to {clean_title(service_name)}, not generic",
        "description": "3 rich paragraphs separated by <br><br>"
    }}
    """
    
    try:
        content = call_claude_json(prompt)
        if content and 'title' in content and 'description' in content:
            desc = content['description'].strip()
            
            # FIXED REGEX REPLACEMENTS
            desc = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', desc)
            
            # Replace incorrect quotes around the generated base path or hardcoded /services/
            desc = re.sub(r'"([^"]*(?:/services/|' + re.escape(base_path) + r')[^"]+\.html)"', r'\1', desc)
            
            if related_services:
                for svc in related_services[:3]:
                    pattern = r'\[' + re.escape(svc) + r'\]'
                    desc = re.sub(pattern, f"<a href='{validate_url('service', svc, mode)}' rel='dofollow'>{clean_title(svc)}</a>", desc, flags=re.IGNORECASE)
                    
                    pattern = r'#' + re.escape(svc)
                    desc = re.sub(pattern, f"<a href='{validate_url('service', svc, mode)}' rel='dofollow'>{clean_title(svc)}</a>", desc, flags=re.IGNORECASE)
            
            desc = re.sub(r'#', '', desc)

            # Forcefully override any AI hallucinations 
            if base_path != "/services/":
                desc = desc.replace('href="/services/', f'href="{base_path}')
                desc = desc.replace("href='/services/", f"href='{base_path}")
            
            # FORCE CLEAN URLS: Remove .html to prevent redirect chains
            desc = desc.replace('.html', '')
            
            # DYNAMIC SPACING REPAIR: Instead of creating a wall of text, add new sentences as a new paragraph
            sentences = desc.split('. ')
            if len(sentences) < 6:
                if target_lang == 'ar':
                    additional = [
                        f"يتوفر أخصائيو {clean_title(service_name)} لدينا على مدار الساعة طوال أيام الأسبوع للمكالمات الطارئة في {location}.",
                        f"نقدم تقديرات مجانية وأسعار تنافسية لجميع مشاريع {clean_title(service_name)}.",
                        f"رضا العملاء هو أولويتنا القصوى في كل خدمة {clean_title(service_name)} نقدمها.",
                        f"اتصل بفريقنا اليوم لمناقشة احتياجات {clean_title(service_name)} الخاصة بك."
                    ]
                else:
                    additional = [
                        f"Our {clean_title(service_name)} specialists are available 24/7 for emergency calls in {location}.",
                        f"We provide free estimates and competitive pricing for all {clean_title(service_name)} projects.",
                        f"Customer satisfaction is our top priority with every {clean_title(service_name)} service we deliver.",
                        f"Contact our team today to discuss your {clean_title(service_name)} needs."
                    ]
                
                # Join the added text and append it with a line break to keep it scannable
                added_text = " ".join(additional[:6-len(sentences)])
                if added_text:
                    desc += f"<br><br>{added_text}"
            
            # Sanitize strings to absolutely prevent any hollow rectangles/hidden zero-width spaces in the final render
            content['title'] = strip_markdown(content['title']).replace('\u200b', '')
            content['description'] = desc.replace('\u200b', '')
            ZIGZAG_CONTENT_CACHE[cache_key] = content
            return content
    except Exception as e:
        print(f"   ⚠️ Zigzag Content Error: {e}")
    
    # Fallback with language support (Now split into two paragraphs!)
    if target_lang == 'ar':
        lines = [
            f"خدمات {clean_title(service_name)} احترافية مصممة خصيصاً لأعمال {location}.",
            f"يقدم خبراؤنا المعتمدون نتائج استثنائية باستخدام أحدث التقنيات في المجال.",
            f"نتعامل مع مشاريع من جميع الأحجام، من الإصلاحات الصغيرة إلى التركيبات الكبيرة.",
            f"جميع الأعمال يتم تنفيذها بواسطة محترفين مرخصين ومؤمن عليهم بالكامل.",
            f"نقدم جداول زمنية مرنة واستجابة للطوارئ خلال 60 دقيقة.",
            f"رضا العملاء مضمون في كل مشروع {clean_title(service_name)} نكمله."
        ]
    else:
        lines = [
            f"Professional {clean_title(service_name)} services tailored for {location} businesses.",
            f"Our certified specialists deliver exceptional results using industry-leading techniques.",
            f"We handle projects of all sizes, from small repairs to large-scale installations.",
            f"All work is performed by licensed, bonded, and insured professionals.",
            f"We offer flexible scheduling and emergency response within 60 minutes.",
            f"Satisfaction guaranteed on every {clean_title(service_name)} project we complete."
        ]
    
    if related_services and should_use_links:
        svc1 = related_services[0] if len(related_services) > 0 else "Services"
        svc2 = related_services[1] if len(related_services) > 1 else "Solutions"
        if target_lang == 'ar':
            lines.append(f"اجمع مع خدمات <a href='{validate_url('service', svc1, mode)}' rel='dofollow'>{clean_title(svc1)}</a> و <a href='{validate_url('service', svc2, mode)}' rel='dofollow'>{clean_title(svc2)}</a> للحصول على حلول شاملة.")
        else:
            lines.append(f"Combine with our <a href='{validate_url('service', svc1, mode)}' rel='dofollow'>{clean_title(svc1)}</a> and <a href='{validate_url('service', svc2, mode)}' rel='dofollow'>{clean_title(svc2)}</a> services for comprehensive solutions.")
    
    # Split the fallback lines into two perfectly sized paragraphs
    p1 = " ".join(lines[:3])
    p2 = " ".join(lines[3:])
    
    fallback = {
        "title": f"Expert {clean_title(service_name)} Solutions" if target_lang == 'en' else f"حلول {clean_title(service_name)} الخبيرة",
        "description": f"{p1}<br><br>{p2}"
    }
    
    # Strip any hidden zero-width spaces that cause hollow rectangles
    fallback['title'] = fallback['title'].replace('\u200b', '')
    fallback['description'] = fallback['description'].replace('\u200b', '')
    
    ZIGZAG_CONTENT_CACHE[cache_key] = fallback
    return fallback
# 🎯 SEO META & TITLE GENERATORS (MISSING FUNCTIONS RESTORED)
# ==============================================================================
def generate_seo_meta_description(b_data, service_name, keywords, industry, location):
    """Generates an SEO-optimized meta description incorporating top keywords."""
    target_lang = b_data.get('target_lang', 'en')
    kw_str = ", ".join(keywords[:3]) if keywords else service_name
    
    # Fallback patterns based on language
    if target_lang == 'ar':
        fallback = f"احصل على أفضل خدمات {clean_title(service_name)} في {location}. خبرة واسعة في {kw_str}. اتصل بنا اليوم."
    else:
        fallback = f"Top-rated {clean_title(service_name)} in {location}. Expert {industry} professionals specializing in {kw_str}. Call us today!"

    # Use GPT if available
    if CLIENTS.get('openai'):
        try:
            prompt = f"""
            Write a high-CTR meta description (140-158 characters) for a {industry} business page.
            Service: {service_name}
            Location: {location}
            Keywords (weave in MAX 1-2 naturally, NEVER stuff all): {kw_str}
            Language: {"Arabic" if target_lang == 'ar' else "English"}
            
            FORMULA: benefit hook + ONE specific number (price-from / response time / guarantee) + trust signal + short CTA.
            Style example: "Gentle, transparent dentistry in New York. Checkups from $150, same-day slots, 5-year guarantee. Book in 2 minutes."
            RULES: never repeat the same keyword twice, use "near me" at most once, sound human not SEO-spam.
            
            Return ONLY the text of the description, nothing else. No quotes.
            """
            response = CLIENTS['openai'].chat.completions.create(
               model=Config.MODEL_HIGH_TIER,
                messages=[{"role": "user", "content": prompt}] ,
                max_completion_tokens=100
            )
            desc = response.choices[0].message.content.strip().strip('"\'')
            if len(desc) > 20:  # Basic validation
                return desc
        except Exception as e:
            print(f"   ⚠️ Meta description generation failed: {e}")
            
    return fallback

def generate_evergreen_title(service_name, business_name, current_year):
    """
    Generates a clean SEO title. Year appears ONCE. No double brand name.
    Format: Service Name | Business Name (Year)
    """
    clean_srv = clean_title(service_name)
    clean_srv = re.sub(r'\s+\d{4}', '', clean_srv).strip()

    if business_name and business_name.lower() in clean_srv.lower():
        return f"{clean_srv} ({current_year})"

    return f"{clean_srv} | {business_name} ({current_year})"
# ==============================================================================
# 🧠 ENHANCED CONTENT ENGINE - WITH SEO OPTIMIZATIONS
# ==============================================================================
@retry_operation(max_retries=3)
def generate_page_content(b_data, page_type, active_service_name=None, parent_service=None, sibling_services=None, child_services=None, sub_services=None):
    """Generate complete page content using AI - with SEO OPTIMIZATIONS and natural keyword weaving."""
    
    # ===== BASIC SETUP =====
    city = b_data.get('city', '')
    location = city if city else b_data.get('country', '')
    state = b_data.get('state', '')
    country = b_data.get('country', '')
    industry = b_data.get('industry', '')
    clean_service_name = clean_title(active_service_name) if active_service_name else industry
    target_lang = b_data.get('target_lang', 'en')
    current_year = datetime.now().year

    # 🆕 FIX: Combine site_seed + page name so same service on two different
    # sites produces different copy, but re-running same site stays consistent
    _base_seed = b_data.get('site_seed', 0)
    _page_key  = (active_service_name or page_type or "home").lower()
    random_seed = (_base_seed + hash(_page_key)) % 99991

    # ===== SEO ENHANCEMENTS =====
    # 1. NEW 3-TIER SEO KEYWORD INTEGRATION
    keyword_tiers = extract_keyword_tiers(b_data, clean_service_name, industry, location, target_lang)
    high_intent_kw = ", ".join(keyword_tiers.get('high_intent', [])[:3])
    semantic_kw = ", ".join(keyword_tiers.get('semantic', [])[:3])
    local_time_kw = ", ".join(keyword_tiers.get('local_time', [])[:3])
    keywords_str = f"{high_intent_kw}, {semantic_kw}, {local_time_kw}"
    
    # 🌟 FIX: DEFINE THE MISSING top_keywords LIST HERE SAFELY 🌟
    high_intent_list = keyword_tiers.get('high_intent', [])
    top_keywords = high_intent_list if high_intent_list else [clean_service_name]
    primary_keyword = top_keywords[0]

    # 2. Get related entities (still needed for schema generation later)
    entities = get_related_entities(clean_service_name, industry, location, target_lang)

    # 3. Generate SEO-optimized meta description using high intent keywords
    seo_meta_description = generate_seo_meta_description(b_data, clean_service_name, keyword_tiers.get('high_intent', []), industry, location)
    
    # 4. Generate evergreen title
    evergreen_title = generate_evergreen_title(clean_service_name, b_data.get('name', ''), current_year)
    
    # LANGUAGE-AWARE WHY CHOOSE US
    if target_lang == 'ar':
        standard_why_choose_us = [
            {
                "title": "فريق خبير", 
                "desc": f"متخصصون معتمدون مع تدريب مكثف في {clean_service_name}. يخضع فريقنا للتعليم المستمر للبقاء في صدارة اتجاهات الصناعة وتقديم حلول متطورة لعملك في {location}.", 
                "icon": "mdi:account-tie", 
                "stat": "10+ سنوات"
            },
            {
                "title": "ضمان الجودة", 
                "desc": f"كل مشروع {clean_service_name} مدعوم بضمان الرضا الشامل. نقف وراء عملنا ونضمن حصولك على أعلى جودة من النتائج، أو سنقوم بتصحيح الأمر - بدون طرح أسئلة.", 
                "icon": "mdi:shield-check", 
                "stat": "100%"
            },
            {
                "title": "استجابة سريعة", 
                "desc": f"الوقت حرج عندما تحتاج إلى خدمات {clean_service_name}. يستجيب فريقنا في غضون 60 دقيقة للطلبات العاجلة ويعمل بكفاءة لتقليل التعطل لعمليات عملك في {location}.", 
                "icon": "mdi:clock-outline", 
                "stat": "60 دقيقة"
            }
        ]
    else:
        standard_why_choose_us = [
            {
                "title": "Expert Team", 
                "desc": f"Certified professionals with extensive training in {clean_service_name}. Our team undergoes continuous education to stay ahead of industry trends and deliver cutting-edge solutions for your business in {location}.", 
                "icon": "mdi:account-tie", 
                "stat": "10+ Years"
            },
            {
                "title": "Quality Guarantee", 
                "desc": f"Every {clean_service_name} project is backed by our comprehensive satisfaction guarantee. We stand behind our work and ensure that you receive the highest quality results, or we'll make it right - no questions asked.", 
                "icon": "mdi:shield-check", 
                "stat": "100%"
            },
            {
                "title": "Fast Response", 
                "desc": f"Time is critical when you need {clean_service_name} services. Our team responds within 60 minutes for urgent requests and works efficiently to minimize disruption to your business operations in {location}.", 
                "icon": "mdi:clock-outline", 
                "stat": "60 Min"
            }
        ]
        
    # Language-aware default hero texts
    if target_lang == 'ar':
        default_hero_title = f"خبراء {clean_service_name} في {location}"
        default_hero_sub = f"خدمات احترافية موثوقة — نصل إليك خلال 60 دقيقة في {location}"
        default_intro = f"خبراء في تقديم {clean_service_name} في {location}. يقدم فريقنا من المتخصصين المعتمدين نتائج استثنائية مع التركيز على الجودة ورضا العملاء. نحن نفهم الاحتياجات الفريدة للأعمال والسكان في {location}، ونقدم حلولاً مخصصة تتجاوز التوقعات. مع سنوات من الخبرة والالتزام بالتميز، أصبحنا الخيار الموثوق لخدمات {clean_service_name} في المنطقة. نهجنا الشامل يضمن إكمال كل مشروع بأعلى المعايير، في الوقت المحدد وضمن الميزانية. اتصل بنا اليوم لتجربة الفرق في العمل مع محترفين حقيقيين."
    else:
        default_hero_title = f"Expert {clean_service_name} in {location}"
        default_hero_sub = f"Fast, reliable {clean_service_name.lower()} — licensed professionals serving {location}"
        default_intro = f"Expert {clean_service_name} services in {location}. Our team of certified professionals delivers exceptional results with a focus on quality and customer satisfaction. We understand the unique needs of {location} businesses and residents, providing tailored solutions that exceed expectations. With years of experience and a commitment to excellence, we've become the trusted choice for {clean_service_name} in the area. Our comprehensive approach ensures that every project is completed to the highest standards, on time and within budget. Contact us today to experience the difference of working with true professionals."

    defaults = {
        "hero_title": default_hero_title,
        "hero_sub": default_hero_sub,
        "trust_signals": ["Satisfaction Guaranteed", "Free Quotes", "Fast Turnaround"] if target_lang != 'ar' else ["ضمان الرضا", "عروض أسعار مجانية", "استجابة سريعة"],
        "intro": default_intro,
        "why_choose_us": standard_why_choose_us,
        "reviews": [
            {"name": "سارة أحمد" if target_lang == 'ar' else "Sarah Johnson", 
             "txt": f"خدمة {clean_service_name} ممتازة! فريق محترف واستجابة سريعة." if target_lang == 'ar' else f"Excellent {clean_service_name} service! Professional team, fast response.", 
             "rating": "5"},
            {"name": "محمد علي" if target_lang == 'ar' else "Michael Chen", 
             "txt": "عمل موثوق وعالي الجودة في كل مرة." if target_lang == 'ar' else "Reliable and high-quality work every time.", 
             "rating": "4.8"},
            {"name": "شركة حلول الأعمال" if target_lang == 'ar' else "Business Solutions Inc.", 
             "txt": "المزود المفضل لدينا لجميع احتياجات الخدمة." if target_lang == 'ar' else "Our go-to provider for all service needs.", 
             "rating": "5"}
        ],
        "faqs": generate_service_faqs(b_data, active_service_name or "services", "General"),
        "meta_title": evergreen_title,
        "meta_description": seo_meta_description,
        "meta_keywords": keywords_str
    }

    # 🛑 PREVENT CRASH IF CLAUDE IS MISSING OR FAILS 🛑
    if not CLIENTS.get('claude'):
        print("   ⚠️ Claude client not initialized. Falling back to defaults to prevent crash.")
        return defaults
    
    neighborhoods, _, entities = get_dynamic_seo_data(clean_service_name, city, state, country, industry, target_lang)
    faqs = generate_service_faqs(b_data, active_service_name or industry, parent_service or "General")
    
    if page_type == "home":
        lang_instruction = "ALL TEXT MUST BE IN ARABIC LANGUAGE. Use proper Arabic marketing phrases. Hero title should be catchy in Arabic." if target_lang == 'ar' else "ALL TEXT MUST BE IN ENGLISH LANGUAGE."
        
        prompt = f"""
        Create UNIQUE homepage content for {b_data.get('name', '')}.
        BUSINESS: {industry} services in {location}
        UNIQUE SEED: {random_seed}
        LANGUAGE INSTRUCTION: {lang_instruction}
        
        REQUIREMENTS:
        - ALL TEXT VALUES MUST BE WRITTEN IN {"ARABIC" if target_lang == 'ar' else "ENGLISH"}.
        - CRITICAL: Output actual native Arabic characters (e.g. مرحبا). DO NOT use unicode escapes.
        - IMPORTANT: Keep the JSON KEYS strictly in English.
        - SEO CRITICAL - META DESCRIPTION: Must naturally include the top keywords: {', '.join(top_keywords)}
        - SEO CRITICAL - HEADINGS: The `hero_title` is the H1. Write it as 5-8 words MAXIMUM. 
          Format: "[Benefit/Action] [Service] in [City]" — e.g. "Fast Appliance Repair Dubai Homes Trust" or "Dubai's Top Fridge Repair Experts".
          DO NOT just concatenate the industry name and city. Write a real headline a human would say.
          No year. No full sentence structure like "We provide...".
        
        RETURN JSON:
        {{
            "hero_title": "string (Catchy H1, 6-9 words maximum, including {industry} and {location}. Do NOT add the year.)",
            "hero_sub": "string (compelling subheadline in {"Arabic" if target_lang == 'ar' else "English"})",
            "trust_signals": ["Signal 1", "Signal 2", "Signal 3"],
            "intro": "string (Write a short, highly scannable intro. Maximum 55 words total. State what you do and where. Break it into exactly 2 paragraphs using <br><br> for spacing. First paragraph MUST naturally include {top_keywords[0]}.)",
            "why_choose_us": [
                {{"title": "string (2-3 word UNIQUE benefit — NOT 'Expert Team')", "desc": "string (40-60 words SPECIFIC to this {industry} business in {location}, include ONE concrete number, zero generic filler)", "icon": "mdi:icon-name", "stat": "string (short stat e.g. '12+ Years')"}},
                {{"title": "string", "desc": "string", "icon": "mdi:icon-name", "stat": "string"}},
                {{"title": "string", "desc": "string", "icon": "mdi:icon-name", "stat": "string"}}
            ], 
            "reviews": [
                {{"name": "string", "txt": "string specific to {industry} (Max 25 words)", "rating": "string"}},
                {{"name": "string", "txt": "string specific to {industry} (Max 25 words)", "rating": "string"}},
                {{"name": "string", "txt": "string specific to {industry} (Max 25 words)", "rating": "string"}}
            ],
            "faqs": {json.dumps(faqs)},
            "meta_title": "string (optional - we'll use our evergreen format)",
            "meta_description": "string (optional - we'll use our optimized version)",
            "meta_keywords": "string (optional - we'll use our keyword list)"
        }}
        """
    else:
        prompt = f"""
        Create UNIQUE service page content for {clean_service_name} in {location}.
        BUSINESS: {industry}
        UNIQUE SEED: {random_seed}
        TARGET LANGUAGE: {"ARABIC" if target_lang == 'ar' else "ENGLISH"}
        
        REQUIREMENTS:
        - ALL TEXT VALUES MUST BE WRITTEN IN {"ARABIC" if target_lang == 'ar' else "ENGLISH"}.
        - CRITICAL: Output actual native Arabic characters. DO NOT use unicode escapes.
        - IMPORTANT: Keep the JSON KEYS strictly in English.
        - SEO CRITICAL - INTRO: Write a clean 2-sentence intro (max 55 words total). First sentence states what you do and where. Second sentence mentions "{primary_keyword}" naturally. No filler phrases like 'In today's competitive...' or 'As a leading...'.
        - SEO CRITICAL - HEADINGS: The `hero_title` is the H1. Write it as 5-8 words MAXIMUM.
          Format: "[Action/Benefit] [Specific Service] [City]" — e.g. "Same-Day Fridge Repair Dubai" or "Dubai's Trusted Washing Machine Experts".
          DO NOT repeat the full business name or industry category verbatim. Make it feel human-written.
          No year. No "We provide" sentence structure.
        - SEO CRITICAL - REVIEWS: Weave these Semantic keywords naturally into the customer reviews: {semantic_kw}. Keep text short.
        
        RETURN JSON:
        {{
            "hero_title": "string (Catchy H1, 6-9 words maximum. Do NOT include the year.)",
            "hero_sub": "string (Compelling H2 including {location})",
            "trust_signals": ["Signal 1", "Signal 2", "Signal 3"],
            "intro": "string (Max 55 words total across 2 short paragraphs separated explicitly by <br><br>. Must include {primary_keyword} early and naturally.)",
            "process": ["Step 1", "Step 2", "Step 3", "Step 4"],
            "why_choose_us": [
                {{"title": "string (2-3 word UNIQUE benefit — NOT 'Expert Team')", "desc": "string (40-60 words SPECIFIC to this {industry} business in {location}, include ONE concrete number, zero generic filler)", "icon": "mdi:icon-name", "stat": "string (short stat e.g. '12+ Years')"}},
                {{"title": "string", "desc": "string", "icon": "mdi:icon-name", "stat": "string"}},
                {{"title": "string", "desc": "string", "icon": "mdi:icon-name", "stat": "string"}}
            ],
            "reviews": [
                {{"name": "string", "txt": "string praising service using semantic keywords (Max 25 words)", "rating": "string"}},
                {{"name": "string", "txt": "string praising service using semantic keywords (Max 25 words)", "rating": "string"}},
                {{"name": "string", "txt": "string praising service using semantic keywords (Max 25 words)", "rating": "string"}}
            ],
            "faqs": {json.dumps(faqs)},
            "meta_title": "string (optional)",
            "meta_description": "string (optional)",
            "meta_keywords": "string (optional)"
        }}
        """
    
    try:
        print(f"   📝 Generating {page_type} content for {clean_service_name} using Claude 3.5 Sonnet...")
        
        # 🔴 CLAUDE 3.5 SONNET CALL 🔴
        content = call_claude_json(
            prompt=prompt, 
            system_prompt="You are an elite SEO copywriter and marketing strategist. Always output valid JSON."
        )
        
        if content:
            # FORCE STRIP YEARS FROM H1 (AI ignores negative prompts)
            if 'hero_title' in content:
                import re
                content['hero_title'] = re.sub(r'\s*\b20\d{2}\b\s*', '', content['hero_title']).strip(' -—|:')
                
            # Claude ka unique why_choose_us prefer karo; invalid/incomplete ho to hi template fallback
            _wcu = content.get('why_choose_us')
            if not (isinstance(_wcu, list) and len(_wcu) >= 3 and
                    all(isinstance(x, dict) and x.get('title') and len(str(x.get('desc',''))) > 30 for x in _wcu[:3])):
                content['why_choose_us'] = standard_why_choose_us
            
            if 'faqs' not in content or len(content['faqs']) < 5:
                content['faqs'] = faqs
            if 'areas_served' not in content:
                content['areas_served'] = neighborhoods
            if 'trust_signals' not in content or not content['trust_signals']:
                content['trust_signals'] = defaults['trust_signals']
            
            # ===== OVERRIDE WITH OUR SEO OPTIMIZATIONS =====
            content['meta_title'] = evergreen_title
            content['meta_description'] = seo_meta_description
            content['meta_keywords'] = keywords_str
            
            # ===== 🌟 NEW: NATURAL AI KEYWORD REVIEW USING CLAUDE =====
            if 'intro' in content and top_keywords:
                intro_text = content['intro']
                if top_keywords[0].lower() not in intro_text.lower():
                    print(f"   🔄 AI missed primary keyword. Executing Natural Rewrite with Claude...")
                    try:
                        rewrite_prompt = f"""
                        Rewrite this introductory paragraph so that it naturally includes the exact keyword phrase: '{top_keywords[0]}'.
                        Do NOT use colons to force it. Make it flow perfectly in the first or second sentence.
                        
                        CRITICAL RULES:
                        1. Keep it SHORT (Maximum 55 words total).
                        2. You MUST break it into exactly 2 paragraphs using <br><br> for spacing.
                        
                        Language: {'Arabic' if target_lang == 'ar' else 'English'}.
                        
                        Original Text:
                        {intro_text}
                        
                        RETURN EXACTLY THIS JSON FORMAT:
                        {{
                            "intro": "your rewritten paragraph here"
                        }}
                        """
                        # 🔴 CLAUDE 3.5 SONNET REWRITE CALL 🔴
                        rewrite_resp = call_claude_json(
                            prompt=rewrite_prompt,
                            system_prompt="You are an expert SEO editor. Return ONLY JSON."
                        )
                        
                        if rewrite_resp and 'intro' in rewrite_resp:
                            content['intro'] = rewrite_resp['intro']
                            print(f"     ✨ Successfully wove keyword naturally into intro!")
                    except Exception as e:
                        print(f"     ⚠️ Failed to rewrite intro naturally: {e}")
            
            return content
    except Exception as e:
        print(f"⚠️ Content Generation Error: {e}")
    
    defaults['faqs'] = faqs
    defaults['areas_served'] = neighborhoods
    defaults['meta_keywords'] = keywords_str
    defaults['why_choose_us'] = standard_why_choose_us
    return defaults


# ==============================================================================
# 📱 JAVASCRIPT GENERATOR
# ==============================================================================
def generate_js_file(b_data, output_folder):
    """Generates the main JavaScript file with PERMANENTLY FIXED form submission and FAQ toggles."""
    
    js_content = f"""// Main JavaScript for {b_data.get('name', '')}
// Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
// PERMANENTLY FIXED: Form redirects to WhatsApp without page refresh
// PERMANENTLY FIXED: FAQ toggles working perfectly

// Business Configuration
const siteConfig = {{
    name: "{b_data.get('name', '')}",
    phone: "{b_data.get('phone', '')}",
    whatsapp: "{b_data.get('whatsapp', '')}",
    email: "info@{b_data.get('domain', 'example.com')}",
    city: "{b_data.get('city', '')}",
    country: "{b_data.get('country', '')}",
    industry: "{b_data.get('industry', '')}",
    logo: "{b_data.get('logo_url', 'fas fa-tools')}"
}};

// Social Media Links
const socialLinks = {{
    facebook: "{b_data.get('facebook', '#')}",
    twitter: "{b_data.get('twitter', '#')}",
    instagram: "{b_data.get('instagram', '#')}",
    linkedin: "{b_data.get('linkedin', '#')}",
    youtube: "{b_data.get('youtube', '#')}",
    pinterest: "{b_data.get('pinterest', '#')}"
}};

// Make config globally available
window.siteConfig = siteConfig;
window.socialLinks = socialLinks;

// ========== PERMANENTLY FIXED: Lead Form Handler - Redirects to WhatsApp without page refresh ==========
window.handleLead = function(e) {{
    e.preventDefault(); // CRITICAL: Stops page from refreshing
    
    // Get form values - UPDATED to match hero form fields (phone instead of loc)
    const name = document.getElementById('name')?.value || '';
    const phone = document.getElementById('phone')?.value || document.getElementById('loc')?.value || ''; // Works with both 'phone' and 'loc' IDs
    const serviceSelect = document.getElementById('svc');
    const service = serviceSelect?.value || '';
    const email = document.getElementById('email')?.value || '';
    
    // Validate required fields
    if (!name || !phone || !service) {{
        alert('Please fill in all required fields (Name, Phone, and Service)');
        return false;
    }}
    
    // Send data to Google Sheets if configured
    if (window.v360Config?.sheetUrl?.length > 10) {{
        const data = new FormData();
        data.append('Source', window.v360Config.source || 'Website');
        data.append('Name', name);
        data.append('Phone', phone);
        data.append('Service', service);
        data.append('Email', email);
        data.append('Date', new Date().toLocaleString());
        
        fetch(window.v360Config.sheetUrl, {{ 
            method: 'POST', 
            body: data, 
            mode: 'no-cors' 
        }})
            .then(() => console.log('Lead saved to sheet'))
            .catch(err => console.error('Error saving lead:', err));
    }}
    
    // Prepare WhatsApp message - FIXED: Clean phone number and proper encoding
    let whatsappNumber = window.v360Config?.whatsapp || siteConfig.whatsapp;
    // Remove any + or spaces from phone number
    whatsappNumber = whatsappNumber.toString().replace(/[+\\s]/g, '');
    
    const message = `New Lead from Website:%0A%0A*Name:* ${{encodeURIComponent(name)}}%0A*Phone:* ${{encodeURIComponent(phone)}}%0A*Service:* ${{encodeURIComponent(service)}}%0A*Email:* ${{encodeURIComponent(email)}}%0A*Date:* ${{encodeURIComponent(new Date().toLocaleString())}}`;
    
    // Open WhatsApp in new tab (NOT redirect)
    const waUrl = `https://wa.me/${{whatsappNumber}}?text=${{message}}`;
    window.open(waUrl, '_blank');
    
    // Show success message
    alert(`Thank you, ${{name}}! WhatsApp will open in a new tab.`);
    
    // Reset form
    if (e.target && typeof e.target.reset === 'function') {{
        e.target.reset();
    }}
    
    return false; // Additional prevention
}};

// ========== PERMANENTLY FIXED: FAQ Toggle Functionality ==========
function initFaqToggle() {{
    const faqQuestions = document.querySelectorAll('.faq-question');
    
    faqQuestions.forEach(question => {{
        // Remove any existing listeners to prevent duplicates
        question.removeEventListener('click', handleFaqClick);
        // Add fresh listener
        question.addEventListener('click', handleFaqClick);
        
        // Also ensure icon clicks work
        const icon = question.querySelector('i');
        if (icon) {{
            icon.removeEventListener('click', handleIconClick);
            icon.addEventListener('click', handleIconClick);
        }}
    }});
}}

// Handle FAQ question click
function handleFaqClick(e) {{
    const question = e.currentTarget;
    const answer = question.nextElementSibling;
    const icon = question.querySelector('i');
    
    // Check if this is a valid FAQ item
    if (!answer || !answer.classList.contains('faq-answer')) return;
    
    // Close all other FAQs first
    document.querySelectorAll('.faq-answer').forEach(ans => {{
        if (ans !== answer) {{
            ans.style.display = 'none';
            const otherIcon = ans.previousElementSibling?.querySelector('i');
            if (otherIcon) otherIcon.className = 'fas fa-plus';
        }}
    }});
    
    // Toggle current FAQ
    if (answer.style.display === 'block') {{
        answer.style.display = 'none';
        if (icon) icon.className = 'fas fa-plus';
    }} else {{
        answer.style.display = 'block';
        if (icon) icon.className = 'fas fa-minus';
    }}
}}

// Handle icon clicks specifically
function handleIconClick(e) {{
    e.stopPropagation(); // Prevent double-triggering
    const question = e.target.closest('.faq-question');
    if (question) {{
        const answer = question.nextElementSibling;
        const icon = question.querySelector('i');
        
        if (!answer || !answer.classList.contains('faq-answer')) return;
        
        // Close others
        document.querySelectorAll('.faq-answer').forEach(ans => {{
            if (ans !== answer) {{
                ans.style.display = 'none';
                const otherIcon = ans.previousElementSibling?.querySelector('i');
                if (otherIcon) otherIcon.className = 'fas fa-plus';
            }}
        }});
        
        // Toggle current
        if (answer.style.display === 'block') {{
            answer.style.display = 'none';
            if (icon) icon.className = 'fas fa-plus';
        }} else {{
            answer.style.display = 'block';
            if (icon) icon.className = 'fas fa-minus';
        }}
    }}
}}

// ========== PERMANENTLY FIXED: Location Rendering Function ==========
function renderLocations(locations) {{
    if (!locations || !Array.isArray(locations)) return;
    
    // Desktop locations container
    const desktopContainer = document.getElementById('desktop-locations-container');
    if (desktopContainer) {{
        let html = '';
        locations.forEach(loc => {{
            html += `<a href="${{loc.url}}" style="display:block; padding:8px 0; color:#64748b; font-size:0.9rem; border-bottom:1px solid #eee;">
                <i class="fas fa-map-marker-alt" style="margin-right:8px; color:#1A73E8;"></i> ${{loc.name}}
            </a>`;
        }});
        desktopContainer.innerHTML = html;
    }}
    
    // Mobile locations container
    const mobileContainer = document.getElementById('mobile-locations-container');
    if (mobileContainer) {{
        let html = '';
        locations.forEach(loc => {{
            html += `<a href="${{loc.url}}" style="display:block; padding:12px; border:1px solid #e2e8f0; border-radius:6px; margin-bottom:8px; text-align:center; color:#475569; font-size:0.9rem; text-decoration:none; background:white;">
                <i class="fas fa-map-marker-alt" style="margin-right:8px; color:#1A73E8;"></i> ${{loc.name}}
            </a>`;
        }});
        mobileContainer.innerHTML = html;
    }}
    
    // Footer locations list
    const footerList = document.querySelector('.footer-locations-list');
    if (footerList) {{
        let html = '';
        locations.forEach(loc => {{
            html += `<li><a href="${{loc.url}}"><i class="fas fa-map-marker-alt"></i> ${{loc.name}}</a></li>`;
        }});
        footerList.innerHTML = html;
    }}
}}

// ========== MAIN INITIALIZATION ==========
document.addEventListener('DOMContentLoaded', function() {{
    console.log('DOM loaded - initializing components');
    
    // 1. Initialize FAQ toggles
    initFaqToggle();
    
    // 2. CRITICAL: Manually attach form handler to hero form
    const heroForm = document.querySelector('.glass-card form');
    if (heroForm) {{
        // Remove any existing submit handlers
        heroForm.removeEventListener('submit', window.handleLead);
        // Add our fixed handler
        heroForm.addEventListener('submit', window.handleLead);
        console.log('Hero form handler attached');
    }}
    
    // 3. Handle any forms with onsubmit attribute
    document.querySelectorAll('form[onsubmit*="handleLead"]').forEach(form => {{
        form.removeAttribute('onsubmit');
        form.addEventListener('submit', window.handleLead);
    }});
    
    // 4. Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
        anchor.addEventListener('click', function (e) {{
            const href = this.getAttribute('href');
            if (href && href !== '#') {{
                e.preventDefault();
                const target = document.querySelector(href);
                if(target) {{
                    target.scrollIntoView({{
                        behavior: 'smooth',
                        block: 'start'
                    }});
                }}
            }}
        }});
    }});
    
    // 5. Dynamic Year in Footer
    const yearElement = document.getElementById('current-year');
    if(yearElement) {{
        yearElement.textContent = new Date().getFullYear();
    }}
    
    // 6. Initialize location data if available
    if (typeof locationData !== 'undefined' && Array.isArray(locationData)) {{
        renderLocations(locationData);
    }}
}});

// ========== HANDLE DYNAMIC CONTENT ==========
window.addEventListener('load', function() {{
    // Re-initialize FAQs after all content is loaded
    setTimeout(initFaqToggle, 500);
    
    // Re-attach form handler
    const heroForm = document.querySelector('.glass-card form');
    if (heroForm) {{
        heroForm.addEventListener('submit', window.handleLead);
    }}
}});

// ========== MUTATION OBSERVER FOR DYNAMICALLY ADDED CONTENT ==========
const observer = new MutationObserver(function(mutations) {{
    mutations.forEach(function(mutation) {{
        if (mutation.addedNodes.length) {{
            // Check for new FAQ elements
            if (document.querySelector('.faq-question:not([data-handler-attached])')) {{
                initFaqToggle();
            }}
            // Check for new forms
            if (document.querySelector('.glass-card form:not([data-handler-attached])')) {{
                const form = document.querySelector('.glass-card form');
                form.setAttribute('data-handler-attached', 'true');
                form.addEventListener('submit', window.handleLead);
            }}
        }}
    }});
}});

// Start observing after DOM is ready
document.addEventListener('DOMContentLoaded', function() {{
    observer.observe(document.body, {{
        childList: true,
        subtree: true
    }});
}});
"""
    
    js_path = os.path.join(output_folder, 'js', 'main.js')
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(js_content)
    
    print(f"✅ Generated JavaScript with PERMANENT FIXES: {js_path}")
    return js_path

# ==============================================================================
# 📍 LOCATIONS JS GENERATOR (SINGLE VERSION - FIXED)
# ==============================================================================
def generate_locations_js(output_folder, created_pages=None, b_data=None):
    """
    Uses GPT-4o to analyze generated pages and identify Location/Neighborhood pages.
    Zero hardcoding. Works for ANY city in the world. Fixed for Mode 2 & 3 string formatting.
    """
    
    # Default to empty pages list if not provided
    if created_pages is None:
        created_pages = []
    
    # Default b_data if not provided
    if b_data is None:
        b_data = {}
    
    # Ensure JS directory exists to prevent FileNotFoundError
    js_folder = os.path.join(output_folder, 'js')
    os.makedirs(js_folder, exist_ok=True)
    
    # 1. Filter only service pages (FIXED FOR MODE 2 HUBS)
    mode = str(b_data.get('mode', '3'))
    hub_folder = Config.HUB_TARGET_URL.strip('/') if Config.HUB_TARGET_URL else "services"
    
    # Match pages in the specific hub folder OR the services folder
    service_pages = [p for p in created_pages if (f"{hub_folder}/" in p or "services/" in p) and "index.html" not in p]
    
    if not service_pages:
        print(f"   ⚠️ No service pages found in /{hub_folder}/ to analyze for locations.")
        # Create a safe fallback file so JS doesn't crash
        js_path = os.path.join(js_folder, 'locations.js')
        with open(js_path, 'w', encoding='utf-8') as f:
            f.write("const locationData = [];\n")
        return js_path
        
    target_city = b_data.get('city', '')
    target_country = b_data.get('country', '')
    
    found_locations = []
    ai_success = False  # Track if AI successfully responded

    # 2. Ask GPT-4o to identify locations
    if CLIENTS.get('openai'):
        try:
            print(f"   🧠 AI analyzing {len(service_pages)} pages to find {target_city} locations...")
            
            prompt = f"""
            I have a list of website pages for a business in {target_city}, {target_country}.
            Identify which of these pages are specifically targeting a NEIGHBORHOOD, DISTRICT, or SUBURB.
            
            PAGE LIST:
            {json.dumps(service_pages)}
            
            RULES:
            1. Return a JSON list of the TOP 6 most important location pages.
            2. "name": Extract a clean, Title Case display name (e.g., "Palm Jumeirah", "Downtown"). 
               - Remove industry words like "SEO", "Marketing", "PPC", "Service", "Agency" from the name.
               - JUST the location name.
            3. "url": The exact path provided in the input.
            
            RETURN JSON ONLY:
            {{
                "locations": [
                    {{"name": "Location Name", "url": "services/page-path.html"}}
                ]
            }}
            """
            
            response = CLIENTS['openai'].chat.completions.create(
                model=Config.MODEL_LOW_TIER,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"} 
            )
            
            data = clean_json_response(response.choices[0].message.content)
            if data and 'locations' in data:
                found_locations = data['locations']
                ai_success = True  # AI successfully completed the task (even if the list is empty!)
                print(f"   ✅ AI identified {len(found_locations)} location pages.")
                
        except Exception as e:
            print(f"   ⚠️ AI Location detection failed: {e}")
    
    # 3. DYNAMIC Fallback (Only runs if AI actually crashed, NOT if it just found 0 locations)
    if not ai_success:
        print("   ℹ️ Using universal dynamic fallback location detection...")
        target_city_lower = target_city.lower()
        
        for page in service_pages:
            filename = page.split('/')[-1]
            clean = filename.replace(".html", "").replace("-", " ")
            
            # UNIVERSAL CHECK: Does the file name actually contain the target city name?
            if target_city_lower and target_city_lower in clean.lower():
                name = clean.title()
                name = " ".join(name.split()) # Clean up spaces
                
                if name.strip():
                    found_locations.append({"name": name.strip(), "url": "/" + page.lstrip("/")})
                
                if len(found_locations) >= 6: break

    # 4. Generate the JS content
    js_content = "// Generated Dynamic Locations Array\n"
    js_content += "const locationData = [\n"
    for loc in found_locations:
        # Ensure URL starts with /
        url = loc['url'] if loc['url'].startswith('/') else '/' + loc['url']
        # Protect language silos
        lang_prefix = getattr(Config, 'LANG_PREFIX', "")
        if lang_prefix and not url.startswith(lang_prefix + '/'):
            url = f"{lang_prefix}{url}"
        js_content += f'    {{ name: "{loc["name"]}", url: "{url}" }},\n'
    js_content += "];\n"
    
    # 5. Save the file
    js_path = os.path.join(js_folder, 'locations.js')
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(js_content)
        
    print(f"✅ Generated Locations Menu at: {js_path}")
    return js_path

# ==============================================================================
# 🏗️ COMPONENT BUILDERS - WITH SHORT FORM PLACEHOLDERS
# ==============================================================================
def build_dynamic_layout_section(b_data, items, section_title, page_type, page_name, limit=15, url_type="service"):
    """
    PRO LEVEL ALGORITHM: Infinite Layering Engine (Round-Robin)
    Dynamically chunks items to guarantee perfect 3-item grids and maximum 4-item zigzags.
    Provides massive SEO word depth while completely eliminating scroll fatigue and broken UI rows.
    """
    if not items:
        return ""

    items_to_process = items[:limit]
    count = len(items_to_process)
    target_lang = b_data.get('target_lang', 'en')
    more_prefix = "المزيد حول " if target_lang == 'ar' else "More "
    is_child = (page_type == "child")

    # 1. Handle purely small lists (Pure SEO depth)
    if count <= 2:
        return build_zigzag_section(b_data, items_to_process, section_title, count, is_child_page=is_child, url_type=url_type)
    elif count == 3:
        return build_grid_section(b_data, items_to_process, section_title, limit=3, url_type=url_type)

    html = ""
    current_index = 0
    iteration = 0

    # 2. The Smart Round-Robin Distribution
    while current_index < count:
        remaining = count - current_index

        # --- LAYER 1: VISUAL GRID ---
        # Only render a grid if we have exactly 3 items, or enough items to support future loops.
        # This prevents ugly 1-card or 2-card desktop grid rows.
        if remaining >= 3 and (iteration == 0 or remaining == 3 or remaining >= 5):
            grid_count = 3
            grid_items = items_to_process[current_index : current_index + grid_count]
            
            title = section_title if current_index == 0 else (f"استكشف المزيد من الخدمات" if target_lang == 'ar' else f"Explore Additional Services")
            html += build_grid_section(b_data, grid_items, title, limit=grid_count, url_type=url_type)
            
            current_index += grid_count

        # --- LAYER 2: DEEP SEO ZIGZAG ---
        # Take the next batch as Zigzags. We cap at 4 to deliver high SEO value without scroll fatigue.
        remaining = count - current_index
        if remaining > 0:
            # The Lookahead Math: Predict the next loop so we leave exactly 3 items for a perfect final Grid
            if remaining == 5:
                zig_count = 2  # Leaves exactly 3 for the next Grid
            elif remaining == 6:
                zig_count = 3  # Leaves exactly 3 for the next Grid
            elif remaining == 7:
                zig_count = 4  # Leaves exactly 3 for the next Grid
            else:
                zig_count = min(4, remaining) # Standard cap at 4

            zig_items = items_to_process[current_index : current_index + zig_count]
            
            # Only append the "More" prefix if it's the very first zigzag block on the page
            zig_title = f"{more_prefix}{section_title}" if iteration == 0 and current_index <= 3 else ""
            
            html += build_zigzag_section(b_data, zig_items, zig_title, limit=zig_count, is_child_page=is_child, url_type=url_type)
            
            current_index += zig_count

        iteration += 1

    return html
def generate_grid_descriptions(items, industry, city, target_lang):
    """Generate unique, conversion-focused descriptions for grid cards — no duplicate copy."""
    if not items:
        return {}
    
    lang_name = "Arabic" if target_lang == 'ar' else "English"
    
    # Build a strong fallback FIRST so we never return empty strings
    fallback = {}
    for item in items:
        name = clean_title(item)
        if target_lang == 'ar':
            fallback[item] = f"حلول {name} سريعة وموثوقة في {city} — اتصل الآن للحجز."
        else:
            templates = [
                f"Struggling with {name.lower()}? Our {city} specialists fix it fast — same day available.",
                f"{city}'s go-to team for {name.lower()} issues. Transparent pricing, no surprises.",
                f"Certified {name.lower()} experts serving {city}. Most jobs completed in under 2 hours.",
                f"Don't wait — get your {name.lower()} sorted today by {city}'s trusted specialists.",
            ]
            import random as _r
            fallback[item] = _r.choice(templates)
    
    # Try Claude/OpenAI for better copy
    client = CLIENTS.get('claude') or CLIENTS.get('openai')
    if not client:
        return fallback
    
    prompt = f"""Write a UNIQUE, punchy 1-sentence description (max 18 words) for each {industry} service below.

RULES:
1. Every description must be DIFFERENT — no repeated phrases across cards.
2. Focus on the CUSTOMER PROBLEM or OUTCOME, not generic "professional service".
3. Include a specific detail: timeframe, brand compatibility, price signal, or symptom.
4. Language: {lang_name}
5. Do NOT start every sentence with "Expert" or "Professional".

SERVICES:
{chr(10).join(f'- {item}' for item in items)}

Return ONLY valid JSON — keys are the exact service names, values are the descriptions:
{{
    "Service Name": "one punchy sentence here",
    ...
}}"""
    
    try:
        result = call_claude_json(prompt) or {}
        # Merge: use AI result where available, fallback where not
        for item in items:
            if item not in result or not result[item] or len(result[item]) < 10:
                result[item] = fallback[item]
        return result
    except Exception as e:
        print(f"   ⚠️ Grid description error: {e}")
        return fallback
def short_card_title(text, max_words=5):
    """Returns a truncated display title for grid cards — max 5 words."""
    words = clean_title(text).split()
    if len(words) <= max_words:
        return clean_title(text)
    return " ".join(words[:max_words]) + "…"  
def service_btn_label(item, target_lang='en', max_words=4):
    """Short, SEO-friendly button label = the service name itself.
    Returns service name (max 4 words). Falls back to generic only if name is empty."""
    name = clean_title(item).strip()
    if not name:
        return "اعرف المزيد" if target_lang == 'ar' else "Get Service"
    words = name.split()
    if len(words) > max_words:
        name = " ".join(words[:max_words])
    return name     
def build_grid_section(b_data, items, section_title, limit=6, url_type="service"):
    """Builds a properly spaced grid layout section with SEO-rich, dynamically AI-generated descriptions."""
    if not items:
        return ""
        
    mode = b_data.get('mode', '3')
    ui = b_data.get('ui', {})
    target_lang = b_data.get('target_lang', 'en')
    city_display = b_data.get('city') if b_data.get('city') else b_data.get('country')
    industry = b_data.get('industry', 'professional')
    
    # Card variant from the niche engine (image_top / icon_left / minimal_border)
    _niche = b_data.get('niche_engine')
    card_variant = getattr(_niche, 'card_variant', 'image_top') if _niche else 'image_top'
    # Mode 1 single-page: image wale dono premium styles mein se seed se pick
    if b_data.get('mode') == "1":
        card_variant = ['image_top', 'minimal_border'][b_data.get('site_seed', 0) % 2]
    
    # 💎 RTL Arrow Logic for Iconify
    arrow_icon = "mdi:arrow-left" if target_lang == 'ar' else "mdi:arrow-right"
    
    # 💎 BATCH GENERATION: Fetch all natural descriptions in one single, fast AI call
    items_to_process = items[:limit]
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
        
        # 🔗 CRITICAL URL FIX: We use the RAW `item` (English) to build the URL slug.
        # We also use `url_type` so it intelligently routes to /categories/ OR /services/ to prevent 404s!
        link = validate_url(url_type, item, mode)
        
        # 💎 AI TEXT INJECTION: Use the AI description if successful
        if item in dynamic_descriptions and dynamic_descriptions[item]:
            description = dynamic_descriptions[item]
        else:
            # 🛡️ DYNAMIC MULTI-LANGUAGE FALLBACK: Randomizes templates so it never sounds robotic
            entities = get_related_entities(item, industry, city_display, target_lang)
            keywords = entities.get("keywords", [])
            related_terms = entities.get("related_terms", [])
            
            kw1 = keywords[1] if len(keywords) > 1 else industry
            kw2 = related_terms[0] if len(related_terms) > 0 else "custom solutions"
            
            # 🌐 CRITICAL UI FIX: We use clean_title to display the ARABIC translated text in the UI
            item_clean = clean_title(item)
            
            if target_lang == 'ar':
                ar_templates = [
                    f"ارتقِ بتجربتك مع حلول {item_clean} المتميزة في {city_display}. نحن نضمن لك أفضل النتائج في {kw1}.",
                    f"هل تبحث عن {kw2}؟ يقدم فريقنا المتخصص في {city_display} خدمات {item_clean} بأعلى معايير الجودة.",
                    f"نقدم خدمات {item_clean} مخصصة لتلبية احتياجاتك في {city_display}، مع التركيز التام على {kw1}."
                ]
                description = random.choice(ar_templates)
            else:
                en_templates = [
                    f"Top-rated {item_clean} solutions in {city_display}. From {kw1} to {kw2}, we deliver reliable results.",
                    f"Looking for {kw1}? Our {item_clean} team in {city_display} guarantees exceptional service, including {kw2}.",
                    f"Enhance your project with our professional {item_clean}. We specialize in {kw2} throughout {city_display}."
                ]
                description = random.choice(en_templates)
                
        btn_text = service_btn_label(item, target_lang)

        # 💎 MODE 1 FIX: sub-service pages exist nahi karte (single-page site),
        # purana link 404 deta tha. Ab pre-filled WhatsApp pe route — better conversion.
        if mode == "1":
            from urllib.parse import quote as _q
            _wa  = b_data.get('whatsapp', '')
            _msg = _q(f"Hi! I need {clean_title(item)} in {city_display}. Please send me a quote.")
            link = f"https://wa.me/{_wa}?text={_msg}"
            btn_text = ui.get('get_quote',
                              'احصل على عرض سعر' if target_lang == 'ar' else 'Get Free Quote')
        
        # icon_left variant: no image, show an icon box instead (faster pages)
        if card_variant == "icon_left":
            item_icon = get_dynamic_icon(item)
            html += f'''
            <div class="service-card cv-icon_left">
                <div class="cv-icon-box">
                    <span class="iconify" data-icon="{item_icon}" data-width="30"></span>
                </div>
                <div class="service-card-content">
                    <h3 title="{clean_title(item)}">{short_card_title(item)}</h3>
                    <div class="v360-desc-text">{description}</div>
                    <a href="{link}" class="btn btn-primary" style="align-self: flex-start; width: 100%; border-radius: 50px;" rel="dofollow" aria-label="{btn_text} - {clean_title(item)}">
                        <span class="iconify" data-icon="{arrow_icon}" data-width="20" style="margin-right: 8px;"></span> {btn_text}
                    </a>
                </div>
            </div>
            '''
        else:
            # image_top (default) and minimal_border both use the image layout;
            # minimal_border just adds a styling class.
            extra_class = " cv-minimal_border" if card_variant == "minimal_border" else ""
            html += f'''
            <div class="service-card{extra_class}">
                <div class="service-card-img">
                    <img src="{img}" loading="lazy" alt="{clean_title(item)}">
                </div>
                <div class="service-card-content">
                    <h3 title="{clean_title(item)}">{short_card_title(item)}</h3>
                    <div class="v360-desc-text">{description}</div>
                    <a href="{link}" class="btn btn-primary" style="align-self: flex-start; width: 100%; border-radius: 50px;" rel="dofollow" aria-label="{btn_text} - {clean_title(item)}">
                        <span class="iconify" data-icon="{arrow_icon}" data-width="20" style="margin-right: 8px;"></span> {btn_text}
                    </a>
                </div>
            </div>
            '''
    
    html += '''
            </div>
        </div>
    </section>
    '''
    return html
# ==============================================================================
# 🧠 SMART HERO DROPDOWN LOGIC (GPT-4o) + "OTHER" OPTION
# ==============================================================================
# Global cache to ensure we only ask AI once for the menu structure
HERO_DROPDOWN_CACHE = []

def get_smart_hero_options(b_data, full_list):
    """Uses GPT-4o to pick the top 7 high-converting services for the dropdown."""
    global HERO_DROPDOWN_CACHE
    
    # 1. Return Cache if already exists (Prevents repeating API calls)
    if HERO_DROPDOWN_CACHE:
        return HERO_DROPDOWN_CACHE

    # 2. Fallback if list is short or API missing
    if not full_list or len(full_list) <= 7 or not CLIENTS['openai']:
        HERO_DROPDOWN_CACHE = full_list[:7]
        return HERO_DROPDOWN_CACHE

    try:
        print("   🧠 AI selecting top 7 services for Hero Dropdown...")
        prompt = f"""
        I have a list of services for a {b_data.get('industry')} business.
        Select exactly 7 "High-Intent" or "Parent Category" services that would work best in a "Get a Quote" dropdown menu.
        
        FULL LIST: {json.dumps(full_list)}
        
        RULES:
        1. Pick the 7 most popular/broad services (e.g. "AC Repair", "Plumbing").
        2. Do NOT pick specific location pages (e.g. "Palm Jumeirah AC" -> NO).
        3. Do NOT pick very specific sub-niche items if a main category exists.
        4. Return ONLY a JSON array of strings.
        
        Example Output: ["AC Repair", "Plumbing", "Electrical", "Painting", "Cleaning", "Handyman", "Water Tank Cleaning"]
        """
        
        response = CLIENTS['openai'].chat.completions.create(
            model=Config.MODEL_LOW_TIER,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} 
        )
        
        data = clean_json_response(response.choices[0].message.content)
        
        if data and isinstance(data, dict) and len(data) > 0:
            # Handle various AI return formats
            key = next(iter(data))
            selected = data[key]
            if isinstance(selected, list):
                # Save to cache
                HERO_DROPDOWN_CACHE = selected[:7]
                return selected[:7]
                
    except Exception as e:
        print(f"   ⚠️ AI Dropdown selection failed: {e}")
    
    # Fallback if AI fails: Just take the first 7 non-location services
    clean_fallback = [s for s in full_list if "Palm" not in s and "Dubai" not in s][:7]
    HERO_DROPDOWN_CACHE = clean_fallback if clean_fallback else full_list[:7]
    return HERO_DROPDOWN_CACHE

def build_hero(b_data, title, sub, img_prompt, hero_img_url, service_list=None, hierarchy=None, trust_signals=None, hero_variant="split_form", show_form=True):
    """Build hero section with SMART AI-SELECTED DROPDOWN + 'Other' Option. Now variant-aware."""
    
    # Safely get the UI dictionary for translations
    ui = b_data.get('ui', {})
    
    # Get raw list
    raw_services = service_list if service_list else b_data.get('flat_services_list', [])
    
    # Get Smart Top 7 List (Cached)
    smart_services = get_smart_hero_options(b_data, raw_services)
    
    # Generate Options HTML
    options_html = "".join([f'<option value="{s}">{clean_title(s)}</option>' for s in smart_services])
    
    # ✅ Translated: "Other Services" option
    options_html += f'<option value="Other">{ui.get("other_services", "Other Services")}</option>'

    city = b_data.get('city', 'Us')
    
    # Pull from DESIGN_SPEC if available
    spec = b_data.get('design_spec', {})
    trust_badge = spec.get('trust_badge', f"{ui.get('rated', '#1 Rated in')} {city}")

    # Build the text column (always present)
    text_col = f"""
            <div class="text-col">
                <div class="hero-gold-badge">
                    <i class="fas fa-star"></i> {trust_badge}
                </div>
                <h1 class="hero-title">{strip_markdown(title)}</h1>
                <p class="hero-sub">{strip_markdown(sub)}</p>
                
                <div class="hero-features">
                    <div class="hero-feature">
                        <i class="fas fa-check-circle"></i> {ui.get('licensed', 'Licensed')}
                    </div>
                    <div class="hero-feature">
                        <i class="fas fa-check-circle"></i> {ui.get('insured', 'Insured')}
                    </div>
                    <div class="hero-feature">
                        <i class="fas fa-check-circle"></i> {ui.get('24_7', '24/7 Service')}
                    </div>
                </div>

                <div class="btn-group">
                    <a href="tel:{b_data.get('phone','')}" class="btn btn-primary">
                        <i class="fas fa-phone-alt"></i> {ui.get('call_now', 'Call Now')}
                    </a>
                    <a href="https://wa.me/{b_data.get('whatsapp','')}" class="btn" style="background:#25D366; color:white; border:none;">
                        <i class="fab fa-whatsapp"></i> {ui.get('whatsapp', 'WhatsApp')}
                    </a>
                </div>
            </div>"""

    # Build the form column
    form_col = ""
    
    if b_data.get('mode') == "1":
        # MODE 1: Form + Call/WhatsApp buttons both
        all_mode1_services = b_data.get('flat_services_list', [])
        sub_svcs = generate_sub_services(b_data, all_mode1_services[0] if all_mode1_services else "service")
        all_options = all_mode1_services + [s for s in sub_svcs if s not in all_mode1_services]
        all_options_html = "".join([
            f'<option value="{s}">{clean_title(s)}</option>'
            for s in all_options[:15]
        ])
        all_options_html += f'<option value="Other">{ui.get("other_services","Other Services")}</option>'
        _primary_hex = b_data.get('primary', '#1A73E8').lstrip('#')
        
        form_col = f"""
            <div class="form-col">
                <div class="glass-card">
                    <h3>
                        <i class="fas fa-file-invoice-dollar"></i> {ui.get('get_quote','Free Quote')}
                    </h3>
                    <form onsubmit="handleLead(event)">
                        <input type="text" id="name" placeholder="{ui.get('name_ph','Name')}" required>
                        <input type="text" id="phone" placeholder="{ui.get('phone_ph','Phone')}" required>
                        <select id="svc">
                            <option value="" disabled selected>{ui.get('service_ph','Select Service...')}</option>
                            {all_options_html}
                        </select>
                        <button type="submit">
                            {ui.get('submit_btn','Get Instant Quote')} <i class="fas fa-arrow-right"></i>
                        </button>
                    </form>
                    <p style="text-align:center; font-size:0.8rem; margin-top:12px; opacity:0.8;">
                        <i class="fas fa-lock"></i> {ui.get('secure','Secure & Confidential')}
                    </p>
                </div>
            </div>"""

    elif show_form:
        form_col = f"""
            <div class="form-col">
                <div class="glass-card">
                    <h3>
                        <i class="fas fa-file-invoice-dollar"></i> {ui.get('get_quote', 'Free Quote')}
                    </h3>
                    <form onsubmit="handleLead(event)">
                        <input type="text" id="name" placeholder="{ui.get('name_ph', 'Name')}" required>
                        <input type="text" id="phone" placeholder="{ui.get('phone_ph', 'Phone')}" required>
                        <select id="svc">
                            <option value="" disabled selected>{ui.get('service_ph', 'Select Service...')}</option>
                            {options_html}
                        </select>
                        <button type="submit">
                            {ui.get('submit_btn', 'Get Instant Quote')} <i class="fas fa-arrow-right"></i>
                        </button>
                    </form>
                    <p style="text-align:center; font-size:0.8rem; margin-top:15px; opacity:0.8;">
                        <i class="fas fa-lock"></i> {ui.get('secure', 'Secure & Confidential')}
                    </p>
                </div>
            </div>"""

    if hero_variant == "centered_cta":
        form_col = ""

    return f"""
    <section class="hero hv-{hero_variant}" style="background-image: url('{hero_img_url}');">
        <div class="hero-overlay"></div>
        <div class="container hero-content">
            {text_col}
            {form_col}
        </div>
    </section>
    """

def build_infographic_section(features, b_data):
    """Why Choose Us — 3 seeded premium skins: icon_circle / stat_band / numbered_minimal."""
    ui = b_data.get('ui', {})
    target_lang = b_data.get('target_lang', 'en')

    if not features or len(features) == 0:
        if target_lang == 'ar':
            features = [
                {"title": "فريق خبير", "desc": "متخصصون معتمدون يتمتعون بتدريب مكثف. يخضع فريقنا للتعليم المستمر لمواكبة اتجاهات الصناعة وتقديم حلول متطورة لعملك.", "icon": "mdi:account-tie", "stat": "10+ سنوات"},
                {"title": "مواد عالية الجودة", "desc": "نحن نستخدم فقط المواد الممتازة لنتائج دائمة. يتم إكمال كل مشروع بمستلزمات عالية الجودة ورقابة صارمة لضمان رضاك التام.", "icon": "mdi:trophy", "stat": "ممتاز"},
                {"title": "استجابة سريعة", "desc": "خدمات الطوارئ متاحة 24/7. عندما تحتاج إلى مساعدة، يستجيب فريقنا في غضون 60 دقيقة لتقليل التعطيل في منزلك أو عملك.", "icon": "mdi:clock-outline", "stat": "24/7"}
            ]
        else:
            features = [
                {"title": "Expert Team", "desc": "Certified professionals with extensive training. Our team undergoes continuous education to stay ahead of industry trends and deliver cutting-edge solutions for your business.", "icon": "mdi:account-tie", "stat": "10+ Years"},
                {"title": "Quality Materials", "desc": "We use only premium materials for lasting results. Every project is completed with top-grade supplies and rigorous quality control to ensure your complete satisfaction.", "icon": "mdi:trophy", "stat": "Premium"},
                {"title": "Fast Response", "desc": "Emergency services available 24/7. When you need help, our team responds within 60 minutes to minimize disruption to your home or business.", "icon": "mdi:clock-outline", "stat": "24/7"}
            ]

    if len(features) < 3:
        if target_lang == 'ar':
            fallbacks = [
                {"title": "رضا مضمون", "desc": "نحن ندعم عملنا بضمان الرضا بنسبة 100%. إذا لم تكن راضيًا عن النتائج، فسنقوم بتصحيح الأمر.", "icon": "mdi:shield-check", "stat": "100%"},
                {"title": "خبراء معتمدون", "desc": "جميع المتخصصين لدينا مرخصون ومؤمنون بالكامل. يمكنك الثقة في أن مشروعك في أيدٍ أمينة ومعتمدة.", "icon": "mdi:certificate", "stat": "معتمد"}
            ]
        else:
            fallbacks = [
                {"title": "Satisfaction Guaranteed", "desc": "We stand behind our work with a 100% satisfaction guarantee. If you're not happy with the results, we'll make it right.", "icon": "mdi:shield-check", "stat": "100%"},
                {"title": "Certified Experts", "desc": "All our professionals are fully licensed, bonded, and insured. You can trust that your project is in capable hands.", "icon": "mdi:certificate", "stat": "Certified"}
            ]
        for i in range(3 - len(features)):
            if i < len(fallbacks):
                features.append(fallbacks[i])

    display_features = features[:3]

    # ── SEO: primary keyword heading mein (same as before) ──
    _kw = ""
    try:
        _kw_data = extract_keyword_tiers(
            b_data, b_data.get("industry", ""), b_data.get("industry", ""),
            b_data.get("city") or b_data.get("country", ""),
            b_data.get("target_lang", "en"))
        _kw = (_kw_data.get("high_intent") or [""])[0]
    except Exception:
        pass

    _why_label = ui.get("why_choose", "Why Choose Us?")
    if _kw and target_lang != 'ar':
        _why_label = f"Why Choose Us for {_kw.title()}?"

    # ── 💎 SKIN SELECT: 0=classic icon circles, 1=stat band, 2=numbered minimal ──
    _skin = (b_data.get('site_seed', 0) + 5) % 3

    def _norm_icon(f):
        i = f.get('icon', 'mdi:star-circle')
        i = i.replace('fa-', '').replace('fas ', '').replace('fab ', '')
        return i if i.startswith('mdi:') else f"mdi:{i}"

    # Header (sub-line same SEO logic)
    html = '<section class="section"><div class="container">'
    html += f'<h2 style="text-align:center; margin-bottom:12px; color:var(--primary); font-size:2.2rem;">{_why_label}</h2>'
    if _kw and target_lang != 'ar':
        _city = b_data.get("city") or b_data.get("country", "")
        html += f'<p style="text-align:center;color:var(--text-gray);margin-bottom:40px;font-size:1.05rem;">Trusted {b_data.get("industry","service").lower()} professionals serving {_city}</p>'
    else:
        html += '<div style="margin-bottom:40px;"></div>'

    if _skin == 1:
        # ══ SKIN 1: STAT BAND — premium horizontal rows ══
        rows = ""
        for f in display_features:
            icon  = _norm_icon(f)
            title = strip_markdown(f.get('title', 'Expert Service'))
            desc  = strip_markdown(f.get('desc', 'Professional quality work.'))
            stat  = strip_markdown(f.get('stat', '15+ Years'))
            rows += f'''
            <div style="display:flex; align-items:center; gap:24px; background:white; border:1px solid #e2e8f0; border-radius:16px; padding:24px 28px; box-shadow:0 4px 15px rgba(0,0,0,0.05); flex-wrap:wrap;">
                <div style="font-size:2.1rem; font-weight:800; color:var(--primary); min-width:110px; text-align:center; font-family:var(--font-primary);">{stat}</div>
                <div style="width:54px; height:54px; border-radius:14px; background:linear-gradient(135deg, var(--accent) 0%, var(--primary) 100%); display:flex; align-items:center; justify-content:center; flex-shrink:0; color:white;">
                    <span class="iconify" data-icon="{icon}" data-width="28"></span>
                </div>
                <div style="flex:1; min-width:220px;">
                    <h4 style="margin:0 0 6px; color:var(--text-dark); font-size:1.15rem;">{title}</h4>
                    <p style="margin:0; color:var(--text-gray); font-size:0.95rem; line-height:1.65;">{desc}</p>
                </div>
            </div>'''
        html += f'<div style="display:flex; flex-direction:column; gap:16px; max-width:880px; margin:0 auto;">{rows}</div>'

    elif _skin == 2:
        # ══ SKIN 2: NUMBERED MINIMAL — premium clean cards ══
        num_side = 'left' if target_lang == 'ar' else 'right'
        cards = ""
        for idx, f in enumerate(display_features):
            icon  = _norm_icon(f)
            title = strip_markdown(f.get('title', 'Expert Service'))
            desc  = strip_markdown(f.get('desc', 'Professional quality work.'))
            stat  = strip_markdown(f.get('stat', '15+ Years'))
            cards += f'''
            <div style="position:relative; background:white; border:1px solid #e2e8f0; border-top:4px solid var(--primary); border-radius:14px; padding:30px 24px 26px; box-shadow:0 4px 15px rgba(0,0,0,0.05);">
                <div style="position:absolute; top:14px; {num_side}:18px; font-size:2.6rem; font-weight:800; color:var(--primary); opacity:0.12; line-height:1; font-family:var(--font-primary);">0{idx+1}</div>
                <span class="iconify" data-icon="{icon}" data-width="34" style="color:var(--primary);"></span>
                <div style="font-size:1.4rem; font-weight:800; color:var(--primary); margin:12px 0 4px; font-family:var(--font-primary);">{stat}</div>
                <h4 style="margin:0 0 8px; color:var(--text-dark); font-size:1.15rem;">{title}</h4>
                <p style="margin:0; color:var(--text-gray); font-size:0.95rem; line-height:1.65;">{desc}</p>
            </div>'''
        html += f'<div class="infographic-grid">{cards}</div>'

    else:
        # ══ SKIN 0: CLASSIC ICON CIRCLES (purana design) ══
        html += '<div class="infographic-grid">'
        for f in display_features:
            icon  = _norm_icon(f)
            title = strip_markdown(f.get('title', 'Expert Service'))
            desc  = strip_markdown(f.get('desc', 'Professional quality work with guaranteed satisfaction.'))
            stat  = strip_markdown(f.get('stat', '15+ Years'))
            html += f"""
            <div class="infographic-item">
                <div class="infographic-icon">
                    <span class="iconify" data-icon="{icon}" data-width="40" data-height="40"></span>
                </div>
                <div class="infographic-number">{stat}</div>
                <h4>{title}</h4>
                <div class="v360-desc-text">{desc}</div>
            </div>
            """
        html += '</div>'

    html += '</div></section>'
    return html
def build_internal_links_section(b_data, service_name, page_type="child"):
    """Build internal links section for SEO using uniform, mobile-friendly horizontal cards with Iconify."""
    mode = b_data.get('mode', '3')
    if not Config.GENERATE_INTERNAL_LINKS:
        return ""          # always respect the toggle, Mode 1 is no exception
    
    global SERVICE_HIERARCHY
    city_display = b_data.get('city') if b_data.get('city') else b_data.get('country')
    target_lang = b_data.get('target_lang', 'en')
    ui = b_data.get('ui', {})
    industry = clean_title(b_data.get('industry', 'Services'))

    # 🌍 RTL Arrow Logic mapped to a guaranteed MDI icon
    arrow_icon = "mdi:arrow-left" if target_lang == 'ar' else "mdi:arrow-right"
    text_align = "right" if target_lang == 'ar' else "left"

    if page_type == "home" and SERVICE_HIERARCHY:
        # Language-aware home page section
        if target_lang == 'ar':
            section_title = "استكشف فئات خدماتنا"
            section_desc = f"تصفح جميع فئات خدمات {b_data.get('industry', '')} الشاملة"
            services_plural = "خدمات"
            available_text_template = "{count} {services} متاحة"
        else:
            section_title = "Explore Our Service Categories"
            section_desc = f"Browse our comprehensive {b_data.get('industry', '')} service categories"
            services_plural = "services"
            available_text_template = "{count} {services} available"
        
        html = '<section class="internal-links-section"><div class="container">'
        html += f'<div style="background:linear-gradient(135deg, #f8fafc 0%, white 100%); border-radius:20px; padding:40px; border: 1px solid #eef2ff;">'
        html += f'<h3 style="margin-bottom:25px; color:var(--primary); font-size:1.8rem; display:flex; align-items:center; gap:10px;"><span class="iconify" data-icon="mdi:sitemap" data-width="30"></span> {section_title}</h3>'
        html += f'<p style="color:var(--text-gray); margin-bottom:30px;">{section_desc}.</p>'
        
        html += '<div class="internal-links-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">'
        
        category_count = 0
        for cat_name, cat_data in SERVICE_HIERARCHY.items():
            if category_count >= 6:
                break
            description = cat_data.get('description', f'Professional {clean_title(cat_name)} services')[:80]
            children_count = len(cat_data.get('children', []))
            
            cat_link = validate_url("category", cat_name, mode)
            available_text = available_text_template.format(count=children_count, services=services_plural)
            
            # CALLING THE DYNAMIC ICON MAPPER HERE
            cat_icon = get_dynamic_icon(cat_name) 
            
            html += f'''
            <div class="pro-internal-link" style="position: relative; display: flex; align-items: flex-start; background: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eef2ff; box-shadow: 0 4px 15px rgba(0,0,0,0.03); gap: 16px; width: 100%; transition: all 0.3s ease;">
                <a href="{cat_link}" style="position: absolute; inset: 0; z-index: 10;"></a>
                
                <div class="pro-link-icon" style="width: 50px; height: 50px; border-radius: 12px; background: rgba(26, 115, 232, 0.08); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                    <span class="iconify" data-icon="{cat_icon}" data-width="26" style="color: var(--primary);"></span>
                </div>
                
                <div class="pro-link-text" style="flex-grow: 1; min-width: 0; text-align: {text_align}; padding-top: 2px;">
                    <h4 style="margin: 0 0 6px 0; font-size: 1.1rem; color: #0f172a; font-weight: 700; line-height: 1.3;">{clean_title(cat_name)}</h4>
                    <p style="margin: 0; font-size: 0.9rem; color: #64748b; line-height: 1.5;">
                        <span style="display: inline-block; background: #f0fdf4; color: #16a34a; padding: 2px 8px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; margin-right: 6px; margin-bottom: 4px;">{available_text}</span>
                        {description}...
                    </p>
                </div>
                
                <div class="pro-link-arrow" style="flex-shrink: 0; display: flex; align-items: center; height: 50px;">
                    <span class="iconify" data-icon="{arrow_icon}" data-width="20" style="color: #cbd5e1;"></span>
                </div>
            </div>
            '''
            category_count += 1
        
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
        
        html = '<section class="internal-links-section"><div class="container">'
        html += '<div style="background:linear-gradient(135deg, #f8fafc 0%, white 100%); border-radius:20px; padding:40px; border: 1px solid #eef2ff;">'
        
        # Language-aware child services section
        if children:
            if target_lang == 'ar':
                child_title = f"خدمات {clean_title(service_name)} المتخصصة"
                child_desc = "استكشف خدماتنا المتخصصة"
                expert_text = "خدمات خبراء"
            else:
                child_title = f"Related {clean_title(service_name)} Services"
                child_desc = "Explore our specialized services"
                expert_text = "Expert"
            
            html += f'''
            <h3 style="margin-bottom: 25px; color: var(--primary); font-size: 1.8rem; display:flex; align-items:center; gap:10px;">
                <span class="iconify" data-icon="mdi:arrow-down-right" data-width="28"></span> {child_title}
            </h3>
            <p style="color: var(--text-gray); margin-bottom: 30px; font-size: 1.1rem;">
                {child_desc}.
            </p>
            <div class="internal-links-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom:40px;">
            '''
            
            for child in children[:6]:
                child_link = validate_url("service", child, mode)
                child_icon = get_dynamic_icon(child)
                
                if target_lang == 'ar':
                    service_text = f"خدمات {clean_title(child)}"
                else:
                    service_text = f"{clean_title(child)} services"
                
                html += f'''
                <div class="pro-internal-link" style="position: relative; display: flex; align-items: flex-start; background: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eef2ff; box-shadow: 0 4px 15px rgba(0,0,0,0.03); gap: 16px; width: 100%; transition: all 0.3s ease;">
                    <a href="{child_link}" style="position: absolute; inset: 0; z-index: 10;"></a>
                    
                    <div class="pro-link-icon" style="width: 50px; height: 50px; border-radius: 12px; background: rgba(26, 115, 232, 0.08); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                        <span class="iconify" data-icon="{child_icon}" data-width="26" style="color: var(--primary);"></span>
                    </div>
                    
                    <div class="pro-link-text" style="flex-grow: 1; min-width: 0; text-align: {text_align}; display: flex; flex-direction: column; justify-content: center; min-height: 50px;">
                        <h4 style="margin: 0; font-size: 1.05rem; color: #0f172a; font-weight: 600; line-height: 1.3;">{clean_title(child)}</h4>
                        <p style="margin: 0; font-size: 0.9rem; color: #64748b; line-height: 1.5; padding-top: 4px;">
                            {expert_text} {service_text} {f"في {city_display}" if target_lang == 'ar' else f"in {city_display}"}
                        </p>
                    </div>
                    
                    <div class="pro-link-arrow" style="flex-shrink: 0; display: flex; align-items: center; height: 50px;">
                        <span class="iconify" data-icon="{arrow_icon}" data-width="20" style="color: #cbd5e1;"></span>
                    </div>
                </div>
                '''
            
            html += '</div>'
        
        # Language-aware sibling services section
        if siblings:
            if children:
                html += '<div style="margin-top: 40px;">'
            
            category_clean = category.replace(" Services", "").strip()
            
            if target_lang == 'ar':
                if category_clean:
                    sibling_title = f"خدمات {clean_title(category_clean)} الأخرى"
                else:
                    sibling_title = "الخدمات الأخرى ذات الصلة"
                sibling_desc = "استكشف الخدمات ذات الصلة"
                professional_text = "حلول احترافية"
            else:
                if category_clean:
                    sibling_title = f"Other {clean_title(category_clean)} Services"
                else:
                    sibling_title = "Other Related Services"
                sibling_desc = "Explore related services"
                professional_text = "Professional solutions"
            
            html += f'''
            <h3 style="margin-bottom: 25px; color: var(--primary); font-size: 1.8rem; display:flex; align-items:center; gap:10px;">
                <span class="iconify" data-icon="mdi:view-grid-plus-outline" data-width="28"></span> {sibling_title}
            </h3>
            <p style="color: var(--text-gray); margin-bottom: 30px; font-size: 1.1rem;">
                {sibling_desc}.
            </p>
            <div class="internal-links-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">
            '''
            
            for sibling in siblings[:6]:
                if sibling.lower() != service_name.lower():
                    sibling_link = validate_url("service", sibling, mode)
                    sibling_icon = get_dynamic_icon(sibling)
                    
                    if target_lang == 'ar':
                        service_text = f"لـ {clean_title(sibling)}"
                    else:
                        service_text = f"for {clean_title(sibling)}"
                    
                    html += f'''
                    <div class="pro-internal-link" style="position: relative; display: flex; align-items: flex-start; background: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eef2ff; box-shadow: 0 4px 15px rgba(0,0,0,0.03); gap: 16px; width: 100%; transition: all 0.3s ease;">
                        <a href="{sibling_link}" style="position: absolute; inset: 0; z-index: 10;"></a>
                        
                        <div class="pro-link-icon" style="width: 50px; height: 50px; border-radius: 12px; background: rgba(26, 115, 232, 0.08); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                            <span class="iconify" data-icon="{sibling_icon}" data-width="26" style="color: var(--primary);"></span>
                        </div>
                        
                        <div class="pro-link-text" style="flex-grow: 1; min-width: 0; text-align: {text_align}; display: flex; flex-direction: column; justify-content: center; min-height: 50px;">
                            <h4 style="margin: 0; font-size: 1.05rem; color: #0f172a; font-weight: 600; line-height: 1.3;">{clean_title(sibling)}</h4>
                            <p style="margin: 0; font-size: 0.9rem; color: #64748b; line-height: 1.5; padding-top: 4px;">
                                {professional_text} {service_text}
                            </p>
                        </div>
                        
                        <div class="pro-link-arrow" style="flex-shrink: 0; display: flex; align-items: center; height: 50px;">
                            <span class="iconify" data-icon="{arrow_icon}" data-width="20" style="color: #cbd5e1;"></span>
                        </div>
                    </div>
                    '''
            
            html += '</div>'
            if children:
                html += '</div>'
        
        html += '</div></div></section>'
        return html
    
    return ""
def build_zigzag_section(b_data, items, section_title, limit=6, is_child_page=False, current_service=None, is_category_page=False, category_name=None, url_type="service"):
    """Build zigzag layout section with Iconify support and clean URL routing."""
    if not items: return ""
    
    ui = b_data.get('ui', {})
    target_lang = b_data.get('target_lang', 'en')
    mode = b_data.get('mode', '3')
    
    # 🌍 RTL Arrow Logic
    arrow_icon = "mdi:arrow-left" if target_lang == 'ar' else "mdi:arrow-right"
    
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
        
        # 🔗 Image Generation uses raw English item
        img = get_hosted_image(item, "zigzag", b_data.get('industry', ''), is_category=False, service_name=item)
        
        related_services = relationships.get('siblings', [])[:3]
        if not related_services and Config.GENERATE_INTERNAL_LINKS:
            flat_list = b_data.get('flat_services_list', [])
            if flat_list and len(flat_list) > 3:
                related_services = [s for s in random.sample(flat_list, min(len(flat_list), 4)) if s != item][:3]
        
        if mode == "1" and current_service and item == current_service:
            related_services = generate_sub_services(b_data, current_service)[:3]
        
        page_seed = f"{item}_{i}_{random.randint(1,1000)}"
        zigzag_content = generate_zigzag_content_with_links(
            b_data, item, category, is_child_page, related_services=related_services, page_seed=page_seed
        )
        
        # 🌐 UI Translation: Ensure AI title falls back to translated Arabic
        raw_title = zigzag_content.get('title', clean_title(item))
        title_text =  escape(raw_title)
        desc_text = zigzag_content.get('description', '')
        
        sentences = desc_text.split('. ')
        if len(sentences) < 6:
            # 🌐 DYNAMIC MULTI-LANGUAGE FALLBACK: Use clean_title for Arabic rendering
            item_clean = clean_title(item)
            if target_lang == 'ar':
                additional = [
                    f"يتوفر أخصائيو {item_clean} لدينا على مدار الساعة طوال أيام الأسبوع للمكالمات الطارئة.",
                    f"نحن نقدم تقديرات مجانية وأسعار تنافسية لجميع مشاريع {item_clean}.",
                    f"رضا العملاء هو أولويتنا القصوى في كل خدمة {item_clean} نقدمها.",
                    f"نستخدم أحدث المعدات والتقنيات لتحقيق النتائج المثالية في {item_clean}.",
                    f"جميع أعمالنا في {item_clean} مدعومة بضمانات شاملة.",
                    f"اتصل بنا اليوم لجدولة استشارة {item_clean} الخاصة بك."
                ]
            else:
                additional = [
                    f"Our {item_clean} specialists are available 24/7 for emergency calls.",
                    f"We provide free estimates and competitive pricing for all {item_clean} projects.",
                    f"Customer satisfaction is our top priority with every {item_clean} service we deliver.",
                    f"We use the latest equipment and techniques for optimal results in {item_clean}.",
                    f"All our {item_clean} work is backed by comprehensive warranties.",
                    f"Contact us today to schedule your {item_clean} consultation."
                ]
            desc_text = '. '.join(sentences + additional[:6-len(sentences)])
        
        # --- NEW PARAGRAPH LOGIC (Replaces bullet_points) ---
        # AI uses <br><br> as instructed, so we split by that instead of \n\n
        paragraphs = [p.strip() for p in desc_text.split('<br><br>') if p.strip()]
        if not paragraphs:
            paragraphs = [desc_text]
        prose_html = ""
        for para in paragraphs:
            prose_html += f'<p style="color: var(--text-gray); font-size: 1.1rem; line-height: 1.8; margin-bottom: 20px;">{para}</p>'
        
        # 🔗 CRITICAL URL FIX: Route dynamically using raw English 'item' and 'url_type'
        # Set defaults first
        link = validate_url(url_type, item, mode)
        btn_class = "btn-primary"
        btn_disabled = ''
        btn_text = service_btn_label(item, target_lang)
        
        # Override if this is the current active service
        if is_child_page and title_text.lower() == clean_title(current_service or "").lower():
            link = "#"
            btn_text = ui.get('current_svc', 'Current Service' if target_lang != 'ar' else 'الخدمة الحالية')
            btn_disabled = 'style="opacity:0.7; cursor:default;"'

        # 💎 MODE 1 FIX: zigzag items = sub-services on SAME page. Pages exist
        # nahi karte, isliye sab buttons WhatsApp pe route (404 khatam, lead aata hai).
        if mode == "1":
            from urllib.parse import quote as _q
            _wa  = b_data.get('whatsapp', '')
            _msg = _q(f"Hi! I'm interested in {clean_title(item)}. Please share details and price.")
            link = f"https://wa.me/{_wa}?text={_msg}"
            btn_text = ui.get('get_quote',
                              'احصل على عرض سعر' if target_lang == 'ar' else 'Get Free Quote')
            btn_class = "btn-primary"
            btn_disabled = ''
        
        html += f'''
        <div class="zigzag-item {rev}">
            <div class="zigzag-content">
                <h3>{title_text}</h3>
                <div class="service-description">
                    {prose_html}
                </div>
                <a href="{link}" class="btn {btn_class}" {btn_disabled} rel="dofollow" aria-label="{btn_text} - {title_text}">
                    <span class="iconify" data-icon="{arrow_icon}" data-width="20" style="margin-right: 8px;"></span> {btn_text}
                </a>
            </div>
            <div class="zigzag-img-wrap">
                <img src="{img}" class="zigzag-img" loading="lazy" 
                     alt="{title_text} - {ui.get('licensed', 'Professional Service' if target_lang != 'ar' else 'خدمة احترافية')}" 
                     title="{btn_text} - {title_text}">
            </div>
        </div>
        '''
    
    html += '</div></section>'
    return html
def build_areas_served(b_data, neighborhoods):
    """Build areas served section with full language support."""
    if not neighborhoods:
        return ""
    
    # Get the UI dictionary for translations
    ui = b_data.get('ui', {})
    city_display = b_data.get('city') if b_data.get('city') else b_data.get('country')
    target_lang = b_data.get('target_lang', 'en')
    
    # Automatically translate the subtext based on the target language
    if target_lang == 'ar':
        subtext = f"نقدم خدمات {b_data.get('industry', '')} احترافية في جميع الأحياء الرئيسية."
        footer_text = "نخدم جميع المناطق المحيطة - اتصل لمعرفة التوافر!"
        area_icon_margin = "margin-left:5px;"  # RTL adjustment
    else:
        subtext = f"Providing professional {b_data.get('industry', '')} services across all major neighborhoods."
        footer_text = "Serving all surrounding areas - Call for availability!"
        area_icon_margin = "margin-right:5px;"

    html = f'''
    <section class="section">
        <div class="container" style="text-align:center;">
            <h2 style="margin-bottom:20px; font-size:2rem;">{ui.get('areas', 'Areas We Serve in')} {city_display}</h2>
            <p style="color:var(--text-gray); margin-bottom:40px; font-size:1.1rem;">
                {subtext}
            </p>
            <div class="pill-container" style="display: flex; flex-wrap: wrap; gap: 12px; justify-content: center;">
    '''
    
    for area in neighborhoods[:12]:
        html += f'<div class="pill" style="background: white; border: 1px solid #e2e8f0; padding: 10px 22px; border-radius: 50px; font-size: 0.9rem; color: var(--text-gray); transition: all 0.3s; font-weight: 500;"><i class="fas fa-map-marker-alt" style="{area_icon_margin} color:var(--primary);"></i>{area}</div>'
    
    html += f'''
            </div>
            <p style="margin-top:30px; color:var(--text-gray); font-size:0.95rem;">
                <i class="fas fa-truck"></i> {footer_text}
            </p>
        </div>
    </section>
    '''
    return html
def build_faq_section(faqs, service_name, b_data=None):
    """Build FAQ section using native <details>/<summary> — Google Helpful Content safe."""
    ui = b_data.get('ui', {}) if b_data else {}
    target_lang = b_data.get('target_lang', 'en') if b_data else 'en'
    clean_srv = clean_title(service_name) if service_name else ui.get('services', 'services')

    if not faqs or len(faqs) < 5:
        if b_data and service_name:
            faqs = generate_service_faqs(b_data, service_name, "General")
        else:
            faqs = [
                {"q": "What areas do you serve?", "a": "We provide comprehensive service coverage throughout the city and surrounding areas."},
                {"q": "How quickly can you respond?", "a": "Emergency service available within 60 minutes. Standard appointments within 24 hours."},
                {"q": "Are you licensed and insured?", "a": "Yes, all our technicians are fully licensed, bonded, and insured."},
                {"q": "What makes your service different?", "a": "We combine deep expertise, premium materials, and a customer-first approach on every job."},
                {"q": "Do you offer warranties?", "a": "Yes, all work comes with a comprehensive warranty covering parts and labour."}
            ] if target_lang != 'ar' else [
                {"q": "ما هي المناطق التي تخدمونها؟", "a": "نقدم تغطية خدمات شاملة في جميع أنحاء المدينة والمناطق المجاورة."},
                {"q": "ما مدى سرعة استجابتكم؟", "a": "خدمة الطوارئ خلال 60 دقيقة، والمواعيد العادية خلال 24 ساعة."},
                {"q": "هل أنتم مرخصون ومؤمنون؟", "a": "نعم، جميع الفنيين لدينا مرخصون ومؤمنون بالكامل."},
                {"q": "ما الذي يميز خدماتكم؟", "a": "نجمع بين الخبرة والجودة والتركيز على رضا العملاء في كل عمل."},
                {"q": "هل تقدمون ضمانات؟", "a": "نعم، جميع أعمالنا مضمونة بضمان شامل للقطع والعمالة."}
            ]

    faqs = faqs[:5]

    faq_html = ""
    for i, f in enumerate(faqs):
        question = strip_markdown(f.get('q', f.get('question', 'Question')))
        answer   = strip_markdown(f.get('a', f.get('answer', 'Professional service with guaranteed satisfaction.')))
        open_attr = " open" if i == 0 else "" 

        faq_html += f"""
        <details{open_attr} style="margin-bottom:12px; background:white; border-radius:12px; border:1px solid #e2e8f0; box-shadow:0 2px 8px rgba(0,0,0,0.04); overflow:hidden;">
            <summary style="padding:20px 24px; cursor:pointer; font-weight:600; font-size:1.05rem; color:var(--text-dark); background:#f8fafc; list-style:none; display:flex; justify-content:space-between; align-items:center;">
                <div style="margin:0; font-size:1.05rem; font-weight:600; color:var(--text-dark);">{question}</div>
                <span style="flex-shrink:0; margin-left:16px; color:var(--primary); font-size:1.2rem; transition:transform 0.2s;">&#9660;</span>
            </summary>
            <div style="padding:16px 24px 20px; color:var(--text-gray); line-height:1.75; font-size:0.97rem;">
                {answer}
            </div>
        </details>
        """

    faq_label = ui.get('faq', 'Frequently Asked Questions' if target_lang != 'ar' else 'الأسئلة الشائعة')
    more_qs   = ui.get('more_qs', 'Have more questions? Call us anytime!' if target_lang != 'ar' else 'لديك أسئلة أخرى؟ اتصل بنا!')

    extra_css = """
    <style>
    details[open] > summary span { transform: rotate(180deg); display: inline-block; }
    details > summary::-webkit-details-marker { display: none; }
    </style>
    """

    # ── 💎 FAQ SKIN: 0 = single column (classic), 1 = 2-column wide (premium) ──
    _fq_seed = b_data.get('site_seed', 0) if b_data else 0
    _fq_skin = (_fq_seed + 17) % 2
    if _fq_skin == 1:
        _wrap_open  = '<div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:0 20px; align-items:start;">'
        _wrap_close = '</div>'
        _maxw = "1050px"
    else:
        _wrap_open, _wrap_close, _maxw = "", "", "820px"

    return f"""
    {extra_css}
    <section class="section">
        <div class="container" style="max-width:{_maxw}; margin:0 auto;">
            <h2 style="text-align:center; margin-bottom:36px; font-size:2rem; color:var(--primary);">
                {faq_label}
            </h2>
            {_wrap_open}{faq_html}{_wrap_close}
            <p style="text-align:center; margin-top:28px; color:#64748b; font-size:0.97rem; font-weight:500;">
                <span class="iconify" data-icon="mdi:message-text-outline" data-width="18" style="color:var(--accent); margin-right:6px;"></span>
                {more_qs}
            </p>
        </div>
    </section>
    """
def build_contact_html(b_data):
    """Build contact page HTML."""
    ui = b_data.get('ui', {})
    city_display = b_data.get('city') if b_data.get('city') else b_data.get('country')
    
    form_html = f'''
    <div class="glass-card" style="background:white; border:1px solid #e2e8f0; max-width:600px; margin:0 auto; box-shadow:0 10px 30px rgba(0,0,0,0.05);">
        <h3 style="margin-bottom:20px; color:var(--text-dark); font-size:1.8rem; text-align:center;">
            <i class="fas fa-envelope"></i> {ui.get('send_msg', 'Send a Message')}
        </h3>
        <form onsubmit="handleLead(event)">
            <input type="text" id="name" style="width:100%; padding:14px; margin-bottom:15px; border-radius:10px; border:1px solid #cbd5e1; font-size:1rem;" placeholder="{ui.get('name_ph', 'Name')}" required>
            <input type="email" id="email" style="width:100%; padding:14px; margin-bottom:15px; border-radius:10px; border:1px solid #cbd5e1; font-size:1rem;" placeholder="{ui.get('email_ph', 'Email')}" required>
            <input type="text" id="phone" style="width:100%; padding:14px; margin-bottom:15px; border-radius:10px; border:1px solid #cbd5e1; font-size:1rem;" placeholder="{ui.get('phone_ph', 'Phone')}" required>
            <input type="text" id="loc" style="width:100%; padding:14px; margin-bottom:15px; border-radius:10px; border:1px solid #cbd5e1; font-size:1rem;" placeholder="{ui.get('city_ph', 'City')}" required>
            <textarea id="svc" style="width:100%; padding:14px; margin-bottom:20px; border-radius:10px; border:1px solid #cbd5e1; font-size:1rem; min-height:120px;" placeholder="{ui.get('needs_ph', 'Your needs')}" required></textarea>
            <button type="submit" class="btn btn-primary btn-submit" style="width:100%;">
                <i class="fas fa-paper-plane"></i> {ui.get('send', 'Send')}
            </button>
        </form>
    </div>
    '''

    html = f'''
    <section class="section">
        <div class="container">
            <div class="infographic-grid" style="margin-bottom:60px;">
                <div class="infographic-item">
                    <div class="infographic-icon"><i class="fas fa-phone-alt"></i></div>
                    <h4>{ui.get('call_us', 'Call Us')}</h4>
                    <p><a href="tel:{b_data['phone']}" style="color:var(--text-gray); text-decoration:none;">{b_data['phone']}</a></p>
                </div>
                <div class="infographic-item">
                    <div class="infographic-icon"><i class="fab fa-whatsapp"></i></div>
                    <h4>{ui.get('whatsapp', 'WhatsApp')}</h4>
                    <p><a href="https://wa.me/{b_data['whatsapp']}" target="_blank" style="color:var(--text-gray); text-decoration:none;">{ui.get('whatsapp', 'WhatsApp')}</a></p>
                </div>
                <div class="infographic-item">
                    <div class="infographic-icon"><i class="fas fa-map-marker-alt"></i></div>
                    <h4>{ui.get('visit_us', 'Visit Us')}</h4>
                    <p>{city_display}, {b_data['country']}</p>
                </div>
            </div>
            {form_html}
        </div>
    </section>
    '''
    return html

# ==============================================================================
# 🦶 FOOTER BUILDER - WITH SEOBLOGY CREDIT & GOOGLE MAP
# ==============================================================================
def build_enhanced_footer(b_data, structure=None):
    """Build enhanced footer with Iconify Support and Global Sticky Lead Buttons."""
    ui = b_data.get('ui', {})

    # MODE 1 FUNNEL FOOTER
    if b_data.get('mode') == "1":
        funnel_footer = f"""
<footer style="background:#1e293b; color:#94a3b8; padding:30px 20px; margin-top:60px;">
    <div style="max-width:1200px; margin:0 auto;">
        <div style="display:flex; flex-wrap:wrap; gap:12px; justify-content:center; margin-bottom:24px;">
            <a href="tel:{b_data.get('phone','')}" 
               style="display:inline-flex; align-items:center; gap:8px; background:var(--primary,#1A73E8); color:white; padding:14px 28px; border-radius:50px; font-weight:700; text-decoration:none; font-size:1rem;">
                <i class="fas fa-phone-alt"></i> {b_data.get('phone','')}
            </a>
            <a href="https://wa.me/{b_data.get('whatsapp','')}" target="_blank"
               style="display:inline-flex; align-items:center; gap:8px; background:#25D366; color:white; padding:14px 28px; border-radius:50px; font-weight:700; text-decoration:none; font-size:1rem;">
                <i class="fab fa-whatsapp"></i> WhatsApp Us
            </a>
        </div>
        <p style="text-align:center; font-size:0.85rem; margin:0;">
            &copy; <span id="current-year">{datetime.now().year}</span> {b_data.get('name','')}. All rights reserved.
            &nbsp;|&nbsp;
            ⚡ Developed by <a href="https://seoblogy.com/" target="_blank" rel="dofollow" style="color:#FFD700; text-decoration:none; font-weight:bold;">SEOBLOGY.COM</a>
        </p>
    </div>
</footer>
<a href="tel:{b_data.get('phone','')}" class="v360-sticky-btn v360-sticky-phone" aria-label="Call Us">
    <span class="iconify" data-icon="mdi:phone-in-talk" data-width="30"></span>
</a>
<a href="https://wa.me/{b_data.get('whatsapp','')}" class="v360-sticky-btn v360-sticky-wa" target="_blank" rel="noopener noreferrer" aria-label="WhatsApp Us">
    <span class="iconify" data-icon="mdi:whatsapp" data-width="34"></span>
</a>
<style>
.v360-sticky-btn {{
    position:fixed; bottom:25px; width:60px; height:60px; border-radius:50%;
    display:flex; align-items:center; justify-content:center; color:white;
    box-shadow:0 4px 15px rgba(0,0,0,0.3); z-index:99999;
    transition:all 0.3s ease; text-decoration:none;
}}
.v360-sticky-phone {{ left:25px; background-color:var(--primary,#1A73E8); animation:v360-pulse-blue 2s infinite; }}
.v360-sticky-wa {{ right:25px; background-color:#25D366; animation:v360-pulse-green 2s infinite; }}
@keyframes v360-pulse-blue {{
    0% {{ box-shadow:0 0 0 0 rgba(26,115,232,0.7); }}
    70% {{ box-shadow:0 0 0 15px rgba(26,115,232,0); }}
    100% {{ box-shadow:0 0 0 0 rgba(26,115,232,0); }}
}}
@keyframes v360-pulse-green {{
    0% {{ box-shadow:0 0 0 0 rgba(37,211,102,0.7); }}
    70% {{ box-shadow:0 0 0 15px rgba(37,211,102,0); }}
    100% {{ box-shadow:0 0 0 0 rgba(37,211,102,0); }}
}}
</style>
"""
        return funnel_footer
    city_display = b_data.get('city') if b_data.get('city') else b_data.get('country')
    target_lang = b_data.get('target_lang', 'en')
    
    # RTL Margin Logic
    icon_margin = "margin-left: 8px;" if target_lang == 'ar' else "margin-right: 8px;"
    arrow_icon = "mdi:chevron-left" if target_lang == 'ar' else "mdi:chevron-right"
    
    social_html = ""
    social_platforms = ['facebook', 'twitter', 'instagram', 'linkedin', 'youtube']
    social_icons = {
        'facebook': 'mdi:facebook',
        'twitter': 'mdi:twitter',
        'instagram': 'mdi:instagram',
        'linkedin': 'mdi:linkedin',
        'youtube': 'mdi:youtube'
    }
    
    for platform in social_platforms:
        url = b_data.get(platform, '#')
        if url and url != '#' and len(url) > 5:
            social_html += f'<a href="{url}" target="_blank" rel="noopener noreferrer" aria-label="{platform.title()}"><span class="iconify" data-icon="{social_icons[platform]}" data-width="20"></span></a>'
    
    footer_links_html = ""
    mode = b_data.get('mode', '3')
    
    # Mode 2 hub: about/contact/blog pages generate nahi hote → sirf safe links
    if mode == "2":
        important_links = {
            ui.get('services', "Services"): validate_url("services_index", None, mode),
            ui.get('contact', "Contact Us"): f"tel:{b_data.get('phone', '')}",
            "Sitemap": "/sitemap.xml"
        }
    else:
        important_links = {
            ui.get('about', "About Us"): validate_url("about", None, mode),
            ui.get('services', "Services"): validate_url("services_index", None, mode),
            ui.get('contact', "Contact Us"): validate_url("contact", None, mode),
            ui.get('blog', "Blog"): validate_url("blog", None, mode),
            "Sitemap": "/sitemap.xml"
        }
    
    for link_name, link_url in important_links.items():
        footer_links_html += f'<li><a href="{link_url}"><span class="iconify" data-icon="{arrow_icon}" style="{icon_margin} color:var(--primary);"></span> {link_name}</a></li>'
    
    locations_footer_html = f"""
    <div class="footer-services">
        <h4>{ui.get('offices', 'Our Offices')}</h4>
        <ul class="footer-locations-list">
            <li><a href="{validate_url('home', None, mode)}"><span class="iconify" data-icon="mdi:map-marker" style="{icon_margin} color:var(--primary);"></span> {ui.get('hq', 'Headquarters')}</a></li>
            <li><a href="{validate_url('services_index', None, mode)}"><span class="iconify" data-icon="mdi:map-marker" style="{icon_margin} color:var(--primary);"></span> {city_display}</a></li>
        </ul>
    </div>
    """

    map_code = b_data.get('map_embed', '')
    if map_code and "<iframe" in map_code:
        map_code = re.sub(r'width="[^"]+"', 'width="100%"', map_code)
        map_code = re.sub(r'height="[^"]+"', 'height="200"', map_code)
        map_code = map_code.replace('<iframe', '<iframe style="border:0; border-radius:10px; margin-top:10px;"')
    
    # 💎 NEW STICKY BUTTON CSS (Injected cleanly so it doesn't touch external files)
    sticky_css = """
    <style>
        .v360-sticky-btn {
            position: fixed;
            bottom: 25px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            z-index: 99999;
            transition: all 0.3s ease;
            text-decoration: none;
        }
        .v360-sticky-btn:hover {
            transform: translateY(-5px) scale(1.05);
            color: white;
        }
        .v360-sticky-phone {
            left: 25px;
            background-color: var(--primary);
            animation: v360-pulse-blue 2s infinite;
        }
        .v360-sticky-wa {
            right: 25px;
            background-color: #25D366;
            animation: v360-pulse-green 2s infinite;
        }
        @keyframes v360-pulse-blue {
            0% { box-shadow: 0 0 0 0 rgba(26, 115, 232, 0.7); }
            70% { box-shadow: 0 0 0 15px rgba(26, 115, 232, 0); }
            100% { box-shadow: 0 0 0 0 rgba(26, 115, 232, 0); }
        }
        @keyframes v360-pulse-green {
            0% { box-shadow: 0 0 0 0 rgba(37, 211, 102, 0.7); }
            70% { box-shadow: 0 0 0 15px rgba(37, 211, 102, 0); }
            100% { box-shadow: 0 0 0 0 rgba(37, 211, 102, 0); }
        }
        @media (max-width: 768px) {
            .v360-sticky-btn { bottom: 20px; width: 55px; height: 55px; }
            .v360-sticky-phone { left: 15px; }
            .v360-sticky-wa { right: 15px; }
        }
    </style>
    """

    # 💎 NEW STICKY BUTTON HTML
    sticky_html = f"""
    {sticky_css}
    <a href="tel:{b_data.get('phone', '')}" class="v360-sticky-btn v360-sticky-phone" aria-label="Call Us">
        <span class="iconify" data-icon="mdi:phone-in-talk" data-width="30"></span>
    </a>
    <a href="https://wa.me/{b_data.get('whatsapp', '')}" class="v360-sticky-btn v360-sticky-wa" target="_blank" rel="noopener noreferrer" aria-label="WhatsApp Us">
        <span class="iconify" data-icon="mdi:whatsapp" data-width="34"></span>
    </a>
    """

    footer = f"""
    <footer class="site-footer">
        <div class="container">
            <div class="footer-grid">
                <div class="footer-info">
                    <h3>{b_data.get('name', '')}</h3>
                    <p>{ui.get('services', 'Professional Services')} - {b_data.get('industry', '')} {city_display}.</p>
                    <div class="social-links">
                        {social_html}
                    </div>
                </div>
                
                <div class="footer-links">
                    <h4>{ui.get('company', 'Company')}</h4>
                    <ul>{footer_links_html}</ul>
                </div>
                
                {locations_footer_html}
                
                <div class="footer-contact">
                    <h4>{ui.get('directions', 'Get Directions')}</h4>
                    <p style="display:flex; align-items:center;"><span class="iconify" data-icon="mdi:phone" style="{icon_margin} color:var(--primary);"></span> <a href="tel:{b_data.get('phone', '')}">{b_data.get('phone', '')}</a></p>
                    <p style="display:flex; align-items:center;"><span class="iconify" data-icon="mdi:map-marker-radius" style="{icon_margin} color:var(--primary);"></span> {city_display}, {b_data.get('country', '')}</p>
                    
                    <div class="footer-map" style="margin-top:15px; width:100%;">
                        {map_code}
                    </div>
                </div>
            </div>
            
            <div class="footer-bottom">
                <div class="copyright-section">
                    <p>&copy; <span id="current-year">{datetime.now().year}</span> {b_data.get('name', '')}. {ui.get('rights', 'All rights reserved.')}</p>
                    <p style="margin-top: 5px; font-size: 0.85rem; opacity: 0.8;">
                        ⚡ Developed by <a href="https://seoblogy.com/" target="_blank" rel="dofollow" style="color: #FFD700; text-decoration: none; font-weight: bold;">SEOBLOGY.COM</a>
                    </p>
                </div>
                <div class="footer-bottom-links">
                    <a href="/sitemap.xml">Sitemap</a>
                </div>
            </div>
        </div>
    </footer>
    {sticky_html}
    """
    return footer
def build_testimonials_section(b_data, reviews, neighborhoods):
    """Testimonials — 2 seeded skins: classic card / premium avatar+verified."""
    if not reviews:
        return ""

    city = b_data.get('city', 'our area')
    target_lang = b_data.get('target_lang', 'en')

    if target_lang == 'ar':
        title_text    = f"ماذا يقول عملاؤنا في {city}"
        sub_text      = "آراء حقيقية من عملائنا المحليين"
        verified_text = "موثوق"
    else:
        title_text    = f"What Our {city} Clients Say"
        sub_text      = "Real feedback from our local customers"
        verified_text = "Verified"

    # ── 💎 SKIN SELECT: 0=classic, 1=avatar premium ──
    _skin = (b_data.get('site_seed', 0) + 11) % 2

    avatar_palette = [
        ("#B5D4F4", "#0C447C"), ("#F4C0D1", "#72243E"),
        ("#C0DD97", "#27500A"), ("#FAC775", "#633806"),
        ("#CECBF6", "#3C3489"),
    ]

    html = f'''
    <section class="section">
        <div class="container">
            <h2 style="text-align:center; margin-bottom:15px; font-size:2.2rem; color:var(--primary);">{title_text}</h2>
            <p style="text-align:center; color:var(--text-gray); margin-bottom:40px; font-size:1.1rem;">{sub_text}</p>
            <div class="service-grid">
    '''

    for ri, rev in enumerate(reviews):
        name = escape(rev.get('name', 'Customer'))
        text = escape(rev.get('txt', 'Great service!'))
        random_location = random.choice(neighborhoods) if neighborhoods else city

        try:
            rating_val = float(str(rev.get('rating', '5')).split('/')[0])
            star_count = max(1, min(5, round(rating_val)))
        except (ValueError, TypeError):
            star_count = 5

        if _skin == 1:
            # ══ SKIN 1: AVATAR PREMIUM ══
            initials = "".join([w[0].upper() for w in name.split()[:2]]) or "C"
            bg, fg = avatar_palette[ri % len(avatar_palette)]
            star_row = "★" * star_count + "☆" * (5 - star_count)
            html += f'''
            <div style="background:white; padding:26px; border-radius:16px; box-shadow:0 4px 15px rgba(0,0,0,0.05); border:1px solid #eef2ff; display:flex; flex-direction:column; height:100%;">
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:14px;">
                    <div style="width:46px; height:46px; border-radius:50%; background:{bg}; color:{fg}; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:15px; flex-shrink:0;">{initials}</div>
                    <div style="flex:1;">
                        <strong style="color:var(--text-dark); display:block; font-size:1rem;">{name}</strong>
                        <span style="color:var(--text-gray); font-size:0.78rem;">📍 {escape(random_location)}</span>
                    </div>
                    <div style="background:#f0fdf4; color:#16a34a; font-size:0.68rem; padding:3px 10px; border-radius:12px; font-weight:600; white-space:nowrap;">✓ {verified_text}</div>
                </div>
                <div style="color:#D97706; font-size:1rem; margin-bottom:12px; letter-spacing:.05em;">{star_row}</div>
                <p style="font-style:italic; color:var(--text-gray); line-height:1.75; flex-grow:1; font-size:0.93rem; margin:0;">"{text}"</p>
            </div>
            '''
        else:
            # ══ SKIN 0: CLASSIC (purana design) ══
            stars_html = '<span class="iconify" data-icon="mdi:star" style="color:var(--gold); font-size:1.3rem;"></span>' * star_count
            empty_stars = 5 - star_count
            if empty_stars > 0:
                stars_html += '<span class="iconify" data-icon="mdi:star-outline" style="color:var(--gold); font-size:1.3rem;"></span>' * empty_stars
            html += f'''
            <div style="background:white; padding:30px; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.05); border:1px solid #eef2ff; display:flex; flex-direction:column; height:100%;">
                <div style="margin-bottom:15px;">{stars_html}</div>
                <p style="font-style:italic; color:var(--text-gray); line-height:1.7; margin-bottom:20px; flex-grow:1; font-size:0.95rem;">"{text}"</p>
                <div style="border-top:1px solid #f1f5f9; padding-top:15px;">
                    <strong style="color:var(--text-dark); display:block; font-size:1.05rem;">{name}</strong>
                    <span style="color:var(--primary); font-size:0.85rem;">{verified_text} — {escape(random_location)}</span>
                </div>
            </div>
            '''

    html += '''
            </div>
        </div>
    </section>
    '''
    return html
# ==============================================================================
# 🔀 SECTION ORDER HELPER — renders a safe middle section by its name
# ==============================================================================
def _render_middle_section(name, b_data, content_data):
    """Render one of the shuffle-safe middle sections by name. Returns HTML string."""
    target_lang = b_data.get('target_lang', 'en')

    if name == "why_choose":
        if content_data.get('why_choose_us'):
            feats = content_data['why_choose_us'][:3]
            return build_infographic_section(feats, b_data)
        else:
            if target_lang == 'ar':
                default_features = [
                    {"title": "فريق خبير", "desc": "متخصصون معتمدون يتمتعون بتدريب مكثف.", "icon": "mdi:account-tie", "stat": "10+ سنوات"},
                    {"title": "مواد عالية الجودة", "desc": "نحن نستخدم فقط المواد الممتازة لنتائج دائمة.", "icon": "mdi:trophy", "stat": "ممتاز"},
                    {"title": "استجابة سريعة", "desc": "خدمات الطوارئ متاحة 24/7.", "icon": "mdi:clock-outline", "stat": "24/7"}
                ]
            else:
                default_features = [
                    {"title": "Expert Team", "desc": "Certified professionals with extensive experience.", "icon": "mdi:account-tie", "stat": "10+ Years"},
                    {"title": "Quality Materials", "desc": "We use only premium materials for lasting results.", "icon": "mdi:trophy", "stat": "Premium"},
                    {"title": "Fast Response", "desc": "Emergency services available 24/7.", "icon": "mdi:clock-outline", "stat": "24/7"}
                ]
            return build_infographic_section(default_features, b_data)

    elif name == "reviews":
        if content_data.get('reviews'):
            areas_list = content_data.get('areas_served', [b_data.get('city', '')])
            return build_testimonials_section(b_data, content_data.get('reviews', []), areas_list)
        return ""

    elif name == "areas":
        return build_areas_served(b_data, content_data.get('areas_served', []))

    elif name == "process_steps":
        from niche_engine import build_service_process_steps, NICHE_PROFILES
        _niche = b_data.get('niche_engine')
        _profile = getattr(_niche, 'profile', NICHE_PROFILES['general']) if _niche else NICHE_PROFILES['general']
        return build_service_process_steps(b_data, _profile)

    elif name == "guarantee_seal":
        from mode1_landing_engine import _s_guarantee_seal, _build_fallback_design
        from mode1_landing_engine import _get_currency, INDUSTRY_PRICE_MULTIPLIER, _detect_niche_key
        _sym, _mult = _get_currency(b_data)
        _pmult = INDUSTRY_PRICE_MULTIPLIER.get(_detect_niche_key(b_data.get('industry', '')), 1.0)
        _svc = (b_data.get('flat_services_list') or ['Services'])[0]
        _design = _build_fallback_design(b_data, _svc, [], _sym, _mult, _pmult)
        return _s_guarantee_seal(b_data, _design, _svc)

    elif name == "internal_links":
        return build_internal_links_section(b_data, "home", "home")

    elif name == "faq":
        return build_faq_section(content_data.get('faqs', []), "", b_data)

    return ""
# ==============================================================================
# 📄 PAGE ASSEMBLER WITH UNIVERSAL HEADER - FIXED FOR ALL MODES
# ==============================================================================
# ==============================================================================
def assemble_page_content(page_type, b_data, structure, content_data, specific_service_name=None, siblings=None, parent_category=None, is_child_page=False, pre_generated_img=None):
    """Assemble complete page content with all sections - FULLY TRANSLATED for all modes"""
    html = ""
    
    # Get UI translations and language
    ui = b_data.get('ui', {})
    target_lang = b_data.get('target_lang', 'en')
    
    # Shuffle-safe middle section order — reads from niche engine
    # For home page, PAGE_DNA overrides this with a full section sequence
    _niche_eng = b_data.get('niche_engine')
    section_order = getattr(_niche_eng, 'section_order', ["why_choose", "reviews", "areas"]) if _niche_eng else ["why_choose", "reviews", "areas"]

    # 🧬 PAGE_DNA: site-unique layout blueprint from Claude
    _page_dna = b_data.get('page_dna', {})
    
    spec = b_data.get('design_spec', {})
    
    # Home page: always use DESIGN_SPEC headline (the coordinated one)
    # Service pages: use AI-generated content_data title (page-specific)
    if page_type == "home" and spec.get('hero_title'):
        title = strip_markdown(spec['hero_title'])
        sub   = strip_markdown(spec.get('hero_sub', content_data.get('hero_sub', '')))
    else:
        title = strip_markdown(content_data.get('hero_title', 
                f"Expert {clean_title(specific_service_name) if specific_service_name else 'Services'}"))
        sub   = strip_markdown(content_data.get('hero_sub', 
                f"Professional & Reliable in {b_data.get('city', '')}"))
    img_subject = specific_service_name if specific_service_name else b_data.get('industry', '')
    
    if pre_generated_img:
        hero_img = pre_generated_img
    else:
        hero_img = get_hosted_image(img_subject, "hero", b_data.get('industry', ''), is_category=False, service_name=img_subject)
    
    # --- Per-page-type hero variant + section order from PAGE_VARIANT_MAP ---
    _niche = b_data.get('niche_engine')
    _niche_slug = getattr(_niche, 'slug', 'general') if _niche else 'general'

    # page_type ko map karo: 'home'|'parent'→'category'|'child'→'child'
    _ptype_key = "home" if page_type == "home" else \
                 "category" if page_type == "parent" else "child"

    from niche_engine import get_page_variant
    _pv = get_page_variant(_niche_slug, _ptype_key, b_data.get('site_seed', 0))

    hero_variant   = _pv.get("variant",   "split_form")
    hero_show_form = _pv.get("show_form", True)
    # Section order bhi page-specific ab
    _page_sections = _pv.get("sections",  ["why_choose", "reviews", "areas", "faq"])
    
    hero_section = build_hero(b_data, title, sub, img_subject, hero_img, b_data.get('flat_services_list'), hierarchy=structure, trust_signals=content_data.get('trust_signals'), hero_variant=hero_variant, show_form=hero_show_form)
    html += hero_section
    
    # --- NEW: INJECT NICHE EXTRA SECTIONS ---
    if b_data.get('mode') != "1":
        niche = b_data.get('niche_engine')
        if niche:
            html += niche.get_extra_sections(content_data, specific_service_name)
    # ----------------------------------------
    
    # ===== MODE 1 — UNIVERSAL SAAS LANDING PAGE ENGINE =====
    if b_data.get('mode') == "1" and page_type == "child" and specific_service_name:
        sub_services = generate_sub_services(b_data, specific_service_name)

        # ── Step 1: Hero Image ──
        if pre_generated_img:
            hero_img = pre_generated_img
        else:
            hero_img = get_hosted_image(
                specific_service_name, "hero",
                b_data.get('industry', ''),
                is_category=False,
                service_name=specific_service_name
            )

        # ── Step 2: Hero Title + Sub from content_data ──
        title = strip_markdown(content_data.get(
            'hero_title', f"Expert {clean_title(specific_service_name)}"))
        sub   = strip_markdown(content_data.get(
            'hero_sub',   f"Professional & Reliable in {b_data.get('city', '')}"))

        # ── Step 3: Hero Variant — Claude decides per niche ──
        _niche       = b_data.get('niche_engine')
        hero_variant = getattr(_niche, 'hero_variant',    'split_form') if _niche else 'split_form'
        hero_show    = getattr(_niche, 'hero_show_form',  True)         if _niche else True

        # ── Step 4: Build Hero HTML ──
        hero_html = build_hero(
            b_data, title, sub,
            specific_service_name, hero_img,
            b_data.get('flat_services_list'),
            hierarchy     = None,
            trust_signals = content_data.get('trust_signals'),
            hero_variant  = hero_variant,
            show_form     = hero_show,
        )

        # ── Step 5: Niche Extra Sections — Mode 1 mein skip ──
        niche_html = ""

        # ── Step 6: All Other Sections via Landing Engine ──
        body_html = build_mode1_landing_page(
            b_data                    = b_data,
            service_name              = specific_service_name,
            sub_services              = sub_services or [],
            content_data              = content_data,
            call_claude_json          = call_claude_json,
            build_zigzag_section      = build_zigzag_section,
            build_grid_section        = build_grid_section,
            build_infographic_section = build_infographic_section,
            build_areas_served        = build_areas_served,
            build_faq_section         = build_faq_section,
        )

        # ── Step 7: Combine — Hero + Niche + Body ──
        return hero_html + niche_html + body_html

    # ===== END MODE 1 =====
    
    if page_type == "home":
        # 1. Gather all items
        items_to_show = []
        is_category_list = False
        
        if structure and isinstance(structure, dict):
            items_to_show = list(structure.keys())
            is_category_list = True
        
        if not items_to_show:
            items_to_show = b_data.get('flat_services_list', [])
        
        # 🔥 FIXED: Translated section titles
        spec = b_data.get('design_spec', {})
        
        if target_lang == 'ar':
            core_title = spec.get('services_intro', "خدماتنا الأساسية")
            zig_title  = "حلول مخصصة لك"
        else:
            core_title = spec.get('services_intro', "Our Core Services")
            zig_title  = "Expert Solutions Tailored For You"
            
        # 💎 URL FIX: Tell the layout builder if these are Categories or Services
        home_url_type = "category" if is_category_list else "service"
        
        # Get secondary items (to fill zigzags if we run out of primary items)
        flat_list = b_data.get('flat_services_list', [])
        secondary_items = [s for s in flat_list if s not in items_to_show]

        # 🚀 PRO LEVEL HOME PAGE FIX: Sync perfectly with the Hero Form Services
        all_available_items = b_data.get('flat_services_list', [])
        
        top_hero_services = get_smart_hero_options(b_data, all_available_items)
        remaining_services = [s for s in all_available_items if s not in top_hero_services]
        final_home_items = top_hero_services + remaining_services[:max(0, 10 - len(top_hero_services))]

       # 💎 PAGE_DNA: use Claude-decided services_display style if available
        _services_display = _page_dna.get("services_display", "mixed")
        
        if _services_display == "zigzag":
            html += build_zigzag_section(b_data, final_home_items, core_title, limit=6, url_type="service")
        elif _services_display == "grid":
            html += build_grid_section(b_data, final_home_items, core_title, limit=9, url_type="service")
        else:
            # "mixed" — default dynamic layout (grid + zigzag alternating)
            html += build_dynamic_layout_section(
                b_data,
                final_home_items,
                core_title,
                page_type,
                "home",
                url_type="service"
            )

        # 🧬 PAGE_DNA home section order — Claude shuffles these per site
        _home_order = _page_dna.get("home_section_order",
                                    ["why_choose", "reviews", "areas"])
        _middle_sections = {"why_choose", "reviews", "areas"}

        for _sec in _home_order:
            if _sec in _middle_sections:
                html += _render_middle_section(_sec, b_data, content_data)
            elif _sec == "process_steps":
                _niche = b_data.get('niche_engine')
                if _niche:
                    html += _niche.get_extra_sections(content_data, "process")
            # services_grid and internal_links handled separately — skip here

        # LOCKED POSITIONS: always last for SEO
        html += build_internal_links_section(b_data, "home", "home")

        # 🧬 FAQ position from PAGE_DNA
        _faq_pos = _page_dna.get("faq_position", "bottom")
        if _faq_pos == "bottom":
            html += build_faq_section(content_data.get('faqs', []), "", b_data)
    elif page_type == "parent":
        # 🔥 FIXED: Translated section titles
        if target_lang == 'ar':
            solutions_title = f"حلول {clean_title(specific_service_name)} الشاملة"
            services_title = f"خدمات {clean_title(specific_service_name)} الشاملة"
        else:
            solutions_title = f"Complete {clean_title(specific_service_name)} Solutions"
            services_title = f"Complete {clean_title(specific_service_name)} Services"
            
        html += f'''
        <section class="section" style="background:#ffffff !important;">
            <div class="container" style="max-width:900px; text-align:center;">
                <h2 style="font-size:2rem; margin-bottom:30px; color:var(--primary);">{solutions_title}</h2>
                <div style="font-size:1.2rem; color:#475569; line-height:1.8;">{strip_markdown(content_data.get('intro', ''))}</div>
            </div>
        </section>
        '''
        
        if siblings:
            # 🚀 THE "GOLDILOCKS" FIX: Cap at exactly 10 local items to protect the SEO Silo.
            final_10_items = siblings[:10]
            
            html += build_dynamic_layout_section(
                b_data,
                final_10_items,  
                services_title,
                page_type,
                f"parent_{slugify(specific_service_name)}"
            )
        
        # SHUFFLED MIDDLE BAND (why_choose / reviews / areas in stable shuffled order)
        for _sec in _page_sections:
            html += _render_middle_section(_sec, b_data, content_data)
        
        # MODE 1 BOTTOM CTA
        if b_data.get('mode') == "1":
            _primary = b_data.get('primary', '#1A73E8')
            _phone   = b_data.get('phone', '')
            _wa      = b_data.get('whatsapp', '')
            _city    = b_data.get('city') or b_data.get('country','')
            _svc     = clean_title(specific_service_name) if specific_service_name else ''
            if target_lang == 'ar':
                cta_h = "هل أنت جاهز؟ اتصل بنا الآن"
                cta_s = f"فريقنا متاح 24/7 في {_city}"
                b1 = "اتصل الآن"; b2 = "واتساب"
                bg1 = "استجابة سريعة"; bg2 = "مرخص ومؤمن"; bg3 = "ضمان الرضا"
            else:
                cta_h = "Ready to Get Started?"
                cta_s = f"Available 24/7 in {_city} — we reach you within 60 minutes"
                b1 = "Call Now"; b2 = "WhatsApp"
                bg1 = "Fast Response"; bg2 = "Licensed & Insured"; bg3 = "Satisfaction Guaranteed"
            html += f"""
<section style="background:linear-gradient(135deg,{_primary} 0%,#0f172a 100%); padding:70px 20px; margin-top:20px;">
    <div style="max-width:800px; margin:0 auto; text-align:center;">
        <h2 style="color:white; font-size:clamp(1.8rem,4vw,2.8rem); margin-bottom:16px; font-weight:800;">{cta_h}</h2>
        <p style="color:rgba(255,255,255,0.85); font-size:1.15rem; margin-bottom:36px;">{cta_s}</p>
        <div style="display:flex; flex-wrap:wrap; gap:16px; justify-content:center; margin-bottom:36px;">
            <a href="tel:{_phone}" style="display:inline-flex; align-items:center; gap:10px; background:white; color:{_primary}; padding:16px 36px; border-radius:50px; font-weight:800; font-size:1.1rem; text-decoration:none; box-shadow:0 8px 24px rgba(0,0,0,0.25);">
                <i class="fas fa-phone-alt"></i> {b1}: {_phone}
            </a>
            <a href="https://wa.me/{_wa}" target="_blank" style="display:inline-flex; align-items:center; gap:10px; background:#25D366; color:white; padding:16px 36px; border-radius:50px; font-weight:800; font-size:1.1rem; text-decoration:none; box-shadow:0 8px 24px rgba(0,0,0,0.25);">
                <i class="fab fa-whatsapp"></i> {b2}
            </a>
        </div>
        <div style="display:flex; flex-wrap:wrap; gap:12px; justify-content:center;">
            <span style="background:rgba(255,255,255,0.12); color:white; padding:8px 20px; border-radius:30px; font-size:0.9rem; font-weight:600; border:1px solid rgba(255,255,255,0.2);">✓ {bg1}</span>
            <span style="background:rgba(255,255,255,0.12); color:white; padding:8px 20px; border-radius:30px; font-size:0.9rem; font-weight:600; border:1px solid rgba(255,255,255,0.2);">✓ {bg2}</span>
            <span style="background:rgba(255,255,255,0.12); color:white; padding:8px 20px; border-radius:30px; font-size:0.9rem; font-weight:600; border:1px solid rgba(255,255,255,0.2);">✓ {bg3}</span>
        </div>
    </div>
</section>"""

        html += build_faq_section(content_data.get('faqs', []), specific_service_name, b_data)
        
    elif page_type == "child":
        # 🔥 FIXED: Translated section titles
        if target_lang == 'ar':
            matters_title = f"لماذا {clean_title(specific_service_name)} الاحترافية مهمة"
            related_title = f"خدمات ذات صلة بـ {clean_title(parent_category) if parent_category else b_data.get('industry', '')}"
        else:
            matters_title = f"Why Professional {clean_title(specific_service_name)} Matters"
            related_title = f"Related {clean_title(parent_category) if parent_category else b_data.get('industry', '')} Services"
            
        html += f'''
        <section class="section" style="background:#ffffff !important;">
            <div class="container" style="max-width:900px; text-align:center;">
                <h2 style="font-size:2rem; margin-bottom:30px; color:var(--primary);">{matters_title}</h2>
                <div style="font-size:1.2rem; color:#475569; line-height:1.8;">{strip_markdown(content_data.get('intro', ''))}</div>
            </div>
        </section>
        '''
        
        # Always show siblings if they exist
        if siblings and len(siblings) > 0:
            # 🚀 CHILD PAGE FIX: Cap at exactly 10 local siblings to protect internal linking.
            final_child_items = siblings[:10]
            
            print(f"   🔗 Building related services section with {len(final_child_items)} highly relevant services")
            
            html += build_dynamic_layout_section(
                b_data,
                final_child_items, 
                related_title,
                page_type,
                f"child_{slugify(specific_service_name)}"
            )
        
        for _sec in _page_sections:
            html += _render_middle_section(_sec, b_data, content_data)

        # Internal links (locked position) — skip entirely for Mode 1
        if b_data.get('mode') == '2' and Config.GENERATE_INTERNAL_LINKS:
            all_services = b_data.get('flat_services_list', [])
            if len(all_services) > 1:
                html += generate_mode2_internal_links(b_data, specific_service_name, all_services)
        elif b_data.get('mode') != '1':
            html += build_internal_links_section(b_data, specific_service_name, "child")
        # Mode 1: internal links section skipped — user disabled them

        html += build_faq_section(content_data.get('faqs', []), specific_service_name, b_data)
        
    return html
# ==============================================================================
# 📄 JINJA2 STYLE TEMPLATE RENDERING - WITH ICONIFY FIX
# ==============================================================================
def render_template(template_name, context):
    """Jinja2-style template rendering with clean HTML/Python separation."""
    
    templates = {
        "page_wrapper": """
        <!DOCTYPE html>
        <html lang="{{ lang }}" dir="{{ dir }}">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
            <title>{{ title }}</title>
            <meta name="description" content="{{ meta_description }}">
            <meta name="keywords" content="{{ keywords }}">
            <link rel="canonical" href="{{ canonical_url }}">
            
            <meta property="og:type" content="website">
            <meta property="og:title" content="{{ title }}">
            <meta property="og:description" content="{{ meta_description }}">
            <meta property="og:url" content="{{ canonical_url }}">
            <meta property="og:image" content="{{ og_image }}">
            <meta property="og:site_name" content="{{ business_name }}">
            <meta name="twitter:card" content="summary_large_image">
            <meta name="twitter:title" content="{{ title }}">
            <meta name="twitter:description" content="{{ meta_description }}">
            <meta name="twitter:image" content="{{ og_image }}">
            
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Tajawal:wght@400;500;700;800&display=swap" rel="stylesheet">
            
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <script src="https://code.iconify.design/3/3.1.0/iconify.min.js"></script>
            
            <link rel="stylesheet" href="/css/styles.css">
            {{ rtl_stylesheet }}
            <style>
                html, body { overflow-x: hidden !important; width: 100% !important; max-width: 100% !important; margin: 0 !important; padding: 0 !important; }
                #v360-wrapper { overflow-x: hidden !important; width: 100% !important; max-width: 100% !important; }
                @media (max-width: 768px) {
                    #v360-wrapper .hero-content { grid-template-columns: 1fr !important; gap: 25px !important; }
                    #v360-wrapper .text-col { order: 1 !important; }
                    #v360-wrapper .form-col { order: 2 !important; width: 100% !important; display: block !important; visibility: visible !important; opacity: 1 !important; }
                    #v360-wrapper .glass-card { margin: 0 auto !important; width: 100% !important; display: block !important; visibility: visible !important; opacity: 1 !important; }
                    #v360-wrapper .hero-title, #v360-wrapper .hero-sub { text-align: center !important; }
                    #v360-wrapper .hero-gold-badge { margin: 0 auto 15px auto !important; display: table !important; }
                    #v360-wrapper .btn-group { justify-content: center !important; }
                    #v360-wrapper .zigzag-item, #v360-wrapper .zigzag-item.reverse { flex-direction: column !important; gap: 25px !important; }
                    #v360-wrapper .zigzag-img { height: 250px !important; width: 100% !important; }
                    #v360-wrapper .zigzag-content h3 { text-align: center !important; }
                    #v360-wrapper .service-grid, #v360-wrapper .infographic-grid, #v360-wrapper .internal-links-grid, #v360-wrapper .footer-grid { grid-template-columns: 1fr !important; }
                    #v360-wrapper .hero { background-position: center 22% !important; }
                    #v360-wrapper h1, #v360-wrapper h2, #v360-wrapper h3 { overflow-wrap: break-word !important; word-break: break-word !important; }
                    #v360-wrapper .section h2 { font-size: clamp(1.45rem, 6.2vw, 1.9rem) !important; line-height: 1.3 !important; }
                    #v360-wrapper .zigzag-content .btn { display: flex !important; width: max-content !important; max-width: 100% !important; margin: 18px auto 0 auto !important; justify-content: center !important; white-space: normal !important; text-align: center !important; }
                    #v360-wrapper table { display: block; overflow-x: auto; }
                    #v360-wrapper img { max-width: 100% !important; height: auto; }
                }
            </style>
            <script>
                window.v360Config = {
                    phone: "{{ phone }}",
                    whatsapp: "{{ whatsapp }}",
                    sheetUrl: "{{ sheet_url }}",
                    source: "{{ business_name }}",
                    businessName: "{{ business_name }}"
                };
            </script>
        </head>
        <body>
            <div id="v360-wrapper">
                {{ header }}
                {{ content }}
                {{ footer }}
            </div>
            <script src="/js/locations.js"></script>
            <script src="/js/main.js"></script>
            {{ schema }}
        </body>
        </html>
        """
    }
    
    template = templates.get(template_name, "")
    for key, value in context.items():
        template = template.replace("{{ " + key + " }}", str(value))
    
    return template
def save_html_file(output_folder, filepath, content, b_data, page_title, canonical_url=None, structure=None, p_data=None):
    """Saves a complete HTML file with universal header and footer - With H1 validation & Canonical Fixes."""
    
    # ❌ REMOVED: global GENERATED_PAGES_LIST (Now SaaS safe!)
    
    # ✅ CRITICAL FIX 1: Prevent script crashes for pages that don't have p_data (like About/Contact)
    p_data = p_data or {}
    
    base_url = Config.SITE_URL.rstrip('/')
    lang_mode = b_data.get('lang_mode', 'no')
    
    # Store original filepath before language prefix addition
    original_filepath = filepath
    
    # Add Language Folder Depth ONLY if 'no' was not selected
    if lang_mode != "no" and not filepath.startswith(f"{lang_mode}/"):
        filepath = f"{lang_mode}/{filepath}"
    
    mode = b_data.get('mode', '3')
    hub_target_url = Config.HUB_TARGET_URL if mode == "2" else ""
    
    header = UniversalHeader.render(b_data, structure, mode, hub_target_url)
    footer = build_enhanced_footer(b_data, structure)
    
    ui = b_data.get('ui', {})
    
    # ✅ FIXED: Unified Canonical URL Stripping (Guarantees no .html)
    raw_path = canonical_url if canonical_url else filepath
    
    # Strip protocol and base URL temporarily if it exists to clean the path
    clean_path = raw_path.replace(base_url, "").lstrip('/')
    
    # Force the language prefix into the canonical path if it's missing
    if lang_mode != "no" and not clean_path.startswith(f"{lang_mode}/"):
        clean_path = f"{lang_mode}/{clean_path}"
        
    # Remove .html extension for clean URL
    if clean_path.endswith('index.html'):
        clean_path = clean_path.replace('index.html', '')
    elif clean_path.endswith('.html'):
        clean_path = clean_path[:-5]
        
    # Ensure base_url has no trailing slash, and clean_path has no leading slash
    safe_base = base_url.rstrip('/')
    safe_path = clean_path.lstrip('/')
    full_canonical = f"{safe_base}/{safe_path}" if safe_path else f"{safe_base}/"
    
    # Ensure no double slashes (ignoring protocol)
    full_canonical = full_canonical.replace('://', 'TEMP_PROTOCOL').replace('//', '/').replace('TEMP_PROTOCOL', '://')
    if full_canonical != f"{base_url}/":
        full_canonical = full_canonical.rstrip('/')
    
    # ===== THE "HIGHLANDER" H1 RULE =====
    # Ensure there's only one H1 tag in the content
    h1_pattern = re.compile(r'<h1\b[^>]*>.*?</h1>', flags=re.IGNORECASE | re.DOTALL)
    h1_matches = h1_pattern.findall(content)
    
    if len(h1_matches) > 1:
        print(f"      🏴 Found {len(h1_matches)} H1s in {filepath}, demoting extras...")
        # Keep the first H1, demote others to H2
        for old_h1 in h1_matches[1:]:
            new_h2 = re.sub(r'<h1\b', '<h2', old_h1, flags=re.IGNORECASE)
            new_h2 = re.sub(r'</h1>', '</h2>', new_h2, flags=re.IGNORECASE)
            content = content.replace(old_h1, new_h2, 1)
    
    # ===== ENSURE TITLE IS EVERGREEN =====
    # Double-check that title has current year
    title_pattern = re.compile(r'<title.*?>(.*?)</title>', flags=re.IGNORECASE | re.DOTALL)
    title_match = title_pattern.search(content)
    if title_match:
        current_title = title_match.group(1)
        current_year = datetime.now().year
        year_str = str(current_year)
        
        # If title doesn't have current year, update it
        if year_str not in current_title:
            # Extract service name
            if "|" in current_title:
                service_part = current_title.split("|")[0].strip()
                brand_part = current_title.split("|")[1].strip() if len(current_title.split("|")) > 1 else b_data.get('name', '')
            else:
                service_part = current_title
                brand_part = b_data.get('name', '')
            
            # Clean up any old year references
            service_part = re.sub(r'\s+in\s+\d{4}', '', service_part)
            service_part = re.sub(r'\s+\d{4}', '', service_part)
            
            # Create new evergreen title
            new_title = f"{service_part} in {current_year} | {brand_part}"
            content = title_pattern.sub(f'<title>{new_title}</title>', content, count=1)
            print(f"      🏷️ Updated title to evergreen format: {new_title}")
    
    # ✅ FIXED: Use AI generated meta title for the page wrapper if it exists
    final_title = p_data.get('meta_title') if p_data and p_data.get('meta_title') else page_title

    # Catch any rogue double-branding before assembly
    brand_name = b_data.get('name', '')
    if brand_name:
        content = content.replace(f"| {brand_name} | {brand_name}", f"| {brand_name}")
        final_title = final_title.replace(f"| {brand_name} | {brand_name}", f"| {brand_name}")

    # Continue with normal saving...
    context = {
        "title": final_title,
        "business_name": b_data.get('name', ''),
        "meta_description": p_data.get('meta_description', b_data.get('meta_description', f"Professional {b_data.get('industry', '')} services")),
        "keywords": p_data.get('meta_keywords', b_data.get('meta_keywords', f"{b_data.get('industry', '')}, {b_data.get('city', '')}, professional services")),
        "canonical_url": full_canonical,
        "og_image": p_data.get('image_url', p_data.get('hero_image', b_data.get('logo_url', ''))),
        "phone": b_data.get('phone', ''),
        "whatsapp": b_data.get('whatsapp', ''),
        "sheet_url": b_data.get('google_sheet_url', ''),
        "header": header,
        "content": content,
        "footer": footer,
        "schema": "",
        "lang": b_data.get('target_lang', 'en'),
        "dir": ui.get('dir', 'ltr'),
        "rtl_stylesheet": '<link rel="stylesheet" href="/css/rtl.css">' if b_data.get('is_rtl') else ''
    }
    
    full_content = render_template("page_wrapper", context)
    full_content = full_content.replace("{{ content }}", content)
    
    full_path = os.path.join(output_folder, filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(full_content)
    
    rel_path = os.path.relpath(full_path, output_folder)
    print(f"    📄 Saved: {rel_path}")
    
    # ✅ FIXED: Store the original relative path safely inside the session's b_data
    if 'generated_pages' not in b_data:
        b_data['generated_pages'] = []
        
    if original_filepath not in b_data['generated_pages']:
        b_data['generated_pages'].append(original_filepath)
    
    return full_path
# ==============================================================================
# 📄 NETLIFY CONFIGURATION - STRICT SEO & PERFORMANCE MODE
# ==============================================================================
def generate_netlify_files(output_folder):
    """Generates Netlify configuration files optimized for Static SEO."""
    
    # 1. _REDIRECTS
    # We REMOVED all the 200 rewrites. 
    # If a page doesn't exist, we want a strict 404 error so Google drops it.
    redirects_content = """# Strict SEO Redirects
# (Optional) If you ever generate a custom 404 page, uncomment the line below:
# /* /404.html 404
"""
    
    with open(os.path.join(output_folder, '_redirects'), 'w', encoding='utf-8') as f:
        f.write(redirects_content)
    
    # 2. NETLIFY.TOML
    # Removed the SPA fallback. Added 'clean_urls' to force 301 redirects from .html to clean paths.
    # Added aggressive 1-year caching for static assets to dominate PageSpeed Insights.
    netlify_toml = """[build]
  publish = "."

[build.processing.html]
  clean_urls = true

[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-XSS-Protection = "1; mode=block"
    X-Content-Type-Options = "nosniff"

# Cache CSS & JS for 1 year (Performance Boost)
[[headers]]
  for = "/**/*.css"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"

[[headers]]
  for = "/**/*.js"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"

# Cache Images for 1 year (Performance Boost)
[[headers]]
  for = "/**/*.jpg"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
    
[[headers]]
  for = "/**/*.png"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
    
[[headers]]
  for = "/**/*.webp"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
"""
    
    with open(os.path.join(output_folder, 'netlify.toml'), 'w', encoding='utf-8') as f:
        f.write(netlify_toml)
    
    # 3. ROBOTS.TXT
    # Using .rstrip('/') ensures we never get a double slash (e.g. domain.com//sitemap.xml)
    robots_content = f"""User-agent: *
Allow: /
Sitemap: {Config.SITE_URL.rstrip('/')}/sitemap.xml
"""
    
    with open(os.path.join(output_folder, 'robots.txt'), 'w', encoding='utf-8') as f:
        f.write(robots_content)
    
    print(f"✅ Generated Netlify configuration files (Strict SEO & Performance Mode)")
def generate_sitemap(output_folder, pages, b_data=None):
    """
    Generates a SMART SEO-optimized sitemap.xml with CLEAN URLS (No .html).
    Flawlessly handles Core Path extraction to prevent duplicate /ar/ar/ routes.
    Includes proper hreflang annotations for multi-language GSC compliance.
    """
    
    if b_data is None:
        b_data = {}
    
    base_url = Config.SITE_URL.rstrip('/')
    lang_mode = b_data.get('lang_mode', 'no')
    
    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">"""
    
    current_date = datetime.now().strftime('%Y-%m-%d')

    # Remove potential duplicates from the list
    unique_pages = sorted(list(set(pages)))
    added_urls = set()

    for page in unique_pages:
        if not page:
            continue
            
        # Clean the base page path
        clean_page = page.lstrip('/')
        
        # --- 1. EXTRACT CORE PATH (The Ultimate Fix for /ar/ar/) ---
        # We strip the language prefix out of the path if it exists, 
        # so we have a clean slate to build our absolute URLs.
        core_path = clean_page
        if lang_mode != "no" and core_path.startswith(f"{lang_mode}/"):
            core_path = core_path[len(lang_mode)+1:] # Strips 'ar/' or 'en/'
            
        # Remove index.html or .html from core_path to match Netlify Clean URLs
        if core_path.endswith('index.html'):
            core_path = core_path[:-10]
        elif core_path.endswith('.html'):
            core_path = core_path[:-5]
            
        core_path = core_path.strip('/')
        
        # --- 2. BUILD MAIN URL ---
        if lang_mode == "no":
            raw_url = f"{base_url}/{core_path}"
        else:
            raw_url = f"{base_url}/{lang_mode}/{core_path}" if core_path else f"{base_url}/{lang_mode}"

        # Clean up duplicate slashes safely (ignores the :// in https://)
        raw_url = re.sub(r'(?<!:)//+', '/', raw_url)
        
        # Ensure consistent trailing slash behavior (strip from ends unless root domain)
        if raw_url != base_url and raw_url != f"{base_url}/":
            raw_url = raw_url.rstrip('/')
            
        # Skip if we already added this exact URL
        if raw_url in added_urls:
            continue
        added_urls.add(raw_url)

        # CRITICAL FIX: Escape the URL for valid XML
        safe_url = escape(raw_url)

        # --- 3. SMART SEO PRIORITY LOGIC ---
        if not core_path or core_path == lang_mode:
            priority, changefreq = "1.0", "weekly"
        elif any(s in core_path for s in ['services', 'categories', 'seo', 'marketing', 'ppc', 'web']):
            priority, changefreq = "0.8", "monthly"
        elif "blog" in core_path:
            priority, changefreq = "0.7", "weekly"
        else:
            priority, changefreq = "0.6", "monthly"

        # Start building the <url> block
        sitemap_content += f"""
  <url>
    <loc>{safe_url}</loc>
    <lastmod>{current_date}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>"""

        # --- 4. HREFLANG TAGS (Multi-Language SEO) ---
        if lang_mode != "no":
            supported_langs = ['en', 'ar']
            
            for alt_lang in supported_langs:
                # Build the alternate URL flawlessly
                alt_url = f"{base_url}/{alt_lang}/{core_path}" if core_path else f"{base_url}/{alt_lang}"
                alt_url = re.sub(r'(?<!:)//+', '/', alt_url)
                if alt_url != base_url and alt_url != f"{base_url}/":
                    alt_url = alt_url.rstrip('/')
                    
                safe_alt_url = escape(alt_url)
                sitemap_content += f"""
    <xhtml:link rel="alternate" hreflang="{alt_lang}" href="{safe_alt_url}"/>"""
            
            # Add x-default pointing to English
            x_default_url = f"{base_url}/en/{core_path}" if core_path else f"{base_url}/en"
            x_default_url = re.sub(r'(?<!:)//+', '/', x_default_url)
            if x_default_url != base_url and x_default_url != f"{base_url}/":
                x_default_url = x_default_url.rstrip('/')
                
            safe_x_default = escape(x_default_url)
            sitemap_content += f"""
    <xhtml:link rel="alternate" hreflang="x-default" href="{safe_x_default}"/>"""

        # Close the <url> block
        sitemap_content += """
  </url>"""
    
    sitemap_content += "\n</urlset>"
    
    # Save the file
    try:
        sitemap_path = os.path.join(output_folder, 'sitemap.xml')
        with open(sitemap_path, 'w', encoding='utf-8') as f:
            f.write(sitemap_content)
        
        url_count = sitemap_content.count('<url>')
        print(f"  ✅ Generated Smart Sitemap with {url_count} Clean URLs for {base_url}")
        
        if url_count > 45000:  # Sitemap limit is 50,000 URLs
            generate_sitemap_index(output_folder, b_data)
            
    except Exception as e:
        print(f"  ❌ Error generating sitemap: {e}")

def generate_sitemap_index(output_folder, b_data=None):
    """Generates a sitemap index file if there are multiple sitemaps."""
    if b_data is None:
        b_data = {}
    
    base_url = Config.SITE_URL.rstrip('/')
    safe_base_url = escape(base_url)
    
    sitemap_index = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>{safe_base_url}/sitemap.xml</loc>
    <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
  </sitemap>
</sitemapindex>"""
    
    try:
        with open(os.path.join(output_folder, 'sitemap-index.xml'), 'w', encoding='utf-8') as f:
            f.write(sitemap_index)
        print("  ✅ Generated Sitemap Index")
    except Exception as e:
        print(f"  ❌ Error generating sitemap index: {e}")

def generate_readme(output_folder, b_data, pages_count, services_count):
    """Generates README.md file."""
    
    readme_content = f"""# {b_data.get('name', '')} - Static Website

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Website Structure
- Homepage: index.html
- Services: /services/
- Categories: /categories/
- Contact: /pages/contact.html
- About: /pages/about.html
- Blog: /blog/

## Mode Information
- Mode: {b_data.get('mode', '3')} 
- Backlinks: {"Enabled" if Config.GENERATE_BACKLINKS else "Disabled"}
- Internal Links: {"Enabled" if Config.GENERATE_INTERNAL_LINKS else "Disabled"}
- Image Model: {Config.IMAGE_MODEL.upper()}

## Deployment Instructions

### Deploy to Netlify:
1. Drag and drop this entire folder to https://app.netlify.com/drop
2. Your site will be live instantly!

## Files Included
- Complete HTML pages with Universal Header System
- CSS stylesheets with responsive design
- JavaScript files
- Netlify configuration (_redirects, netlify.toml)
- robots.txt
- sitemap.xml

## Business Information
- Name: {b_data.get('name', '')}
- Industry: {b_data.get('industry', '')}
- Location: {b_data.get('city', '')}, {b_data.get('country', '')}
- Phone: {b_data.get('phone', '')}

## Site Statistics
- Total Pages: {pages_count}
- Services: {services_count}
- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
Generated with Universal Static Site Generator v6.0 - SaaS Edition
"""
    
    with open(os.path.join(output_folder, 'README.md'), 'w', encoding='utf-8') as f:
        f.write(readme_content)
# ==============================================================================
# 📄 SMART ABOUT US GENERATOR (AI-POWERED)
# ==============================================================================
@retry_operation(max_retries=3)
def generate_additional_pages(output_folder, b_data, structure):
    """Generate About Us page using GPT-4o for industry-relevant content."""
    
    mode = b_data.get('mode', '3')
    industry = b_data.get('industry', 'Business')
    name = b_data.get('name', 'Our Company')
    city = b_data.get('city', 'the area')

    # 1. Default Content (Fallback if AI fails)
    content = {
        "story": f"{name} is a leading provider of {industry} solutions. We are dedicated to delivering excellence and building long-term relationships with our clients in {city}.",
        "mission": f"Our mission is to provide top-tier {industry} services that exceed customer expectations through reliability, integrity, and innovation.",
        "values": [
            {"title": "Experienced Team", "desc": "Our professionals are highly trained and experts in their field.", "icon": "user-tie"},
            {"title": "Quality Assured", "desc": "We maintain the highest standards of quality in every project.", "icon": "check-circle"},
            {"title": "Client Focused", "desc": "Your satisfaction is our top priority.", "icon": "smile"},
            {"title": "Reliable Service", "desc": "We deliver on time and on budget.", "icon": "clock"}
        ]
    }

    # 2. GPT-4o Generation
    if CLIENTS.get('openai'):
        try:
            print(f"   🧠 Generating AI About Us content for {industry}...")
            prompt = f"""
            Write content for an 'About Us' page for a {industry} business named '{name}' in {city}.
            
            REQUIREMENTS:
            1. 'story': A 2-paragraph origin story. Tone: Professional and authoritative.
            2. 'mission': A strong 1-paragraph mission statement.
            3. 'values': 4 distinct 'Why Choose Us' points. 
               - MUST BE relevant to {industry} (e.g., if Marketing -> 'Data Driven', if Electrician -> 'Safety First').
               - NO generic 'technicians' terminology unless it's a trade job.
            
            RETURN JSON ONLY:
            {{
                "story": "string",
                "mission": "string",
                "values": [
                    {{"title": "Point 1", "desc": "Description 1", "icon": "fa-icon-name-without-fa-prefix"}},
                    ... 4 items total
                ]
            }}
            """
            
            response = CLIENTS['openai'].chat.completions.create(
                model=Config.MODEL_LOW_TIER,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"} 
            )
            
            ai_data = clean_json_response(response.choices[0].message.content)
            if ai_data and 'story' in ai_data and 'values' in ai_data:
                content = ai_data
                print("   ✅ About Us content generated successfully.")
                
        except Exception as e:
            print(f"   ⚠️ AI About Us generation failed, using fallback: {e}")

    # 3. Build HTML
    values_html = ""
    for val in content['values']:
        icon = val.get('icon', 'check').replace('fa-', '')
        values_html += f"""
        <div style="background: var(--light-bg); padding: 25px; border-radius: 15px; border: 1px solid #e2e8f0; transition: transform 0.3s ease;">
            <i class="fas fa-{icon}" style="font-size: 2rem; color: var(--gold); margin-bottom: 15px;"></i>
            <h3 style="margin-bottom: 10px; font-size: 1.3rem; color: var(--primary);">{val['title']}</h3>
            <p style="color: var(--text-gray); font-size: 0.95rem;">{val['desc']}</p>
        </div>
        """

    hero_img = get_hosted_image(f"{industry} team professional", "hero", industry, service_name='About Team')

    # FIX: Prepare text outside of f-string to avoid SyntaxError in Python < 3.12
    story_text = content['story'].replace('\n', '<br><br>')

    about_html = f"""
    <section class="section">
        <div class="container">
            <h1 style="font-size: 2.8rem; margin-bottom: 20px; color: var(--primary); text-align: center;">About {name}</h1>
            <p style="text-align: center; color: var(--text-gray); font-size: 1.2rem; max-width: 700px; margin: 0 auto 50px;">
                Leading the way in {industry} excellence in {city}.
            </p>
            
            <div style="max-width: 1000px; margin: 0 auto;">
                <div style="position: relative; margin-bottom: 50px;">
                    <img src="{hero_img}" 
                         style="width: 100%; height: 450px; object-fit: cover; border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.1);" 
                         alt="{name} Team">
                </div>
                
                <div style="margin-bottom: 50px;">
                    <h2 style="font-size: 2rem; margin-bottom: 20px; color: var(--primary);">Our Story</h2>
                    <div style="font-size: 1.1rem; color: var(--text-gray); line-height: 1.8;">
                        {story_text}
                    </div>
                </div>
                
                <div style="background: var(--primary); color: white; padding: 40px; border-radius: 20px; margin-bottom: 60px; text-align: center;">
                    <h2 style="font-size: 2rem; margin-bottom: 15px; color: white;">Our Mission</h2>
                    <p style="font-size: 1.25rem; line-height: 1.6; max-width: 800px; margin: 0 auto;">
                        "{content['mission']}"
                    </p>
                </div>
                
                <h2 style="font-size: 2.2rem; margin-bottom: 30px; color: var(--primary); text-align: center;">Why Choose Us</h2>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 30px; margin-bottom: 40px;">
                    {values_html}
                </div>
            </div>
        </div>
    </section>
    """
    
    # Save About Page
    save_html_file(output_folder, 'pages/about.html', about_html, b_data, f"About Us - {name}", validate_url("about", None, mode), structure)
def auto_translate_services(b_data, structure=None):
    """Automatically translates English service names AND categories to target language for UI display."""
    target_lang = b_data.get('target_lang', 'en')
    
    # 1. Grab all base services
    items_to_translate = list(b_data.get('flat_services_list', []))
    
    # 2. Add Category Names to the translation payload
    if structure and isinstance(structure, dict):
        items_to_translate.extend(list(structure.keys()))
        
    # 3. Strip duplicates to save API tokens and processing time
    items_to_translate = list(set(items_to_translate))

    # 4. Safely exit if running in English, missing API, or list is empty
    if target_lang == 'en' or not CLIENTS.get('openai') or not items_to_translate:
        return

    print(f"\n🌐 Auto-Translating {len(items_to_translate)} items to {'Arabic' if target_lang == 'ar' else target_lang} for UI Display...")

    try:
        prompt = f"""
        Translate these English names into {'Arabic' if target_lang == 'ar' else target_lang}.
        Keep them short (2-4 words).
        CRITICAL: Output actual native Arabic characters (e.g. تحسين). DO NOT use unicode escapes like \\u0627 or \\u0006.
        Return ONLY a JSON dictionary where Key is the exact English name, and Value is the Translation.
        Items: {json.dumps(items_to_translate)}
        """

        response = CLIENTS['openai'].chat.completions.create(
            model=Config.MODEL_LOW_TIER,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} 
        )

        data = clean_json_response(response.choices[0].message.content)
        if data and isinstance(data, dict):
            # 🔥 POPULATE GLOBAL DICTIONARY TO FIX MENUS
            global GLOBAL_TRANSLATIONS
            GLOBAL_TRANSLATIONS.update({k.lower(): v for k, v in data.items()})
            print("   ✅ UI Translations Complete!")
    except Exception as e:
        print(f"   ⚠️ UI Translation failed: {e}")

# ==============================================================================
# 🎯 DESIGN SPEC ENGINE — One coordinated Claude call for entire site personality
# ==============================================================================
def generate_design_spec(b_data):
    """
    Single Claude call that defines the entire site's content personality.
    Returns a DESIGN_SPEC dict used by hero, How It Works, and intro sections.
    Runs once per site — cached in b_data['design_spec'].
    """
    
    name     = b_data.get('name', 'Our Company')
    industry = b_data.get('industry', 'Service')
    city     = b_data.get('city') or b_data.get('country', 'your area')
    phone    = b_data.get('phone', '')
    services = b_data.get('flat_services_list', [])[:8]
    target_lang = b_data.get('target_lang', 'en')
    
    lang_name = "Arabic" if target_lang == 'ar' else "English"
    
    if target_lang == 'ar':
        fallback = {
            "hero_title":    f"خبراء {industry} الموثوقون في {city}",
            "hero_sub":      f"خدمة سريعة واحترافية — نصل إليك خلال 60 دقيقة في {city}",
            "trust_badge":   f"#1 موثوق في {city}",
            "how_it_works":  [
                {"emoji": "📞", "title": "اتصل أو احجز",
                 "desc":  f"تواصل معنا 24/7 لأي احتياج في {city}. نرد خلال دقائق."},
                {"emoji": "🔍", "title": "تشخيص مجاني",
                 "desc":  "يفحص فنيّنا المشكلة مجاناً قبل تقديم أي سعر."},
                {"emoji": "💰", "title": "سعر واضح مسبقاً",
                 "desc":  "سعر ثابت بدون مفاجآت — تعرف التكلفة قبل بدء العمل."},
                {"emoji": "✅", "title": "عمل مضمون",
                 "desc":  "ننجز العمل من أول مرة مع ضمان شامل على الخدمة."},
            ],
            "services_intro": f"اكتشف خدمات {industry} الاحترافية في {city}.",
            "why_choose_intro": f"لماذا يختارنا أهل {city}؟",
        }
    else:
        fallback = {
            "hero_title":    f"Expert {industry} in {city}",
            "hero_sub":      f"Fast, reliable service — licensed professionals reaching {city} in 60 minutes",
            "trust_badge":   f"#1 Rated in {city}",
            "how_it_works":  [
                {"emoji": "📞", "title": "Call or Book Online",
                 "desc":  f"Reach us 24/7 for any {industry.lower()} need in {city}. We respond within minutes."},
                {"emoji": "🔍", "title": "Free Diagnosis",
                 "desc":  "A certified specialist inspects the problem at no charge before quoting."},
                {"emoji": "💰", "title": "Upfront Quote",
                 "desc":  "Fixed price — no hidden charges. You know the cost before we start."},
                {"emoji": "✅", "title": "Guaranteed Work",
                 "desc":  "We complete the job right the first time, backed by our full warranty."},
            ],
            "services_intro": f"Explore our professional {industry.lower()} services across {city}.",
            "why_choose_intro": f"Why {city} residents choose {name}",
        }
    
    if not CLIENTS.get('claude'):
        print("   ℹ️  No Claude client — using fallback DESIGN_SPEC")
        return fallback
    
    services_str = ", ".join(services) if services else industry

    # 💎 HEADLINE STYLE ROTATION — har business ko alag headline formula
    _seed = b_data.get('site_seed', 0)
    _headline_styles = [
        "BENEFIT-LED: lead with the strongest outcome (e.g. 'Same-Day AC Repair Dubai')",
        "URGENCY-LED: lead with speed/response time (e.g. 'AC Repair Dubai — 45-Min Arrival')",
        "TRUST-LED: lead with social proof/rating (e.g. \"Dubai's 4.9-Star AC Repair Team\")",
        "PROBLEM-LED: open with the customer's pain (e.g. 'AC Not Cooling? Dubai Experts On Call')",
    ]
    _chosen_style = _headline_styles[_seed % 4]

    prompt = f"""You are an elite conversion copywriter designing a local service website.

UNIQUENESS SEED: {_seed}
MANDATORY HEADLINE STYLE for hero_title (rule 1 MUST follow this formula):
{_chosen_style}

BUSINESS:
- Name: {name}
- Industry: {industry}
- City / Area: {city}
- Phone: {phone}
- Key services: {services_str}

OUTPUT LANGUAGE: {lang_name}

Generate a DESIGN_SPEC for this business. Every string must be in {lang_name}.

RULES:
1. hero_title: 5-8 words MAXIMUM. This is the H1 — ONE H1 only per page.
   Format: "[High-Intent Keyword] + [City]" or "[Action] + [Specific Service] + [City]".
   The title MUST naturally contain the business's top search keyword.
   Examples: "Same-Day Appliance Repair Dubai" / "Dubai Fridge Repair Experts".
   DO NOT use generic phrases like "Professional Services" or "We Provide".
   DO NOT add year. Write exactly what a customer would type in Google.
   
2. hero_sub: One compelling sentence (max 15 words). Mention speed, reliability, or guarantee.

3. trust_badge: 3-5 words. What locals would say about this business. E.g. "#1 Rated in Dubai".

4. how_it_works: EXACTLY 4 steps. Each step must be SPECIFIC to {industry} — 
   mention real actions a {industry.lower()} business does.
   Step titles: max 3 words each.
   Step desc: 1 sentence, max 18 words, mention {city} in at least one step.
   Use these emojis in order: 📞 🔍 💰 ✅

5. services_intro: One sentence (max 20 words) introducing the services section.
   Must feel like a real human wrote it, not AI.

6. why_choose_intro: 4-6 words. Section heading for "Why Choose Us".

Return ONLY valid JSON — no markdown, no explanation:
{{
    "hero_title": "string",
    "hero_sub": "string",
    "trust_badge": "string",
    "how_it_works": [
        {{"emoji": "📞", "title": "string", "desc": "string"}},
        {{"emoji": "🔍", "title": "string", "desc": "string"}},
        {{"emoji": "💰", "title": "string", "desc": "string"}},
        {{"emoji": "✅", "title": "string", "desc": "string"}}
    ],
    "services_intro": "string",
    "why_choose_intro": "string"
}}"""
    
    try:
        print(f"\n🎯 Generating DESIGN_SPEC for {name} ({industry}, {city})...")
        spec = call_claude_json(prompt)
        
        if not spec or 'hero_title' not in spec:
            print("   ⚠️  DESIGN_SPEC parse failed — using fallback")
            return fallback
        
        hiw = spec.get('how_it_works', [])
        if len(hiw) < 4:
            print(f"   ⚠️  Only {len(hiw)} How It Works steps — padding with fallback")
            while len(hiw) < 4:
                hiw.append(fallback['how_it_works'][len(hiw)])
            spec['how_it_works'] = hiw
        
        import re as _re
        spec['hero_title'] = _re.sub(r'\s*\b20\d{2}\b\s*', '', spec['hero_title']).strip(' -—|:')
        
        print(f"   ✅ DESIGN_SPEC ready: \"{spec['hero_title']}\"")
        return spec
        
    except Exception as e:
        print(f"   ⚠️  DESIGN_SPEC generation error: {e} — using fallback")
        return fallback        

# ==============================================================================
# 🌐 RTL CSS GENERATOR
# ==============================================================================
def generate_rtl_css(output_folder):
    """Generates RTL stylesheet for Arabic and other RTL languages."""
    rtl_css = """/* RTL Stylesheet - Auto Generated */
/* Applied when target_lang is 'ar' */

body {
    direction: rtl;
    text-align: right;
}

#v360-wrapper .hero-content {
    direction: rtl;
}

#v360-wrapper .hero-features {
    justify-content: flex-end;
}

#v360-wrapper .btn-group {
    justify-content: flex-end;
}

#v360-wrapper .zigzag-item {
    flex-direction: row-reverse;
}

#v360-wrapper .zigzag-item.reverse {
    flex-direction: row;
}

#v360-wrapper .service-card.cv-icon_left {
    flex-direction: row-reverse;
}

#v360-wrapper .footer-grid {
    direction: rtl;
}

#v360-wrapper .footer-links ul {
    padding-right: 0;
}

#v360-wrapper .infographic-grid {
    direction: rtl;
}

#v360-wrapper .pill-container {
    direction: rtl;
}

#v360-wrapper .faq-question {
    flex-direction: row-reverse;
}

#v360-wrapper .glass-card input,
#v360-wrapper .glass-card select {
    text-align: right;
    direction: rtl;
}

#v360-wrapper .pro-internal-link {
    flex-direction: row-reverse;
}

@media (max-width: 768px) {
    #v360-wrapper .hero-title,
    #v360-wrapper .hero-sub {
        text-align: center !important;
    }
    
    #v360-wrapper .btn-group {
        justify-content: center !important;
    }
}
"""
    
    css_dir = os.path.join(output_folder, 'css')
    os.makedirs(css_dir, exist_ok=True)
    
    rtl_path = os.path.join(css_dir, 'rtl.css')
    with open(rtl_path, 'w', encoding='utf-8') as f:
        f.write(rtl_css)
    
    print(f"✅ Generated RTL stylesheet: {rtl_path}")
    return rtl_path
# ==============================================================================
# 🧬 PAGE DNA GENERATOR — Claude decides section order per site (one call)
# ==============================================================================
def generate_page_dna(b_data: dict) -> dict:
    """
    One Claude call per site. Returns a layout blueprint so every page type
    (home, category, service) has a consistent but site-unique structure.
    Two different handyman Dubai sites will get different home page layouts.
    Falls back safely if Claude fails.
    """
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
    niche_label = niche_obj.label if niche_obj else "general"

    prompt = f"""You are a web architect. Design a UNIQUE section order for this site.

BUSINESS: {industry} in {city}
NICHE: {niche_label}
UNIQUENESS SEED: {site_seed}

IMPORTANT: Use the seed to vary your choices. Two sites with different seeds
MUST produce different layouts. Do not always put "why_choose" first.

Choose a distinct layout for each page type from the allowed sections:

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
            # Safety: ensure required keys exist, fill missing from fallback
            for k, v in fallback.items():
                if k not in result:
                    result[k] = v
            print(f"   ✅ PAGE_DNA: home starts with [{result['home_section_order'][0]}]")
            return result
    except Exception as e:
        print(f"   ⚠️ PAGE_DNA generation failed: {e}")

    return fallback
# ==============================================================================
# 🎮 MAIN EXECUTION LOOP - WITH IMAGE MODEL SELECTION AND CITY VALIDATION
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

    # ── LANGUAGE ──────────────────────────────────────────────────────────────
    lang_input = cfg.get("language", "no").strip().lower()
    ui_lang    = "ar" if lang_input == "ar" else "en"
    is_rtl     = True if ui_lang == "ar" else False

    UI_DICT = {
    "en": {
        "home": "Home", "services": "Services", "blog": "Blog", "contact": "Contact", "about": "About Us",
        "get_quote": "Free Quote", "call_now": "Call Now", "whatsapp": "WhatsApp",
        "name_ph": "Name", "phone_ph": "Phone", "email_ph": "Email", "city_ph": "City",
        "needs_ph": "Your needs", "service_ph": "Select Service...", "submit_btn": "Get Instant Quote",
        "send_msg": "Send a Message", "send": "Send", "call_us": "Call Us", "visit_us": "Visit Us",
        "why_choose": "Why Choose Us?", "areas": "Areas We Serve in", "faq": "Frequently Asked Questions",
        "secure": "Secure & Confidential", "rights": "All rights reserved.", "dir": "ltr",
        "rated": "#1 Rated in", "licensed": "Licensed", "insured": "Insured", "24_7": "24/7 Service",
        "other_services": "Other Services", "learn_more": "Learn More", "current_svc": "Current Service",
        "related_svc": "Related Services", "explore_cat": "Explore Our Service Categories",
        "categories": "Categories",
        "company": "Company", "offices": "Our Offices", "directions": "Get Directions", "hq": "Headquarters",
        "more_qs": "Have more questions? Call us anytime!", "locations": "Locations", "loading": "Loading...",
        "menu": "Menu", "more": "More", "get_in_touch": "Get in Touch"
    },
    "ar": {
        "home": "الرئيسية", "services": "خدماتنا", "blog": "المدونة", "contact": "اتصل بنا", "about": "من نحن",
        "get_quote": "احصل على عرض سعر", "call_now": "اتصل الآن", "whatsapp": "واتساب",
        "name_ph": "الاسم", "phone_ph": "رقم الهاتف", "email_ph": "البريد الإلكتروني", "city_ph": "المدينة",
        "needs_ph": "تفاصيل الطلب", "service_ph": "...اختر الخدمة", "submit_btn": "احصل على السعر",
        "send_msg": "أرسل رسالة", "send": "إرسال", "call_us": "اتصل بنا", "visit_us": "تفضل بزيارتنا",
        "why_choose": "لماذا تختارنا؟", "areas": "المناطق التي نخدمها في", "faq": "الأسئلة الشائعة",
        "secure": "آمن وسري", "rights": "جميع الحقوق محفوظة.", "dir": "rtl",
        "rated": "الأفضل تقييماً في", "licensed": "مرخص", "insured": "مؤمن", "24_7": "خدمة 24/7",
        "other_services": "خدمات أخرى", "learn_more": "اعرف المزيد", "current_svc": "الخدمة الحالية",
        "related_svc": "خدمات ذات صلة", "explore_cat": "استكشف فئات خدماتنا",
        "categories": "الفئات",
        "company": "الشركة", "offices": "مكاتبنا", "directions": "احصل على الاتجاهات", "hq": "المقر الرئيسي",
        "more_qs": "لديك أسئلة أخرى؟ اتصل بنا في أي وقت!", "locations": "المواقع", "loading": "جاري التحميل...",
        "menu": "القائمة", "more": "المزيد", "get_in_touch": "تواصل معنا"
    }
    }
    ui = UI_DICT[ui_lang]

    # ── IMAGE / LOGO MODEL ────────────────────────────────────────────────────
    image_model_input = str(cfg.get("image_model", "1")).strip()
    Config.IMAGE_MODEL = "gpt" if image_model_input == "2" else "replicate"
    logo_model_input   = str(cfg.get("logo_model",  "1")).strip()
    Config.LOGO_MODEL  = "openai" if logo_model_input == "2" else "replicate"
    print(f"✅ Image: {Config.IMAGE_MODEL.upper()} | Logo: {Config.LOGO_MODEL.upper()}")

    # ── BUSINESS INPUTS ───────────────────────────────────────────────────────
    name     = cfg.get("business_name", "Global Services").strip()
    industry = cfg.get("industry",      "General").strip()
    country  = cfg.get("country",       "UAE").strip()
    state    = cfg.get("state",         "").strip()
    city     = cfg.get("city",          "Dubai").strip()
    phone    = cfg.get("phone",         "+971501234567").strip()

    site_domain = cfg.get("domain", "").strip().replace("https://","").replace("http://","").strip("/")
    Config.SITE_URL = f"https://{site_domain}" if site_domain else f"https://{name.lower().replace(' ','')}.com"
    print(f"✅ Business: {name} | City: {city} | URL: {Config.SITE_URL}")

    # ── SOCIAL LINKS ──────────────────────────────────────────────────────────
    facebook  = cfg.get("facebook",  "#")
    twitter   = cfg.get("twitter",   "#")
    instagram = cfg.get("instagram", "#")
    linkedin  = cfg.get("linkedin",  "#")
    youtube   = cfg.get("youtube",   "#")
    map_embed = cfg.get("map_embed", "")

    # ── MODE ──────────────────────────────────────────────────────────────────
    mode_input = str(cfg.get("mode", "1")).strip()
    print(f"✅ Mode: {mode_input}")

    # ── BACKLINKS / INTERNAL LINKS ────────────────────────────────────────────
    Config.GENERATE_BACKLINKS      = cfg.get("backlinks", "no").strip().lower() in ["yes","y"]
    Config.GENERATE_INTERNAL_LINKS = cfg.get("internal_links", "yes").strip().lower() in ["yes","y",""]

    # ── HUB TARGET URL (Mode 2 only) ──────────────────────────────────────────
    hub_target_url = ""
    if mode_input == "2":
        hub_target_url = cfg.get("hub_target_url", "/services/").strip()
        if not hub_target_url.startswith("/"): hub_target_url = "/" + hub_target_url
        if not hub_target_url.endswith("/"):   hub_target_url = hub_target_url + "/"
        if lang_input != "no":
            hub_target_url = f"/{lang_input}{hub_target_url}"
        Config.HUB_TARGET_URL    = hub_target_url
        Config.SERVICE_BASE_PATH = hub_target_url
        print(f"✅ Hub URL: {hub_target_url}")

    # ── CLEAN PHONE ───────────────────────────────────────────────────────────
    clean_phone = phone.replace(" ","").replace("-","").replace("(","").replace(")","").replace("+","")
    if not phone.startswith("+"): clean_phone = "+" + clean_phone

    services_list = []
    structure     = {}

    # 2. AI Colors
    print("\n🎨 Generating Brand Identity...")
    colors = {"primary": "#1e40af", "secondary": "#0f766e", "accent": "#d4af37"}
    if CLIENTS['openai']:
        
        try:
            c_resp = CLIENTS['openai'].chat.completions.create(
                model=Config.MODEL_LOW_TIER,
                messages=[{"role": "user", "content": f"Generate 3 VIBRANT, high-contrast, bright hex colors for a {industry} business. Return JSON with keys: primary, secondary, accent."}],
                response_format={"type": "json_object"} 
            )
            ai_colors = clean_json_response(c_resp.choices[0].message.content)
            if ai_colors and isinstance(ai_colors, dict):
                colors.update(ai_colors)
                print(f"    🎨 Colors: {colors}")
        except Exception as e:
            print(f"    ⚠️ Color Generation Error: {e}")
    
    # 3. Create folder structure first (will generate unique name)
    output_folder = create_folder_structure()
    
    # 4. Generate Logo - ENHANCED VERSION
    print("\n🖼️ Generating Business Logo...")
    b_data_temp = {
        "name": name,
        "industry": industry,
        "city": city,
        "country": country
    }
    logo_url = generate_logo(b_data_temp, output_folder) or "fas fa-tools"
    
    import hashlib as _hashlib
    _site_seed_src = f"{name}{industry}{city}{country}".lower().strip()
    _site_seed = int(_hashlib.md5(_site_seed_src.encode()).hexdigest()[:8], 16)

    b_data = {
        "name": name,
        "city": city,
        "state": state,
        "country": country,
        "industry": industry,
        "phone": phone,
        "whatsapp": clean_phone.lstrip('+'),
        "primary": colors.get('primary', '#1e40af'),
        "secondary": colors.get('secondary', '#0f766e'),
        "accent": colors.get('accent', '#d4af37'),
        "mode": mode_input,
        "domain": name.lower().replace(' ', '') + '.com',
        "google_sheet_url": Config.GOOGLE_SHEET_URL,
        "flat_services_list": [],
        "logo_url": logo_url,
        "facebook": facebook,
        "twitter": twitter,
        "instagram": instagram,
        "linkedin": linkedin,
        "youtube": youtube,
        "map_embed": map_embed,
        
        "lang_mode": lang_input,
        "target_lang": ui_lang,
        "is_rtl": is_rtl,
        "ui": ui,
        "site_seed": _site_seed,
        "generated_pages": ['index.html']  
    }
    # ── MODE-SPECIFIC SERVICE SETUP (config.json driven) ────────────────
    if mode_input == "1":
        main_service       = cfg.get("main_service", industry).strip()
        custom_sub_input   = cfg.get("sub_services", "").strip()
        _mode1_custom_subs = [s.strip() for s in custom_sub_input.split(",") if s.strip()] if custom_sub_input else []
        _mode1_flat_list   = [main_service] + _mode1_custom_subs if _mode1_custom_subs else [main_service]
        b_data['mode1_custom_subs']  = _mode1_custom_subs
        b_data['flat_services_list'] = _mode1_flat_list
        services_list = [main_service]
        print(f"✅ Mode 1 | Main: {main_service} | Subs: {len(_mode1_custom_subs)}")

    elif mode_input == "2":
        raw_svc   = cfg.get("sub_services", "Service 1, Service 2").strip()
        services_list = [s.strip() for s in raw_svc.split(",") if s.strip()]
        b_data['flat_services_list'] = services_list
        print(f"✅ Mode 2 | Hub pages: {len(services_list)}")

    elif mode_input == "3":
        raw_svc = cfg.get("services_mode3", "").strip()
        lines   = [s.strip() for s in raw_svc.split(",") if s.strip()]
        if lines:
            structure = analyze_structure_with_ai("\n".join(lines), "services", ui_lang)
            flat_ai = []
            for k, v in structure.items():
                if isinstance(v, dict) and "children" in v: flat_ai.extend(v["children"])
                elif isinstance(v, list): flat_ai.extend(v)
            orig_lower = {s.lower(): s for s in lines}
            ai_lower   = [s.lower() for s in flat_ai]
            missing    = [orig_lower[k] for k in orig_lower if k not in ai_lower]
            if missing:
                cats = list(structure.keys()) or ["General Services"]
                if not cats: structure["General Services"] = {"description":"Services","children":[]}
                for i, item in enumerate(missing):
                    cat = cats[i % len(cats)]
                    if isinstance(structure[cat], dict):
                        structure[cat].setdefault("children",[]).append(item)
        else:
            structure = {"General Services":{"description":"Comprehensive services","children":["Service 1","Service 2","Service 3"]}}
        final_flat = []
        for k, v in structure.items():
            if isinstance(v, dict) and "children" in v: final_flat.extend(v["children"])
            elif isinstance(v, list): final_flat.extend(v)
        b_data['flat_services_list'] = list(set(final_flat))
        print(f"✅ Mode 3 | Services: {len(b_data['flat_services_list'])}")
    # ─────────────────────────────────────────────────────────────────────
    Config.LOGO_URL = logo_url
    # 🎯 DESIGN SPEC — coordinated content personality for entire site
    design_spec = generate_design_spec(b_data)
    
    # ── H1 KEYWORD GUARANTEE: primary keyword force karo ─────────────────
    _loc  = b_data.get("city") or b_data.get("country", "")
    _ind  = b_data.get("industry", "")
    _kw_check = extract_keyword_tiers(b_data, _ind, _ind, _loc,
                                      b_data.get("target_lang", "en"))
    _primary_kw = (_kw_check.get("high_intent") or [None])[0]
    
    if _primary_kw:
        _h1 = design_spec.get("hero_title", "")
        if _primary_kw.lower() not in _h1.lower():
            # Silently fix: keyword ko title mein weave karo
            _words = _primary_kw.title().split()[:3]
            design_spec["hero_title"] = f"{' '.join(_words)} — {_loc}".strip(" —")
            print(f"   ⚡ H1 keyword fixed: \"{design_spec['hero_title']}\"")
    # ─────────────────────────────────────────────────────────────────────
    
    b_data['design_spec'] = design_spec
    print(f"   Hero: \"{design_spec['hero_title']}\"")
    print(f"   Badge: \"{design_spec['trust_badge']}\"")

    # 🔥 GLOBAL URL ROUTING FIX 🔥
    # This ensures that Home, About, and Service links point to the correct folder
    if lang_input != "no":
        Config.LANG_PREFIX = f"/{lang_input}"
        if Config.HUB_TARGET_URL:
            Config.SERVICE_BASE_PATH = Config.HUB_TARGET_URL
        else:
            Config.SERVICE_BASE_PATH = f"/{lang_input}/services/"
    else:
        Config.LANG_PREFIX = ""
        if Config.HUB_TARGET_URL:
            Config.SERVICE_BASE_PATH = Config.HUB_TARGET_URL
        else:
            Config.SERVICE_BASE_PATH = "/services/"

    if mode_input == "3":
        print("\n✅ Mode 3 — services already loaded from config.json")
    elif mode_input == "2":
        print(f"\n✅ Mode 2 Hub — {len(services_list)} pages from config.json")
        Config.HUB_TARGET_URL    = hub_target_url
        Config.SERVICE_BASE_PATH = hub_target_url
        Config.LANG_PREFIX = f"/{lang_input}" if lang_input != "no" else ""
    else:
        print(f"\n✅ Mode 1 — {len(b_data.get('flat_services_list',[]))} services from config.json")
        services_list = b_data.get('flat_services_list', [industry])[:1]
    # 🌐 TRIGGER INTERNATIONAL SEO TRANSLATION
    auto_translate_services(b_data, structure)

    # 5. Generate CSS and JS
    # --- NEW NICHE ENGINE LOGIC ---
    # Pass call_claude_json so unknown niches get a custom AI-designed profile.
    niche = NicheEngine(b_data, claude_caller=call_claude_json)
    b_data['niche_engine'] = niche

    # 💎 CSS Generate karne se pehle tokens nikal kar Header ke liye save karein
    from niche_engine import _get_business_tokens, _hue_shift
    tok = _get_business_tokens(b_data)
    p = niche.profile["palette"]
    
    # AI Colors ko Niche Engine ki logic se replace kar dein
    b_data['primary'] = _hue_shift(p["primary"], tok["hue_shift"])
    b_data['secondary'] = _hue_shift(p["secondary"], tok["hue_shift"] + tok["secondary_extra"])
    b_data['accent'] = p["accent"]

    # 🧬 PAGE DNA: one Claude call that makes every site's layout unique
    page_dna = generate_page_dna(b_data)
    b_data['page_dna'] = page_dna

    css_content = niche.get_css()
    css_path = os.path.join(output_folder, 'css', 'styles.css')
    os.makedirs(os.path.join(output_folder, 'css'), exist_ok=True)
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(css_content)

    # Update UI definitions dynamically
    b_data['ui']['get_quote'] = niche.cta_label
    b_data['ui']['cta_icon'] = niche.cta_icon
    b_data['image_mood_suffix'] = niche.get_image_prompt_suffix()
    Config.IMAGE_MOOD_SUFFIX = niche.get_image_prompt_suffix()
    # ------------------------------

    if b_data.get('is_rtl'):
        generate_rtl_css(output_folder)
    generate_js_file(b_data, output_folder)
    # 🔥 FIX: REMOVED generate_locations_js FROM HERE. It must run at the end! 🔥
    
    # 6. Generate Netlify Configuration
    generate_netlify_files(output_folder)
    
    # Initialize the pages list BEFORE we start generating HTML pages
    GENERATED_PAGES_LIST = ['index.html']
    
    # ROOT INDEX FOR MODE 1 AND MODE 2
    if mode_input in ["1", "2"]:
        _main_svc = b_data['flat_services_list'][0] if b_data['flat_services_list'] else industry
        if mode_input == "1":
            # Clean URL — .html hatao taake Netlify clean_urls double-301 na kare
            _target = f"/services/{slugify(_main_svc)}"
        else:
            _hub = Config.HUB_TARGET_URL.rstrip('/')
            _target = f"{_hub}/"
        index_redirect = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="0; url={_target}">
<link rel="canonical" href="{Config.SITE_URL.rstrip('/')}{_target}">
<title>{clean_title(_main_svc)} - {name}</title>
</head><body>
<script>window.location.replace("{_target}")</script>
<p>Redirecting... <a href="{_target}">Click here</a></p>
</body></html>"""
        index_path = os.path.join(output_folder, 'index.html')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(index_redirect)
        print(f"    ✅ Root index.html created → redirects to {_target}")
        if 'generated_pages' not in b_data:
            b_data['generated_pages'] = []
        if 'index.html' not in b_data['generated_pages']:
            b_data['generated_pages'].append('index.html')

    # 7. Generate Homepage (only for Mode 3)
    if mode_input == "3":
        print(f"\n🏠 Generating Homepage...")
        home_content = generate_page_content(b_data, "home")
        b_data['meta_description'] = home_content.get('meta_description', f"Professional {industry} services")
        b_data['meta_keywords'] = home_content.get('meta_keywords', f"{industry}, {city}, professional services")
        
        page_content = assemble_page_content("home", b_data, structure, home_content)
        schema_json = generate_hierarchical_schema(b_data, home_content, "Home", "/")
        
        page_content += f'\n<script type="application/ld+json">{schema_json}</script>'
        save_html_file(output_folder, 'index.html', page_content, b_data, f"Home - Professional {industry} Services", "/", structure, p_data=home_content)
    
    # 8. Generate Service Pages
    print(f"\n📄 Generating Service Pages...")
    
    if mode_input == "3":
        for category, data in structure.items():
            if not isinstance(data, dict):
                continue
            
            # Category Page
            print(f"\n📂 Generating Category: {category}...")
            cat_content = generate_page_content(b_data, "parent", category, sub_services=data.get('children', []))
            
            cat_page_content = assemble_page_content("parent", b_data, structure, cat_content, category, siblings=data.get('children', []))
            cat_schema = generate_hierarchical_schema(b_data, cat_content, category, f"/categories/{slugify(category)}.html", parent_category=None)
            cat_page_content += f'\n<script type="application/ld+json">{cat_schema}</script>'
            
            cat_filename = f"categories/{slugify(category)}.html"
            save_html_file(output_folder, cat_filename, cat_page_content, b_data, f"{clean_title(category)} Services", f"/categories/{slugify(category)}.html", structure, p_data=cat_content)
            
            # Child Pages — CRASH-SAFE: ek page fail ho to baqi pages bante rahein
            for service in data.get('children', []):
              try:
                print(f"    📄 Generating Service: {service}...")
                
                hero_img = get_hosted_image(service, "hero", industry, service_name=service)
                rel = get_service_relationships(service)
                
                child_content = generate_page_content(
                    b_data, "child", service,
                    parent_service=category,
                    sibling_services=rel.get('siblings', []),
                    child_services=rel.get('children', [])
                )
                
                child_page_content = assemble_page_content(
                    "child", b_data, structure, child_content, service,
                    siblings=rel.get('siblings', []),
                    parent_category=category,
                    is_child_page=True,
                    pre_generated_img=hero_img
                )
                
                child_schema = generate_hierarchical_schema(
                    b_data, child_content, service,
                    f"/services/{slugify(service)}.html",
                    parent_category=category,
                    is_child_page=True,
                    parent_url=f"/categories/{slugify(category)}.html"
                )
                child_page_content += f'\n<script type="application/ld+json">{child_schema}</script>'
                
                service_filename = f"services/{slugify(service)}.html"
                save_html_file(output_folder, service_filename, child_page_content, b_data, f"{clean_title(service)} Services", f"/services/{slugify(service)}.html", structure, p_data=child_content)
                
                if hero_img and Config.GENERATE_BACKLINKS:
                    base_url = Config.SITE_URL.rstrip('/')
                    live_link = f"{base_url}/services/{slugify(service)}.html"
                    social_desc = child_content.get('intro', f"Best {service} services in {city if city else country}")[:300]
                    BacklinkManager.create_devto_post(f"Expert Guide: {clean_title(service)}", social_desc, hero_img, live_link)
                    BacklinkManager.create_blogger_post(f"New Guide: {clean_title(service)}", social_desc, hero_img, live_link)
                
                time.sleep(Config.API_DELAY)
              except Exception as _pg_err:
                b_data.setdefault('_failed_pages', []).append(service)
                print(f"    ❌ Page FAILED, skipping to next: {service} — {str(_pg_err)[:100]}")
                continue

    elif mode_input == "3" and False:
        pass
    elif mode_input == "2":
        # 1. SETUP THE FOLDER NAME
        hub_folder_name = Config.HUB_TARGET_URL.strip('/')
        if not hub_folder_name: 
            hub_folder_name = "services"
            
        print(f"\n🔗 HUB MODE - Building Mini-Site in folder: /{hub_folder_name}/")
        
        # 2. GENERATE SERVICE PAGES (The Children)
        clean_services_list = [s for s in services_list if s.strip()]
        
        # We need a hero image for the hub home later
        hub_hero_img = None 

        for index, service in enumerate(clean_services_list):
            print(f"\n📄 Generating Hub Page: {service}...")
            
            hero_img = get_hosted_image(service, "hero", industry, service_name=service)
            if index == 0: hub_hero_img = hero_img # Save for hub home backlink

            siblings = [s for s in clean_services_list if s != service]
            
            s_content = generate_page_content(b_data, "child", service, sibling_services=siblings)
            
            s_page_content = assemble_page_content(
                "child", b_data, {}, s_content, service,
                siblings=siblings,
                is_child_page=True,
                pre_generated_img=hero_img
            )
            
            s_schema = generate_hierarchical_schema(b_data, s_content, service, f"/{hub_folder_name}/{slugify(service)}.html")
            s_page_content += f'\n<script type="application/ld+json">{s_schema}</script>'
            
            service_filename = f"{hub_folder_name}/{slugify(service)}.html"
            
            # ✅ FIXED: Absolute Canonical URL for Child Pages
            child_canonical = f"{Config.SITE_URL.rstrip('/')}/{hub_folder_name}/{slugify(service)}.html"
            
            save_html_file(output_folder, service_filename, s_page_content, b_data, f"{clean_title(service)}", child_canonical, structure, p_data=s_content)
            
            # ✅ FIXED: Backlinks with Absolute URL
            if hero_img and Config.GENERATE_BACKLINKS:
                live_link = child_canonical 
                social_desc = s_content.get('intro', f"Best {service} services")[:300]
                
                BacklinkManager.create_devto_post(f"Expert Guide: {clean_title(service)}", social_desc, hero_img, live_link)
                BacklinkManager.create_blogger_post(f"New Guide: {clean_title(service)}", social_desc, hero_img, live_link)
            
            time.sleep(Config.API_DELAY)
        # 3. GENERATE HUB HOMEPAGE
        print(f"\n🏠 Generating Hub Homepage ({hub_folder_name}/index.html)...")
        
        # 🟢 THE FIX: Strip 'ar/' or 'en/' from the folder name before making the title
        clean_hub_name = hub_folder_name
        
        # Safely get lang_input from b_data just in case
        current_lang = b_data.get('lang_mode', 'no')
        if current_lang != "no" and clean_hub_name.startswith(f"{current_lang}/"):
            # Removes 'ar/' from 'ar/riyadh-seo'
            clean_hub_name = clean_hub_name.replace(f"{current_lang}/", "", 1)
            
        # Generate the beautiful, clean title
        hub_title = clean_title(clean_hub_name.replace('-', ' ')) + " Services"
        
        # Safety net: Prevent "Riyadh Seo Services Services" if folder was named that way
        if hub_title.lower().endswith("services services"):
            hub_title = hub_title[:-9]

        # Generate the page content using the clean title
        hub_content = generate_page_content(b_data, "parent", hub_title, sub_services=clean_services_list)
        
        if not hub_hero_img:
            hub_hero_img = get_hosted_image(hub_title, "hero", industry, service_name=hub_title)

        hub_page_content = assemble_page_content(
            "parent", b_data, {}, hub_content, hub_title, 
            siblings=clean_services_list,
            pre_generated_img=hub_hero_img
        )
        
        # ✅ FIXED: Schema for Hub Index
        hub_schema = generate_hierarchical_schema(
            b_data, hub_content, hub_title, 
            f"/{hub_folder_name}/", 
            parent_category=None
        )
        hub_page_content += f'\n<script type="application/ld+json">{hub_schema}</script>'
        
        # ✅ FIXED: Absolute Canonical URL for Hub Homepage
        hub_canonical = f"{Config.SITE_URL.rstrip('/')}/{hub_folder_name}/"
        
        save_html_file(output_folder, f"{hub_folder_name}/index.html", hub_page_content, b_data, f"{hub_title} - Home", hub_canonical, structure, p_data=hub_content)
        
        # ✅ FIXED: Backlinks for Hub Index with Absolute URL
        if hub_hero_img and Config.GENERATE_BACKLINKS:
            print(f"   🔗 Generating Backlinks for Hub Homepage...")
            
            live_link = hub_canonical # Re-use absolute URL
            social_desc = hub_content.get('intro', f"Complete {hub_title} solutions in {city}")[:300]
            
            BacklinkManager.create_devto_post(f"Ultimate Guide: {hub_title}", social_desc, hub_hero_img, live_link)
            BacklinkManager.create_blogger_post(f"Overview: {hub_title}", social_desc, hub_hero_img, live_link)
    else:  # Mode 1 — Universal SaaS Landing Page
        for service in services_list:
            print(f"\n📄 Generating Mode 1 Universal Landing Page: {service}...")
            
            s_content = generate_page_content(b_data, "child", service)
            hero_img = get_hosted_image(service, "hero", industry, service_name=service)
            
            s_page_content = assemble_page_content(
                "child", b_data, {}, s_content, service, 
                siblings=[],  # No siblings for Mode 1
                is_child_page=True, 
                pre_generated_img=hero_img
            )
            
            s_schema = generate_hierarchical_schema(b_data, s_content, service, f"/services/{slugify(service)}.html")
            s_page_content += f'\n<script type="application/ld+json">{s_schema}</script>'
            
            service_filename = f"services/{slugify(service)}.html"
            save_html_file(output_folder, service_filename, s_page_content, b_data, f"{clean_title(service)} Services", f"/services/{slugify(service)}.html", structure, p_data=s_content)
            
            if hero_img and Config.GENERATE_BACKLINKS:
                base_url = Config.SITE_URL.rstrip('/') # Use absolute URL for Mode 1 too
                live_link = f"{base_url}/services/{slugify(service)}.html"
                social_desc = s_content.get('intro', f"Best {service} services")[:300]
                BacklinkManager.create_devto_post(f"Expert Guide: {clean_title(service)}", social_desc, hero_img, live_link)
                BacklinkManager.create_blogger_post(f"New Guide: {clean_title(service)}", social_desc, hero_img, live_link)
            
            time.sleep(Config.API_DELAY)

    # 9. Generate Contact Page (MODE 3 ONLY)
    if mode_input == "3":
        print(f"\n📄 Generating Contact Page...")
        contact_content = build_contact_html(b_data)
        save_html_file(output_folder, 'pages/contact.html', contact_content, b_data, f"Contact Us - {name}", validate_url("contact", None, mode_input), structure)
    
    # 10. Generate Services Index Page (MODE 3 ONLY)
    if mode_input == "3":
        print(f"\n📄 Generating Services Index Page...")
        arrow_icon = "mdi:arrow-left" if ui_lang == 'ar' else "mdi:arrow-right"
        
        services_index_content = f"""
        <section class="section">
            <div class="container">
                <h1 style="font-size: 2.5rem; margin-bottom: 30px; color: var(--primary); text-align: center;">{ui.get('services', 'Our Services')}</h1>
                <p style="font-size: 1.2rem; color: var(--text-gray); margin-bottom: 50px; text-align: center;">
                    Professional {industry} services in {city if city else country}
                </p>
                <div class="service-grid">
        """
        
        for service in b_data.get('flat_services_list', [])[:12]:
            img = get_hosted_image(service, "grid", industry, service_name=service)
            svc_btn = service_btn_label(service, ui_lang)
            services_index_content += f"""
                <div class="service-card">
                    <div class="service-card-img">
                        <img src="{img}" loading="lazy" alt="{clean_title(service)}">
                    </div>
                    <div class="service-card-content">
                        <h3>{clean_title(service)}</h3>
                        <div class="v360-desc-text">Professional {clean_title(service)} services in {city if city else country}.</div>
                        <a href="{validate_url("service", service, mode_input)}" class="btn btn-primary" style="width:100%; border-radius:50px;" aria-label="{svc_btn} - {clean_title(service)}">
                            <span class="iconify" data-icon="{arrow_icon}" data-width="20" style="margin-right:8px;"></span> {svc_btn}
                        </a>
                    </div>
                </div>
            """
            
        services_index_content += """
                </div>
            </div>
        </section>
        """
        
        save_html_file(output_folder, 'services/index.html', services_index_content, b_data, f"Our Services - {name}", validate_url("services_index", None, mode_input), structure)
    
    # 11. Generate Blog Page (MODE 3 ONLY)
    if mode_input == "3":
        print(f"\n📄 Generating Blog Page...")
        blog_content = f"""
        <section class="section">
            <div class="container">
                <h1 style="font-size: 2.5rem; margin-bottom: 30px; color: var(--primary); text-align: center;">{ui.get('blog', 'Our Blog')}</h1>
                <p style="font-size: 1.2rem; color: var(--text-gray); margin-bottom: 50px; text-align: center;">
                    Latest updates, tips, and insights from our team
                </p>
                <div style="text-align: center; padding: 100px 20px; background: var(--light-bg); border-radius: 20px;">
                    <span class="iconify" data-icon="mdi:newspaper-variant-outline" data-width="80" style="color: var(--primary); margin-bottom: 20px;"></span>
                    <h3 style="margin-bottom: 20px;">Coming Soon</h3>
                    <p style="color: var(--text-gray); max-width: 600px; margin: 0 auto;">
                        We're working on creating valuable content for you. Check back soon for updates!
                    </p>
                </div>
            </div>
        </section>
        """
        
        save_html_file(output_folder, 'blog/index.html', blog_content, b_data, f"Blog - {name}", "/blog/", structure)
    
    # 12. Generate Categories Index Page (MODE 3 ONLY)
    if mode_input == "3" and structure:
        print(f"\n📄 Generating Categories Index Page...")
        categories_index_content = f"""
        <section class="section">
            <div class="container">
                <h1 style="font-size: 2.5rem; margin-bottom: 30px; color: var(--primary); text-align: center;">{ui.get('explore_cat', 'Service Categories')}</h1>
                <p style="font-size: 1.2rem; color: var(--text-gray); margin-bottom: 50px; text-align: center;">
                    Browse our {industry} service categories
                </p>
                <div class="internal-links-grid">
        """
        
        for cat_name in structure.keys():
            children_count = len(structure[cat_name].get('children', [])) if isinstance(structure[cat_name], dict) else 0
            cat_icon = get_dynamic_icon(cat_name) 
            
            categories_index_content += f"""
            <a href="{validate_url("category", cat_name, mode_input)}" class="internal-link-card">
                <div class="link-icon">
                    <span class="iconify" data-icon="{cat_icon}" data-width="30" style="color: var(--primary);"></span>
                </div>
                <h4 style="margin-bottom:10px;">{clean_title(cat_name)}</h4>
                <p style="color: var(--text-gray);">{children_count} {ui.get('services', 'services').lower()} available</p>
            </a>
            """
        
        categories_index_content += """
                </div>
            </div>
        </section>
        """
        
        save_html_file(output_folder, 'categories/index.html', categories_index_content, b_data, f"Service Categories - {name}", validate_url("categories_index", None, mode_input), structure)
        
    # 13. Generate Additional Pages (About only - removed Privacy, Terms, Careers) (MODE 3 ONLY)
    if mode_input == "3":
        print(f"\n📄 Generating Additional Pages...")
        generate_additional_pages(output_folder, b_data, structure)
    # 13.9 LOCALIZE IMAGES — Cloudinary → local /images/ (zero live bandwidth)
    try:
        from image_localizer import localize_images
        localize_images(output_folder, b_data, Config.SITE_URL)
    except Exception as _le:
        print(f"   ⚠️ Image localization failed — Cloudinary URLs rakhe gaye: {_le}")

    # 14. Generate Sitemap
    print(f"\n🗺️ Generating Sitemap...")
    generate_sitemap(output_folder, b_data['generated_pages'], b_data)
    
    # 14.5 Generate Locations JS
    print(f"\n📍 Generating Locations Menu...")
    generate_locations_js(
        output_folder,
        b_data.get('generated_pages', []),
        b_data
    )
    
    # 15. Generate README
    generate_readme(output_folder, b_data, len(b_data.get('generated_pages', [])), len(b_data.get('flat_services_list', [])))
    print("\n" + "=" * 60)
    print(" ✅ STATIC SITE GENERATION COMPLETE!")
    print("=" * 60)
    print(f"\n 📁 Output folder: {os.path.abspath(output_folder)}/")
    print(f"\n 🚀 To deploy to Netlify:")
    print(f"    1. Go to https://app.netlify.com/drop")
    print(f"    2. Drag and drop the '{Config.OUTPUT_FOLDER}' folder")
    print(f"    3. Your site will be live instantly!")
    print("\n 📊 Site Statistics:")
    print(f"    - Total Pages: {len(b_data.get('generated_pages', []))}")
    print(f"    - Services: {len(b_data.get('flat_services_list', []))}")
    if mode_input == "1":
        print(f"    - Sub-Services: 6+ auto-generated per service")
    print(f"    - Categories: {len(structure) if structure else 0}")
    print(f"    - Layout Style: SEO-Safe Random (Grid/Zigzag)")
    print(f"    - Header Style: Simplified Universal Header - NO CSS CONFLICTS")
    print(f"    - Images: ALL images include FACES (no faceless people)")
    print(f"    - Images: Context-aware service demonstrations")
    print(f"    - Image Model: {Config.IMAGE_MODEL.upper()}")
    print(f"    - Zigzag: Each section has 6+ lines of text with PROPER links")
    print(f"    - Why Choose Us: EQUAL rich descriptive content on ALL pages")
    print(f"    - Internal Links: {'ENABLED' if Config.GENERATE_INTERNAL_LINKS else 'DISABLED'}")
    print(f"    - Backlinks: {'ENABLED' if Config.GENERATE_BACKLINKS else 'DISABLED'}")
    print(f"    - Footer: Enhanced with social links (Terms/Privacy/Careers removed)")
    print(f"    - Blog/Contact: Always present in all modes")
    print(f"    - Menu Text: Shortened to 2-3 words for cleaner display")
    print(f"    - Mobile Hero: Form GUARANTEED visible on all devices")
    print(f"    - Form Placeholders: Short, mobile-optimized text (Name, Phone, Service)")
    print(f"    - Meta Tags: Enhanced with related keywords and entities")
    print(f"    - Schema: Enhanced with LocalBusiness, Service, FAQ, Review")
    print(f"    - Folder: Unique timestamp folder - no overwrites")
    print("=" * 60)

if __name__ == "__main__":
    import sys
    try:
        run_generator()
    except KeyboardInterrupt:
        print("\n🛑 Generation stopped by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Critical Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

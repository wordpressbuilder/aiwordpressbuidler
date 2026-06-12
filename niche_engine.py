"""
NICHE-AWARE DESIGN ENGINE
=========================
Drop this file next to your main generator and import it.

Usage in your generate_css_file() and assemble_page_content():
    from niche_engine import NicheEngine
    niche = NicheEngine(b_data)
    css   = niche.get_css()          # replaces your full generate_css_file() output
    extra = niche.get_extra_sections(p_data, service_name)  # inject after hero
"""

import random
import re
import json
from datetime import datetime


# ==============================================================================
# 1. NICHE CLASSIFIER  — maps industry keywords → niche slug
# ==============================================================================
NICHE_MAP = {
    # key = niche slug, value = list of trigger keywords
    "medical":        ["doctor", "clinic", "medical", "physician", "health", "hospital",
                       "urgent care", "family medicine", "internal medicine"],
    "dental":         ["dent", "teeth", "tooth", "orthodont", "oral", "braces", "implant"],
    "home_services":  ["plumb", "electric", "hvac", "heat", "cool", "ac ", "roof", "paint",
                       "handyman", "appliance", "repair", "install", "window", "door",
                       "garage", "gutter", "pest", "landscap", "lawn", "clean"],
    "legal":          ["law", "lawyer", "attorney", "legal", "litigation", "firm"],
    "real_estate":    ["real estate", "realtor", "property", "mortgage", "broker",
                       "home buy", "home sell"],
    "restaurant":     ["restaurant", "cafe", "food", "catering", "bakery", "pizza",
                       "sushi", "diner"],
    "beauty":         ["salon", "beauty", "hair", "nail", "spa", "barber", "lash",
                       "makeup", "skincare"],
    "fitness":        ["gym", "fitness", "yoga", "crossfit", "pilates", "personal train",
                       "martial arts", "boxing", "dance"],
    "digital_agency": ["seo", "digital market", "ppc", "google ads", "social media",
                       "content market", "email market", "affiliate"],
    "web_dev":        ["web develop", "web design", "software", "app develop", "saas",
                       "mobile app", "ui/ux", "ecommerce"],
    "finance":        ["account", "tax", "bookkeep", "cpa", "financial plan", "invest",
                       "insurance", "mortgage"],
    "education":      ["tutoring", "school", "educat", "coaching", "online course",
                       "training center"],
    "auto":           ["auto", "car ", "mechanic", "tow", "vehicle", "tire", "brake",
                       "oil change", "collision"],
    "moving":         ["moving", "movers", "relocat", "storage", "packing"],
    "pet":            ["vet", "veterinar", "pet", "dog", "cat", "grooming", "animal"],
}

def classify_niche(industry: str, service_list: list = None) -> str:
    """Return the best niche slug for this business."""
    combined = (industry or "").lower()
    if service_list:
        combined += " " + " ".join(service_list[:10]).lower()

    best_niche, best_score = "general", 0
    for niche, keywords in NICHE_MAP.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > best_score:
            best_niche, best_score = niche, score
    return best_niche

# ==============================================================================
# 1.5 DYNAMIC PROFILE GENERATOR — for niches NOT in NICHE_PROFILES
# ==============================================================================

# Safe, pre-validated background keys the Claude profile is ALLOWED to use.
# This guarantees Claude can never invent a bg key that breaks generate_niche_css.
_ALLOWED_BG_KEYS = [
    "white", "light_gray", "light_blue", "sky_light", "orange_light",
    "cream", "green_light", "blush_light", "rose_subtle", "red_subtle",
    "gradient_subtle", "dark_navy_subtle",
]

# Safe Google-Fonts the niche_font_import() function already knows.
_ALLOWED_FONTS = [
    "Outfit", "Poppins", "Inter", "Merriweather",
    "Playfair Display", "Cormorant Garamond", "Barlow Condensed",
]

# Safe extra-section keys that have REAL builders (no broken stubs that return "").
_ALLOWED_SECTIONS = ["service_process_steps", "roi_stats_counter", "certifications_bar"]


def _sanitize_dynamic_profile(raw: dict, industry: str) -> dict:
    """
    Take Claude's raw JSON and force every value into a SAFE, known-good shape.
    Anything missing or invalid falls back to the 'general' profile value.
    This is what guarantees zero broken CSS / zero crashes.
    """
    base = NICHE_PROFILES["general"]
    safe = {}

    # ---- label ----
    safe["label"] = str(raw.get("label") or industry.title() or "Business")[:40]

    # ---- palette (validate each hex; fall back if malformed) ----
    def _hex(v, fallback):
        v = str(v or "").strip()
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
            return v
        return fallback
    rp = raw.get("palette", {}) if isinstance(raw.get("palette"), dict) else {}
    bp = base["palette"]
    safe["palette"] = {
        "primary":      _hex(rp.get("primary"),   bp["primary"]),
        "secondary":    _hex(rp.get("secondary"), bp["secondary"]),
        "accent":       _hex(rp.get("accent"),    bp["accent"]),
        "hero_overlay": bp["hero_overlay"],   # always safe overlay, never trust AI here
    }

    # ---- fonts (only allow known Google fonts) ----
    fp = raw.get("font_primary", "")
    fs = raw.get("font_secondary", "")
    safe["font_primary"]   = fp if fp in _ALLOWED_FONTS else "Outfit"
    safe["font_secondary"] = fs if fs in _ALLOWED_FONTS else "Outfit"

    # ---- CTA ----
    safe["cta_label"] = str(raw.get("cta_label") or base["cta_label"])[:30]
    safe["cta_icon"]  = base["cta_icon"]   # keep a guaranteed-valid FA icon

    # ---- trust items (list of short strings) ----
    ti = raw.get("trust_items")
    if isinstance(ti, list) and len(ti) >= 3:
        safe["trust_items"] = [str(x)[:40] for x in ti[:4]]
    else:
        safe["trust_items"] = base["trust_items"]

    # ---- extra sections (only allow ones with real builders) ----
    rs = raw.get("extra_sections")
    if isinstance(rs, list):
        cleaned = [s for s in rs if s in _ALLOWED_SECTIONS]
        safe["extra_sections"] = cleaned if cleaned else ["service_process_steps"]
    else:
        safe["extra_sections"] = ["service_process_steps"]

    # ---- bg_pattern (only allow LIGHT, pre-validated keys → no navy-text bug) ----
    rb = raw.get("bg_pattern")
    if isinstance(rb, list) and rb:
        cleaned = [k for k in rb if k in _ALLOWED_BG_KEYS]
        safe["bg_pattern"] = cleaned if len(cleaned) >= 2 else ["white", "light_gray", "white"]
    else:
        safe["bg_pattern"] = ["white", "light_gray", "white"]

    # ---- image mood ----
    safe["image_mood"] = str(raw.get("image_mood") or base["image_mood"])[:120]

    # ---- everything else: keep guaranteed-valid defaults ----
    safe["hero_style"]   = "lead_form"
    safe["card_style"]   = "standard_card"
    safe["faq_tone"]     = "friendly_professional"
    safe["schema_types"] = ["LocalBusiness", "Organization"]

    return safe


def generate_dynamic_profile(b_data: dict, claude_caller=None) -> dict:
    """
    Build a niche profile on-the-fly using Claude for businesses that don't
    match any built-in niche. `claude_caller` is a function (prompt, system) -> dict
    passed in from the generator (so this file stays import-free of your API code).
    Falls back to the 'general' profile if anything goes wrong.
    """
    industry = b_data.get("industry", "business")
    services = ", ".join(b_data.get("flat_services_list", [])[:8])

    # If no Claude caller was provided, just use general (100% safe).
    if not claude_caller:
        prof = dict(NICHE_PROFILES["general"])
        prof["label"] = industry.title()
        return prof

    prompt = f"""You are a senior brand & web designer. Design a website visual identity
for this business. Return ONLY JSON (no prose).

BUSINESS INDUSTRY: {industry}
SAMPLE SERVICES: {services}

Choose colours and styling that genuinely fit this industry's mood and audience.

Return EXACTLY this JSON shape:
{{
  "label": "short human label, e.g. 'Photography Studio'",
  "palette": {{
    "primary":   "#RRGGBB (main brand colour, must be a 6-digit hex)",
    "secondary": "#RRGGBB",
    "accent":    "#RRGGBB (a LIGHT tint, used for soft backgrounds)"
  }},
  "font_primary":   "ONE of: Outfit, Poppins, Inter, Merriweather, Playfair Display, Cormorant Garamond, Barlow Condensed",
  "font_secondary": "ONE of the same list (usually Outfit)",
  "cta_label": "2-3 word call to action button text fitting this industry",
  "trust_items": ["4 short trust signals customers of THIS industry care about"],
  "extra_sections": ["pick 1-2 ONLY from: service_process_steps, roi_stats_counter, certifications_bar"],
  "bg_pattern": ["pick 3-4 ONLY from: white, light_gray, light_blue, sky_light, orange_light, cream, green_light, blush_light, rose_subtle, red_subtle, gradient_subtle"],
  "image_mood": "5-8 keywords describing ideal photography mood for this industry"
}}

RULES:
- All palette values MUST be valid 6-digit hex like #1A73E8.
- 'accent' MUST be a very light/pale colour (it is used behind dark text).
- Do NOT invent font names or background keys outside the lists given.
- Output ONLY the JSON object."""

    try:
        raw = claude_caller(prompt, "You are a brand designer. Output only valid JSON.")
        if raw and isinstance(raw, dict):
            return _sanitize_dynamic_profile(raw, industry)
    except Exception as e:
        print(f"   ⚠️ Dynamic profile generation failed: {e}")

    # Ultimate safe fallback
    prof = dict(NICHE_PROFILES["general"])
    prof["label"] = industry.title()
    return prof
# ==============================================================================
# 1.6 HERO VARIANT DECISION — Claude picks the best hero layout per business
# ==============================================================================

# The only hero variants the generator knows how to render. Claude MUST pick
# from this list — anything else falls back to "split_form" (100% safe default).
_ALLOWED_HERO_VARIANTS = ["split_form", "centered_cta", "left_form_wide", "overlay_band"]


def decide_hero_variant(b_data: dict, niche_slug: str, claude_caller=None) -> dict:
    """
    Ask Claude which hero layout fits this business, and whether the lead-form
    should be shown. Returns a SAFE dict the generator can trust:
        {"variant": "<one of _ALLOWED_HERO_VARIANTS>", "show_form": bool}

    Emergency / urgent businesses → form strongly preferred.
    Premium / boutique businesses → form may be dropped for a cleaner look.
    Falls back to a safe split_form + show_form=True if anything goes wrong.
    """
    safe_default = {"variant": "split_form", "show_form": True}

    industry = b_data.get("industry", "business")
    services = ", ".join(b_data.get("flat_services_list", [])[:6])

    if not claude_caller:
        return safe_default

    prompt = f"""You are a senior conversion-focused web designer choosing a HERO layout
for a local business landing page. Return ONLY JSON.

BUSINESS INDUSTRY: {industry}
NICHE TYPE: {niche_slug}
SAMPLE SERVICES: {services}

Choose ONE hero layout that best fits this business type:

- "split_form": headline + text on one side, a lead-capture form on the other.
  Best for: urgent/emergency services, home services, lead-gen businesses.
- "left_form_wide": headline on top, a wide form band below it.
  Best for: high-urgency services where capturing the lead fast matters most.
- "centered_cta": big centered headline + call/WhatsApp buttons, NO form.
  Best for: premium, boutique, creative, or appointment-based brands.
- "overlay_band": centered headline with a slim contact band below, optional form.
  Best for: modern, design-forward brands that still want some lead capture.

Also decide "show_form":
- If this business is EMERGENCY / URGENT (people search in a crisis, e.g. plumber,
  locksmith, towing, AC repair, water damage) → show_form MUST be true.
- If it's premium / appointment / creative (e.g. photography, salon, fine dining,
  law boutique) → show_form may be false for a cleaner look.

Return EXACTLY:
{{
  "variant": "one of: split_form, left_form_wide, centered_cta, overlay_band",
  "show_form": true or false,
  "reason": "one short sentence"
}}

Output ONLY the JSON object."""

    try:
        raw = claude_caller(prompt, "You are a conversion web designer. Output only valid JSON.")
        if raw and isinstance(raw, dict):
            variant = raw.get("variant", "split_form")
            if variant not in _ALLOWED_HERO_VARIANTS:
                variant = "split_form"
            show_form = raw.get("show_form", True)
            # Coerce to a real bool no matter what Claude returns
            if isinstance(show_form, str):
                show_form = show_form.strip().lower() in ("true", "yes", "1")
            show_form = bool(show_form)
            reason = str(raw.get("reason", ""))[:120]
            print(f"   🎨 Hero variant: [{variant}] show_form={show_form} — {reason}")
            return {"variant": variant, "show_form": show_form}
    except Exception as e:
        print(f"   ⚠️ Hero variant decision failed: {e}")

    return safe_default
# ==============================================================================
# 1.7 CARD VARIANT RESOLVER — maps any profile card_style to 3 safe renderers
# ==============================================================================

# The only card layouts the generator knows how to render.
_ALLOWED_CARD_VARIANTS = ["image_top", "icon_left", "minimal_border"]

# Map every profile's card_style string onto one of the 3 real renderers.
_CARD_STYLE_MAP = {
    "image_top_clean":        "image_top",
    "food_card_full_image":   "image_top",
    "property_card":          "image_top",
    "gradient_border_card":   "image_top",
    "standard_card":          "image_top",
    "bold_icon_dark_header":  "icon_left",
    "icon_top_border_left":   "icon_left",
    "code_card_dark":         "icon_left",
    "dark_bold_card":         "icon_left",
    "minimal_serif_border":   "minimal_border",
    "elegant_rounded":        "minimal_border",
}


def _resolve_card_variant(card_style: str) -> str:
    """Turn any profile card_style into one of the 3 real card renderers."""
    v = _CARD_STYLE_MAP.get(card_style, "image_top")
    if v not in _ALLOWED_CARD_VARIANTS:
        v = "image_top"
    return v
# ==============================================================================
# 1.8 SECTION ORDER — stable shuffle of the SAFE middle sections only
# ==============================================================================

# Only these three "middle" sections are safe to reorder. Hero, services, and
# FAQ stay locked in place to protect layout integrity and SEO.
_SHUFFLE_SAFE_SECTIONS = ["why_choose", "reviews", "areas"]


def get_section_order(b_data: dict) -> list:
    """
    Return a STABLE shuffled order of the safe middle sections for this site.
    'Stable' = same business name always yields the same order (so re-running
    the generator doesn't randomly change the layout). Two DIFFERENT businesses
    get different orders → visual variety without breaking anything.
    """
    seed_src = (b_data.get("name", "") + b_data.get("industry", "")).lower().strip()
    seed = sum(ord(c) for c in seed_src) if seed_src else 0

    order = list(_SHUFFLE_SAFE_SECTIONS)
    rng = random.Random(seed)   # deterministic, seeded by business identity
    rng.shuffle(order)
    return order
# ==============================================================================
# 2. NICHE PROFILES  — each profile defines visual identity + section logic
# ==============================================================================
NICHE_PROFILES = {

    # ── MEDICAL ────────────────────────────────────────────────────────────────
    "medical": {
        "label": "Medical / Healthcare",
        # Color overrides (applied on top of AI brand colors if desired)
        "palette": {
            "primary":   "#0A5C8A",   # deep medical blue
            "secondary": "#157A6E",   # teal-green
            "accent":    "#E8F4FD",   # soft sky
            "hero_overlay": "rgba(10, 40, 70, 0.82)",
        },
        # Typography
        "font_primary":   "Merriweather",
        "font_secondary": "Outfit",
        # Hero CTA label override
        "cta_label":   "Book Appointment",
        "cta_icon":    "fa-calendar-check",
        # Trust bar items shown below hero
        "trust_items": [
            "Board Certified Physicians",
            "Same-Day Appointments",
            "Insurance Accepted",
            "HIPAA Compliant",
        ],
        # Which extra sections to inject (in order)
        "extra_sections": ["team_cards", "certifications_bar", "insurance_logos"],
        # Hero style: minimal form, show phone prominently
        "hero_style":  "appointment",
        # Card style for service grid
        "card_style":  "icon_top_border_left",
        # FAQ tone
        "faq_tone":    "clinical_reassuring",
        # Schema types
        "schema_types": ["MedicalClinic", "Physician"],
        # Color mood for images
        "image_mood":  "clean white clinical professional friendly",
        # Section background alternation pattern
        "bg_pattern":  ["white", "light_blue", "white", "light_blue"],
    },

    # ── DENTAL ────────────────────────────────────────────────────────────────
    "dental": {
        "label": "Dental Practice",
        "palette": {
            "primary":   "#1B6CA8",
            "secondary": "#34A8A4",
            "accent":    "#FFF8E7",
            "hero_overlay": "rgba(15, 50, 90, 0.80)",
        },
        "font_primary":   "Poppins",
        "font_secondary": "Outfit",
        "cta_label":   "Schedule Consultation",
        "cta_icon":    "fa-tooth",
        "trust_items": [
            "Painless Procedures",
            "Flexible Payment Plans",
            "State-of-the-Art Equipment",
            "Family Friendly",
        ],
        "extra_sections": ["before_after_gallery", "team_cards", "financing_badge"],
        "hero_style":  "appointment",
        "card_style":  "image_top_clean",
        "faq_tone":    "reassuring_comfort",
        "schema_types": ["Dentist", "MedicalOrganization"],
        "image_mood":  "bright white smile happy dental office",
        "bg_pattern":  ["white", "sky_light", "white"],
    },

    # ── HOME SERVICES ─────────────────────────────────────────────────────────
    "home_services": {
        "label": "Home Services",
        "palette": {
            "primary":   "#D44A15",   # urgent orange
            "secondary": "#1A2E4A",   # dark navy
            "accent":    "#FFD700",   # gold
            "hero_overlay": "rgba(15, 25, 40, 0.88)",
        },
        "font_primary":   "Outfit",
        "font_secondary": "Outfit",
        "cta_label":   "Get Free Estimate",
        "cta_icon":    "fa-tools",
        "trust_items": [
            "Licensed & Insured",
            "Same-Day Service",
            "Upfront Pricing",
            "5-Star Rated",
        ],
        "extra_sections": ["emergency_banner", "service_process_steps", "guarantee_badge"],
        "hero_style":  "lead_form",
        "card_style":  "bold_icon_dark_header",
        "faq_tone":    "direct_practical",
        "schema_types": ["HomeAndConstructionBusiness", "LocalBusiness"],
        "image_mood":  "professional technician tools work in progress",
        "bg_pattern":  ["white", "orange_light", "white", "light_gray"],
        # Special: emergency banner text
        "emergency_text": "⚡ 24/7 Emergency Service Available — Call Now!",
    },

    # ── LEGAL ─────────────────────────────────────────────────────────────────
    "legal": {
        "label": "Law Firm",
        "palette": {
            "primary":   "#1A1A2E",   # deep navy / authority
            "secondary": "#8B6914",   # gold / prestige
            "accent":    "#F5F0E8",   # cream
            "hero_overlay": "rgba(10, 10, 25, 0.90)",
        },
        "font_primary":   "Playfair Display",
        "font_secondary": "Outfit",
        "cta_label":   "Free Case Evaluation",
        "cta_icon":    "fa-balance-scale",
        "trust_items": [
            "No Win No Fee",
            "Confidential Consultation",
            "Decades of Experience",
            "Track Record of Success",
        ],
        "extra_sections": ["verdict_stats", "team_cards", "awards_bar"],
        "hero_style":  "appointment",
        "card_style":  "minimal_serif_border",
        "faq_tone":    "authoritative_clear",
        "schema_types": ["Attorney", "LegalService"],
        "image_mood":  "law office professional suit courtroom authority",
        "bg_pattern":  ["cream", "white", "dark_navy_subtle", "white"],
    },

    # ── REAL ESTATE ───────────────────────────────────────────────────────────
    "real_estate": {
        "label": "Real Estate",
        "palette": {
            "primary":   "#2C5F2E",   # forest green
            "secondary": "#97BC62",   # lime accent
            "accent":    "#FFF9F0",
            "hero_overlay": "rgba(20, 45, 22, 0.82)",
        },
        "font_primary":   "Outfit",
        "font_secondary": "Outfit",
        "cta_label":   "Browse Listings",
        "cta_icon":    "fa-home",
        "trust_items": [
            "MLS Listed Properties",
            "Free Home Valuation",
            "Local Market Experts",
            "Thousands of Happy Clients",
        ],
        "extra_sections": ["property_stats", "map_embed_section", "testimonials_carousel"],
        "hero_style":  "search_bar",
        "card_style":  "property_card",
        "faq_tone":    "friendly_informative",
        "schema_types": ["RealEstateAgent", "LocalBusiness"],
        "image_mood":  "beautiful home exterior suburb neighborhood",
        "bg_pattern":  ["white", "green_light", "white"],
    },

    # ── RESTAURANT ────────────────────────────────────────────────────────────
    "restaurant": {
        "label": "Restaurant / Food",
        "palette": {
            "primary":   "#C0392B",   # appetite red
            "secondary": "#F39C12",   # warm amber
            "accent":    "#FEF9EF",
            "hero_overlay": "rgba(40, 10, 5, 0.80)",
        },
        "font_primary":   "Playfair Display",
        "font_secondary": "Outfit",
        "cta_label":   "Reserve a Table",
        "cta_icon":    "fa-utensils",
        "trust_items": [
            "Fresh Ingredients Daily",
            "Chef-Crafted Menu",
            "Private Dining Available",
            "Online Reservations",
        ],
        "extra_sections": ["menu_preview", "chef_spotlight", "reservation_widget"],
        "hero_style":  "minimal_cta",
        "card_style":  "food_card_full_image",
        "faq_tone":    "warm_hospitable",
        "schema_types": ["Restaurant", "FoodEstablishment"],
        "image_mood":  "delicious food plated restaurant atmosphere warm lighting",
        "bg_pattern":  ["cream", "white", "orange_light"],
    },

    # ── BEAUTY ────────────────────────────────────────────────────────────────
    "beauty": {
        "label": "Beauty / Salon / Spa",
        "palette": {
            "primary":   "#9B4D7A",   # rose-mauve
            "secondary": "#D4A5B5",   # blush
            "accent":    "#FFF5F8",
            "hero_overlay": "rgba(60, 20, 50, 0.78)",
        },
        "font_primary":   "Cormorant Garamond",
        "font_secondary": "Outfit",
        "cta_label":   "Book Your Session",
        "cta_icon":    "fa-spa",
        "trust_items": [
            "Certified Stylists",
            "Luxury Products",
            "Relaxing Atmosphere",
            "Online Booking 24/7",
        ],
        "extra_sections": ["before_after_gallery", "team_cards", "loyalty_badge"],
        "hero_style":  "minimal_cta",
        "card_style":  "elegant_rounded",
        "faq_tone":    "warm_luxurious",
        "schema_types": ["BeautySalon", "HealthAndBeautyBusiness"],
        "image_mood":  "luxury beauty salon elegant soft light serene",
        "bg_pattern":  ["blush_light", "white", "rose_subtle"],
    },

    # ── FITNESS ───────────────────────────────────────────────────────────────
    "fitness": {
        "label": "Fitness / Gym",
        "palette": {
            "primary":   "#E63946",   # high-energy red
            "secondary": "#1D1D1D",   # near-black
            "accent":    "#F4D03F",   # electric yellow
            "hero_overlay": "rgba(15, 15, 15, 0.85)",
        },
        "font_primary":   "Barlow Condensed",
        "font_secondary": "Outfit",
        "cta_label":   "Start Free Trial",
        "cta_icon":    "fa-dumbbell",
        "trust_items": [
            "Open 24/7",
            "Certified Trainers",
            "State-of-the-Art Equipment",
            "No Long-Term Contract",
        ],
        "extra_sections": ["transformation_stats", "class_schedule", "trainer_cards"],
        "hero_style":  "energy_cta",
        "card_style":  "dark_bold_card",
        "faq_tone":    "motivational_direct",
        "schema_types": ["ExerciseGym", "SportsActivityLocation"],
        "image_mood":  "gym workout intense athlete energy motion",
        "bg_pattern":  ["white", "light_gray", "red_subtle", "white"],
    },

    # ── DIGITAL AGENCY ────────────────────────────────────────────────────────
    "digital_agency": {
        "label": "Digital Marketing Agency",
        "palette": {
            "primary":   "#4F46E5",   # electric indigo
            "secondary": "#7C3AED",   # violet
            "accent":    "#F0FDFA",
            "hero_overlay": "rgba(20, 15, 60, 0.88)",
        },
        "font_primary":   "Inter",
        "font_secondary": "Outfit",
        "cta_label":   "Get Free Audit",
        "cta_icon":    "fa-chart-line",
        "trust_items": [
            "Google Premier Partner",
            "500+ Clients Served",
            "Average 340% ROI",
            "No Lock-In Contracts",
        ],
        "extra_sections": ["roi_stats_counter", "client_logos", "case_study_snippet"],
        "hero_style":  "lead_form",
        "card_style":  "gradient_border_card",
        "faq_tone":    "data_driven_confident",
        "schema_types": ["ProfessionalService", "LocalBusiness"],
        "image_mood":  "modern office team dashboard analytics data",
        "bg_pattern":  ["white", "gradient_subtle", "white", "light_gray"],
    },

    # ── WEB DEV ───────────────────────────────────────────────────────────────
    "web_dev": {
        "label": "Web / Software Development",
        "palette": {
            "primary":   "#0F172A",   # dark slate
            "secondary": "#38BDF8",   # sky blue
            "accent":    "#F8FAFC",
            "hero_overlay": "rgba(5, 10, 25, 0.92)",
        },
        "font_primary":   "JetBrains Mono",
        "font_secondary": "Outfit",
        "cta_label":   "Start Your Project",
        "cta_icon":    "fa-code",
        "trust_items": [
            "Agile Development",
            "Clean Scalable Code",
            "Post-Launch Support",
            "On-Time Delivery",
        ],
        "extra_sections": ["tech_stack_badges", "portfolio_grid", "github_stats"],
        "hero_style":  "minimal_cta",
        "card_style":  "code_card_dark",
        "faq_tone":    "technical_clear",
        "schema_types": ["WebDesignAgency", "Organization"],
        "image_mood":  "modern tech code monitor dark developer workspace",
        "bg_pattern":  ["white", "light_gray", "sky_light"],
    },

    # ── AUTO ──────────────────────────────────────────────────────────────────
    "auto": {
        "label": "Automotive",
        "palette": {
            "primary":   "#B91C1C",   # bold red
            "secondary": "#1C1C1E",   # carbon black
            "accent":    "#FFD60A",   # chrome yellow
            "hero_overlay": "rgba(10, 10, 10, 0.87)",
        },
        "font_primary":   "Outfit",
        "font_secondary": "Outfit",
        "cta_label":   "Book Service Appointment",
        "cta_icon":    "fa-car",
        "trust_items": [
            "ASE Certified Technicians",
            "OEM Parts Used",
            "Free Diagnostics",
            "Loaner Cars Available",
        ],
        "extra_sections": ["emergency_banner", "service_process_steps", "warranty_badge"],
        "hero_style":  "lead_form",
        "card_style":  "bold_icon_dark_header",
        "faq_tone":    "direct_practical",
        "schema_types": ["AutoRepair", "AutomotiveBusiness"],
        "image_mood":  "car mechanic garage professional automotive",
        "bg_pattern":  ["white", "red_subtle", "light_gray"],
    },

    # ── GENERAL FALLBACK ──────────────────────────────────────────────────────
    "general": {
        "label": "General Business",
        "palette": {
            "primary":   "#1A73E8",
            "secondary": "#34A853",
            "accent":    "#FFB300",
            "hero_overlay": "rgba(15, 23, 42, 0.85)",
        },
        "font_primary":   "Outfit",
        "font_secondary": "Outfit",
        "cta_label":   "Get Free Quote",
        "cta_icon":    "fa-file-invoice-dollar",
        "trust_items": [
            "Licensed & Insured",
            "Free Consultations",
            "Satisfaction Guaranteed",
            "Fast Response",
        ],
        "extra_sections": ["service_process_steps"],
        "hero_style":  "lead_form",
        "card_style":  "standard_card",
        "faq_tone":    "friendly_professional",
        "schema_types": ["LocalBusiness", "Organization"],
        "image_mood":  "professional business service",
        "bg_pattern":  ["white", "light_gray", "white"],
    },
}


# ==============================================================================
# 3. CSS THEME GENERATOR  — one per niche, fully distinct visual identity
# ==============================================================================

# Background color values mapped from bg_pattern names
BG_COLORS = {
    "white":             "#ffffff",
    "light_gray":        "#f8fafc",
    "light_blue":        "#EFF6FF",
    "sky_light":         "#F0F9FF",
    "orange_light":      "#FFF7ED",
    "dark_navy":         "#0f1d2e",
    "dark_navy_subtle":  "#f1f5f9",
    "cream":             "#FAF7F2",
    "green_light":       "#F0FDF4",
    "blush_light":       "#FFF0F5",
    "rose_subtle":       "#FFF5F8",
    "black":             "#111111",
    "red_dark":          "#1a0505",
    "red_subtle":        "#FFF5F5",
    "dark_indigo":       "#0f0e2a",
    "gradient_subtle":   "#f5f3ff",
    "dark_slate":        "#0f172a",
    "dark_charcoal":     "#1a1a1a",
    "dark_carbon":       "#111111",
}


def niche_font_import(profile: dict) -> str:
    """Return Google Fonts import for the niche."""
    fonts = {
        "Merriweather":         "Merriweather:wght@400;700;900",
        "Poppins":              "Poppins:wght@400;500;600;700",
        "Playfair Display":     "Playfair+Display:wght@400;600;700;900",
        "Cormorant Garamond":   "Cormorant+Garamond:wght@400;500;600;700",
        "Barlow Condensed":     "Barlow+Condensed:wght@400;600;700;800",
        "Inter":                "Inter:wght@400;500;600;700",
        "JetBrains Mono":       "JetBrains+Mono:wght@400;500;700",
        "Outfit":               "Outfit:wght@300;400;500;600;700;800",
    }
    p_font = profile.get("font_primary", "Outfit")
    s_font = profile.get("font_secondary", "Outfit")
    families = set()
    for f in [p_font, s_font]:
        if f in fonts:
            families.add(fonts[f])
    return "&family=".join(sorted(families))


def get_section_bg(profile: dict, index: int) -> str:
    """Return CSS background color for section by index."""
    pattern = profile.get("bg_pattern", ["white", "light_gray"])
    key = pattern[index % len(pattern)]
    return BG_COLORS.get(key, "#ffffff")


def generate_niche_css(b_data: dict, profile: dict) -> str:
    """
    Generate a complete, distinct CSS file for the given niche.
    Returns the full CSS string to write to styles.css.
    """
    p      = profile["palette"]
    primary   = b_data.get("primary",   p["primary"])
    secondary = b_data.get("secondary", p["secondary"])
    accent    = b_data.get("accent",    p["accent"])
    overlay   = p.get("hero_overlay",  "rgba(15,23,42,0.85)")
    font_p    = profile.get("font_primary",   "Outfit")
    font_s    = profile.get("font_secondary", "Outfit")

    # Section backgrounds from pattern
    sec0 = get_section_bg(profile, 0)
    sec1 = get_section_bg(profile, 1)
    sec2 = get_section_bg(profile, 2)
    sec3 = get_section_bg(profile, 3)

    niche_label = profile.get("label", "Business")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    css = f"""/* ============================================================
   NICHE-AWARE STYLESHEET — {niche_label}
   Generated: {now}
   ============================================================ */

:root {{
    --primary:     {primary};
    --secondary:   {secondary};
    --accent:      {accent};
    --gold:        #D4AF37;
    --gold-secondary: #B8960C;
    --gold-text:   #7A5C00;
    --dark:        #0f172a;
    --text-dark:   #0f172a;
    --text-gray:   #64748b;
    --light-bg:    #f8fafc;
    --white:       #ffffff;
    --shadow-sm:   0 1px 3px rgba(0,0,0,0.12);
    --shadow-md:   0 4px 6px rgba(0,0,0,0.1);
    --shadow-lg:   0 10px 25px rgba(0,0,0,0.1);
    --border-radius:   8px;
    --transition:      all 0.3s ease;
    --container-width: 1200px;
    --font-primary:    '{font_p}', sans-serif;
    --font-secondary:  '{font_s}', sans-serif;
    --hero-overlay:    {overlay};
    --sec0: {sec0}; --sec1: {sec1}; --sec2: {sec2}; --sec3: {sec3};
}}

*, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; }}

body {{
    font-family: var(--font-secondary);
    color: var(--text-dark);
    line-height: 1.6;
    overflow-x: hidden;
    background: var(--white);
}}

h1, h2, h3 {{ font-family: var(--font-primary); }}

#v360-wrapper .container {{
    max-width: var(--container-width);
    margin: 0 auto;
    padding: 0 20px;
    width: 100%;
}}

/* ── SECTION ALTERNATING BACKGROUNDS ── */
#v360-wrapper .section:nth-child(4n+1) {{ background: var(--sec0); }}
#v360-wrapper .section:nth-child(4n+2) {{ background: var(--sec1); }}
#v360-wrapper .section:nth-child(4n+3) {{ background: var(--sec2); }}
#v360-wrapper .section:nth-child(4n+4) {{ background: var(--sec3); }}
#v360-wrapper .section {{ padding: 60px 0; position: relative; }}

/* ── HERO ── */
#v360-wrapper .hero {{
    position: relative;
    padding: 70px 0 90px;
    background-size: cover;
    background-position: center;
    color: white;
    min-height: 620px;
    display: flex;
    align-items: center;
}}

#v360-wrapper .hero-overlay {{
    position: absolute;
    inset: 0;
    background: var(--hero-overlay);
}}

#v360-wrapper .hero-content {{
    position: relative;
    z-index: 2;
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    gap: 40px;
    align-items: center;
    width: 100%;
}}

#v360-wrapper .hero-title {{
    line-height: 1.1;
    margin-bottom: 20px;
    font-weight: 800;
    color: white;
    font-size: clamp(2rem, 5vw, 3.5rem);
    text-shadow: 0 2px 6px rgba(0,0,0,0.5);
}}

#v360-wrapper .hero-sub {{
    font-size: 1.2rem;
    line-height: 1.5;
    margin-bottom: 25px;
    color: rgba(255,255,255,0.92);
}}

/* ══ HERO VARIANT: centered_cta (no form, big centered headline) ══ */
#v360-wrapper .hero.hv-centered_cta .hero-content {{
    grid-template-columns: 1fr;
    text-align: center;
    max-width: 860px;
    margin: 0 auto;
}}
#v360-wrapper .hero.hv-centered_cta .text-col {{ width: 100%; }}
#v360-wrapper .hero.hv-centered_cta .hero-gold-badge,
#v360-wrapper .hero.hv-overlay_band .hero-gold-badge {{ margin-left: auto; margin-right: auto; }}
#v360-wrapper .hero.hv-centered_cta .hero-features,
#v360-wrapper .hero.hv-centered_cta .btn-group {{ justify-content: center; }}

/* ══ HERO VARIANT: left_form_wide (text top, wide form band below) ══ */
#v360-wrapper .hero.hv-left_form_wide .hero-content {{
    grid-template-columns: 1fr;
    gap: 30px;
}}
#v360-wrapper .hero.hv-left_form_wide .form-col {{ width: 100%; }}
#v360-wrapper .hero.hv-left_form_wide .glass-card {{
    max-width: 100%;
}}
#v360-wrapper .hero.hv-left_form_wide .glass-card form {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    align-items: end;
}}
#v360-wrapper .hero.hv-left_form_wide .glass-card form input,
#v360-wrapper .hero.hv-left_form_wide .glass-card form select,
#v360-wrapper .hero.hv-left_form_wide .glass-card form button {{
    margin-bottom: 0;
}}
#v360-wrapper .hero.hv-left_form_wide .glass-card h3 {{ grid-column: 1 / -1; text-align: left; }}

/* ══ HERO VARIANT: overlay_band (centered text + slim band) ══ */
#v360-wrapper .hero.hv-overlay_band .hero-content {{
    grid-template-columns: 1fr;
    text-align: center;
    max-width: 920px;
    margin: 0 auto;
}}
#v360-wrapper .hero.hv-overlay_band .hero-features,
#v360-wrapper .hero.hv-overlay_band .btn-group {{ justify-content: center; }}
#v360-wrapper .hero.hv-overlay_band .form-col {{ width: 100%; margin-top: 10px; }}
#v360-wrapper .hero.hv-overlay_band .glass-card {{ max-width: 680px; margin: 0 auto; }}

/* ── NICHE-SPECIFIC TRUST BADGE ── */
#v360-wrapper .hero-gold-badge {{
    background: linear-gradient(135deg, var(--accent) 0%, {primary} 100%);
    color: white;
    padding: 8px 22px;
    border-radius: 30px;
    font-weight: 700;
    display: inline-block;
    margin-bottom: 18px;
    font-size: 0.95rem;
    box-shadow: 0 4px 15px rgba(0,0,0,0.25);
}}

/* ── NICHE-SPECIFIC BUTTONS ── */
#v360-wrapper .btn {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 14px 28px;
    border-radius: 50px;
    font-weight: 700;
    text-decoration: none;
    transition: var(--transition);
    cursor: pointer;
    border: none;
    font-family: var(--font-secondary);
    font-size: 1rem;
}}

#v360-wrapper .btn-primary {{
    background: {primary};
    color: white;
    box-shadow: 0 4px 18px rgba(0,0,0,0.25);
}}

#v360-wrapper .btn-primary:hover {{
    transform: translateY(-3px);
    filter: brightness(1.1);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}}

#v360-wrapper .btn-accent {{
    background: {accent};
    color: {primary};
    box-shadow: 0 4px 15px rgba(0,0,0,0.15);
}}

/* ── GLASS CARD (HERO FORM) ── */
#v360-wrapper .glass-card {{
    background: rgba(255,255,255,0.14);
    backdrop-filter: blur(18px);
    border: 1px solid rgba(255,255,255,0.28);
    padding: 32px;
    border-radius: 20px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.3);
}}

#v360-wrapper .glass-card h3 {{
    margin-bottom: 20px;
    color: white;
    font-size: 1.45rem;
    text-align: center;
    font-family: var(--font-primary);
}}

#v360-wrapper .glass-card input,
#v360-wrapper .glass-card select {{
    width: 100%;
    padding: 13px 16px;
    margin-bottom: 14px;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,0.35);
    background: rgba(255,255,255,0.92);
    font-size: 0.97rem;
    color: var(--text-dark);
    font-family: var(--font-secondary);
}}

#v360-wrapper .glass-card button {{
    width: 100%;
    padding: 15px;
    background: {primary};
    color: white;
    border: none;
    border-radius: 10px;
    font-size: 1.05rem;
    font-weight: 700;
    cursor: pointer;
    transition: var(--transition);
    font-family: var(--font-secondary);
}}

#v360-wrapper .glass-card button:hover {{
    filter: brightness(1.12);
    transform: translateY(-2px);
}}

/* ── SERVICE CARDS (base — overridden by niche card style) ── */
#v360-wrapper .service-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 30px;
    margin-top: 40px;
}}

#v360-wrapper .service-card {{
    background: white;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: var(--shadow-lg);
    transition: all 0.4s ease;
    border: 1px solid #e2e8f0;
    display: flex;
    flex-direction: column;
}}

#v360-wrapper .service-card:hover {{
    transform: translateY(-8px);
    box-shadow: 0 20px 40px rgba(0,0,0,0.14);
}}

#v360-wrapper .service-card-img {{ height: 200px; overflow: hidden; }}
#v360-wrapper .service-card-img img {{
    width: 100%; height: 100%; object-fit: cover;
    transition: transform 0.5s ease;
}}
#v360-wrapper .service-card:hover img {{ transform: scale(1.05); }}

#v360-wrapper .service-card-content {{
    padding: 24px;
    flex-grow: 1;
    display: flex;
    flex-direction: column;
}}

#v360-wrapper .service-card h3 {{
    font-size: 1.2rem;
    margin-bottom: 10px;
    color: {primary};
    font-family: var(--font-primary);
}}

#v360-wrapper .service-card p, #v360-wrapper .v360-desc-text {{
    color: var(--text-gray);
    margin-bottom: 18px;
    flex-grow: 1;
    font-size: 0.96rem;
    line-height: 1.65;
}}

/* ══ CARD VARIANT: icon_left (no image, icon beside text — fast & clean) ══ */
#v360-wrapper .service-card.cv-icon_left {{
    flex-direction: row;
    align-items: flex-start;
    gap: 18px;
    padding: 26px;
}}
#v360-wrapper .service-card.cv-icon_left .cv-icon-box {{
    flex-shrink: 0;
    width: 60px; height: 60px;
    border-radius: 14px;
    background: linear-gradient(135deg, {accent} 0%, {primary} 100%);
    display: flex; align-items: center; justify-content: center;
    color: white;
}}
#v360-wrapper .service-card.cv-icon_left .service-card-content {{ padding: 0; }}

/* ══ CARD VARIANT: minimal_border (flat, thin border, premium) ══ */
#v360-wrapper .service-card.cv-minimal_border {{
    box-shadow: none;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}}
#v360-wrapper .service-card.cv-minimal_border:hover {{
    box-shadow: 0 8px 24px rgba(0,0,0,0.08);
    border-color: {primary};
    transform: translateY(-4px);
}}
#v360-wrapper .service-card.cv-minimal_border .service-card-img {{ height: 170px; }}

/* ── INFOGRAPHIC / WHY CHOOSE US ── */

/* ── INFOGRAPHIC / WHY CHOOSE US ── */
#v360-wrapper .infographic-grid {{
    display: grid !important;
    grid-template-columns: repeat(3, 1fr) !important;
    gap: 30px;
    margin-top: 40px;
}}

#v360-wrapper .infographic-item {{
    background: white;
    border-radius: 18px;
    padding: 32px 24px;
    text-align: center;
    box-shadow: var(--shadow-lg);
    transition: all 0.4s ease;
    border: 1px solid #e2e8f0;
    display: flex;
    flex-direction: column;
    align-items: center;
}}

#v360-wrapper .infographic-item:hover {{
    transform: translateY(-8px);
    box-shadow: 0 20px 40px rgba(0,0,0,0.12);
}}

#v360-wrapper .infographic-icon {{
    width: 80px; height: 80px;
    background: linear-gradient(135deg, {accent} 0%, {primary} 100%);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 20px;
    font-size: 1.8rem; color: white;
    box-shadow: 0 8px 20px rgba(0,0,0,0.15);
}}

#v360-wrapper .infographic-number {{
    font-size: 2.5rem; font-weight: 800;
    background: linear-gradient(135deg, {primary} 0%, {secondary} 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 10px;
    font-family: var(--font-primary);
}}

#v360-wrapper .infographic-item h4 {{
    margin: 10px 0 12px; color: var(--text-dark);
    font-size: 1.25rem; font-family: var(--font-primary);
}}

/* ── ZIGZAG ── */
#v360-wrapper .zigzag-item {{
    display: flex; align-items: center; gap: 50px; margin-bottom: 60px;
}}
#v360-wrapper .zigzag-item.reverse {{ flex-direction: row-reverse; }}
#v360-wrapper .zigzag-content, #v360-wrapper .zigzag-img-wrap {{ flex: 1; }}
#v360-wrapper .zigzag-img {{
    width: 100%; border-radius: 18px;
    box-shadow: 0 15px 40px rgba(0,0,0,0.15);
    height: auto; min-height: 320px; max-height: 500px;
    object-fit: cover;
    transition: transform 0.5s ease;
    display: block;
}}
#v360-wrapper .zigzag-img-wrap {{
    display: flex;
    align-items: stretch;
}}
#v360-wrapper .zigzag-img:hover {{ transform: scale(1.02); }}
#v360-wrapper .zigzag-content h3 {{
    font-size: 1.9rem; margin-bottom: 20px;
    color: {primary}; font-family: var(--font-primary);
}}

/* ── FAQ ── */
#v360-wrapper .faq-item {{
    margin-bottom: 12px; background: white;
    border-radius: 12px; overflow: hidden;
    border: 1px solid #e2e8f0;
    box-shadow: var(--shadow-sm);
}}
#v360-wrapper .faq-question {{
    padding: 22px 24px; cursor: pointer;
    font-weight: 600; display: flex;
    justify-content: space-between; align-items: center;
    background: #f8fafc; font-size: 1.05rem;
    font-family: var(--font-primary);
}}
#v360-wrapper .faq-answer {{
    padding: 0 24px 22px; display: none;
    color: var(--text-gray); border-top: 1px solid #f1f5f9;
    padding-top: 18px; line-height: 1.8;
}}

/* ── REVIEWS ── */
#v360-wrapper .review-card {{
    background: white; padding: 28px;
    border-radius: 14px; margin-bottom: 20px;
    border-left: 5px solid {primary};
    box-shadow: var(--shadow-sm);
}}

/* ── FOOTER ── */
#v360-wrapper .site-footer {{
    background: #1e293b;
    color: white; padding: 60px 0 20px;
}}
#v360-wrapper .footer-grid {{
    display: grid;
    grid-template-columns: 2fr 1fr 1.5fr 1.5fr;
    gap: 40px; margin-bottom: 40px;
}}

/* ── INTERNAL LINKS ── */
#v360-wrapper .internal-links-section {{
    background: linear-gradient(135deg, #f8fafc 0%, white 100%);
    border-radius: 20px; padding: 40px;
    margin: 40px 0; border: 1px solid #e2e8f0;
}}
#v360-wrapper .internal-links-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px;
}}

/* ── AREAS SERVED ── */
#v360-wrapper .pill-container {{ display:flex; flex-wrap:wrap; gap:12px; justify-content:center; }}
#v360-wrapper .pill {{
    background: white; border: 1px solid #e2e8f0;
    padding: 10px 22px; border-radius: 50px;
    font-size: 0.9rem; color: var(--text-gray);
    transition: all 0.3s; font-weight: 500;
}}
#v360-wrapper .pill:hover {{
    background: {primary}; color: white;
    border-color: {primary}; transform: translateY(-2px);
}}

/* ── MOBILE ── */
@media (max-width: 991px) {{
    #v360-wrapper .footer-grid {{ grid-template-columns: repeat(2, 1fr); }}
    #v360-wrapper .service-grid,
    #v360-wrapper .infographic-grid {{ grid-template-columns: repeat(2, 1fr) !important; }}
}}

@media (max-width: 768px) {{
    #v360-wrapper .hero {{ padding: 40px 0 60px; min-height: auto; }}
    #v360-wrapper .hero-content {{
        display: flex !important; flex-direction: column !important; gap: 0 !important;
    }}
    #v360-wrapper .text-col {{
        order: 1 !important; width: 100% !important;
        text-align: center !important; margin-bottom: 28px !important;
    }}
    #v360-wrapper .form-col {{
        order: 2 !important; width: 100% !important;
        display: block !important; visibility: visible !important;
    }}
    #v360-wrapper .glass-card {{
        margin: 0 auto !important; width: 100% !important;
        padding: 22px 18px !important; box-sizing: border-box !important;
    }}
    #v360-wrapper .hero-title {{
        text-align: center !important;
        font-size: clamp(1.6rem, 7vw, 2.4rem) !important;
    }}
    #v360-wrapper .hero-sub {{ text-align: center !important; }}
    #v360-wrapper .hero-gold-badge {{
        margin: 0 auto 14px auto !important; display: table !important;
    }}
    #v360-wrapper .hero-features, #v360-wrapper .btn-group {{
        justify-content: center !important;
    }}
    #v360-wrapper .zigzag-item,
    #v360-wrapper .zigzag-item.reverse {{ flex-direction: column !important; gap: 24px !important; }}
    #v360-wrapper .zigzag-img {{ height: auto !important; min-height: 200px !important; max-height: 320px !important; }}
    #v360-wrapper .service-grid,
    #v360-wrapper .infographic-grid,
    #v360-wrapper .footer-grid {{
        grid-template-columns: 1fr !important;
    }}
    #v360-wrapper .service-card.cv-icon_left {{ flex-direction: row !important; }}
    #v360-wrapper .section {{ padding: 35px 0 !important; }}
    #v360-wrapper .container {{ padding: 0 14px !important; }}
}}

@media (max-width: 480px) {{
    #v360-wrapper .hero-title {{ font-size: 1.75rem !important; }}
    #v360-wrapper .zigzag-content h3 {{ font-size: 1.4rem !important; }}
    #v360-wrapper .infographic-number {{ font-size: 2rem; }}
}}
"""

    # ══ 💎 PREMIUM FORM SKINS — seed se 3 looks: glass / solid white / dark navy ══
    _fseed = b_data.get('site_seed', 0)
    _form_skin = ["glass", "solid", "dark"][(_fseed + 2) % 3]

    if _form_skin == "solid":
        css += """
/* FORM SKIN: SOLID WHITE — premium clean look */
#v360-wrapper .glass-card {
    background: #ffffff !important;
    backdrop-filter: none !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 24px 50px rgba(0,0,0,0.28) !important;
}
#v360-wrapper .glass-card h3 { color: var(--primary) !important; }
#v360-wrapper .glass-card p { color: #64748b !important; }
#v360-wrapper .glass-card input,
#v360-wrapper .glass-card select {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
}
"""
    elif _form_skin == "dark":
        css += """
/* FORM SKIN: DARK NAVY — premium bold look */
#v360-wrapper .glass-card {
    background: rgba(10, 18, 32, 0.92) !important;
    backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
}
#v360-wrapper .glass-card h3 { color: #ffffff !important; }
#v360-wrapper .glass-card input,
#v360-wrapper .glass-card select {
    background: rgba(255,255,255,0.96) !important;
}
#v360-wrapper .glass-card button {
    background: var(--accent) !important;
    color: #0f172a !important;
}
"""
    # "glass" = default (kuch add nahi karna — purana look)

    return css


# ==============================================================================
# 4. EXTRA SECTION BUILDERS  — niche-specific HTML sections
# ==============================================================================

def build_emergency_banner(b_data: dict, profile: dict) -> str:
    text = profile.get("emergency_text", "⚡ 24/7 Emergency Service — Call Now!")
    phone = b_data.get("phone", "")
    primary = b_data.get("primary", profile["palette"]["primary"])
    return f"""
<div style="background:{primary}; color:white; text-align:center; padding:18px 20px;
            font-size:1.15rem; font-weight:700; letter-spacing:0.02em;">
    {text}
    {'<a href="tel:' + phone + '" style="color:white; margin-left:20px; text-decoration:underline;">' + phone + '</a>' if phone else ''}
</div>
"""


def build_roi_stats_counter(b_data: dict) -> str:
    stats = [
        {"num": "500+", "label": "Clients Served"},
        {"num": "340%", "label": "Average ROI"},
        {"num": "$12M+", "label": "Revenue Generated"},
        {"num": "98%",  "label": "Client Retention"},
    ]
    cards = ""
    for s in stats:
        cards += f"""
        <div style="text-align:center; padding:30px 20px;">
            <div style="font-size:2.8rem; font-weight:800; color:var(--primary);">{s['num']}</div>
            <div style="color:var(--text-gray); font-size:1rem; margin-top:8px;">{s['label']}</div>
        </div>"""
    return f"""
<section class="section">
    <div class="container">
        <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:20px;">
            {cards}
        </div>
    </div>
</section>
"""


def build_service_process_steps(b_data: dict, profile: dict) -> str:
    industry  = b_data.get("industry", "service")
    city      = b_data.get("city") or b_data.get("country", "")
    primary   = b_data.get("primary", "#1A73E8")
    target_lang = b_data.get("target_lang", "en")

    # ── 1. DESIGN_SPEC se milein to wahi use karo (best quality) ──────────
    design_spec = b_data.get("design_spec", {})
    spec_steps  = design_spec.get("how_it_works", [])
    spec_heading = design_spec.get("how_it_works_heading", "")

    if spec_steps and len(spec_steps) >= 4:
        steps = [
            (s.get("emoji", "✅"), s.get("title", "Step"), s.get("desc", ""))
            for s in spec_steps[:4]
        ]
    else:
        # ── 2. Fallback: industry + city se dynamic steps ─────────────────
        industry_title = industry.title() if industry else "Service"
        if target_lang == "ar":
            steps = [
                ("📞", f"اتصل أو احجز",
                 f"تواصل معنا 24/7 لأي احتياج في {city}. نرد خلال دقائق."),
                ("🔍", f"تشخيص مجاني لـ{industry_title}",
                 f"يفحص أخصائيونا المعتمدون المشكلة مجاناً قبل تقديم أي سعر."),
                ("💰", "سعر ثابت مسبقاً",
                 f"سعر محدد بدون مفاجآت — تعرف التكلفة قبل بدء عمل {industry_title}."),
                ("✅", "ضمان شامل",
                 f"ننجز مشروع {industry_title} من أول مرة مع ضمان كامل على العمل."),
            ]
        else:
            steps = [
                ("📞", f"Book Your {industry_title}",
                 f"Call or WhatsApp 24/7 for any {industry.lower()} need in {city}. We respond within minutes."),
                ("🔍", f"Free {industry_title} Diagnosis",
                 f"A certified {industry.lower()} specialist inspects the problem at no charge before quoting."),
                ("💰", "Upfront Fixed Price",
                 f"One fixed price for your {industry.lower()} job — no hidden charges, ever."),
                ("✅", f"{industry_title} Guaranteed",
                 f"We complete your {industry.lower()} job right the first time, backed by our full warranty."),
            ]

    # ── 3. Section heading: DESIGN_SPEC → fallback ───────────────────────
    if not spec_heading:
        if target_lang == "ar":
            spec_heading = f"كيف تعمل خدمات {industry.title()}"
        else:
            spec_heading = f"How Our {industry.title()} Service Works"

    # ── 4. Pull primary keyword for SEO ──────────────────────────────────
    # Inject into heading so it reads as an H2 keyword signal
    _niche = b_data.get("niche_engine")
    _kw_tiers = {}
    try:
        from main import extract_keyword_tiers
        _kw_tiers = extract_keyword_tiers(
            b_data, industry,
            b_data.get("industry", ""),
            city, target_lang
        )
    except Exception:
        pass
    _primary_kw = (_kw_tiers.get("high_intent") or [None])[0]
    if _primary_kw and _primary_kw.lower() not in spec_heading.lower():
        if target_lang != "ar":
            spec_heading = f"{spec_heading} — {_primary_kw.title()}"

    cards = ""
    for i, (emoji, title, desc) in enumerate(steps):
        cards += f"""
        <div style="background:white; border-radius:16px; padding:28px 22px;
                    box-shadow:0 4px 20px rgba(0,0,0,0.07); border:1px solid #e2e8f0;
                    text-align:center; position:relative;">
            <div style="width:48px;height:48px;background:{primary};border-radius:50%;
                        display:flex;align-items:center;justify-content:center;
                        font-size:1.4rem;margin:0 auto 16px;color:white;
                        box-shadow:0 4px 12px rgba(0,0,0,0.15);">{i+1}</div>
            <div style="font-size:1.8rem;margin-bottom:10px;">{emoji}</div>
            <h4 style="font-size:1.1rem;margin-bottom:10px;color:var(--text-dark);
                       font-weight:700;">{title}</h4>
            <p style="color:var(--text-gray);font-size:0.95rem;line-height:1.7;">{desc}</p>
        </div>"""

    return f"""
<section class="section">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:12px;font-size:2.2rem;
                   color:var(--primary);">
            {spec_heading}
        </h2>
        <p style="text-align:center;color:var(--text-gray);margin-bottom:40px;
                  font-size:1.05rem;">
            {"خطواتنا البسيطة لخدمة مثالية في " + city if target_lang == "ar"
             else f"Simple steps to expert {industry.lower()} service in {city}"}
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
                    gap:24px;">
            {cards}
        </div>
    </div>
</section>
"""


def build_certifications_bar(b_data: dict) -> str:
    certs = ["HIPAA Compliant", "Board Certified", "AMA Member", "Joint Commission", "Medicare/Medicaid"]
    items = "".join(
        f'<div style="background:white;padding:14px 24px;border-radius:50px;'
        f'border:1px solid #e2e8f0;font-weight:600;font-size:0.9rem;'
        f'color:var(--primary);white-space:nowrap;">✓ {c}</div>'
        for c in certs
    )
    return f"""
<section class="section">
    <div class="container">
        <div style="display:flex;flex-wrap:wrap;gap:14px;justify-content:center;">{items}</div>
    </div>
</section>
"""


def build_before_after_placeholder(b_data: dict) -> str:
    primary = b_data.get("primary", "#1A73E8")
    return f"""
<section class="section">
    <div class="container" style="text-align:center;">
        <h2 style="font-size:2.2rem;color:var(--primary);margin-bottom:40px;">Before &amp; After Results</h2>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px;">
            {"".join(f'''
            <div style="border-radius:16px;overflow:hidden;box-shadow:0 8px 24px rgba(0,0,0,0.1);">
                <div style="background:linear-gradient(135deg,#f1f5f9,#e2e8f0);height:220px;
                            display:flex;align-items:center;justify-content:center;
                            font-size:3rem;">{'🦷' if 'ental' in b_data.get('industry','') else '✨'}</div>
                <div style="padding:18px;background:white;">
                    <p style="color:var(--text-gray);font-size:0.9rem;">
                        Real patient result #{i+1} — individual results vary
                    </p>
                </div>
            </div>''' for i in range(3))}
        </div>
        <p style="color:var(--text-gray);margin-top:24px;font-size:0.9rem;">
            * Results shown are real clients. Individual results may vary.
        </p>
    </div>
</section>
"""

def build_before_after_real(b_data: dict, profile: dict) -> str:
    primary  = b_data.get("primary", "#9B4D7A")
    accent   = b_data.get("accent",  "#FFF5F8")
    label    = profile.get("label", "Beauty")
    industry = b_data.get("industry", "salon")
    city     = b_data.get("city") or b_data.get("country", "")
    treatments = [
        {"before": "Damaged & Dull",  "after": "Glossy & Vibrant",  "service": "Hair Treatment"},
        {"before": "Uneven Tone",     "after": "Radiant & Clear",   "service": "Skin Facial"},
        {"before": "Short & Plain",   "after": "Long Luxurious",    "service": "Hair Extensions"},
    ]
    cards = ""
    for t in treatments:
        bef   = t["before"]
        aft   = t["after"]
        svc   = t["service"]
        cards += (
            f'<div style="background:white;border-radius:16px;overflow:hidden;'
            f'box-shadow:0 8px 24px rgba(0,0,0,0.08);border:1px solid #f0e6f0;">'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;">'
            f'<div style="background:linear-gradient(135deg,#e2e8f0,#cbd5e1);height:160px;'
            f'display:flex;align-items:center;justify-content:center;flex-direction:column;gap:8px;">'
            f'<span style="font-size:0.75rem;font-weight:700;color:#94a3b8;'
            f'text-transform:uppercase;letter-spacing:0.1em;">Before</span>'
            f'<span style="font-size:0.95rem;color:#64748b;font-weight:600;">{bef}</span>'
            f'</div>'
            f'<div style="background:linear-gradient(135deg,{primary}20,{primary}40);height:160px;'
            f'display:flex;align-items:center;justify-content:center;flex-direction:column;gap:8px;">'
            f'<span style="font-size:0.75rem;font-weight:700;color:{primary};'
            f'text-transform:uppercase;letter-spacing:0.1em;">After</span>'
            f'<span style="font-size:0.95rem;color:{primary};font-weight:700;">{aft}</span>'
            f'</div></div>'
            f'<div style="padding:16px;text-align:center;background:{accent};">'
            f'<span style="font-weight:600;color:{primary};font-size:0.9rem;">{svc}</span>'
            f'<span style="color:#94a3b8;font-size:0.8rem;margin-left:8px;">in {city}</span>'
            f'</div></div>'
        )
    return f"""
<section class="section" style="background:{accent};">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:12px;font-size:2.2rem;color:var(--primary);">
            Transformations We've Delivered
        </h2>
        <p style="text-align:center;color:var(--text-gray);margin-bottom:40px;">
            Real results from our {city} {industry} clients
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px;">
            {cards}
        </div>
        <p style="text-align:center;margin-top:24px;font-size:0.82rem;color:#94a3b8;">
            * Representation of typical results. Individual results vary.
        </p>
    </div>
</section>"""
# Dispatcher: section name → builder function
# ==============================================================================
# REAL SECTION BUILDERS (previously stubs)
# ==============================================================================

def build_team_cards(b_data: dict, profile: dict) -> str:
    primary = b_data.get("primary", "#1A73E8")
    label   = profile.get("label", "Our")
    city    = b_data.get("city") or b_data.get("country", "")
    members = [
        {"name": "Sarah Johnson", "role": "Lead Specialist",   "exp": "12 yrs", "badge": "Certified"},
        {"name": "Mike Chen",     "role": "Senior Technician", "exp": "8 yrs",  "badge": "Licensed"},
        {"name": "Lisa Martinez", "role": "Quality Manager",   "exp": "10 yrs", "badge": "Insured"},
    ]
    cards = ""
    for m in members:
        cards += f"""
        <div style="background:white;border-radius:16px;padding:28px;text-align:center;
                    box-shadow:0 4px 20px rgba(0,0,0,0.07);border:1px solid #e2e8f0;">
            <div style="width:80px;height:80px;border-radius:50%;
                        background:linear-gradient(135deg,{primary} 0%,#1e3a8a 100%);
                        margin:0 auto 16px;display:flex;align-items:center;
                        justify-content:center;font-size:2rem;color:white;font-weight:700;">
                {m['name'][0]}
            </div>
            <span style="background:{primary}15;color:{primary};padding:3px 12px;
                         border-radius:20px;font-size:0.78rem;font-weight:600;">
                {m['badge']}
            </span>
            <h4 style="margin:12px 0 4px;color:var(--text-dark);font-size:1.1rem;">{m['name']}</h4>
            <p style="color:{primary};font-weight:600;font-size:0.9rem;margin:0 0 6px;">{m['role']}</p>
            <p style="color:var(--text-gray);font-size:0.85rem;">{m['exp']} experience in {city}</p>
        </div>"""
    return f"""
<section class="section">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:40px;font-size:2.2rem;color:var(--primary);">
            Meet Our {label} Team
        </h2>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:24px;">
            {cards}
        </div>
    </div>
</section>"""


def build_warranty_guarantee_badge(b_data: dict, profile: dict) -> str:
    primary = b_data.get("primary", "#1A73E8")
    accent  = b_data.get("accent", "#FFB300")
    label   = profile.get("label", "Service")
    items   = profile.get("trust_items", ["Licensed & Insured", "Satisfaction Guaranteed",
                                          "Free Estimates", "Fast Response"])
    pills = "".join(
        f'<div style="display:flex;align-items:center;gap:10px;background:white;'
        f'padding:14px 22px;border-radius:50px;border:1px solid #e2e8f0;'
        f'box-shadow:0 2px 8px rgba(0,0,0,0.05);font-weight:600;font-size:0.95rem;color:{primary};">'
        f'<span style="color:{accent};font-size:1.1rem;">✓</span> {item}</div>'
        for item in items[:4]
    )
    return f"""
<section class="section" style="background:linear-gradient(135deg,{primary}08 0%,white 100%);">
    <div class="container" style="text-align:center;">
        <h2 style="font-size:2rem;color:var(--primary);margin-bottom:12px;">
            Our {label} Promise
        </h2>
        <p style="color:var(--text-gray);margin-bottom:32px;font-size:1.05rem;">
            Every job backed by our full guarantee
        </p>
        <div style="display:flex;flex-wrap:wrap;gap:16px;justify-content:center;">
            {pills}
        </div>
    </div>
</section>"""


def build_client_logos(b_data: dict, profile: dict) -> str:
    primary = b_data.get("primary", "#1A73E8")
    label   = profile.get("label", "Our")
    names   = ["TechCorp", "BuildRight", "MediaGroup", "RetailPlus",
               "HealthFirst", "EduTech", "FinanceHub", "GreenCo"]
    logos = "".join(
        f'<div style="background:white;border:1px solid #e2e8f0;border-radius:10px;'
        f'padding:16px 24px;font-weight:700;font-size:0.9rem;color:#94a3b8;'
        f'display:flex;align-items:center;justify-content:center;min-width:120px;">'
        f'{n}</div>'
        for n in names
    )
    return f"""
<section class="section" style="background:#f8fafc;">
    <div class="container" style="text-align:center;">
        <p style="color:var(--text-gray);font-size:0.9rem;margin-bottom:24px;
                  text-transform:uppercase;letter-spacing:0.08em;font-weight:600;">
            Trusted by leading businesses
        </p>
        <div style="display:flex;flex-wrap:wrap;gap:16px;justify-content:center;">
            {logos}
        </div>
    </div>
</section>"""


def build_case_study_snippet(b_data: dict, profile: dict) -> str:
    primary  = b_data.get("primary", "#1A73E8")
    industry = b_data.get("industry", "service")
    city     = b_data.get("city") or b_data.get("country", "")
    cases = [
        {"client": "Local Business A", "result": "340% ROI increase",
         "desc": f"Transformed their {industry} strategy in {city}"},
        {"client": "Enterprise Client B", "result": "60% cost reduction",
         "desc": f"Streamlined {industry} operations across all locations"},
        {"client": "Startup C", "result": "10x growth in 6 months",
         "desc": f"Built a scalable {industry} foundation from scratch"},
    ]
    cards = ""
    for c in cases:
        cards += f"""
        <div style="background:white;border-radius:14px;padding:28px;
                    border:1px solid #e2e8f0;border-top:4px solid {primary};
                    box-shadow:0 4px 15px rgba(0,0,0,0.05);">
            <div style="font-size:1.8rem;font-weight:800;color:{primary};margin-bottom:8px;">
                {c['result']}
            </div>
            <h4 style="margin:0 0 8px;color:var(--text-dark);">{c['client']}</h4>
            <p style="color:var(--text-gray);font-size:0.92rem;">{c['desc']}</p>
        </div>"""
    return f"""
<section class="section">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:40px;font-size:2.2rem;color:var(--primary);">
            Results We've Delivered
        </h2>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:24px;">
            {cards}
        </div>
    </div>
</section>"""


def build_transformation_stats(b_data: dict, profile: dict) -> str:
    primary  = b_data.get("primary", "#E63946")
    industry = b_data.get("industry", "fitness")
    city     = b_data.get("city") or b_data.get("country", "")
    stats = [
        {"num": "2,400+",  "label": "Members Trained"},
        {"num": "94%",     "label": "Goal Achievement Rate"},
        {"num": "6 Weeks", "label": "Avg. Visible Results"},
        {"num": "4.9★",    "label": "Member Rating"},
    ]
    cards = ""
    for s in stats:
        num   = s["num"]
        label = s["label"]
        cards += (
            f'<div style="text-align:center;padding:28px 16px;background:white;'
            f'border-radius:14px;box-shadow:0 4px 15px rgba(0,0,0,0.06);'
            f'border:1px solid #e2e8f0;">'
            f'<div style="font-size:2.6rem;font-weight:800;color:{primary};">{num}</div>'
            f'<div style="color:var(--text-gray);font-size:0.95rem;margin-top:8px;">{label}</div>'
            f'</div>'
        )
    return f"""
<section class="section" style="background:#f8fafc;">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:12px;font-size:2.2rem;color:var(--primary);">
            Real Results, Real Members
        </h2>
        <p style="text-align:center;color:var(--text-gray);margin-bottom:40px;">
            Proven outcomes from our {city} {industry} community
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:20px;">
            {cards}
        </div>
    </div>
</section>"""


def build_insurance_logos(b_data: dict, profile: dict) -> str:
    primary  = b_data.get("primary", "#0A5C8A")
    accent   = b_data.get("accent",  "#E8F4FD")
    industry = b_data.get("industry", "medical")
    providers = ["Aetna", "BlueCross", "Cigna", "UnitedHealth",
                 "Humana", "Medicare", "Medicaid", "Tricare"]
    pills = ""
    for prov in providers:
        pills += (
            f'<div style="background:white;border:1px solid #e2e8f0;border-radius:10px;'
            f'padding:14px 20px;font-weight:600;font-size:0.88rem;color:{primary};'
            f'display:flex;align-items:center;gap:8px;white-space:nowrap;">'
            f'<span style="color:{primary};font-size:1rem;">✓</span>{prov}'
            f'</div>'
        )
    return f"""
<section class="section" style="background:{accent};">
    <div class="container" style="text-align:center;">
        <h2 style="font-size:2rem;color:var(--primary);margin-bottom:10px;">
            Insurance We Accept
        </h2>
        <p style="color:var(--text-gray);margin-bottom:32px;">
            We work with all major {industry} insurance providers
        </p>
        <div style="display:flex;flex-wrap:wrap;gap:14px;justify-content:center;">
            {pills}
        </div>
        <p style="margin-top:20px;color:var(--text-gray);font-size:0.88rem;">
            Don't see yours? Call us — we likely accept it.
        </p>
    </div>
</section>"""


def build_tech_stack_badges(b_data: dict, profile: dict) -> str:
    primary  = b_data.get("primary", "#0F172A")
    industry = b_data.get("industry", "software")
    techs = [
        {"name": "React",      "color": "#61DAFB"},
        {"name": "Python",     "color": "#3776AB"},
        {"name": "Node.js",    "color": "#339933"},
        {"name": "PostgreSQL", "color": "#336791"},
        {"name": "AWS",        "color": "#FF9900"},
        {"name": "Docker",     "color": "#2496ED"},
        {"name": "TypeScript", "color": "#3178C6"},
        {"name": "GraphQL",    "color": "#E10098"},
    ]
    badges = ""
    for t in techs:
        tname  = t["name"]
        tcolor = t["color"]
        badges += (
            f'<div style="background:white;border:2px solid {tcolor}20;border-radius:12px;'
            f'padding:16px 20px;text-align:center;min-width:100px;">'
            f'<div style="width:10px;height:10px;border-radius:50%;background:{tcolor};'
            f'margin:0 auto 10px;"></div>'
            f'<span style="font-weight:700;font-size:0.9rem;color:{primary};">{tname}</span>'
            f'</div>'
        )
    return f"""
<section class="section" style="background:#f8fafc;">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:12px;font-size:2.2rem;color:var(--primary);">
            Our Technology Stack
        </h2>
        <p style="text-align:center;color:var(--text-gray);margin-bottom:36px;">
            Battle-tested tools we use to build your {industry} solution
        </p>
        <div style="display:flex;flex-wrap:wrap;gap:16px;justify-content:center;">
            {badges}
        </div>
    </div>
</section>"""


def build_portfolio_grid(b_data: dict, profile: dict) -> str:
    primary  = b_data.get("primary", "#0F172A")
    accent   = b_data.get("accent",  "#F8FAFC")
    industry = b_data.get("industry", "web development")
    city     = b_data.get("city") or b_data.get("country", "")
    projects = [
        {"title": "E-Commerce Platform",  "tag": "Web Dev",    "result": "320% revenue increase"},
        {"title": "Mobile Booking App",   "tag": "App Dev",    "result": "50k downloads in 3 months"},
        {"title": "SEO Campaign",         "tag": "Digital",    "result": "Page 1 in 60 days"},
        {"title": "Brand Identity System","tag": "Design",     "result": "40% higher conversion"},
        {"title": "CRM Integration",      "tag": "Automation", "result": "8hrs saved per week"},
        {"title": "Social Media Growth",  "tag": "Marketing",  "result": "10x follower growth"},
    ]
    cards = ""
    for proj in projects:
        ptitle  = proj["title"]
        ptag    = proj["tag"]
        presult = proj["result"]
        cards += (
            f'<div style="background:white;border-radius:14px;overflow:hidden;'
            f'box-shadow:0 4px 20px rgba(0,0,0,0.07);border:1px solid #e2e8f0;">'
            f'<div style="height:120px;background:linear-gradient(135deg,{primary}15,{primary}35);'
            f'display:flex;align-items:center;justify-content:center;">'
            f'<span style="font-size:0.75rem;font-weight:700;color:{primary};'
            f'text-transform:uppercase;letter-spacing:0.1em;background:{accent};'
            f'padding:4px 14px;border-radius:20px;">{ptag}</span>'
            f'</div>'
            f'<div style="padding:20px;">'
            f'<h4 style="margin:0 0 8px;color:var(--text-dark);font-size:1rem;">{ptitle}</h4>'
            f'<p style="margin:0;color:var(--text-gray);font-size:0.85rem;">📈 {presult}</p>'
            f'</div>'
            f'</div>'
        )
    return f"""
<section class="section">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:12px;font-size:2.2rem;color:var(--primary);">
            Our Work in {city}
        </h2>
        <p style="text-align:center;color:var(--text-gray);margin-bottom:40px;">
            Real {industry} projects, real results
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:24px;">
            {cards}
        </div>
    </div>
</section>"""


def build_github_stats(b_data: dict, profile: dict) -> str:
    primary = b_data.get("primary", "#0F172A")
    name    = b_data.get("name", "Our Team")
    stats = [
        {"num": "200+",  "label": "Repositories"},
        {"num": "50k+",  "label": "Commits"},
        {"num": "98%",   "label": "On-time Delivery"},
        {"num": "4.9/5", "label": "Code Quality Score"},
    ]
    cards = ""
    for s in stats:
        num   = s["num"]
        label = s["label"]
        cards += (
            f'<div style="text-align:center;padding:24px;background:white;'
            f'border-radius:12px;border:1px solid #e2e8f0;">'
            f'<div style="font-size:2.2rem;font-weight:800;color:{primary};">{num}</div>'
            f'<div style="color:var(--text-gray);font-size:0.9rem;margin-top:6px;">{label}</div>'
            f'</div>'
        )
    return f"""
<section class="section" style="background:#f8fafc;">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:12px;font-size:2.2rem;color:var(--primary);">
            Built by Engineers Who Ship
        </h2>
        <p style="text-align:center;color:var(--text-gray);margin-bottom:36px;">
            {name} — open source contributors, production-grade delivery
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:20px;">
            {cards}
        </div>
    </div>
</section>"""


def build_financing_badge(b_data: dict, profile: dict) -> str:
    primary = b_data.get("primary", "#1B6CA8")
    accent  = b_data.get("accent",  "#FFF8E7")
    label   = profile.get("label", "Service")
    options = [
        "0% Interest for 12 Months",
        "No Credit Check Required",
        "Same-Day Approval",
        "Flexible Monthly Payments",
    ]
    items = ""
    for opt in options:
        items += (
            f'<div style="display:flex;align-items:center;gap:12px;background:white;'
            f'padding:16px 20px;border-radius:12px;border:1px solid #e2e8f0;'
            f'box-shadow:0 2px 8px rgba(0,0,0,0.04);">'
            f'<span style="width:32px;height:32px;border-radius:50%;background:{primary};'
            f'color:white;display:flex;align-items:center;justify-content:center;'
            f'font-size:0.9rem;flex-shrink:0;">✓</span>'
            f'<span style="font-weight:600;color:var(--text-dark);font-size:0.95rem;">{opt}</span>'
            f'</div>'
        )
    return f"""
<section class="section" style="background:{accent};">
    <div class="container">
        <div style="max-width:720px;margin:0 auto;text-align:center;">
            <h2 style="font-size:2rem;color:var(--primary);margin-bottom:10px;">
                Flexible Financing for {label}
            </h2>
            <p style="color:var(--text-gray);margin-bottom:32px;">
                Don't let cost stop you — we make it affordable
            </p>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;text-align:left;">
                {items}
            </div>
        </div>
    </div>
</section>"""


def build_loyalty_badge(b_data: dict, profile: dict) -> str:
    primary = b_data.get("primary", "#9B4D7A")
    accent  = b_data.get("accent",  "#FFF0F5")
    name    = b_data.get("name", "Us")
    tiers = [
        {"tier": "Silver",   "visits": "1st visit",  "perk": "10% off your next booking"},
        {"tier": "Gold",     "visits": "5 visits",   "perk": "Free treatment + priority booking"},
        {"tier": "Platinum", "visits": "10 visits",  "perk": "VIP lounge + 20% off always"},
    ]
    tier_colors = {"Silver": "#94a3b8", "Gold": "#D4AF37", "Platinum": primary}
    cards = ""
    for t in tiers:
        tier   = t["tier"]
        visits = t["visits"]
        perk   = t["perk"]
        color  = tier_colors.get(tier, primary)
        cards += (
            f'<div style="background:white;border-radius:16px;padding:28px;text-align:center;'
            f'box-shadow:0 4px 20px rgba(0,0,0,0.07);border:2px solid {color}30;">'
            f'<div style="font-size:1.8rem;margin-bottom:8px;">⭐</div>'
            f'<div style="font-size:1.1rem;font-weight:800;color:{color};margin-bottom:6px;">'
            f'{tier}</div>'
            f'<div style="font-size:0.85rem;color:var(--text-gray);margin-bottom:12px;">'
            f'Unlocks at {visits}</div>'
            f'<div style="font-size:0.9rem;font-weight:600;color:var(--text-dark);">{perk}</div>'
            f'</div>'
        )
    return f"""
<section class="section" style="background:{accent};">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:10px;font-size:2.2rem;color:var(--primary);">
            Rewards for Loyal Clients
        </h2>
        <p style="text-align:center;color:var(--text-gray);margin-bottom:40px;">
            The more you visit {name}, the more you save
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:24px;">
            {cards}
        </div>
    </div>
</section>"""


def build_menu_preview(b_data: dict, profile: dict) -> str:
    primary = b_data.get("primary", "#C0392B")
    accent  = b_data.get("accent",  "#FEF9EF")
    name    = b_data.get("name", "Our Restaurant")
    city    = b_data.get("city") or b_data.get("country", "")
    categories = [
        {
            "cat": "Starters",
            "items": [
                {"name": "Bruschetta",      "desc": "Toasted bread, tomato, basil", "price": "$8"},
                {"name": "Soup of the Day", "desc": "Chef's daily creation",        "price": "$9"},
                {"name": "Caesar Salad",    "desc": "Romaine, croutons, parmesan",  "price": "$11"},
            ],
        },
        {
            "cat": "Mains",
            "items": [
                {"name": "Grilled Salmon",   "desc": "Lemon butter, seasonal veg",  "price": "$24"},
                {"name": "Ribeye Steak",     "desc": "12oz, truffle mash, jus",     "price": "$38"},
                {"name": "Mushroom Risotto", "desc": "Arborio, porcini, pecorino",  "price": "$18"},
            ],
        },
    ]
    sections = ""
    for cat in categories:
        cat_name = cat["cat"]
        rows = ""
        for item in cat["items"]:
            iname  = item["name"]
            idesc  = item["desc"]
            iprice = item["price"]
            rows += (
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
                f'padding:12px 0;border-bottom:1px dashed #e2e8f0;">'
                f'<div>'
                f'<div style="font-weight:600;color:var(--text-dark);font-size:0.95rem;">{iname}</div>'
                f'<div style="color:var(--text-gray);font-size:0.82rem;margin-top:2px;">{idesc}</div>'
                f'</div>'
                f'<div style="font-weight:700;color:{primary};font-size:0.95rem;'
                f'margin-left:16px;white-space:nowrap;">{iprice}</div>'
                f'</div>'
            )
        sections += (
            f'<div style="background:white;border-radius:14px;padding:28px;'
            f'box-shadow:0 4px 15px rgba(0,0,0,0.06);border:1px solid #e2e8f0;">'
            f'<h3 style="color:{primary};font-size:1.2rem;margin-bottom:16px;'
            f'padding-bottom:10px;border-bottom:2px solid {primary};">{cat_name}</h3>'
            f'{rows}'
            f'</div>'
        )
    return f"""
<section class="section" style="background:{accent};">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:10px;font-size:2.2rem;color:var(--primary);">
            A Taste of Our Menu
        </h2>
        <p style="text-align:center;color:var(--text-gray);margin-bottom:40px;">
            Fresh ingredients, crafted daily at {name} in {city}
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px;">
            {sections}
        </div>
        <p style="text-align:center;margin-top:24px;color:var(--text-gray);font-size:0.88rem;">
            Menu changes seasonally. Ask your server for today's specials.
        </p>
    </div>
</section>"""


def build_chef_spotlight(b_data: dict, profile: dict) -> str:
    primary = b_data.get("primary", "#C0392B")
    accent  = b_data.get("accent",  "#FEF9EF")
    name    = b_data.get("name", "Our Restaurant")
    city    = b_data.get("city") or b_data.get("country", "")
    return f"""
<section class="section">
    <div class="container">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:50px;align-items:center;
                    max-width:900px;margin:0 auto;">
            <div style="background:linear-gradient(135deg,{primary}15,{primary}35);
                        height:340px;border-radius:20px;display:flex;align-items:center;
                        justify-content:center;font-size:5rem;">👨‍🍳</div>
            <div>
                <span style="background:{primary};color:white;padding:4px 16px;
                             border-radius:20px;font-size:0.8rem;font-weight:700;
                             text-transform:uppercase;letter-spacing:0.08em;">Head Chef</span>
                <h2 style="font-size:2rem;color:var(--primary);margin:16px 0 8px;">
                    Meet Chef Marco
                </h2>
                <p style="color:var(--text-gray);line-height:1.8;margin-bottom:20px;">
                    With over 18 years of culinary experience across three continents,
                    Chef Marco brings authentic flavour and modern technique to every
                    dish at {name} in {city}. Trained in Paris, refined in Tokyo.
                </p>
                <div style="display:flex;gap:24px;">
                    <div style="text-align:center;">
                        <div style="font-size:1.6rem;font-weight:800;color:{primary};">18+</div>
                        <div style="font-size:0.8rem;color:var(--text-gray);">Years Exp.</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:1.6rem;font-weight:800;color:{primary};">3</div>
                        <div style="font-size:0.8rem;color:var(--text-gray);">Countries</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:1.6rem;font-weight:800;color:{primary};">2★</div>
                        <div style="font-size:0.8rem;color:var(--text-gray);">Michelin</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</section>"""


def build_reservation_widget(b_data: dict, profile: dict) -> str:
    primary  = b_data.get("primary", "#C0392B")
    accent   = b_data.get("accent",  "#FEF9EF")
    phone    = b_data.get("phone", "")
    whatsapp = b_data.get("whatsapp", "")
    name     = b_data.get("name", "Us")
    return f"""
<section class="section" style="background:{accent};">
    <div class="container">
        <div style="max-width:600px;margin:0 auto;text-align:center;">
            <h2 style="font-size:2rem;color:var(--primary);margin-bottom:10px;">
                Reserve Your Table
            </h2>
            <p style="color:var(--text-gray);margin-bottom:32px;">
                Book online or call {name} directly — we'll confirm within 30 minutes
            </p>
            <div style="background:white;border-radius:20px;padding:32px;
                        box-shadow:0 8px 30px rgba(0,0,0,0.08);border:1px solid #e2e8f0;">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;">
                    <input type="text" placeholder="Your Name"
                           style="width:100%;padding:13px 16px;border-radius:10px;
                                  border:1px solid #cbd5e1;font-size:0.97rem;">
                    <input type="text" placeholder="Phone Number"
                           style="width:100%;padding:13px 16px;border-radius:10px;
                                  border:1px solid #cbd5e1;font-size:0.97rem;">
                    <input type="date"
                           style="width:100%;padding:13px 16px;border-radius:10px;
                                  border:1px solid #cbd5e1;font-size:0.97rem;">
                    <select style="width:100%;padding:13px 16px;border-radius:10px;
                                   border:1px solid #cbd5e1;font-size:0.97rem;">
                        <option>2 Guests</option>
                        <option>4 Guests</option>
                        <option>6 Guests</option>
                        <option>8+ Guests</option>
                    </select>
                </div>
                <a href="tel:{phone}"
                   style="display:block;width:100%;padding:15px;background:{primary};
                          color:white;border-radius:10px;font-weight:700;font-size:1rem;
                          text-align:center;text-decoration:none;margin-bottom:12px;">
                    📞 Call to Reserve: {phone}
                </a>
                <a href="https://wa.me/{whatsapp}"
                   style="display:block;width:100%;padding:14px;background:#25D366;
                          color:white;border-radius:10px;font-weight:700;font-size:1rem;
                          text-align:center;text-decoration:none;">
                    💬 WhatsApp Reservation
                </a>
            </div>
        </div>
    </div>
</section>"""


def build_class_schedule(b_data: dict, profile: dict) -> str:
    primary = b_data.get("primary", "#E63946")
    accent  = b_data.get("accent",  "#FFF5F5")
    city    = b_data.get("city") or b_data.get("country", "")
    schedule = [
        {"day": "Monday",    "classes": ["6:00 AM — HIIT Bootcamp", "12:00 PM — Yoga Flow",   "6:00 PM — CrossFit"]},
        {"day": "Wednesday", "classes": ["7:00 AM — Spin Class",    "1:00 PM — Boxing",        "7:00 PM — Pilates"]},
        {"day": "Friday",    "classes": ["6:30 AM — Strength",      "5:30 PM — Zumba",         "7:30 PM — HIIT"]},
        {"day": "Saturday",  "classes": ["8:00 AM — Open Gym",      "10:00 AM — Group Yoga",   "12:00 PM — Sparring"]},
    ]
    cols = ""
    for day_data in schedule:
        day     = day_data["day"]
        classes = day_data["classes"]
        rows = ""
        for cls in classes:
            rows += (
                f'<div style="padding:10px 14px;border-radius:8px;background:{accent};'
                f'font-size:0.85rem;color:var(--text-dark);border-left:3px solid {primary};">'
                f'{cls}</div>'
            )
        cols += (
            f'<div style="background:white;border-radius:14px;padding:22px;'
            f'box-shadow:0 4px 15px rgba(0,0,0,0.06);border:1px solid #e2e8f0;">'
            f'<h4 style="color:{primary};margin-bottom:14px;font-size:1rem;'
            f'text-transform:uppercase;letter-spacing:0.05em;">{day}</h4>'
            f'<div style="display:flex;flex-direction:column;gap:8px;">{rows}</div>'
            f'</div>'
        )
    return f"""
<section class="section" style="background:#f8fafc;">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:10px;font-size:2.2rem;color:var(--primary);">
            Weekly Class Schedule
        </h2>
        <p style="text-align:center;color:var(--text-gray);margin-bottom:40px;">
            Join us at our {city} facility — all fitness levels welcome
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:20px;">
            {cols}
        </div>
    </div>
</section>"""


def build_trainer_cards(b_data: dict, profile: dict) -> str:
    primary = b_data.get("primary", "#E63946")
    city    = b_data.get("city") or b_data.get("country", "")
    trainers = [
        {"name": "Jake Morrison", "spec": "Strength & Conditioning", "cert": "NASM-CPT", "exp": "9 yrs"},
        {"name": "Priya Sharma",  "spec": "Yoga & Mindfulness",      "cert": "RYT-500",  "exp": "7 yrs"},
        {"name": "Carlos Reyes", "spec": "Boxing & MMA",             "cert": "ISSA-CPT", "exp": "11 yrs"},
    ]
    cards = ""
    for t in trainers:
        tname = t["name"]
        spec  = t["spec"]
        cert  = t["cert"]
        exp   = t["exp"]
        cards += (
            f'<div style="background:white;border-radius:16px;padding:28px;text-align:center;'
            f'box-shadow:0 4px 20px rgba(0,0,0,0.07);border:1px solid #e2e8f0;">'
            f'<div style="width:80px;height:80px;border-radius:50%;'
            f'background:linear-gradient(135deg,{primary},#1D1D1D);'
            f'margin:0 auto 16px;display:flex;align-items:center;'
            f'justify-content:center;font-size:2rem;color:white;font-weight:800;">'
            f'{tname[0]}'
            f'</div>'
            f'<h4 style="margin:0 0 4px;color:var(--text-dark);">{tname}</h4>'
            f'<p style="color:{primary};font-weight:600;font-size:0.9rem;margin:0 0 6px;">{spec}</p>'
            f'<span style="background:{primary}15;color:{primary};padding:3px 12px;'
            f'border-radius:20px;font-size:0.78rem;font-weight:600;">{cert}</span>'
            f'<p style="color:var(--text-gray);font-size:0.82rem;margin-top:10px;">'
            f'{exp} experience · {city}</p>'
            f'</div>'
        )
    return f"""
<section class="section">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:40px;font-size:2.2rem;color:var(--primary);">
            Train With the Best
        </h2>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:24px;">
            {cards}
        </div>
    </div>
</section>"""


def build_property_stats(b_data: dict, profile: dict) -> str:
    primary = b_data.get("primary", "#2C5F2E")
    city    = b_data.get("city") or b_data.get("country", "")
    name    = b_data.get("name", "Our Agency")
    stats = [
        {"num": "1,200+", "label": "Properties Sold"},
        {"num": "$2.4B",  "label": "Total Sales Volume"},
        {"num": "14 Days","label": "Avg. Days on Market"},
        {"num": "98%",    "label": "List-to-Sale Ratio"},
    ]
    cards = ""
    for s in stats:
        num   = s["num"]
        label = s["label"]
        cards += (
            f'<div style="background:white;border-radius:14px;padding:28px;text-align:center;'
            f'box-shadow:0 4px 15px rgba(0,0,0,0.06);border:1px solid #e2e8f0;">'
            f'<div style="font-size:2.4rem;font-weight:800;color:{primary};">{num}</div>'
            f'<div style="color:var(--text-gray);font-size:0.92rem;margin-top:8px;">{label}</div>'
            f'</div>'
        )
    return f"""
<section class="section" style="background:#f0fdf4;">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:10px;font-size:2.2rem;color:var(--primary);">
            {name} by the Numbers
        </h2>
        <p style="text-align:center;color:var(--text-gray);margin-bottom:36px;">
            Proven performance in the {city} property market
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:20px;">
            {cards}
        </div>
    </div>
</section>"""


def build_map_embed_section(b_data: dict, profile: dict) -> str:
    import re as _re
    primary   = b_data.get("primary", "#1A73E8")
    map_embed = b_data.get("map_embed", "")
    city      = b_data.get("city") or b_data.get("country", "")
    phone     = b_data.get("phone", "")
    name      = b_data.get("name", "Us")
    if not map_embed or "<iframe" not in map_embed:
        return ""
    map_embed = _re.sub(r'width="[^"]+"',  'width="100%"', map_embed)
    map_embed = _re.sub(r'height="[^"]+"', 'height="360"', map_embed)
    map_embed = map_embed.replace(
        "<iframe",
        '<iframe style="border:0;border-radius:16px;display:block;"'
    )
    return f"""
<section class="section">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:10px;font-size:2.2rem;color:var(--primary);">
            Find Us in {city}
        </h2>
        <p style="text-align:center;color:var(--text-gray);margin-bottom:36px;">
            Visit {name} — we're easy to reach
        </p>
        <div style="display:grid;grid-template-columns:2fr 1fr;gap:30px;align-items:start;">
            <div style="border-radius:16px;overflow:hidden;
                        box-shadow:0 8px 24px rgba(0,0,0,0.1);">
                {map_embed}
            </div>
            <div style="background:#f8fafc;border-radius:16px;padding:28px;
                        border:1px solid #e2e8f0;">
                <h3 style="color:{primary};margin-bottom:20px;">Contact Info</h3>
                <p style="display:flex;align-items:center;gap:10px;
                           color:var(--text-gray);margin-bottom:14px;">
                    <span style="color:{primary};">📍</span> {city}
                </p>
                <p style="display:flex;align-items:center;gap:10px;
                           color:var(--text-gray);margin-bottom:14px;">
                    <span style="color:{primary};">📞</span>
                    <a href="tel:{phone}" style="color:var(--text-gray);
                       text-decoration:none;">{phone}</a>
                </p>
                <a href="tel:{phone}"
                   style="display:block;padding:14px;background:{primary};color:white;
                          border-radius:10px;text-align:center;font-weight:700;
                          text-decoration:none;margin-top:20px;">
                    Call Now
                </a>
            </div>
        </div>
    </div>
</section>"""


def build_testimonials_carousel_section(b_data: dict, profile: dict) -> str:
    primary  = b_data.get("primary", "#1A73E8")
    accent   = b_data.get("accent",  "#f8fafc")
    city     = b_data.get("city") or b_data.get("country", "")
    industry = b_data.get("industry", "service")
    reviews = [
        {"name": "Sarah K.",  "txt": f"Best {industry} experience I've had in {city}. Highly recommend!"},
        {"name": "James R.",  "txt": "Professional, fast, and reasonably priced. Will use again."},
        {"name": "Aisha M.",  "txt": f"Transformed our project completely. The team in {city} is top-tier."},
        {"name": "Tom B.",    "txt": "Exceeded every expectation. Communication was excellent throughout."},
        {"name": "Fatima A.", "txt": "Trustworthy and skilled. Wouldn't go anywhere else for this."},
        {"name": "David L.",  "txt": f"Outstanding quality. The go-to {industry} team in {city}."},
    ]
    stars = "★" * 5
    cards = ""
    for r in reviews:
        rname = r["name"]
        rtxt  = r["txt"]
        cards += (
            f'<div style="background:white;border-radius:14px;padding:24px;'
            f'box-shadow:0 4px 15px rgba(0,0,0,0.06);border:1px solid #e2e8f0;'
            f'display:flex;flex-direction:column;height:100%;">'
            f'<div style="color:#D4AF37;font-size:1rem;margin-bottom:12px;">{stars}</div>'
            f'<p style="color:var(--text-gray);font-style:italic;line-height:1.7;'
            f'flex-grow:1;font-size:0.92rem;">"{rtxt}"</p>'
            f'<div style="margin-top:16px;font-weight:700;color:{primary};'
            f'font-size:0.9rem;">— {rname}</div>'
            f'</div>'
        )
    return f"""
<section class="section" style="background:{accent};">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:10px;font-size:2.2rem;color:var(--primary);">
            What Clients Are Saying
        </h2>
        <p style="text-align:center;color:var(--text-gray);margin-bottom:40px;">
            Real feedback from our {city} customers
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:22px;">
            {cards}
        </div>
    </div>
</section>"""


def build_verdict_stats(b_data: dict, profile: dict) -> str:
    primary   = b_data.get("primary",   "#1A1A2E")
    secondary = b_data.get("secondary", "#8B6914")
    name      = b_data.get("name", "Our Firm")
    city      = b_data.get("city") or b_data.get("country", "")
    verdicts = [
        {"num": "$480M+", "label": "Recovered for Clients"},
        {"num": "97%",    "label": "Cases Won or Settled"},
        {"num": "3,200+", "label": "Clients Represented"},
        {"num": "28 Yrs", "label": "Combined Experience"},
    ]
    cards = ""
    for v in verdicts:
        num   = v["num"]
        label = v["label"]
        cards += (
            f'<div style="text-align:center;padding:28px;background:white;'
            f'border-radius:14px;border:1px solid #e2e8f0;'
            f'box-shadow:0 4px 15px rgba(0,0,0,0.06);">'
            f'<div style="font-size:2.2rem;font-weight:800;color:{secondary};">{num}</div>'
            f'<div style="color:var(--text-gray);font-size:0.92rem;margin-top:8px;">{label}</div>'
            f'</div>'
        )
    return f"""
<section class="section" style="background:#FAF7F2;">
    <div class="container">
        <h2 style="text-align:center;margin-bottom:10px;font-size:2.2rem;color:var(--primary);">
            {name} — Track Record
        </h2>
        <p style="text-align:center;color:var(--text-gray);margin-bottom:36px;">
            Results that speak for themselves in {city}
        </p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:20px;">
            {cards}
        </div>
    </div>
</section>"""


def build_awards_bar(b_data: dict, profile: dict) -> str:
    primary = b_data.get("primary", "#1A1A2E")
    accent  = b_data.get("accent",  "#F5F0E8")
    name    = b_data.get("name", "Our Firm")
    awards = [
        "Best Law Firm 2024",
        "Super Lawyers® Rated",
        "AV Preeminent® Rating",
        "Top 100 Trial Lawyers",
        "BBB A+ Accredited",
    ]
    badges = ""
    for award in awards:
        badges += (
            f'<div style="display:flex;align-items:center;gap:10px;background:white;'
            f'padding:14px 20px;border-radius:50px;border:1px solid #e2e8f0;'
            f'box-shadow:0 2px 8px rgba(0,0,0,0.05);white-space:nowrap;">'
            f'<span style="color:#D4AF37;font-size:1rem;">🏆</span>'
            f'<span style="font-weight:600;font-size:0.88rem;color:{primary};">{award}</span>'
            f'</div>'
        )
    return f"""
<section class="section" style="background:{accent};">
    <div class="container" style="text-align:center;">
        <h2 style="font-size:1.8rem;color:var(--primary);margin-bottom:28px;">
            Recognition &amp; Awards — {name}
        </h2>
        <div style="display:flex;flex-wrap:wrap;gap:14px;justify-content:center;">
            {badges}
        </div>
    </div>
</section>"""


# ==============================================================================
# SECTION BUILDERS REGISTRY — all 27 wired, zero stubs remaining
# ==============================================================================

SECTION_BUILDERS = {
    "emergency_banner":       lambda b, p: build_emergency_banner(b, p),
    "service_process_steps":  lambda b, p: build_service_process_steps(b, p),
    "roi_stats_counter":      lambda b, p: build_roi_stats_counter(b),
    "certifications_bar":     lambda b, p: build_certifications_bar(b),
    "before_after_gallery":   lambda b, p: build_before_after_real(b, p),
    "team_cards":             lambda b, p: build_team_cards(b, p),
    "warranty_badge":         lambda b, p: build_warranty_guarantee_badge(b, p),
    "guarantee_badge":        lambda b, p: build_warranty_guarantee_badge(b, p),
    "client_logos":           lambda b, p: build_client_logos(b, p),
    "case_study_snippet":     lambda b, p: build_case_study_snippet(b, p),
    "transformation_stats":   lambda b, p: build_transformation_stats(b, p),
    "insurance_logos":        lambda b, p: build_insurance_logos(b, p),
    "tech_stack_badges":      lambda b, p: build_tech_stack_badges(b, p),
    "portfolio_grid":         lambda b, p: build_portfolio_grid(b, p),
    "github_stats":           lambda b, p: build_github_stats(b, p),
    "financing_badge":        lambda b, p: build_financing_badge(b, p),
    "loyalty_badge":          lambda b, p: build_loyalty_badge(b, p),
    "menu_preview":           lambda b, p: build_menu_preview(b, p),
    "chef_spotlight":         lambda b, p: build_chef_spotlight(b, p),
    "reservation_widget":     lambda b, p: build_reservation_widget(b, p),
    "class_schedule":         lambda b, p: build_class_schedule(b, p),
    "trainer_cards":          lambda b, p: build_trainer_cards(b, p),
    "property_stats":         lambda b, p: build_property_stats(b, p),
    "map_embed_section":      lambda b, p: build_map_embed_section(b, p),
    "testimonials_carousel":  lambda b, p: build_testimonials_carousel_section(b, p),
    "verdict_stats":          lambda b, p: build_verdict_stats(b, p),
    "awards_bar":             lambda b, p: build_awards_bar(b, p),
}
# ==============================================================================
# HELPER FUNCTIONS — called from main.py
# ==============================================================================

def _get_business_tokens(b_data: dict) -> dict:
    """Returns hue/secondary shift tokens based on business identity seed."""
    name     = (b_data.get("name", "") + b_data.get("industry", "")).lower()
    seed     = sum(ord(c) for c in name) if name else 0
    rng      = random.Random(seed)
    return {
        "hue_shift":       rng.randint(-15, 15),
        "secondary_extra": rng.randint(-10, 10),
    }


def _hue_shift(hex_color: str, shift: int) -> str:
    """Shift hue of a hex color by `shift` degrees. Returns new hex string."""
    try:
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0

        # RGB to HLS
        import colorsys
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        h = (h + shift / 360.0) % 1.0
        r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)

        return "#{:02X}{:02X}{:02X}".format(
            int(r2 * 255), int(g2 * 255), int(b2 * 255)
        )
    except Exception:
        return f"#{hex_color}"
# ==============================================================================
# 5. MAIN ENGINE CLASS  — what you import in your generator
# ==============================================================================

class NicheEngine:
    """
    Main entry point. Construct once per site, reuse across all pages.

    Example:
        niche = NicheEngine(b_data)
        css_content = niche.get_css()
        extra_html  = niche.get_extra_sections(p_data, service_name)
        image_mood  = niche.image_mood          # inject into image prompts
        cta_label   = niche.cta_label           # override hero button text
    """

    def __init__(self, b_data: dict, claude_caller=None):
        self.b_data  = b_data
        self.slug    = classify_niche(
            b_data.get("industry", ""),
            b_data.get("flat_services_list", [])
        )

        # If we matched a real built-in niche, use it.
        # If classifier fell back to 'general' (no real match), ask Claude
        # to design a custom profile for this unknown industry.
        if self.slug != "general" and self.slug in NICHE_PROFILES:
            self.profile = NICHE_PROFILES[self.slug]
        else:
            self.profile = generate_dynamic_profile(b_data, claude_caller)
            self.slug = "custom"

        self.label   = self.profile.get("label", "General")

        # --- HERO VARIANT — seed-aware: har business ko alag variant ---
        _seed = b_data.get('site_seed', 0)
        _home_pv = get_page_variant(self.slug, "home", _seed)
        self.hero_variant   = _home_pv["variant"]
        self.hero_show_form = _home_pv["show_form"]
        self.page_variant_map = PAGE_VARIANT_MAP.get(self.slug, PAGE_VARIANT_MAP["general"])
        print(f"   🎨 Hero variants (seed {_seed}): home={_home_pv['variant']} | "
              f"cat={get_page_variant(self.slug,'category',_seed)['variant']} | "
              f"child={get_page_variant(self.slug,'child',_seed)['variant']}")

        # --- CARD VARIANT — seed se rotate (same niche, alag business = alag cards) ---
        _base_cv = _resolve_card_variant(self.profile.get("card_style", ""))
        _cv_pool = ["image_top", "icon_left", "minimal_border"]
        if _seed:
            _start = _cv_pool.index(_base_cv)
            self.card_variant = _cv_pool[(_start + (_seed // 3)) % len(_cv_pool)]
        else:
            self.card_variant = _base_cv

        # --- SECTION ORDER — PAGE_VARIANT_MAP se aata hai ab ---
        self.section_order = get_page_variant(self.slug, "home").get(
            "sections", ["why_choose", "reviews", "areas"]
        )

        # Quick-access properties
        self.image_mood   = self.profile.get("image_mood", "professional business")
        self.cta_label    = self.profile.get("cta_label", "Get Free Quote")
        self.cta_icon     = self.profile.get("cta_icon",  "fa-file-invoice-dollar")
        self.trust_items  = self.profile.get("trust_items", [])
        self.schema_types = self.profile.get("schema_types", ["LocalBusiness"])
        self.faq_tone     = self.profile.get("faq_tone", "friendly_professional")
        self.hero_style   = self.profile.get("hero_style", "lead_form")

        print(f"   🎨 NicheEngine: classified as [{self.slug.upper()}] — {self.label}")

    # ------------------------------------------------------------------
    def get_css(self) -> str:
        """Return the full niche-specific CSS string."""
        return generate_niche_css(self.b_data, self.profile)

    # ------------------------------------------------------------------
    def get_extra_sections(self, p_data: dict = None, service_name: str = "") -> str:
        """
        Return HTML string of all niche-specific extra sections.
        Inject this right after the hero section in assemble_page_content().
        """
        # ⚠️ FAKE-CLAIM sections default OFF — fabricated stats/teams/awards
        # E-E-A-T aur client trust ke liye nuksandeh hain. Real data milne
        # par specific section is set se hata dena.
        _FAKE_CLAIM_SECTIONS = {
            "team_cards", "roi_stats_counter", "client_logos",
            "case_study_snippet", "verdict_stats", "awards_bar",
            "github_stats", "transformation_stats", "property_stats",
            "insurance_logos", "certifications_bar", "chef_spotlight",
            "menu_preview", "trainer_cards",
        }
        sections = [s for s in self.profile.get("extra_sections", [])
                    if s not in _FAKE_CLAIM_SECTIONS]
        html = ""
        for sec_name in sections:
            builder = SECTION_BUILDERS.get(sec_name)
            if builder:
                try:
                    html += builder(self.b_data, self.profile)
                except Exception as e:
                    print(f"   ⚠️ Section [{sec_name}] failed: {e}")
        return html

    # ------------------------------------------------------------------
    def get_image_prompt_suffix(self) -> str:
        """Append to every image prompt for niche-consistent visuals."""
        return f" {self.image_mood}. Photorealistic, professional, high quality."

    # ------------------------------------------------------------------
    def get_schema_types(self) -> list:
        return self.schema_types

    # ------------------------------------------------------------------
    def get_faq_tone_instruction(self) -> str:
        """Returns a natural language instruction to pass to Claude for FAQs."""
        tones = {
            "clinical_reassuring":   "Use calm, reassuring medical language. Avoid jargon. Emphasise patient safety.",
            "reassuring_comfort":    "Be warm and calming. Address fear of pain. Use simple words.",
            "direct_practical":      "Be direct and practical. Include costs, timeframes, emergency info.",
            "authoritative_clear":   "Be authoritative but accessible. Avoid legalese. Focus on outcomes.",
            "friendly_informative":  "Be friendly and informative. Include local market context.",
            "warm_hospitable":       "Be warm and inviting. Focus on experience and atmosphere.",
            "warm_luxurious":        "Use luxurious, aspirational language. Focus on self-care outcomes.",
            "motivational_direct":   "Be energetic and motivational. Use action verbs. Challenge the reader.",
            "data_driven_confident": "Use data, percentages, and ROI figures. Be confident and specific.",
            "technical_clear":       "Be technically precise but accessible. Explain concepts clearly.",
            "friendly_professional": "Balance professionalism with approachability.",
        }
        return tones.get(self.faq_tone, tones["friendly_professional"])

    # ------------------------------------------------------------------
    def get_hero_trust_bar_html(self) -> str:
        """Returns HTML for the niche trust items shown in hero."""
        items_html = ""
        for item in self.trust_items[:4]:
            items_html += f"""
            <div class="hero-feature">
                <i class="fas fa-check-circle" style="color:var(--accent);"></i> {item}
            </div>"""
        return f'<div class="hero-features">{items_html}</div>'


# ==============================================================================
# PAGE-TYPE VARIANT MAP — har page type ka alag hero + section combo
# niche_slug → page_type → {variant, show_form, sections}
# ==============================================================================
PAGE_VARIANT_MAP = {

    "home_services": {
        "home":     {"variant": "split_form",    "show_form": True,
                     "sections": ["process_steps","why_choose","reviews","guarantee_seal","areas","internal_links","faq"]},
        "category": {"variant": "overlay_band",  "show_form": False,
                     "sections": ["why_choose","reviews","areas","internal_links","faq"]},
        "child":    {"variant": "left_form_wide","show_form": True,
                     "sections": ["why_choose","guarantee_seal","reviews","areas","internal_links","faq"]},
        "contact":  {"variant": "centered_cta",  "show_form": False, "sections": []},
        "about":    {"variant": "centered_cta",  "show_form": False, "sections": []},
    },

    "medical": {
        "home":     {"variant": "split_form",    "show_form": True,
                     "sections": ["process_steps","why_choose","reviews","areas","internal_links","faq"]},
        "category": {"variant": "centered_cta",  "show_form": False,
                     "sections": ["why_choose","reviews","faq"]},
        "child":    {"variant": "overlay_band",  "show_form": True,
                     "sections": ["why_choose","reviews","areas","internal_links","faq"]},
        "contact":  {"variant": "centered_cta",  "show_form": False, "sections": []},
        "about":    {"variant": "centered_cta",  "show_form": False, "sections": []},
    },

    "dental": {
        "home":     {"variant": "split_form",    "show_form": True,
                     "sections": ["process_steps","why_choose","reviews","areas","internal_links","faq"]},
        "category": {"variant": "overlay_band",  "show_form": False,
                     "sections": ["why_choose","reviews","faq"]},
        "child":    {"variant": "left_form_wide","show_form": True,
                     "sections": ["why_choose","reviews","areas","internal_links","faq"]},
        "contact":  {"variant": "centered_cta",  "show_form": False, "sections": []},
        "about":    {"variant": "centered_cta",  "show_form": False, "sections": []},
    },

    "digital_agency": {
        "home":     {"variant": "left_form_wide","show_form": True,
                     "sections": ["process_steps","why_choose","reviews","areas","internal_links","faq"]},
        "category": {"variant": "overlay_band",  "show_form": False,
                     "sections": ["why_choose","reviews","faq"]},
        "child":    {"variant": "split_form",    "show_form": True,
                     "sections": ["why_choose","reviews","areas","internal_links","faq"]},
        "contact":  {"variant": "centered_cta",  "show_form": False, "sections": []},
        "about":    {"variant": "centered_cta",  "show_form": False, "sections": []},
    },

    "legal": {
        "home":     {"variant": "overlay_band",  "show_form": True,
                     "sections": ["process_steps","why_choose","reviews","areas","internal_links","faq"]},
        "category": {"variant": "centered_cta",  "show_form": False,
                     "sections": ["why_choose","reviews","faq"]},
        "child":    {"variant": "split_form",    "show_form": True,
                     "sections": ["why_choose","reviews","areas","internal_links","faq"]},
        "contact":  {"variant": "centered_cta",  "show_form": False, "sections": []},
        "about":    {"variant": "centered_cta",  "show_form": False, "sections": []},
    },

    "beauty": {
        "home":     {"variant": "centered_cta",  "show_form": False,
                     "sections": ["process_steps","why_choose","reviews","areas","internal_links","faq"]},
        "category": {"variant": "overlay_band",  "show_form": False,
                     "sections": ["why_choose","reviews","faq"]},
        "child":    {"variant": "split_form",    "show_form": True,
                     "sections": ["why_choose","reviews","areas","internal_links","faq"]},
        "contact":  {"variant": "centered_cta",  "show_form": False, "sections": []},
        "about":    {"variant": "centered_cta",  "show_form": False, "sections": []},
    },

    "fitness": {
        "home":     {"variant": "overlay_band",  "show_form": False,
                     "sections": ["process_steps","why_choose","reviews","areas","internal_links","faq"]},
        "category": {"variant": "centered_cta",  "show_form": False,
                     "sections": ["why_choose","reviews","faq"]},
        "child":    {"variant": "left_form_wide","show_form": True,
                     "sections": ["why_choose","reviews","areas","internal_links","faq"]},
        "contact":  {"variant": "centered_cta",  "show_form": False, "sections": []},
        "about":    {"variant": "centered_cta",  "show_form": False, "sections": []},
    },

    "restaurant": {
        "home":     {"variant": "centered_cta",  "show_form": False,
                     "sections": ["process_steps","why_choose","reviews","areas","faq"]},
        "category": {"variant": "overlay_band",  "show_form": False,
                     "sections": ["why_choose","reviews","faq"]},
        "child":    {"variant": "overlay_band",  "show_form": False,
                     "sections": ["why_choose","reviews","areas","faq"]},
        "contact":  {"variant": "centered_cta",  "show_form": False, "sections": []},
        "about":    {"variant": "centered_cta",  "show_form": False, "sections": []},
    },

    "real_estate": {
        "home":     {"variant": "split_form",    "show_form": True,
                     "sections": ["process_steps","why_choose","reviews","areas","internal_links","faq"]},
        "category": {"variant": "overlay_band",  "show_form": False,
                     "sections": ["why_choose","reviews","faq"]},
        "child":    {"variant": "left_form_wide","show_form": True,
                     "sections": ["why_choose","reviews","areas","internal_links","faq"]},
        "contact":  {"variant": "centered_cta",  "show_form": False, "sections": []},
        "about":    {"variant": "centered_cta",  "show_form": False, "sections": []},
    },

    "auto": {
        "home":     {"variant": "split_form",    "show_form": True,
                     "sections": ["process_steps","why_choose","reviews","guarantee_seal","areas","internal_links","faq"]},
        "category": {"variant": "overlay_band",  "show_form": False,
                     "sections": ["why_choose","reviews","faq"]},
        "child":    {"variant": "left_form_wide","show_form": True,
                     "sections": ["why_choose","guarantee_seal","reviews","areas","internal_links","faq"]},
        "contact":  {"variant": "centered_cta",  "show_form": False, "sections": []},
        "about":    {"variant": "centered_cta",  "show_form": False, "sections": []},
    },

    "web_dev": {
        "home":     {"variant": "left_form_wide","show_form": True,
                     "sections": ["process_steps","why_choose","reviews","areas","internal_links","faq"]},
        "category": {"variant": "overlay_band",  "show_form": False,
                     "sections": ["why_choose","reviews","faq"]},
        "child":    {"variant": "split_form",    "show_form": True,
                     "sections": ["why_choose","reviews","areas","internal_links","faq"]},
        "contact":  {"variant": "centered_cta",  "show_form": False, "sections": []},
        "about":    {"variant": "centered_cta",  "show_form": False, "sections": []},
    },

    "general": {
        "home":     {"variant": "split_form",    "show_form": True,
                     "sections": ["process_steps","why_choose","reviews","areas","internal_links","faq"]},
        "category": {"variant": "overlay_band",  "show_form": False,
                     "sections": ["why_choose","reviews","faq"]},
        "child":    {"variant": "split_form",    "show_form": True,
                     "sections": ["why_choose","reviews","areas","internal_links","faq"]},
        "contact":  {"variant": "centered_cta",  "show_form": False, "sections": []},
        "about":    {"variant": "centered_cta",  "show_form": False, "sections": []},
    },
}


HERO_VARIANT_POOLS = {
    "home_services": {"home":  ["split_form", "left_form_wide", "overlay_band"],
                      "child": ["left_form_wide", "split_form", "overlay_band"]},
    "medical":       {"home":  ["split_form", "overlay_band"],
                      "child": ["overlay_band", "split_form"]},
    "dental":        {"home":  ["split_form", "overlay_band"],
                      "child": ["left_form_wide", "split_form"]},
    "digital_agency":{"home":  ["left_form_wide", "split_form", "overlay_band"],
                      "child": ["split_form", "left_form_wide"]},
    "legal":         {"home":  ["overlay_band", "split_form"],
                      "child": ["split_form", "overlay_band"]},
    "auto":          {"home":  ["split_form", "left_form_wide"],
                      "child": ["left_form_wide", "split_form", "overlay_band"]},
    "real_estate":   {"home":  ["split_form", "left_form_wide"],
                      "child": ["left_form_wide", "split_form"]},
    "web_dev":       {"home":  ["left_form_wide", "split_form"],
                      "child": ["split_form", "left_form_wide", "overlay_band"]},
    "general":       {"home":  ["split_form", "overlay_band", "left_form_wide"],
                      "child": ["split_form", "left_form_wide", "overlay_band"]},
}


def get_page_variant(niche_slug: str, page_type: str, seed: int = 0) -> dict:
    """Page type ke liye hero variant + section order. Seed-aware variety."""
    niche_map = PAGE_VARIANT_MAP.get(niche_slug, PAGE_VARIANT_MAP["general"])
    base = dict(niche_map.get(page_type, niche_map.get("child", {
        "variant":   "split_form",
        "show_form": True,
        "sections":  ["why_choose", "reviews", "areas", "faq"]
    })))

    if seed and page_type in ("home", "category", "child"):
        pools = HERO_VARIANT_POOLS.get(niche_slug, HERO_VARIANT_POOLS["general"])
        pool = pools.get(page_type) or pools.get("child")
        if pool:
            base["variant"] = pool[seed % len(pool)]

    return base

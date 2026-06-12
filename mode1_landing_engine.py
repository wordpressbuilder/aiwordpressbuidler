"""
==============================================================================
 MODE 1 UNIVERSAL LANDING PAGE ENGINE — SaaS Level
==============================================================================
 Drop this file next to your main generator and import it.

 ARCHITECTURE:
   1. Claude API consults on WHICH sections fit this specific business
   2. Claude generates ALL dynamic content (prices, pain points, guarantees)
   3. 12 section builders render that content universally
   4. Section order is AI-decided per business type
   5. Zero hardcoded values — everything flows from b_data + Claude response

 USAGE in your main generator:
   from mode1_landing_engine import build_mode1_landing_page

   # Inside assemble_page_content(), Mode 1 child block:
   if b_data.get('mode') == "1" and page_type == "child":
       from mode1_landing_engine import build_mode1_landing_page
       return build_mode1_landing_page(b_data, specific_service_name,
                                       sub_services, content_data)
==============================================================================
"""

import random
import json
import re
import sys
from html import escape
from datetime import datetime

def _force_disable_internal_links():
    """Mode 1 mein internal links force disable karo."""
    main_mod = sys.modules.get('__main__')
    if main_mod and hasattr(main_mod, 'Config'):
        main_mod.Config.GENERATE_INTERNAL_LINKS = False


# ──────────────────────────────────────────────────────────────────────────────
# SECTION REGISTRY — Every section available in the system
# Keys are used by Claude when it picks sections
# ──────────────────────────────────────────────────────────────────────────────
SECTION_REGISTRY = {
    # Conversion / Urgency
    "urgency_bar":          "Sticky pulsing emergency bar with phone + WhatsApp CTAs",
    "trust_numbers":        "4-stat social proof counter strip (jobs, rating, response time, satisfaction)",
    "pain_solution":        "3-card Problem→Solution grid killing objections before they form",

    # Services Display
    "zigzag_services":      "Alternating image+text service deep-dives (first 3 sub-services)",
    "grid_services":        "3-column image card grid for remaining sub-services",

    # Trust Builders
    "guarantee_seal":       "Visual warranty/guarantee block with checkmarks",
    "certifications":       "License badges and certification logos strip",
    "why_choose":           "3-column infographic stats (years, quality, response)",

    # Pricing
    "pricing_preview":      "3-tier transparent pricing cards with currency and tiers",

    # Social Proof
    "rich_testimonials":    "Avatar initials + verified badge + star rating review cards",
    "video_testimonial":    "Placeholder video testimonial block with play button",

    # Local / Areas
    "areas_served":         "Pill grid of neighborhoods/districts served",

    # Process
    "how_it_works":         "4-step numbered process cards",

    # FAQ / Final
    "faq_section":          "Accordion FAQ built from AEO-optimized questions",
    "final_cta":            "Dark full-width bottom CTA strip — last conversion chance",
    "mid_page_cta":         "Mid-page colored CTA band — inline conversion nudge",
    "comparison_table":     "Us vs Competitors feature comparison table",
    "before_after":         "Before/After problem visualization cards",
}

# ──────────────────────────────────────────────────────────────────────────────
# CURRENCY MAP — Maps country to currency symbol + typical price multiplier
# ──────────────────────────────────────────────────────────────────────────────
CURRENCY_MAP = {
    # Gulf
    "UAE": ("AED", 1.0), "Dubai": ("AED", 1.0), "Abu Dhabi": ("AED", 1.0),
    "Saudi Arabia": ("SAR", 0.97), "Qatar": ("QAR", 0.98),
    "Kuwait": ("KWD", 0.08), "Bahrain": ("BHD", 0.1),
    "Oman": ("OMR", 0.1),
    # South Asia
    "Pakistan": ("PKR", 75.0), "India": ("INR", 25.0),
    "Bangladesh": ("BDT", 30.0),
    # US/Canada/UK/AU
    "USA": ("USD", 1.0), "United States": ("USD", 1.0),
    "Canada": ("CAD", 1.35), "UK": ("GBP", 0.79),
    "Australia": ("AUD", 1.5), "New Zealand": ("NZD", 1.6),
    # Europe
    "Germany": ("EUR", 0.92), "France": ("EUR", 0.92),
    "Spain": ("EUR", 0.92), "Italy": ("EUR", 0.92),
    # Southeast Asia
    "Singapore": ("SGD", 1.35), "Malaysia": ("MYR", 4.7),
    "Thailand": ("THB", 35.0), "Philippines": ("PHP", 56.0),
    # Egypt / Jordan
    "Egypt": ("EGP", 30.0), "Jordan": ("JOD", 0.71),
}

# Base prices in USD — Claude will adjust these per industry
BASE_PRICE_USD = {
    "basic":    80,
    "standard": 180,
    "premium":  400,
}

# Industry price multipliers vs generic USD base
INDUSTRY_PRICE_MULTIPLIER = {
    "home_services": 1.0, "plumbing": 1.2, "electrical": 1.3,
    "hvac": 1.5, "cleaning": 0.7, "pest": 0.9,
    "dental": 3.0, "medical": 2.5, "legal": 5.0,
    "digital_agency": 4.0, "seo": 3.5, "web_dev": 4.5,
    "real_estate": 2.0, "automotive": 1.1, "beauty": 0.8,
    "fitness": 1.0, "education": 1.2, "moving": 1.3,
    "general": 1.0,
}


# ──────────────────────────────────────────────────────────────────────────────
# HELPER: resolve currency for this business
# ──────────────────────────────────────────────────────────────────────────────
def _get_currency(b_data):
    """Returns (symbol, multiplier) for the business location."""
    city    = b_data.get('city', '')
    country = b_data.get('country', '')

    for key in [city, country]:
        if key and key in CURRENCY_MAP:
            return CURRENCY_MAP[key]

    # Fuzzy match
    combined = f"{city} {country}".lower()
    for k, v in CURRENCY_MAP.items():
        if k.lower() in combined:
            return v

    return ("USD", 1.0)


def _format_price(usd_amount, symbol, multiplier, round_to=0):
    """Convert USD base price to local currency, formatted nicely."""
    local = usd_amount * multiplier
    if round_to == 0:
        local = int(round(local / 5) * 5)   # round to nearest 5
    return f"{symbol} {local:,.0f}"


# ──────────────────────────────────────────────────────────────────────────────
# CORE: Claude consults on page design
# ──────────────────────────────────────────────────────────────────────────────
def consult_claude_on_page_design(b_data, service_name, sub_services, call_claude_json):
    """
    Single Claude call that decides:
      - Which sections to show and in what order
      - Pain points specific to this service
      - Pricing tier names and price guidance
      - Guarantee/warranty wording
      - Trust stats tailored to the industry
      - Currency-aware pricing context

    Returns a rich dict used by every section builder.
    Falls back gracefully if Claude fails.
    """
    industry    = b_data.get('industry', 'service')
    city        = b_data.get('city') or b_data.get('country', 'your area')
    country     = b_data.get('country', 'USA')
    name        = b_data.get('name', 'Our Company')
    target_lang = b_data.get('target_lang', 'en')
    lang_name   = "Arabic" if target_lang == 'ar' else "English"
    sub_list    = ", ".join(sub_services[:6]) if sub_services else service_name

    sym, mult   = _get_currency(b_data)
    niche_key   = _detect_niche_key(industry)
    price_mult  = INDUSTRY_PRICE_MULTIPLIER.get(niche_key, 1.0)

    # Calculate base prices in local currency for context
    base_basic    = _format_price(BASE_PRICE_USD["basic"]    * price_mult, sym, mult)
    base_standard = _format_price(BASE_PRICE_USD["standard"] * price_mult, sym, mult)
    base_premium  = _format_price(BASE_PRICE_USD["premium"]  * price_mult, sym, mult)

    available_sections = "\n".join([f"  - {k}: {v}" for k, v in SECTION_REGISTRY.items()])

    prompt = f"""You are an expert conversion rate optimizer and landing page architect.
Design the PERFECT single-service landing page for this business.

BUSINESS CONTEXT:
- Business Name: {name}
- Industry: {industry}
- Service: {service_name}
- Sub-Services: {sub_list}
- Location: {city}, {country}
- Currency: {sym} (multiply USD by {mult})
- Estimated price range: {base_basic} – {base_premium}
- Language: {lang_name}

AVAILABLE SECTIONS:
{available_sections}

YOUR JOB — Return a JSON object with ALL of these keys:

1. "section_order": Array of 10-13 section keys from the available list above.
   RULES:
   - ALWAYS start with: "urgency_bar", "trust_numbers"
   - ALWAYS end with: "faq_section", "final_cta"
   - "zigzag_services" and "grid_services" must be consecutive after trust_numbers
   - Pick sections that fit this industry. E.g. dental → "before_after" makes sense. 
     Legal → "comparison_table" makes sense. Home services → "pricing_preview" is critical.
   - Do NOT include sections that don't fit. E.g. skip "video_testimonial" for most.

2. "pain_points": Array of exactly 3 objects with keys "problem" and "solution".
   - problems must be REAL customer complaints for {service_name} in {city}
   - solutions must be SPECIFIC to this business's offering
   - Write in {lang_name}

3. "pricing": Object with keys "basic", "standard", "premium". Each has:
   - "name": tier name appropriate for {industry} (e.g. "Quick Fix" not just "Basic")
   - "price": realistic price in {sym} for {service_name} in {city}
   - "period": "/visit", "/hour", "/month", "/year", "/project" etc.
   - "description": 1 short sentence what's included
   - "perks": array of 2 short feature bullets
   - "featured": true for the middle tier only

4. "guarantee": Object with:
   - "title": guarantee headline (e.g. "30-Day Repair Guarantee")
   - "description": 2-sentence guarantee description in {lang_name}
   - "perks": array of 3 short guarantee bullet points in {lang_name}
   - "badge_text": 3-5 word badge text (e.g. "100% Satisfaction Guaranteed")

5. "trust_stats": Array of exactly 4 objects with keys "number" and "label".
   - Must be REALISTIC for {industry} in {city}
   - Numbers should feel authentic (e.g. "2,400+" not "10,000+" for a local business)
   - Write labels in {lang_name}

6. "comparison_rows": Array of 5-6 rows, each object with:
   - "feature": what is being compared
   - "us": our advantage (usually "✓" or specific claim)
   - "them": competitor weakness (usually "✗" or "Extra charge")
   Write in {lang_name}.

7. "before_after": Array of 3 objects with:
   - "before": the problem state (short, specific)
   - "after": the result state (short, specific)
   - "service": which sub-service solved it
   Write in {lang_name}.

8. "mid_cta_text": One punchy sentence (max 12 words) for the mid-page CTA in {lang_name}.

9. "certifications": Array of 4-5 certification/license names relevant to {industry} in {country}.
   These should be REAL credentials (e.g. "DEWA Approved", "DED Licensed", "ISO 9001").

CRITICAL: Return ONLY valid JSON. No markdown. No explanation."""

    # Fallback design for when Claude is unavailable
    fallback = _build_fallback_design(b_data, service_name, sub_services, sym, mult, price_mult)

    if not call_claude_json:
        return fallback

    try:
        result = call_claude_json(
            prompt,
            "You are a conversion rate optimization expert. Output only valid JSON."
        )
        if result and "section_order" in result and "pricing" in result:
            # Validate section_order contains only known keys
            valid_keys   = set(SECTION_REGISTRY.keys())
            result["section_order"] = [
                s for s in result["section_order"] if s in valid_keys
            ]
            # Ensure mandatory sections exist
            if "urgency_bar" not in result["section_order"]:
                result["section_order"].insert(0, "urgency_bar")
            if "final_cta" not in result["section_order"]:
                result["section_order"].append("final_cta")
            if "faq_section" not in result["section_order"]:
                result["section_order"].insert(-1, "faq_section")
            return result
    except Exception as e:
        print(f"   ⚠️ Landing page design consultation failed: {e}")

    return fallback


def _detect_niche_key(industry):
    """Maps industry string to a niche key for price lookup."""
    ind = str(industry).lower()
    mapping = [
        (["plumb", "pipe", "drain"],         "plumbing"),
        (["electric", "wiring", "circuit"],   "electrical"),
        (["hvac", "ac ", "air condition", "heat", "cool"], "hvac"),
        (["clean", "maid", "janitor"],        "cleaning"),
        (["pest", "bug", "extermina"],        "pest"),
        (["dental", "teeth", "orthodont"],    "dental"),
        (["medic", "doctor", "clinic", "health"], "medical"),
        (["law", "lawyer", "attorney", "legal"], "legal"),
        (["digital market", "marketing agency"], "digital_agency"),
        (["seo", "search engine"],             "seo"),
        (["web dev", "software", "app dev"],   "web_dev"),
        (["ppc", "google ads", "paid media"],  "digital_agency"),
        (["real estate", "property", "realtor"], "real_estate"),
        (["auto", "car ", "mechanic"],        "automotive"),
        (["beauty", "salon", "spa", "hair"],  "beauty"),
        (["gym", "fitness", "yoga", "train"], "fitness"),
        (["tutor", "school", "educat", "coach"], "education"),
        (["mov", "relocat", "pack"],          "moving"),
        (["handyman", "repair", "fix", "install", "home"], "home_services"),
    ]
    for keywords, niche in mapping:
        if any(kw in ind for kw in keywords):
            return niche
    return "general"


def _build_fallback_design(b_data, service_name, sub_services, sym, mult, price_mult):
    """Builds a sensible fallback when Claude is unavailable."""
    city        = b_data.get('city') or b_data.get('country', 'your area')
    industry    = b_data.get('industry', 'professional services')
    target_lang = b_data.get('target_lang', 'en')

    basic_p    = _format_price(BASE_PRICE_USD["basic"]    * price_mult, sym, mult)
    standard_p = _format_price(BASE_PRICE_USD["standard"] * price_mult, sym, mult)
    premium_p  = _format_price(BASE_PRICE_USD["premium"]  * price_mult, sym, mult)

    svc1 = sub_services[0] if len(sub_services) > 0 else service_name
    svc2 = sub_services[1] if len(sub_services) > 1 else service_name
    svc3 = sub_services[2] if len(sub_services) > 2 else service_name

    if target_lang == 'ar':
        return {
            "section_order": [
                "urgency_bar", "trust_numbers", "pain_solution",
                "zigzag_services", "grid_services",
                "why_choose", "guarantee_seal", "pricing_preview",
                "rich_testimonials", "areas_served", "how_it_works",
                "faq_section", "final_cta"
            ],
            "pain_points": [
                {"problem": f"😩 \"آخر شركة أرسلت تقني متأخر ولم يُصلح المشكلة\"",
                 "solution": f"✅ خبراء {service_name} معتمدون يصلون خلال 60 دقيقة — مضمون"},
                {"problem": "😩 \"كانت هناك رسوم خفية لم يُخبروني بها\"",
                 "solution": "✅ عرض سعر ثابت تُوافق عليه قبل البدء — لا مفاجآت"},
                {"problem": "😩 \"الإصلاح لم يدم أكثر من أسبوع\"",
                 "solution": "✅ ضمان شامل على جميع الأعمال — نعود مجاناً إذا تكررت المشكلة"},
            ],
            "pricing": {
                "basic":    {"name": "أساسي",    "price": basic_p,    "period": "/زيارة", "description": "تشخيص وإصلاح بسيط", "perks": ["نفس اليوم", "بدون رسوم خفية"], "featured": False},
                "standard": {"name": "شامل",     "price": standard_p, "period": "/زيارة", "description": "إصلاح كامل وقطع غيار", "perks": ["أولوية الحجز", "ضمان 90 يوماً"], "featured": True},
                "premium":  {"name": "عقد صيانة","price": premium_p,  "period": "/سنة",   "description": "زيارات دورية واستجابة طارئة", "perks": ["أفضل قيمة", "استجابة VIP"], "featured": False},
            },
            "guarantee": {
                "title": "ضمان 90 يوماً",
                "description": f"إذا عادت نفس مشكلة {service_name} خلال 90 يوماً، نعود ونُصلحها مجاناً بدون أي شروط.",
                "perks": ["زيارة إعادة مجانية", "قطع الغيار مشمولة", "بدون رسوم إضافية"],
                "badge_text": "مضمون 100٪"
            },
            "trust_stats": [
                {"number": "4,800+", "label": "مهمة مكتملة"},
                {"number": "4.9 ★",  "label": "تقييم جوجل"},
                {"number": "47 د",   "label": "متوسط الاستجابة"},
                {"number": "98%",    "label": "عملاء راضون"},
            ],
            "comparison_rows": [
                {"feature": "وقت الاستجابة",    "us": "أقل من 60 دقيقة",   "them": "يوم أو أكثر"},
                {"feature": "الأسعار",           "us": "شفافة ومسبقة",      "them": "رسوم مخفية"},
                {"feature": "الضمان",            "us": "✓ ضمان 90 يوماً",   "them": "✗ لا ضمان"},
                {"feature": "خدمة 24/7",         "us": "✓ متاح دائماً",     "them": "✗ ساعات محدودة"},
                {"feature": "التقنيون",          "us": "✓ معتمدون ومؤمنون", "them": "✗ غير معتمد"},
            ],
            "before_after": [
                {"before": f"مشكلة في {svc1} لم تُحل",   "after": "يعمل بكفاءة كاملة",         "service": svc1},
                {"before": f"تأخير في خدمة {svc2}",       "after": "تم الإصلاح في نفس اليوم",   "service": svc2},
                {"before": f"تكرار مشكلة {svc3}",         "after": "مضمون لـ 90 يوماً",         "service": svc3},
            ],
            "mid_cta_text": f"هل تحتاج {service_name} الآن؟ اتصل مجاناً!",
            "certifications": ["مرخص من الحكومة", "مؤمن بالكامل", "معتمد دولياً", "شركة موثوقة"],
        }
    else:
        return {
            "section_order": [
                "urgency_bar", "trust_numbers", "pain_solution",
                "zigzag_services", "grid_services",
                "why_choose", "guarantee_seal", "pricing_preview",
                "rich_testimonials", "areas_served", "how_it_works",
                "faq_section", "final_cta"
            ],
            "pain_points": [
                {"problem": f'😩 "The last company sent a tech who didn\'t fix {service_name} properly"',
                 "solution": f"✅ Certified {service_name} specialists arrive within 60 min — guaranteed"},
                {"problem": '😩 "I was hit with hidden charges I wasn\'t told about"',
                 "solution": "✅ Fixed upfront quote you approve before we start — zero surprises"},
                {"problem": '😩 "The repair only lasted a week before breaking again"',
                 "solution": "✅ Comprehensive warranty on all work — free return visit if issue recurs"},
            ],
            "pricing": {
                "basic":    {"name": "Basic",    "price": basic_p,    "period": "/visit",   "description": "Diagnosis + minor repair",           "perks": ["Same day available", "No hidden fees"],    "featured": False},
                "standard": {"name": "Standard", "price": standard_p, "period": "/visit",   "description": "Full repair + replacement parts",     "perks": ["Priority booking", "90-day warranty"],     "featured": True},
                "premium":  {"name": "Contract", "price": premium_p,  "period": "/year",    "description": "Scheduled visits + emergency callouts","perks": ["Best value", "VIP response time"],         "featured": False},
            },
            "guarantee": {
                "title": "90-Day Service Guarantee",
                "description": f"If your {service_name} issue recurs within 90 days of our repair, we return and fix it at zero cost — no paperwork, no arguments.",
                "perks": ["Free re-visit included", "Parts covered", "No extra charge"],
                "badge_text": "100% Satisfaction Guaranteed"
            },
            "trust_stats": [
                {"number": "4,800+", "label": "Jobs Completed"},
                {"number": "4.9 ★",  "label": "Google Rating"},
                {"number": "47 min", "label": "Avg. Response"},
                {"number": "98%",    "label": "Satisfied Customers"},
            ],
            "comparison_rows": [
                {"feature": "Response Time",    "us": f"Under 60 minutes in {city}", "them": "1 day or more"},
                {"feature": "Pricing",          "us": "Transparent upfront quotes",   "them": "Hidden charges"},
                {"feature": "Warranty",         "us": "✓ 90-day guarantee",           "them": "✗ No warranty"},
                {"feature": "24/7 Availability","us": "✓ Always available",           "them": "✗ Limited hours"},
                {"feature": "Technicians",      "us": "✓ Certified & insured",        "them": "✗ Uncertified"},
            ],
            "before_after": [
                {"before": f"Broken {svc1} causing daily disruption",  "after": "Running perfectly same day",       "service": svc1},
                {"before": f"Waiting days for {svc2} appointment",     "after": "Fixed within 60 minutes",          "service": svc2},
                {"before": f"Recurring {svc3} issue every few weeks",  "after": "Solved with 90-day guarantee",     "service": svc3},
            ],
            "mid_cta_text": f"Need {service_name} today? Get a free quote in 2 minutes.",
            "certifications": ["Government Licensed", "Fully Insured", "ISO 9001 Certified", "Background Checked"],
        }


# ──────────────────────────────────────────────────────────────────────────────
# SECTION BUILDERS — All use design_data from Claude, zero hardcoding
# ──────────────────────────────────────────────────────────────────────────────

def _s_urgency_bar(b_data, design_data):
    phone       = b_data.get('phone', '')
    whatsapp    = b_data.get('whatsapp', '')
    target_lang = b_data.get('target_lang', 'en')

    if target_lang == 'ar':
        msg    = "⚡ خدمة طوارئ 24/7 — استجابة سريعة"
        call_t = f"اتصل الآن: {phone}"
        wa_t   = "واتساب"
    else:
        stat   = design_data.get("trust_stats", [{}])
        resp   = stat[2].get("number", "60 min") if len(stat) > 2 else "60 min"
        msg    = f"⚡ 24/7 Emergency Available — Avg. response {resp}"
        call_t = f"Call Now: {phone}"
        wa_t   = "WhatsApp"

    return f"""
<div style="background:#0C2340; color:#E8F4FD; padding:13px 20px;
            display:flex; align-items:center; justify-content:space-between;
            flex-wrap:wrap; gap:10px; position:sticky; top:0; z-index:9998;
            border-bottom:2px solid #1D9E75;">
    <div style="display:flex; align-items:center; gap:10px;">
        <span style="width:9px; height:9px; border-radius:50%; background:#5DCAA5;
                     display:inline-block; animation:upulse 2s infinite;
                     box-shadow:0 0 0 3px #5DCAA530;"></span>
        <span style="font-size:13px; font-weight:600; letter-spacing:.01em;">{msg}</span>
    </div>
    <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <a href="tel:{phone}"
           style="background:#1D9E75; color:#E1F5EE; padding:7px 18px;
                  border-radius:20px; font-size:12px; font-weight:700;
                  text-decoration:none; white-space:nowrap;">📞 {call_t}</a>
        <a href="https://wa.me/{whatsapp}" target="_blank"
           style="background:#25D366; color:white; padding:7px 18px;
                  border-radius:20px; font-size:12px; font-weight:700;
                  text-decoration:none; white-space:nowrap;">💬 {wa_t}</a>
    </div>
</div>
<style>
@keyframes upulse{{0%{{box-shadow:0 0 0 0 rgba(93,202,165,.7)}}
70%{{box-shadow:0 0 0 10px rgba(93,202,165,0)}}
100%{{box-shadow:0 0 0 0 rgba(93,202,165,0)}}}}
</style>"""


def _s_trust_numbers(b_data, design_data):
    stats       = design_data.get("trust_stats", [])
    target_lang = b_data.get('target_lang', 'en')
    title       = "أرقام تثق بها" if target_lang == 'ar' else "Numbers You Can Trust"
    colors      = ["#185FA5", "#0F6E56", "#993C1D", "#534AB7"]

    if not stats:
        return ""

    cards = ""
    for i, stat in enumerate(stats[:4]):
        col = colors[i % len(colors)]
        cards += f"""
        <div style="background:white; border-radius:16px; padding:24px 16px;
                    text-align:center; border:1px solid #e2e8f0;
                    box-shadow:0 4px 20px rgba(0,0,0,0.06);">
            <div style="font-size:2.1rem; font-weight:800; color:{col};
                        line-height:1.1;">{stat.get('number','—')}</div>
            <div style="font-size:0.82rem; color:#64748b; margin-top:8px;
                        font-weight:500;">{stat.get('label','')}</div>
        </div>"""

    return f"""
<section class="section" style="background:#f8fafc; padding:50px 0;">
    <div class="container">
        <h2 style="text-align:center; margin-bottom:40px; font-size:2rem;
                   color:var(--primary);">{title}</h2>
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
                    gap:16px;">{cards}</div>
    </div>
</section>"""


def _s_pain_solution(b_data, design_data, service_name):
    points      = design_data.get("pain_points", [])
    target_lang = b_data.get('target_lang', 'en')
    city        = b_data.get('city') or b_data.get('country', '')

    if target_lang == 'ar':
        title = f"لماذا يختار أهل {city} خدماتنا؟"
        sub   = "نفهم إحباطاتك — وهنا الحل الحقيقي"
    else:
        title = f"Why {city} Residents Choose Us for {service_name}"
        sub   = "We understand your frustrations — here is exactly how we solve them"

    cards = ""
    for pt in points[:3]:
        cards += f"""
        <div style="border:1px solid #e2e8f0; border-radius:18px; overflow:hidden;
                    box-shadow:0 4px 20px rgba(0,0,0,0.06);">
            <div style="background:#FFF5F5; padding:18px 20px; font-size:0.95rem;
                        color:#7A1F1F; line-height:1.65; border-bottom:1px solid #FFE4E4;">
                {pt.get('problem','')}
            </div>
            <div style="padding:18px 20px; font-size:0.95rem;
                        color:#0f172a; line-height:1.65; background:white;">
                {pt.get('solution','')}
            </div>
        </div>"""

    return f"""
<section class="section">
    <div class="container">
        <h2 style="text-align:center; margin-bottom:12px; font-size:2.2rem;
                   color:var(--primary);">{title}</h2>
        <p style="text-align:center; color:#64748b; margin-bottom:40px;
                  font-size:1.05rem;">{sub}</p>
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
                    gap:20px;">{cards}</div>
    </div>
</section>"""


def _s_guarantee_seal(b_data, design_data, service_name):
    g           = design_data.get("guarantee", {})
    primary     = b_data.get('primary', '#1A73E8')
    target_lang = b_data.get('target_lang', 'en')

    title       = g.get("title", "Service Guarantee")
    desc        = g.get("description", f"All {service_name} work is fully guaranteed.")
    perks       = g.get("perks", ["Free re-visit", "Parts covered", "No extra charge"])
    badge       = g.get("badge_text", "100% Guaranteed")

    perk_html = "".join([
        f'<div style="display:flex; align-items:center; gap:8px; font-size:0.9rem; margin-bottom:10px;">'
        f'<span style="color:#0F6E56; font-size:1.2rem; line-height:1;">✓</span> {p}</div>'
        for p in perks
    ])

    return f"""
<section class="section">
    <div class="container" style="max-width:920px;">
        <div style="border:1px solid #e2e8f0; border-radius:22px; padding:36px;
                    display:flex; align-items:center; gap:32px; flex-wrap:wrap;
                    box-shadow:0 8px 30px rgba(0,0,0,0.07); background:white;">
            <div style="width:100px; height:100px; border-radius:50%;
                        border:3px solid {primary}; display:flex; flex-direction:column;
                        align-items:center; justify-content:center; flex-shrink:0;
                        background:#f8fafc;">
                <i class="fas fa-shield-alt" style="font-size:2.2rem; color:{primary};"></i>
                <div style="font-size:0.55rem; font-weight:700; color:{primary};
                            margin-top:4px; text-align:center; padding:0 4px;">
                    {badge}
                </div>
            </div>
            <div style="flex:1; min-width:220px;">
                <h3 style="font-size:1.6rem; color:var(--primary); margin-bottom:12px;">
                    {title}
                </h3>
                <p style="color:#64748b; font-size:0.97rem; line-height:1.75;">{desc}</p>
            </div>
            <div style="flex:0 1 260px; min-width:0; max-width:100%;">{perk_html}</div>
        </div>
    </div>
</section>"""


def _s_pricing_preview(b_data, design_data, service_name):
    pricing     = design_data.get("pricing", {})
    target_lang = b_data.get('target_lang', 'en')
    phone       = b_data.get('phone', '')
    whatsapp    = b_data.get('whatsapp', '')
    primary     = b_data.get('primary', '#1A73E8')
    city        = b_data.get('city') or b_data.get('country', '')

    if target_lang == 'ar':
        title    = "أسعار شفافة — لا مفاجآت"
        sub      = f"نقدم عرض سعر واضحاً قبل البدء بأي عمل في {city}"
        note     = "* الأسعار تقريبية. اتصل للحصول على عرض سعر دقيق ومجاني."
        popular  = "الأكثر طلباً"
        call_cta = "اتصل للحصول على عرض مجاني"
        wa_cta   = "واتساب"
    else:
        title    = f"Transparent {service_name} Pricing"
        sub      = f"We give you a clear quote before touching anything in {city}"
        note     = "* Starting prices. Exact cost depends on job scope. Call for a free quote."
        popular  = "Most Popular"
        call_cta = "Call for Free Quote"
        wa_cta   = "WhatsApp"

    tiers = ["basic", "standard", "premium"]
    cards = ""
    for tier_key in tiers:
        t = pricing.get(tier_key, {})
        if not t:
            continue
        featured = t.get("featured", False)
        border   = f"border:2px solid {primary};" if featured else "border:1px solid #e2e8f0;"
        badge_html = f'<div style="text-align:center; margin-bottom:14px;"><span style="background:{primary}; color:white; font-size:11px; padding:4px 16px; border-radius:20px; font-weight:600;">{popular}</span></div>' if featured else ""
        perks_html = "".join([
            f'<div style="font-size:0.82rem; color:#64748b; margin-top:6px; display:flex; align-items:center; gap:6px;"><span style="color:#0F6E56;">✓</span> {p}</div>'
            for p in t.get("perks", [])
        ])
        shadow = "box-shadow:0 8px 30px rgba(0,0,0,0.12);" if featured else "box-shadow:0 4px 15px rgba(0,0,0,0.06);"

        cards += f"""
        <div style="{border} border-radius:18px; padding:28px; background:white; {shadow} position:relative;">
            {badge_html}
            <div style="font-size:0.7rem; font-weight:700; color:#94a3b8;
                        text-transform:uppercase; letter-spacing:.1em; margin-bottom:12px;">
                {t.get('name', tier_key.title())}
            </div>
            <div style="font-size:2.2rem; font-weight:800; color:var(--primary); line-height:1.1;">
                {t.get('price','—')}<span style="font-size:0.85rem; font-weight:400;
                color:#94a3b8;">{t.get('period','')}</span>
            </div>
            <div style="font-size:0.88rem; color:#64748b; margin:10px 0 18px;
                        line-height:1.55; border-bottom:1px solid #f1f5f9;
                        padding-bottom:16px;">{t.get('description','')}</div>
            {perks_html}
        </div>"""

    return f"""
<section class="section" style="background:#f8fafc;">
    <div class="container">
        <h2 style="text-align:center; margin-bottom:12px; font-size:2.2rem;
                   color:var(--primary);">{title}</h2>
        <p style="text-align:center; color:#64748b; margin-bottom:44px;
                  font-size:1.05rem;">{sub}</p>
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
                    gap:24px; margin-bottom:28px;">{cards}</div>
        <p style="text-align:center; font-size:0.8rem; color:#94a3b8;
                  margin-bottom:32px;">{note}</p>
        <div style="display:flex; gap:14px; justify-content:center; flex-wrap:wrap;">
            <a href="tel:{phone}"
               style="background:var(--primary); color:white; padding:14px 36px;
                      border-radius:50px; font-weight:700; font-size:0.95rem;
                      text-decoration:none; box-shadow:0 6px 20px rgba(0,0,0,0.2);">
                📞 {call_cta}
            </a>
            <a href="https://wa.me/{whatsapp}" target="_blank"
               style="background:#25D366; color:white; padding:14px 36px;
                      border-radius:50px; font-weight:700; font-size:0.95rem;
                      text-decoration:none; box-shadow:0 6px 20px rgba(0,0,0,0.15);">
                💬 {wa_cta}
            </a>
        </div>
    </div>
</section>"""


def _s_rich_testimonials(b_data, design_data, reviews, neighborhoods):
    if not reviews:
        return ""

    target_lang = b_data.get('target_lang', 'en')
    city        = b_data.get('city', '')
    title       = f"ماذا يقول عملاؤنا في {city}" if target_lang == 'ar' else f"What {city} Residents Are Saying"
    verified_lbl = "موثوق" if target_lang == 'ar' else "Verified"

    avatar_palette = [
        ("#B5D4F4","#0C447C"), ("#F4C0D1","#72243E"),
        ("#C0DD97","#27500A"), ("#FAC775","#633806"),
        ("#CECBF6","#3C3489"),
    ]

    cards = ""
    for i, rev in enumerate(reviews[:3]):
        name = escape(str(rev.get('name', 'Customer')))
        txt  = escape(str(rev.get('txt', 'Great service!')))
        loc  = escape(random.choice(neighborhoods) if neighborhoods else city)
        initials = "".join([w[0].upper() for w in name.split()[:2]]) or "C"
        bg, fg   = avatar_palette[i % len(avatar_palette)]
        try:
            stars = min(5, max(1, round(float(str(rev.get('rating', '5')).split('/')[0]))))
        except Exception:
            stars = 5
        star_row = "★" * stars + "☆" * (5 - stars)

        cards += f"""
        <div style="border:1px solid #e2e8f0; border-radius:18px; padding:24px;
                    background:white; box-shadow:0 4px 15px rgba(0,0,0,0.05);
                    display:flex; flex-direction:column;">
            <div style="display:flex; align-items:center; gap:12px; margin-bottom:16px;">
                <div style="width:46px; height:46px; border-radius:50%;
                            background:{bg}; color:{fg}; display:flex;
                            align-items:center; justify-content:center;
                            font-weight:700; font-size:15px; flex-shrink:0;">{initials}</div>
                <div style="flex:1;">
                    <div style="font-weight:700; font-size:0.95rem;">{name}</div>
                    <div style="font-size:0.76rem; color:#64748b;">📍 {loc}</div>
                </div>
                <div style="background:#f0fdf4; color:#16a34a; font-size:0.68rem;
                            padding:3px 10px; border-radius:12px; font-weight:600;
                            white-space:nowrap;">✓ {verified_lbl}</div>
            </div>
            <div style="color:#D97706; font-size:1rem; margin-bottom:12px;
                        letter-spacing:.05em;">{star_row}</div>
            <p style="font-style:italic; color:#64748b; font-size:0.92rem;
                      line-height:1.75; flex-grow:1;">"{txt}"</p>
        </div>"""

    return f"""
<section class="section" style="background:#f8fafc;">
    <div class="container">
        <h2 style="text-align:center; margin-bottom:40px; font-size:2.2rem;
                   color:var(--primary);">{title}</h2>
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
                    gap:20px;">{cards}</div>
    </div>
</section>"""


def _s_comparison_table(b_data, design_data, service_name):
    rows        = design_data.get("comparison_rows", [])
    target_lang = b_data.get('target_lang', 'en')
    name        = b_data.get('name', 'Us')
    primary     = b_data.get('primary', '#1A73E8')

    if target_lang == 'ar':
        title    = f"لماذا نحن أفضل من المنافسين في {service_name}؟"
        us_head  = name
        them_head = "الآخرون"
    else:
        title    = f"Why Choose Us for {service_name}?"
        us_head  = name
        them_head = "Other Companies"

    if not rows:
        return ""

    row_html = ""
    for i, row in enumerate(rows):
        bg = "#f8fafc" if i % 2 == 0 else "white"
        row_html += f"""
        <tr style="background:{bg};">
            <td style="padding:14px 20px; font-weight:600; font-size:0.9rem;
                       color:#0f172a; border-bottom:1px solid #f1f5f9;">
                {row.get('feature','')}
            </td>
            <td style="padding:14px 20px; font-size:0.9rem; color:#0F6E56;
                       font-weight:600; border-bottom:1px solid #f1f5f9; text-align:center;">
                {row.get('us','')}
            </td>
            <td style="padding:14px 20px; font-size:0.9rem; color:#991B1B;
                       border-bottom:1px solid #f1f5f9; text-align:center;">
                {row.get('them','')}
            </td>
        </tr>"""

    return f"""
<section class="section">
    <div class="container" style="max-width:800px;">
        <h2 style="text-align:center; margin-bottom:40px; font-size:2.2rem;
                   color:var(--primary);">{title}</h2>
        <div style="border:1px solid #e2e8f0; border-radius:18px; overflow:hidden;
                    box-shadow:0 8px 30px rgba(0,0,0,0.07);">
            <table style="width:100%; border-collapse:collapse;">
                <thead>
                    <tr style="background:{primary}; color:white;">
                        <th style="padding:16px 20px; text-align:left; font-size:0.9rem;
                                   font-weight:600; width:40%;">Feature</th>
                        <th style="padding:16px 20px; text-align:center; font-size:0.9rem;
                                   font-weight:600; width:30%;">{us_head}</th>
                        <th style="padding:16px 20px; text-align:center; font-size:0.9rem;
                                   font-weight:600; width:30%;">{them_head}</th>
                    </tr>
                </thead>
                <tbody>{row_html}</tbody>
            </table>
        </div>
    </div>
</section>"""


def _s_before_after(b_data, design_data, service_name):
    items       = design_data.get("before_after", [])
    target_lang = b_data.get('target_lang', 'en')
    primary     = b_data.get('primary', '#1A73E8')

    if target_lang == 'ar':
        title    = f"قبل وبعد — {service_name}"
        before_l = "قبل"
        after_l  = "بعد"
        sub      = "نتائج حقيقية من عملائنا"
    else:
        title    = f"Before & After — {service_name}"
        before_l = "Before"
        after_l  = "After"
        sub      = "Real results from real customers"

    if not items:
        return ""

    cards = ""
    for item in items[:3]:
        cards += f"""
        <div style="border:1px solid #e2e8f0; border-radius:18px; overflow:hidden;
                    box-shadow:0 4px 20px rgba(0,0,0,0.07);">
            <div style="display:grid; grid-template-columns:1fr 1fr;">
                <div style="background:#FFF5F5; padding:20px 16px; text-align:center;">
                    <div style="font-size:0.68rem; font-weight:700; color:#991B1B;
                                text-transform:uppercase; letter-spacing:.1em;
                                margin-bottom:8px;">{before_l}</div>
                    <div style="font-size:0.9rem; color:#7A1F1F; line-height:1.5;">
                        {item.get('before','')}
                    </div>
                </div>
                <div style="background:#F0FDF4; padding:20px 16px; text-align:center;
                            border-left:1px solid #e2e8f0;">
                    <div style="font-size:0.68rem; font-weight:700; color:#0F6E56;
                                text-transform:uppercase; letter-spacing:.1em;
                                margin-bottom:8px;">{after_l}</div>
                    <div style="font-size:0.9rem; color:#134E2A; line-height:1.5;">
                        {item.get('after','')}
                    </div>
                </div>
            </div>
            <div style="background:#f8fafc; padding:12px 16px; text-align:center;
                        border-top:1px solid #e2e8f0;">
                <span style="font-size:0.78rem; color:{primary}; font-weight:600;">
                    ✦ {item.get('service','')}
                </span>
            </div>
        </div>"""

    return f"""
<section class="section" style="background:#f8fafc;">
    <div class="container">
        <h2 style="text-align:center; margin-bottom:10px; font-size:2.2rem;
                   color:var(--primary);">{title}</h2>
        <p style="text-align:center; color:#64748b; margin-bottom:40px;">{sub}</p>
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
                    gap:20px;">{cards}</div>
    </div>
</section>"""


def _s_certifications(b_data, design_data):
    certs       = design_data.get("certifications", [])
    target_lang = b_data.get('target_lang', 'en')
    primary     = b_data.get('primary', '#1A73E8')

    title = "شهاداتنا وتراخيصنا" if target_lang == 'ar' else "Our Certifications & Licenses"

    if not certs:
        return ""

    badges = ""
    for cert in certs:
        badges += f"""
        <div style="display:flex; align-items:center; gap:10px; background:white;
                    padding:12px 22px; border-radius:50px; border:1px solid #e2e8f0;
                    box-shadow:0 2px 8px rgba(0,0,0,0.05); white-space:nowrap;">
            <i class="fas fa-certificate" style="color:{primary}; font-size:1rem;"></i>
            <span style="font-size:0.88rem; font-weight:600; color:#0f172a;">{cert}</span>
        </div>"""

    return f"""
<section class="section" style="background:#f8fafc;">
    <div class="container" style="text-align:center;">
        <h2 style="margin-bottom:32px; font-size:2rem; color:var(--primary);">{title}</h2>
        <div style="display:flex; flex-wrap:wrap; gap:14px; justify-content:center;">
            {badges}
        </div>
    </div>
</section>"""


def _s_mid_page_cta(b_data, design_data, service_name):
    text        = design_data.get("mid_cta_text", f"Need {service_name}? Call now!")
    phone       = b_data.get('phone', '')
    whatsapp    = b_data.get('whatsapp', '')
    primary     = b_data.get('primary', '#1A73E8')
    target_lang = b_data.get('target_lang', 'en')
    call_lbl    = "اتصل الآن" if target_lang == 'ar' else "Call Now"
    wa_lbl      = "واتساب" if target_lang == 'ar' else "WhatsApp"

    return f"""
<div style="background:linear-gradient(135deg, {primary} 0%, #0f172a 100%);
            padding:40px 20px; margin:0;">
    <div style="max-width:800px; margin:0 auto; display:flex;
                align-items:center; justify-content:space-between;
                flex-wrap:wrap; gap:20px;">
        <div style="font-size:1.3rem; font-weight:700; color:white;
                    flex:1; min-width:200px;">{text}</div>
        <div style="display:flex; gap:12px; flex-wrap:wrap; flex-shrink:0;">
            <a href="tel:{phone}"
               style="background:white; color:{primary}; padding:13px 28px;
                      border-radius:50px; font-weight:700; text-decoration:none;
                      font-size:0.9rem; white-space:nowrap;">📞 {call_lbl}</a>
            <a href="https://wa.me/{whatsapp}" target="_blank"
               style="background:#25D366; color:white; padding:13px 28px;
                      border-radius:50px; font-weight:700; text-decoration:none;
                      font-size:0.9rem; white-space:nowrap;">💬 {wa_lbl}</a>
        </div>
    </div>
</div>"""


def _s_final_cta(b_data, design_data, service_name):
    phone       = b_data.get('phone', '')
    whatsapp    = b_data.get('whatsapp', '')
    city        = b_data.get('city') or b_data.get('country', '')
    target_lang = b_data.get('target_lang', 'en')
    name        = b_data.get('name', '')

    if target_lang == 'ar':
        eyebrow  = "لا تزال تفكر؟"
        headline = f"احصل على عرض سعر مجاني خلال دقيقتين"
        sub      = "بدون التزام. بدون بريد مزعج. إجابة واضحة فقط."
        call_cta = f"📞 اتصل بنا {phone}"
        wa_cta   = "💬 واتساب"
        trust    = "🔒 بياناتك في أمان تام  •  متاح 24/7  •  بدون التزام"
    else:
        eyebrow  = "Still not sure?"
        headline = f"Get a free {service_name} quote in {city} — 2 minutes"
        sub      = f"No commitment. No spam. {name} gives you a clear answer fast."
        call_cta = f"📞 Call {phone}"
        wa_cta   = "💬 WhatsApp"
        trust    = "🔒 Info never shared  •  24/7 available  •  Zero obligation"

    return f"""
<section style="background:#042C53; padding:80px 20px; margin-top:20px;">
    <div style="max-width:760px; margin:0 auto; text-align:center;">
        <div style="font-size:0.72rem; color:#85B7EB; letter-spacing:.1em;
                    text-transform:uppercase; margin-bottom:12px;">{eyebrow}</div>
        <h2 style="font-size:clamp(1.8rem,4vw,2.6rem); font-weight:800;
                   color:#E6F1FB; margin-bottom:14px;">{headline}</h2>
        <p style="font-size:1.05rem; color:#85B7EB; margin-bottom:38px;">{sub}</p>
        <div style="display:flex; gap:16px; justify-content:center;
                    flex-wrap:wrap; margin-bottom:24px;">
            <a href="tel:{phone}"
               style="background:#5DCAA5; color:#04342C; padding:16px 38px;
                      border-radius:50px; font-weight:800; font-size:1.05rem;
                      text-decoration:none; box-shadow:0 8px 25px rgba(0,0,0,0.35);">
                {call_cta}
            </a>
            <a href="https://wa.me/{whatsapp}" target="_blank"
               style="background:#25D366; color:white; padding:16px 38px;
                      border-radius:50px; font-weight:800; font-size:1.05rem;
                      text-decoration:none; box-shadow:0 8px 25px rgba(0,0,0,0.3);">
                {wa_cta}
            </a>
        </div>
        <div style="font-size:0.78rem; color:#378ADD;">{trust}</div>
    </div>
</section>"""


# ──────────────────────────────────────────────────────────────────────────────
# SECTION DISPATCH MAP
# Maps section key → builder function signature
# ──────────────────────────────────────────────────────────────────────────────
def _dispatch_section(key, b_data, design_data, service_name,
                      sub_services, content_data,
                      # Pass these from the caller
                      build_zigzag_section_fn,
                      build_grid_section_fn,
                      build_infographic_section_fn,
                      build_areas_served_fn,
                      build_faq_section_fn,
                      build_how_it_works_fn):
    """Route a section key to its builder. Returns HTML string."""

    reviews     = content_data.get('reviews', [])
    areas       = content_data.get('areas_served', [])
    faqs        = content_data.get('faqs', [])
    why_feats   = content_data.get('why_choose_us', [])

    if key == "urgency_bar":
        return _s_urgency_bar(b_data, design_data)

    elif key == "trust_numbers":
        return _s_trust_numbers(b_data, design_data)

    elif key == "pain_solution":
        return _s_pain_solution(b_data, design_data, service_name)

    elif key == "zigzag_services":
        user_subs = b_data.get('mode1_custom_subs', [])
        subs_to_use = (user_subs if user_subs else sub_services)[:10]  # max 10

        if not subs_to_use:
            return ""

        total = len(subs_to_use)
        target_lang = b_data.get('target_lang', 'en')
        title = f"حلول {service_name} الاحترافية" if target_lang == 'ar' else f"Professional {service_name} Solutions"

        # Smart split table
        split = {
            1: (1, 0),
            2: (2, 0),
            3: (3, 0),
            4: (1, 3),
            5: (2, 3),
            6: (3, 3),
            7: (4, 3),
            8: (5, 3),
            9: (3, 6),
            10: (4, 6),
        }
        zig_count, grid_count = split.get(total, (4, 6))

        # Grid block ke liye save karo
        b_data['_m1_zig_count']   = zig_count
        b_data['_m1_grid_count']  = grid_count
        b_data['_m1_subs_to_use'] = subs_to_use

        if zig_count == 0:
            return ""

        return build_zigzag_section_fn(
            b_data, subs_to_use[:zig_count], title,
            limit=zig_count, is_child_page=True, current_service=service_name
        )

    elif key == "grid_services":
        # Zigzag block ne save kiya tha
        subs_to_use = b_data.get('_m1_subs_to_use', [])
        zig_count   = b_data.get('_m1_zig_count', 4)
        grid_count  = b_data.get('_m1_grid_count', 6)

        if not subs_to_use or grid_count == 0:
            return ""

        grid_items = subs_to_use[zig_count : zig_count + grid_count]

        if not grid_items:
            return ""

        target_lang = b_data.get('target_lang', 'en')
        title = f"خدمات {service_name} الأخرى" if target_lang == 'ar' else f"More {service_name} Services"

        return build_grid_section_fn(b_data, grid_items, title, limit=len(grid_items))

    elif key == "why_choose":
        return build_infographic_section_fn(why_feats, b_data)

    elif key == "guarantee_seal":
        return _s_guarantee_seal(b_data, design_data, service_name)

    elif key == "pricing_preview":
        return _s_pricing_preview(b_data, design_data, service_name)

    elif key == "rich_testimonials":
        return _s_rich_testimonials(b_data, design_data, reviews, areas)

    elif key == "areas_served":
        return build_areas_served_fn(b_data, areas)

    elif key == "how_it_works":
        return build_how_it_works_fn(b_data, service_name)

    elif key == "faq_section":
        return build_faq_section_fn(faqs, service_name, b_data)

    elif key == "final_cta":
        return _s_final_cta(b_data, design_data, service_name)

    elif key == "mid_page_cta":
        return _s_mid_page_cta(b_data, design_data, service_name)

    elif key == "comparison_table":
        return _s_comparison_table(b_data, design_data, service_name)

    elif key == "before_after":
        return _s_before_after(b_data, design_data, service_name)

    elif key == "certifications":
        return _s_certifications(b_data, design_data)

    elif key == "video_testimonial":
        return _s_video_placeholder(b_data, service_name)

    return ""


def _s_video_placeholder(b_data, service_name):
    """Video testimonial placeholder block."""
    target_lang = b_data.get('target_lang', 'en')
    primary     = b_data.get('primary', '#1A73E8')
    title = f"شاهد عملاؤنا يتحدثون" if target_lang == 'ar' else f"Hear From Our Customers"
    sub   = f"شاهد كيف حسّنا {service_name}" if target_lang == 'ar' else f"Watch how we solved {service_name} for real customers"

    return f"""
<section class="section">
    <div class="container" style="max-width:720px;">
        <h2 style="text-align:center; margin-bottom:10px; font-size:2.2rem;
                   color:var(--primary);">{title}</h2>
        <p style="text-align:center; color:#64748b; margin-bottom:36px;">{sub}</p>
        <div style="border:1px solid #e2e8f0; border-radius:18px; overflow:hidden;
                    box-shadow:0 8px 30px rgba(0,0,0,0.08); aspect-ratio:16/9;
                    background:#0f172a; display:flex; align-items:center;
                    justify-content:center; flex-direction:column; gap:16px; padding:40px;">
            <div style="width:72px; height:72px; border-radius:50%; background:{primary};
                        display:flex; align-items:center; justify-content:center;
                        cursor:pointer; box-shadow:0 0 0 16px rgba(255,255,255,0.08);">
                <i class="fas fa-play" style="color:white; font-size:1.6rem; margin-left:4px;"></i>
            </div>
            <div style="color:#94a3b8; font-size:0.88rem;">
                {'انقر لمشاهدة قصص عملائنا' if target_lang == 'ar' else 'Customer success stories'}
            </div>
        </div>
    </div>
</section>"""


def _build_how_it_works_universal(b_data, service_name):
    """
    Builds 'How It Works' using DESIGN_SPEC how_it_works steps from Claude.
    Falls back to generic 4 steps if missing.
    """
    spec        = b_data.get('design_spec', {})
    steps       = spec.get('how_it_works', [])
    target_lang = b_data.get('target_lang', 'en')
    primary     = b_data.get('primary', '#1A73E8')
    phone       = b_data.get('phone', '')
    city        = b_data.get('city') or b_data.get('country', '')

    title = "كيف نعمل؟" if target_lang == 'ar' else "How It Works"

    if not steps or len(steps) < 4:
        # Generic fallback
        if target_lang == 'ar':
            steps = [
                {"emoji": "📞", "title": "اتصل أو احجز", "desc": f"تواصل معنا 24/7. نرد فوراً."},
                {"emoji": "🔍", "title": "تشخيص مجاني", "desc": "نفحص المشكلة قبل تقديم أي سعر."},
                {"emoji": "💰", "title": "سعر واضح مسبقاً", "desc": "سعر ثابت بدون مفاجآت."},
                {"emoji": "✅", "title": "عمل مضمون", "desc": "ننجز العمل من أول مرة مع ضمان."},
            ]
        else:
            steps = [
                {"emoji": "📞", "title": "Call or Book", "desc": f"Reach us 24/7 for any {service_name} need in {city}."},
                {"emoji": "🔍", "title": "Free Diagnosis", "desc": "We inspect the issue at no charge before quoting."},
                {"emoji": "💰", "title": "Upfront Quote", "desc": "Fixed price — you approve before we start."},
                {"emoji": "✅", "title": "Guaranteed Work", "desc": "We complete the job right the first time."},
            ]

    cards = ""
    for i, step in enumerate(steps[:4]):
        cards += f"""
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
        </div>"""

    return f"""
<section class="section" style="background:#f8fafc;">
    <div class="container">
        <h2 style="text-align:center; margin-bottom:50px; font-size:2.2rem;
                   color:var(--primary);">{title}</h2>
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
                    gap:24px;">{cards}</div>
    </div>
</section>"""


# ──────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────
def build_mode1_landing_page(b_data, service_name, sub_services, content_data,
                              call_claude_json=None,
                              build_zigzag_section=None,
                              build_grid_section=None,
                              build_infographic_section=None,
                              build_areas_served=None,
                              build_faq_section=None):
    """
    MAIN FUNCTION — call this from assemble_page_content() for Mode 1 child pages.

    Parameters
    ----------
    b_data               : dict — full business data dict
    service_name         : str — main service (e.g. "Handyman Services")
    sub_services         : list — list of sub-service strings
    content_data         : dict — AI-generated page content (reviews, faqs, etc.)
    call_claude_json     : callable — your existing call_claude_json function
    build_*              : callables — your existing builder functions from main generator

    Returns
    -------
    str — complete HTML for the Mode 1 single-service landing page
    """

    _force_disable_internal_links()

    print(f"\n   🎨 Consulting Claude on landing page design for: {service_name}...")
    design_data = consult_claude_on_page_design(
        b_data, service_name, sub_services, call_claude_json
    )

    # urgency_bar hata do — header mein already hai
    section_order = design_data.get("section_order", [
        "trust_numbers", "pain_solution",
        "zigzag_services", "grid_services",
        "why_choose", "guarantee_seal", "pricing_preview",
        "rich_testimonials", "areas_served", "how_it_works",
        "faq_section", "final_cta"
    ])

    # Claude ne urgency_bar select kiya ho toh bhi hata do
    section_order = [s for s in section_order if s != "urgency_bar"]

    # trust_numbers hamesha pehle aaye
    if "trust_numbers" in section_order:
        section_order.remove("trust_numbers")

    # Fixed start and end — SEEDED (every business gets its own stable layout)
    _seed = b_data.get('site_seed', 0)
    _openers = [
        ["trust_numbers", "pain_solution", "zigzag_services", "grid_services"],
        ["trust_numbers", "zigzag_services", "pain_solution", "grid_services"],
    ]
    fixed_start = _openers[_seed % 2]
    fixed_end   = ["areas_served", "faq_section", "final_cta"]

    # Middle shuffle — seeded: same business = same order on every rebuild
    middle = [s for s in section_order if s not in fixed_start and s not in fixed_end]
    random.Random(_seed + 31).shuffle(middle)
    section_order = fixed_start + middle + fixed_end

    print(f"   🔀 Section order: {' → '.join(section_order)}")
    print(f"   ✅ Total sections: {len(section_order)}")

   # ── ANCHOR MAP: header menu in IDs pe scroll karta hai ──
    ANCHOR_MAP = {
        "zigzag_services":   "services",
        "pricing_preview":   "pricing",
        "rich_testimonials": "reviews",
        "faq_section":       "faq",
        "final_cta":         "contact",
    }
    present_anchors = []

    html = ""
    for section_key in section_order:
        try:
            sec_html = _dispatch_section(
                key                          = section_key,
                b_data                       = b_data,
                design_data                  = design_data,
                service_name                 = service_name,
                sub_services                 = sub_services,
                content_data                 = content_data,
                build_zigzag_section_fn      = build_zigzag_section or (lambda *a, **k: ""),
                build_grid_section_fn        = build_grid_section   or (lambda *a, **k: ""),
                build_infographic_section_fn = build_infographic_section or (lambda *a, **k: ""),
                build_areas_served_fn        = build_areas_served   or (lambda *a, **k: ""),
                build_faq_section_fn         = build_faq_section    or (lambda *a, **k: ""),
                build_how_it_works_fn        = _build_how_it_works_universal,
            )

            # Anchor span inject karo (sticky header ke liye scroll-margin)
            anchor = ANCHOR_MAP.get(section_key)
            if anchor and sec_html and anchor not in present_anchors:
                sec_html = (f'<span id="{anchor}" '
                            f'style="display:block; height:0; scroll-margin-top:130px;"></span>'
                            + sec_html)
                present_anchors.append(anchor)

            html += sec_html
        except Exception as e:
            print(f"   ⚠️ Section [{section_key}] failed: {e}")
            continue

    # 💎 Header isse padh kar dynamic menu banata hai (zero 404 guarantee)
    b_data['_m1_anchors'] = present_anchors
    print(f"   🔗 Menu anchors: {present_anchors}")

    return html

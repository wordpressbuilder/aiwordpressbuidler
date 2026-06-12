"""
IMAGE LOCALIZER — Cloudinary → Local /images/ folder
=====================================================
Site generate hone ke BAAD chalta hai:
1. Saari HTML files scan karta hai, har Cloudinary URL dhoondta hai
2. Image download karta hai → WebP (q=82) mein convert — quality same, size 30-50% kam
3. SEO filename deta hai (alt text se: "fridge-repair-dubai.webp")
4. EXIF metadata embed karta hai (description, artist, copyright)
5. HTML mein saare URLs ko /images/... se replace karta hai (schema JSON samet)
6. image-sitemap.xml banata hai aur robots.txt mein register karta hai

Result: Cloudinary bandwidth = ZERO on live sites. Har client site independent.

Requirements: requests (already hai) + Pillow  →  requirements.txt mein "Pillow" add karo
Usage (main.py mein):  localize_images(output_folder, b_data, Config.SITE_URL)
"""

import os
import re
import time
from io import BytesIO

import requests

try:
    from PIL import Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

# Cloudinary URL matcher — src, href, background-image url(), schema JSON sab pakdega
_URL_RE = re.compile(r'https?://res\.cloudinary\.com/[^\s"\'<>)\\]+')
_IMG_TAG_RE = re.compile(r'<img[^>]+>', re.IGNORECASE)
_SRC_RE = re.compile(r'src=["\'](https?://res\.cloudinary\.com/[^"\']+)["\']', re.IGNORECASE)
_ALT_RE = re.compile(r'alt=["\']([^"\']*)["\']', re.IGNORECASE)


def _slug(text, max_len=60):
    text = re.sub(r'[^\w\s-]', '', (text or '').lower()).strip()
    return re.sub(r'[-\s]+', '-', text)[:max_len].strip('-')


def _ascii(text):
    """EXIF ASCII-safe banata hai (Arabic chars EXIF tags tod sakte hain)."""
    try:
        return str(text).encode('ascii', 'ignore').decode().strip() or "image"
    except Exception:
        return "image"


def _collect_alt_map(html_files):
    """Har Cloudinary src URL ke liye uska alt text nikalo (SEO filename ke liye)."""
    alt_map = {}
    for fpath in html_files:
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            continue
        for tag in _IMG_TAG_RE.findall(content):
            src_m = _SRC_RE.search(tag)
            if not src_m:
                continue
            url = src_m.group(1)
            if url not in alt_map:
                alt_m = _ALT_RE.search(tag)
                if alt_m and alt_m.group(1).strip():
                    alt_map[url] = alt_m.group(1).strip()
    return alt_map


def _make_filename(url, alt_map, b_data, used_names, counter):
    """SEO-rich filename: alt text → 'same-day-fridge-repair-dubai.webp'"""
    industry = _slug(b_data.get('industry', 'service'))
    city = _slug(b_data.get('city') or b_data.get('country', ''))

    if "/logos/" in url:
        base = f"{_slug(b_data.get('name', 'logo'))}-logo"
    else:
        alt = alt_map.get(url, "")
        base = _slug(alt) if alt else f"{industry}-{city}-{counter}"
        # City filename mein ho to local-SEO ke liye behtar
        if city and city not in base:
            base = f"{base}-{city}"[:70].strip('-')

    fname = f"{base}.webp"
    n = 2
    while fname in used_names:
        fname = f"{base}-{n}.webp"
        n += 1
    used_names.add(fname)
    return fname


def _download_and_convert(url, out_path, b_data, alt_map, quality=82):
    """Download → WebP convert → EXIF metadata embed. Returns saved KB or None."""
    try:
        resp = requests.get(url, timeout=40)
        if resp.status_code != 200 or len(resp.content) < 500:
            return None

        if not _PIL_OK:
            # Pillow nahi → original bytes hi save kar do (format change ke baghair)
            ext = ".png" if url.lower().endswith(".png") else ".jpg"
            out_path = out_path.rsplit(".", 1)[0] + ext
            with open(out_path, 'wb') as f:
                f.write(resp.content)
            return out_path, len(resp.content) // 1024

        img = Image.open(BytesIO(resp.content))

        # Transparency handle: logo PNG → white bg flatten (WebP lossy ke liye)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Width cap: logo 480px, baqi 1280px (upscale kabhi nahi hota)
        max_w = 480 if "/logos/" in url else 1280
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)

        # ── EXIF METADATA (SEO): description + artist + copyright ──
        exif_bytes = None
        try:
            name = b_data.get('name', '')
            city = b_data.get('city') or b_data.get('country', '')
            industry = b_data.get('industry', 'service')
            alt = alt_map.get(url, "")
            desc = alt if alt else f"{industry} in {city}"

            exif = Image.Exif()
            exif[0x010E] = _ascii(f"{desc} - {name} {city}")          # ImageDescription
            exif[0x013B] = _ascii(name)                                 # Artist
            exif[0x8298] = _ascii(f"(c) {name}, {city}")               # Copyright
            exif[0x0131] = _ascii(f"{name} - {industry} {city}")      # Software/source
            exif_bytes = exif.tobytes()
        except Exception:
            exif_bytes = None

        save_kwargs = {"format": "WEBP", "quality": quality, "method": 6}
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes

        img.save(out_path, **save_kwargs)
        return out_path, os.path.getsize(out_path) // 1024

    except Exception as e:
        print(f"      ⚠️ Skip ({str(e)[:60]}): {url[:70]}")
        return None


def _write_image_sitemap(output_folder, site_url, page_images):
    """image-sitemap.xml — Google Images ke liye strong white-hat signal."""
    site_url = (site_url or "").rstrip('/')
    if not site_url.startswith('http') or not page_images:
        return

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
    xml += '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'

    for rel_page, images in sorted(page_images.items()):
        clean = rel_page.replace('\\', '/')
        if clean.endswith('index.html'):
            clean = clean[:-10]
        elif clean.endswith('.html'):
            clean = clean[:-5]
        page_url = f"{site_url}/{clean}".rstrip('/')
        if not clean:
            page_url = f"{site_url}/"

        xml += f"  <url>\n    <loc>{page_url}</loc>\n"
        for img_path in sorted(set(images))[:50]:
            title = img_path.rsplit('/', 1)[-1].rsplit('.', 1)[0].replace('-', ' ').title()
            xml += f"    <image:image>\n"
            xml += f"      <image:loc>{site_url}{img_path}</image:loc>\n"
            xml += f"      <image:title>{title}</image:title>\n"
            xml += f"    </image:image>\n"
        xml += "  </url>\n"

    xml += "</urlset>\n"

    with open(os.path.join(output_folder, 'image-sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write(xml)

    # robots.txt mein register karo
    robots_path = os.path.join(output_folder, 'robots.txt')
    try:
        sitemap_line = f"Sitemap: {site_url}/image-sitemap.xml"
        existing = ""
        if os.path.exists(robots_path):
            with open(robots_path, 'r', encoding='utf-8') as f:
                existing = f.read()
        if sitemap_line not in existing:
            with open(robots_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{sitemap_line}\n")
    except Exception:
        pass

    print(f"  ✅ image-sitemap.xml generated ({len(page_images)} pages)")


def localize_images(output_folder, b_data, site_url="", quality=82):
    """MAIN ENTRY: saari Cloudinary images ko local /images/ mein le aao."""
    print("\n📦 LOCALIZING IMAGES (Cloudinary → /images/ WebP)...")
    t0 = time.time()

    images_dir = os.path.join(output_folder, 'images')
    os.makedirs(images_dir, exist_ok=True)

    # 1. Saari HTML files dhoondo
    html_files = []
    for root, _, files in os.walk(output_folder):
        for fn in files:
            if fn.endswith('.html'):
                html_files.append(os.path.join(root, fn))

    if not html_files:
        print("   ⚠️ No HTML files found.")
        return

    # 2. Alt text map banao (SEO filenames ke liye)
    alt_map = _collect_alt_map(html_files)

    # 3. Saare unique Cloudinary URLs collect karo
    all_urls = set()
    for fpath in html_files:
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                all_urls.update(_URL_RE.findall(f.read()))
        except Exception:
            continue

    if not all_urls:
        print("   ℹ️ No Cloudinary URLs found — nothing to localize.")
        return

    print(f"   🔍 Found {len(all_urls)} unique Cloudinary images across {len(html_files)} pages")

    # 4. Download + convert + map build karo
    url_to_local = {}
    used_names = set()
    total_kb = 0
    for i, url in enumerate(sorted(all_urls), 1):
        fname = _make_filename(url, alt_map, b_data, used_names, i)
        out_path = os.path.join(images_dir, fname)
        result = _download_and_convert(url, out_path, b_data, alt_map, quality)
        if result:
            saved_path, kb = result
            final_name = os.path.basename(saved_path)
            url_to_local[url] = f"/images/{final_name}"
            total_kb += kb
            print(f"      ✅ [{i}/{len(all_urls)}] {final_name} ({kb} KB)")
        # Fail hone par URL replace NAHI hoga → Cloudinary fallback (site kabhi nahi tooti)

    # 5. HTML files mein URLs replace karo + image sitemap data collect karo
    page_images = {}
    replaced_count = 0
    for fpath in html_files:
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            changed = False
            for url, local in url_to_local.items():
                if url in content:
                    content = content.replace(url, local)
                    changed = True
                    replaced_count += 1
                    rel = os.path.relpath(fpath, output_folder)
                    page_images.setdefault(rel, []).append(local)
            if changed:
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(content)
        except Exception as e:
            print(f"      ⚠️ Rewrite failed for {fpath}: {e}")

    # 6. Image sitemap + robots
    _write_image_sitemap(output_folder, site_url, page_images)

    elapsed = int(time.time() - t0)
    print(f"  ✅ Localized {len(url_to_local)}/{len(all_urls)} images | "
          f"{replaced_count} replacements | total {total_kb//1024}.{(total_kb%1024)//103} MB | {elapsed}s")
    print(f"  🚀 Live site ab Cloudinary se ZERO bandwidth use karegi.")

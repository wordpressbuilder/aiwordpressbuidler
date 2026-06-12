"""
LINK CHECKER — Generated static site mein 404 links dhoondta hai
================================================================
Usage:
    python check_links.py static_website_20260612_153000

Netlify clean URLs ko samajhta hai (/services/abc → services/abc.html).
Agar koi broken link mila to RED mein report karega aur exit code 1 dega
(GitHub Actions mein fail ho jayega — deploy se pehle pakda jayega).
"""

import os
import re
import sys

SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#",
                 "javascript:", "data:", "//")

HREF_RE = re.compile(r'(?:href|src)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def resolve(folder: str, link: str) -> bool:
    """Check karo ke link kisi real file pe resolve hota hai (Netlify clean URL aware)."""
    # Query string / hash hatao
    link = link.split("?")[0].split("#")[0].strip()
    if not link:
        return True  # pure "#anchor" — same page, OK

    path = link.lstrip("/")

    candidates = []
    if path.endswith("/") or path == "":
        candidates.append(os.path.join(folder, path, "index.html"))
    elif "." in os.path.basename(path):
        candidates.append(os.path.join(folder, path))          # .html, .css, .js, .xml
    else:
        candidates.append(os.path.join(folder, path + ".html"))            # clean URL
        candidates.append(os.path.join(folder, path, "index.html"))        # folder index

    return any(os.path.isfile(c) for c in candidates)


def main():
    if len(sys.argv) < 2:
        # Latest static_website_* folder auto-detect
        dirs = sorted([d for d in os.listdir(".") if d.startswith("static_website")])
        if not dirs:
            print("❌ Koi static_website_* folder nahi mila. Usage: python check_links.py <folder>")
            sys.exit(1)
        folder = dirs[-1]
        print(f"ℹ️  Auto-detected folder: {folder}")
    else:
        folder = sys.argv[1]

    broken = []
    total_links = 0
    pages_scanned = 0

    for root, _, files in os.walk(folder):
        for fname in files:
            if not fname.endswith(".html"):
                continue
            pages_scanned += 1
            fpath = os.path.join(root, fname)
            rel_page = os.path.relpath(fpath, folder)

            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            for link in HREF_RE.findall(content):
                link = link.strip()
                if link.startswith(SKIP_PREFIXES) or not link:
                    continue
                # Sirf root-relative internal links check karo
                if not link.startswith("/"):
                    continue
                total_links += 1
                if not resolve(folder, link):
                    broken.append((rel_page, link))

    print("\n" + "=" * 60)
    print(f" 📄 Pages scanned:   {pages_scanned}")
    print(f" 🔗 Internal links:  {total_links}")
    print("=" * 60)

    if broken:
        print(f"\n❌ {len(broken)} BROKEN LINKS MILE:\n")
        seen = set()
        for page, link in broken:
            key = (page, link)
            if key in seen:
                continue
            seen.add(key)
            print(f"   [{page}]  →  {link}")
        sys.exit(1)
    else:
        print("\n✅ ZERO 404 — saare internal links sahi hain. Deploy ready! 🚀")
        sys.exit(0)


if __name__ == "__main__":
    main()

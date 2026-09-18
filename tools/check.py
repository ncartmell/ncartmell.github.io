#!/usr/bin/env python3
"""Validate the built site. Run locally, and in CI on every push.

Catches the things that break silently on a static site: an internal link that
points at nothing, a post that exists but was never listed in the index, malformed
JSON-LD, and a feed or sitemap that will not parse.

The "did you run sync.py" check is not here — CI does that by running the script
and failing if it produces a diff.
"""
import json, pathlib, re, sys
import xml.dom.minidom as minidom
from urllib.parse import unquote

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP = {"og-card.html"}
fails = []


def fail(msg):
    fails.append(msg)


def pages():
    return [p for p in sorted(ROOT.rglob("*.html"))
            if ".git" not in p.parts and p.name not in SKIP]


def check_links():
    for p in pages():
        for href in re.findall(r'(?:href|src)="([^"]+)"', p.read_text()):
            if href.startswith(("http://", "https://", "mailto:", "data:", "#")):
                continue
            rel = unquote(href).split("#")[0]
            target = (ROOT / rel.lstrip("/")) if href.startswith("/") else (p.parent / rel)
            target = target.resolve()
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                fail(f"broken link: {p.relative_to(ROOT)} -> {href}")


def check_posts_listed():
    index = (ROOT / "writing/index.html").read_text()
    listed = set(re.findall(r'<a href="([^"]+\.html)">', index))
    on_disk = {p.name for p in (ROOT / "writing").glob("*.html")} - {"index.html", "template.html"}
    for name in sorted(on_disk - listed):
        fail(f"post not listed in writing/index.html: {name}")
    for name in sorted(listed - on_disk):
        fail(f"index lists a post that does not exist: {name}")


def check_json_ld():
    for p in pages():
        for blob in re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                               p.read_text(), re.S):
            try:
                json.loads(blob)
            except ValueError as e:
                fail(f"invalid JSON-LD: {p.relative_to(ROOT)}: {e}")


def check_landmarks():
    for p in pages():
        t = p.read_text()
        if p.name == "template.html":
            continue
        for needle, what in [('id="main"', "<main id=main>"), ("<footer", "<footer>"),
                             ('class="skip', "skip link")]:
            if needle not in t:
                fail(f"missing {what}: {p.relative_to(ROOT)}")


def check_xml():
    for name in ("feed.xml", "sitemap.xml"):
        try:
            minidom.parse(str(ROOT / name))
        except Exception as e:
            fail(f"{name} does not parse: {e}")


for fn in (check_links, check_posts_listed, check_json_ld, check_landmarks, check_xml):
    fn()

if fails:
    print(f"{len(fails)} problem(s):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print(f"ok — {len(pages())} pages, no problems")

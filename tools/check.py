#!/usr/bin/env python3
"""Validate the built site. Run locally, and in CI on every push.

Catches the things that break silently on a static site: an internal link that
points at nothing, a post that exists but was never listed in the index, malformed
JSON-LD, and a feed or sitemap that will not parse.

The "did you run sync.py" check is not here — CI does that by running the script
and failing if it produces a diff.
"""
import json, pathlib, re, sys
import cvstamp
import xml.dom.minidom as minidom
from urllib.parse import unquote

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
ROOT = pathlib.Path(__file__).resolve().parent.parent
# og-card.html and tools/*.html are render templates, not pages of the site
SKIP = {"og-card.html"}
fails = []


def fail(msg):
    fails.append(msg)


def pages():
    return [p for p in sorted(ROOT.rglob("*.html"))
            if ".git" not in p.parts and "tools" not in p.parts and p.name not in SKIP]


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


def check_og_cards():
    """Every post's og:image must exist. The cards need Chrome to build, so CI
    cannot regenerate them — it can only refuse to ship a post pointing at one
    that is missing."""
    pages = [p for p in sorted((ROOT / "writing").glob("*.html"))
             if p.name not in ("index.html", "template.html")]
    pages += [ROOT / s / "index.html" for s in ("writing", "projects", "outside")]
    for post in pages:
        m = re.search(r'<meta property="og:image" content="[^"]*?([^/"]+\.png)"', post.read_text())
        if not m:
            fail(f"no og:image: {post.relative_to(ROOT)}")
        elif not (ROOT / "og" / m.group(1)).exists():
            fail(f"og:image missing from disk: {post.relative_to(ROOT)} -> og/{m.group(1)}")


def check_feed_categories():
    """An empty <category> means the index parser silently stopped matching the
    heading markup — which is exactly what adding the group icons did."""
    feed = (ROOT / "feed.xml").read_text()
    groups = {re.sub(r"<[^>]+>", "", m).strip() for m in
              re.findall(r'<span class="group-name">(.*?)</span>',
                         (ROOT / "writing/index.html").read_text(), re.S)}
    topics = {l.strip() for l in (ROOT / "tools/topics.txt").read_text().splitlines() if l.strip()}
    known = groups | topics
    for term in re.findall(r'<category term="([^"]*)"/>', feed):
        if not term.strip():
            fail("feed.xml has an empty <category term>")
        elif term not in known:
            fail(f"feed category is neither a group nor a topic: {term!r}")


def check_topics():
    """Every post declares topics, and only from the controlled list in
    tools/topics.txt. Without the list, "Data modelling" and "Data Modelling"
    quietly become two topics."""
    vocab = {l.strip() for l in (ROOT / "tools/topics.txt").read_text().splitlines() if l.strip()}
    for post in sorted((ROOT / "writing").glob("*.html")):
        if post.name == "index.html":
            continue
        m = re.search(r'<meta name="topics" content="([^"]*)"', post.read_text())
        if not m or not m.group(1).strip():
            fail(f"no topics declared: {post.relative_to(ROOT)}")
            continue
        for topic in (x.strip() for x in m.group(1).split(",")):
            if topic not in vocab:
                fail(f"topic not in tools/topics.txt: {post.relative_to(ROOT)} -> {topic!r}")


def check_cv_stamp():
    """cv.pdf is rendered from index.html and drifts silently. cv.stamp holds a
    fingerprint of only the parts of the page the print stylesheet keeps, so
    this fires when the printed CV is genuinely out of date and stays quiet for
    head-only or .no-print edits."""
    stamp = ROOT / "cv.stamp"
    if not stamp.exists():
        fail("cv.stamp missing — run: python3 tools/cvstamp.py --write")
        return
    if stamp.read_text().strip() != cvstamp.fingerprint():
        fail("cv.pdf is stale: index.html's printed content changed. "
             "Regenerate it (see BUILD.md), then: python3 tools/cvstamp.py --write")


def check_seealso_titles():
    """The 'Also in this series' blocks are hand-written. Their links resolve, but
    nothing notices when a post is retitled and its neighbours go on using the
    old name."""
    titles = {}
    for post in (ROOT / "writing").glob("*.html"):
        m = re.search(r"<h1>(.*?)</h1>", post.read_text(), re.S)
        if m:
            titles[post.name] = re.sub(r"\s+", " ", m.group(1)).strip()
    for post in sorted((ROOT / "writing").glob("*.html")):
        for blob in re.findall(r'<div class="seealso">(.*?)</div>', post.read_text(), re.S):
            for href, text in re.findall(r'<a href="([^"]+\.html)">(.*?)</a>', blob, re.S):
                want = titles.get(href)
                got = re.sub(r"\s+", " ", text).strip()
                if want and got != want:
                    fail(f"seealso text is stale: {post.relative_to(ROOT)} -> {href}: "
                         f"says {got!r}, title is {want!r}")


def check_xml():
    for name in ("feed.xml", "sitemap.xml"):
        try:
            minidom.parse(str(ROOT / name))
        except Exception as e:
            fail(f"{name} does not parse: {e}")


for fn in (check_links, check_posts_listed, check_json_ld, check_landmarks,
           check_og_cards, check_feed_categories, check_topics,
           check_cv_stamp, check_seealso_titles, check_xml):
    fn()

if fails:
    print(f"{len(fails)} problem(s):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print(f"ok — {len(pages())} pages, no problems")

#!/usr/bin/env python3
"""Regenerate everything about /writing/ that is derived from the index.

`writing/index.html` is the single source of truth for which posts exist and what
order they are in. This script reads that order and rewrites:

  * feed.xml                    — the Atom feed
  * the <!-- sync:head --> block in each post   (theme-color, feed link, JSON-LD)
  * the <!-- sync:nav --> block in each post    (previous / next)

It is idempotent: run it after adding a post, or after editing a title or
description, and commit the result. It never touches hand-written markup.
"""
import datetime, html, json, pathlib, re, sys

SITE = "https://ncartmell.co.uk"
ROOT = pathlib.Path(__file__).resolve().parent.parent
WRITING = ROOT / "writing"

# All 21 posts went up on the same day. Rather than invent dates that never happened,
# the feed spreads them a minute apart across that real date, in index order, so
# readers get the site's own sequence instead of an arbitrary one.
BASE = datetime.datetime(2026, 9, 17, 12, 0, 0)
TZ = "+01:00"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def read_order():
    t = (WRITING / "index.html").read_text()
    order = []
    for sec in re.findall(r'<section class="collection">(.*?)</section>', t, re.S):
        group = re.search(r'<h2 class="group">(.*?)<span', sec, re.S).group(1).strip()
        for href in re.findall(r'<a href="([^"]+\.html)">', sec):
            order.append((group, href))
    return order


def load(href, group, i):
    t = (WRITING / href).read_text()

    def m(pat):
        r = re.search(pat, t)
        return html.unescape(r.group(1)) if r else None

    post = dict(
        href=href, group=group, text=t,
        url=m(r'<link rel="canonical" href="([^"]+)"'),
        title=m(r"<h1>(.*?)</h1>"),
        summary=m(r'<meta name="description" content="([^"]*)"'),
        date=m(r'<time datetime="([^"]+)"'),
        stamp=(BASE - datetime.timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%S") + TZ,
    )
    missing = [k for k in ("url", "title", "summary", "date") if not post[k]]
    if missing:
        sys.exit(f"{href}: missing {', '.join(missing)}")
    return post


def block(tag, body, indent=""):
    return f"{indent}<!-- sync:{tag} -->\n{body}\n{indent}<!-- /sync:{tag} -->"


def replace_block(text, tag, new, anchor):
    """Swap an existing sync block, or insert one before `anchor` the first time."""
    pat = re.compile(rf"[ \t]*<!-- sync:{tag} -->.*?<!-- /sync:{tag} -->\n?", re.S)
    if pat.search(text):
        return pat.sub(new + "\n", text, count=1)
    assert anchor in text, f"anchor {anchor!r} not found"
    return text.replace(anchor, new + "\n" + anchor, 1)


def head_block(p):
    # json.dumps, not string formatting: three of these titles contain apostrophes.
    ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": p["title"],
        "description": p["summary"],
        "datePublished": p["date"],
        "dateModified": p["date"],
        "url": p["url"],
        "mainEntityOfPage": p["url"],
        "image": f"{SITE}/og.png",
        "inLanguage": "en-GB",
        "author": {"@type": "Person", "name": "Nathan Cartmell", "url": f"{SITE}/"},
        "publisher": {"@type": "Person", "name": "Nathan Cartmell"},
        "isPartOf": {"@type": "Blog", "name": "Nathan Cartmell \u2014 Writing",
                     "url": f"{SITE}/writing/"},
    }, indent=2, ensure_ascii=False).replace("</", "<\\/")
    body = (
        '<meta name="theme-color" content="#fbfbfa" media="(prefers-color-scheme: light)">\n'
        '<meta name="theme-color" content="#101215" media="(prefers-color-scheme: dark)">\n'
        '<link rel="alternate" type="application/atom+xml" title="Nathan Cartmell \u2014 Writing" href="/feed.xml">\n'
        '<script type="application/ld+json">\n' + ld + "\n</script>"
    )
    return block("head", body)


def nav_block(prev, nxt):
    parts = []
    if prev:
        parts.append(f'    <a class="prev" href="{prev["href"]}">'
                     f'<span class="dir">Previous</span>{esc(prev["title"])}</a>')
    if nxt:
        parts.append(f'    <a class="next" href="{nxt["href"]}">'
                     f'<span class="dir">Next</span>{esc(nxt["title"])}</a>')
    return block("nav", '  <nav class="postnav">\n' + "\n".join(parts) + "\n  </nav>", "  ")


def write_feed(posts):
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           '<feed xmlns="http://www.w3.org/2005/Atom">',
           "  <title>Nathan Cartmell — Writing</title>",
           "  <subtitle>Notes on systems, telecoms infrastructure and problems worth "
           "explaining.</subtitle>",
           f'  <link href="{SITE}/feed.xml" rel="self" type="application/atom+xml"/>',
           f'  <link href="{SITE}/writing/" rel="alternate" type="text/html"/>',
           f"  <id>{SITE}/writing/</id>",
           f"  <updated>{posts[0]['stamp']}</updated>",
           "  <author>", "    <name>Nathan Cartmell</name>", f"    <uri>{SITE}/</uri>",
           "  </author>",
           "  <rights>© 2026 Nathan Cartmell</rights>", ""]
    for p in posts:
        out += ["  <entry>",
                f"    <title>{esc(p['title'])}</title>",
                f'    <link href="{p["url"]}" rel="alternate" type="text/html"/>',
                f"    <id>{p['url']}</id>",
                f"    <published>{p['stamp']}</published>",
                f"    <updated>{p['stamp']}</updated>",
                f'    <category term="{esc(p["group"])}"/>',
                f"    <summary>{esc(p['summary'])}</summary>",
                "  </entry>", ""]
    out += ["</feed>", ""]
    (ROOT / "feed.xml").write_text("\n".join(out))


def main():
    order = read_order()
    posts = [load(href, group, i) for i, (group, href) in enumerate(order)]

    for i, p in enumerate(posts):
        t = p["text"]
        t = replace_block(t, "head", head_block(p), '<link rel="stylesheet" href="../style.css">')
        t = replace_block(t, "nav",
                          nav_block(posts[i - 1] if i else None,
                                    posts[i + 1] if i + 1 < len(posts) else None),
                          "</div>\n</body>")
        (WRITING / p["href"]).write_text(t)

    write_feed(posts)
    print(f"synced {len(posts)} posts + feed.xml")


if __name__ == "__main__":
    main()

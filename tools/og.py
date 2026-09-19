#!/usr/bin/env python3
"""Render a 1200x630 Open Graph card for each post.

Needs headless Chrome, so this is not part of sync.py and does not run in CI.
Run it when a post is added or retitled; check.py verifies the cards exist.

The background is near-flat on purpose: the radial wash used by og.png dithers,
which tripled the PNG size for a card that is otherwise large flat areas of one
colour. 36KB each instead of 122KB, and the text stays lossless.
"""
import html, pathlib, re, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sync  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT = sync.ROOT / "og"


def size_for(title):
    n = len(title)
    return 82 if n <= 28 else 72 if n <= 40 else 64


def main():
    if not pathlib.Path(CHROME).exists():
        sys.exit(f"Chrome not found at {CHROME}")
    OUT.mkdir(exist_ok=True)
    tpl = (HERE / "og-post.html").read_text()
    tmp = HERE / ".og-tmp.html"

    order = sync.read_order()
    for group, href in order:
        t = (sync.WRITING / href).read_text()
        title = html.unescape(re.search(r"<h1>(.*?)</h1>", t).group(1))
        slug = href[:-5]
        page = (tpl.replace("__TITLE__", html.escape(title))
                   .replace("__GROUP__", html.escape(group))
                   .replace("__SIZE__", str(size_for(title))))
        tmp.write_text(page)
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--window-size=1200,630",
                        f"--screenshot={OUT / (slug + '.png')}", f"file://{tmp}"],
                       capture_output=True)
        print(f"  og/{slug}.png  ({(OUT / (slug + '.png')).stat().st_size // 1024}KB)  {title}")
    tmp.unlink(missing_ok=True)
    total = sum(p.stat().st_size for p in OUT.glob("*.png"))
    print(f"{len(order)} cards, {total // 1024}KB total")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Add a wildlife photo to /outside/, or take one off again.

  python3 tools/wildlife.py PHOTO "Red fox" [--latin "Vulpes vulpes"] [--place "Epping Forest"]
                            [--date 2026-10-12] [--inat 123456789] [--alt "..."]
  python3 tools/wildlife.py --remove red-fox-2026-10-12

Writes two JPEGs into outside/wildlife/ — the photo at 1600px on its long edge and a
640px thumbnail — and puts a <figure> at the top of the gallery in outside/index.html.
Everything between the <!-- wildlife:start --> and <!-- wildlife:end --> markers
belongs to this script, but existing figures are carried over verbatim, so a caption
can still be corrected by hand afterwards.

All metadata is stripped on the way through. A phone photo carries the GPS position
it was taken at, and for anything shot in a garden that is a home address. The place
in the caption is only ever what --place says. The colour profile is kept: it is not
personal, and dropping a Display P3 profile visibly flattens the colours.

The date comes from the photo's own EXIF unless --date is given. With neither, it
refuses rather than guess. HEIC, which Pillow cannot read, goes through macOS `sips`.

Needs Pillow, so like og.py this runs locally and not in CI. check.py verifies what it
leaves behind: every file on disk shown on the page, none carrying EXIF, none over
budget.
"""
import argparse, datetime, html, pathlib, re, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "outside" / "index.html"
DIR = ROOT / "outside" / "wildlife"
FULL, THUMB = 1600, 640

REGION = re.compile(r"<!-- wildlife:start[^>]*-->\n(.*?)\n[ \t]*<!-- wildlife:end -->", re.S)
FIGURE = re.compile(r'[ \t]*<figure id="([^"]+)">.*?</figure>', re.S)


def load(src):
    from PIL import Image, UnidentifiedImageError
    try:
        img = Image.open(src)
        img.load()
        return img
    except UnidentifiedImageError:
        if sys.platform != "darwin":
            sys.exit(f"cannot read {src}")
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "photo.jpg"
        r = subprocess.run(["sips", "-s", "format", "jpeg", str(src), "--out", str(out)],
                           capture_output=True)
        if r.returncode or not out.exists():
            sys.exit(f"cannot read {src}, and sips could not convert it either")
        img = Image.open(out)
        img.load()
        return img


def taken(img):
    """DateTimeOriginal from the Exif IFD, falling back to the base DateTime."""
    exif = img.getexif()
    raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)
    try:
        return datetime.datetime.strptime(str(raw).strip("\0 ")[:10], "%Y:%m:%d").date()
    except ValueError:
        return None


def save(img, size, path, quality, icc):
    from PIL import Image
    out = img.copy()
    out.thumbnail((size, size), Image.Resampling.LANCZOS)
    # No exif= and no xmp=, so Pillow writes neither: that is the stripping.
    extra = {"icc_profile": icc} if icc else {}
    out.save(path, "JPEG", quality=quality, optimize=True, progressive=True, **extra)
    return out.size


def figure(slug, a, date, w, h):
    e = html.escape
    seen = [f'<time datetime="{date.isoformat()}">{date.day} {date:%B %Y}</time>']
    if a.place:
        seen.append(e(a.place))
    if a.inat:
        seen.append(f'<a href="{a.inat}">iNaturalist</a>')
    lines = [
        f'      <figure id="{slug}">',
        f'        <a href="wildlife/{slug}.jpg"><img src="wildlife/{slug}-thumb.jpg" '
        f'width="{w}" height="{h}" alt="{e(a.alt or a.name)}" loading="lazy" decoding="async"></a>',
        '        <figcaption>',
        f'          <span class="species">{e(a.name)}</span>',
    ]
    if a.latin:
        lines.append(f'          <i class="latin">{e(a.latin)}</i>')
    lines += [
        f'          <span class="seen">{" &middot; ".join(seen)}</span>',
        '        </figcaption>',
        '      </figure>',
    ]
    return "\n".join(lines)


def seen_on(fig):
    m = re.search(r'<time datetime="([^"]+)"', fig)
    return m.group(1) if m else ""


def render(figures):
    if not figures:
        return '    <p class="empty">No photos yet.</p>'
    return '    <div class="gallery">\n' + "\n".join(figures) + "\n    </div>"


def add(a, figures):
    try:
        from PIL import ImageOps
    except ImportError as e:  # missing, or installed for the wrong architecture
        sys.exit(f"cannot load Pillow ({e})\n"
                 "install it for this Python, or run the script with one that has it")
    src = pathlib.Path(a.photo).expanduser()
    if not src.is_file():
        sys.exit(f"no such file: {src}")
    if a.inat:
        m = re.search(r"(\d+)/?\s*$", a.inat)
        if not m:
            sys.exit(f"--inat wants an observation URL or number, not {a.inat!r}")
        a.inat = f"https://www.inaturalist.org/observations/{m.group(1)}"

    img = load(src)
    if a.date:
        try:
            date = datetime.date.fromisoformat(a.date)
        except ValueError:
            sys.exit(f"--date wants YYYY-MM-DD, not {a.date!r}")
    else:
        date = taken(img)
        if not date:
            sys.exit("the photo carries no date; pass --date YYYY-MM-DD")

    # A profile only describes the pixels in the mode it came with.
    icc = img.info.get("icc_profile") if img.mode == "RGB" else None
    img = ImageOps.exif_transpose(img).convert("RGB")

    ids = {re.search(r'id="([^"]+)"', f).group(1) for f in figures}
    base = (re.sub(r"[^a-z0-9]+", "-", a.name.lower()).strip("-") or "photo") + f"-{date}"
    slug, n = base, 2
    while slug in ids or (DIR / f"{slug}.jpg").exists():
        slug, n = f"{base}-{n}", n + 1

    DIR.mkdir(exist_ok=True)
    full, thumb = DIR / f"{slug}.jpg", DIR / f"{slug}-thumb.jpg"
    save(img, FULL, full, 82, icc)
    w, h = save(img, THUMB, thumb, 78, icc)
    for p in (full, thumb):
        print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size // 1024}KB)")
    if not a.alt:
        print("  alt text is just the name — pass --alt to describe the photo itself")
    return [figure(slug, a, date, w, h)] + figures


def remove(slug, figures):
    keep = [f for f in figures if f'<figure id="{slug}">' not in f]
    if len(keep) == len(figures):
        sys.exit(f"no photo {slug!r} on the page")
    for p in (DIR / f"{slug}.jpg", DIR / f"{slug}-thumb.jpg"):
        if p.exists():
            p.unlink()
            print(f"  removed {p.relative_to(ROOT)}")
    return keep


def main():
    ap = argparse.ArgumentParser(
        description="Add a wildlife photo to /outside/, or remove one.",
        epilog='e.g. tools/wildlife.py ~/Pictures/fox.heic "Red fox" --latin "Vulpes vulpes"')
    ap.add_argument("photo", nargs="?", help="JPEG, PNG, HEIC — anything Pillow or sips reads")
    ap.add_argument("name", nargs="?", help="common name, shown as the caption")
    ap.add_argument("--latin", help="scientific name, shown in italics under it")
    ap.add_argument("--place", help="where, as you want it shown — never read from GPS")
    ap.add_argument("--date", help="YYYY-MM-DD; defaults to the date in the photo's EXIF")
    ap.add_argument("--inat", help="iNaturalist observation URL or number, to link to it")
    ap.add_argument("--alt", help="describe the photo for screen readers; defaults to the name")
    ap.add_argument("--remove", metavar="SLUG", help="take a photo off the page, files and all")
    a = ap.parse_args()
    if not a.remove and not (a.photo and a.name):
        ap.error("give a photo and a name, or --remove SLUG")

    text = PAGE.read_text()
    m = REGION.search(text)
    if not m:
        sys.exit("wildlife:start / wildlife:end markers not found in outside/index.html")
    figures = [f.group(0) for f in FIGURE.finditer(m.group(1))]
    figures = remove(a.remove, figures) if a.remove else add(a, figures)
    # Newest sighting first, not newest added: backfilling an old photo should land it
    # where it belongs. The sort is stable, so a same-day addition still goes first.
    figures.sort(key=seen_on, reverse=True)
    PAGE.write_text(text[:m.start(1)] + render(figures) + text[m.end(1):])
    print(f"  outside/index.html  ({len(figures)} photo{'s' if len(figures) != 1 else ''})")


if __name__ == "__main__":
    main()

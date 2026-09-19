#!/usr/bin/env python3
"""Fingerprint the part of index.html that actually reaches cv.pdf.

A naive "index.html changed but cv.pdf did not" check nags constantly, because
most edits to that page are in the <head> or inside .no-print / .print-hide
blocks and never touch the PDF. This strips exactly what the print stylesheet
strips and hashes what is left, so it only fires when the printed CV really has
drifted from the page it is rendered from.

  python3 tools/cvstamp.py          print the current fingerprint
  python3 tools/cvstamp.py --write  record it, after regenerating cv.pdf
"""
import hashlib, pathlib, re, sys
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
STAMP = ROOT / "cv.stamp"
HIDDEN = ("no-print", "print-hide")
VOID = {"br", "img", "link", "meta", "hr", "input", "source"}


class PrintText(HTMLParser):
    """Collect text, skipping <head>, <script>, <style> and hidden subtrees."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip_depth, self.skip_tag = [], 0, None

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        if self.skip_depth:
            if tag == self.skip_tag:
                self.skip_depth += 1
            return
        classes = dict(attrs).get("class", "").split()
        if tag in ("head", "script", "style") or any(c in HIDDEN for c in classes):
            self.skip_tag, self.skip_depth = tag, 1

    def handle_endtag(self, tag):
        if self.skip_depth and tag == self.skip_tag:
            self.skip_depth -= 1
            if not self.skip_depth:
                self.skip_tag = None

    def handle_data(self, data):
        if not self.skip_depth:
            self.out.append(data)


def fingerprint():
    p = PrintText()
    p.feed((ROOT / "index.html").read_text())
    text = re.sub(r"\s+", " ", "".join(p.out)).strip()
    return hashlib.sha256(text.encode()).hexdigest()[:16]


if __name__ == "__main__":
    fp = fingerprint()
    if "--write" in sys.argv:
        STAMP.write_text(fp + "\n")
        print(f"recorded {fp}")
    else:
        print(fp)

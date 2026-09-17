# Build notes

Static site — no build step. Edit `index.html` and push.

## Regenerating cv.pdf

`cv.pdf` is rendered from `index.html` through the print stylesheet, so it must be
regenerated whenever the page content changes, or it will drift.

```sh
cd ~/Sites/ncartmell.github.io
python3 -m http.server 8799 &
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$PWD/cv.pdf" "http://localhost:8799/"
kill %1
```

The print stylesheet hides: the Download CV button, the "Currently" block, the Strava
line, the colophon, and the Selected Work entries marked `.print-hide`.

## Regenerating og.png

The Open Graph card (1200x630) is rendered from `og-card.html` the same way, with
`--window-size=1200,630 --screenshot`.

## Adding a writing post

1. `cp writing/template.html writing/your-slug.html`
2. Edit the title, description, canonical URL, og: tags, the `<h1>` and the date.
3. Add a row to the list in `writing/index.html` (there's a commented-out example),
   and delete the "Nothing published yet" paragraph once the first post is live.
4. Add the post to `sitemap.xml`.

Styling is shared via `style.css`; post-specific rules live in each post's own
`<style>` block, copied from the template.

## Adding a project

Uncomment the `<ul class="entries">` block in `projects/index.html`, add a row per
project, and delete the "Nothing public yet" paragraph once the first one is listed.

Shared sub-page styles (`.backlink`, `.page-title`, `.lede`, `.entries`, `.empty`)
live in `style.css` and are used by both `/writing/` and `/projects/`.

## Held back

One Selected Work entry is held back pending a public launch. Its markup is kept
outside this repository; drop it back into the Selected Work section when the time
comes, and regenerate `cv.pdf`.

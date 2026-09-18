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
2. Edit the title, description, canonical URL, og: tags, the `<h1>` and the date, and
   remove the `robots: noindex` line the template carries.
3. Add an entry to the right `<section class="collection">` in `writing/index.html`:

   ```html
   <li>
     <a href="your-slug.html">Title</a>
     <p class="entry-note">One or two sentences on what it is about.</p>
   </li>
   ```

   The index shows no per-post date — every post carries its own date, and repeating one
   identical date down a list of twenty is noise. Bump the `<span class="count">` on the
   section heading, and the total in the lede.
4. Add the post to `sitemap.xml`.

`writing/template.html` is deliberately `noindex`: it is published like everything else in
this repository, and it contains placeholder text.

Styling is shared via `style.css`; post-specific rules live in each post's own
`<style>` block, copied from the template.

## Adding a project

Add an entry to `<ul class="projects">` in `projects/index.html`:

```html
<li>
  <div class="project-head">
    <a href="https://github.com/ncartmell/name">name</a>
    <span class="chips"><span class="chip">Kotlin</span></span>
  </div>
  <p class="entry-note">What it is, and why it exists.</p>
</li>
```

The chips reuse the same `.chip` style as the Technical section of the CV, so the stack
reads the same way in both places.

Shared sub-page styles live in `style.css` and are used by both `/writing/` and
`/projects/`: `.subnav`, `.page-title`, `.lede`, `.collection`, `.group`, `.entries`,
`.entry-note`, `.projects`, `.empty`. `.backlink` is still used by the individual posts.

## Nav links

The links under the name on `index.html` are pills, with the CV as a filled primary
action. They are a screen affordance only — the print stylesheet strips the background,
border and padding back off, so the PDF keeps the plain `Email (me@…)` form. Regenerate
`cv.pdf` and check page one if you touch `.links`.

## Held back

One Selected Work entry is held back pending a public launch. Its markup is kept
outside this repository; drop it back into the Selected Work section when the time
comes, and regenerate `cv.pdf`.

"""Reflowable EPUB stylesheet (backlog M4-01) and font embedding (M4-04).

Book typography rules for comfortable Latin and Arabic reading:

- justified Latin body with automatic hyphenation (relies on the per-element
  `lang` attributes the renderer emits), no justification for RTL paragraphs
- restrained heading scale (h1 1.85x body down to h6 0.95x, weight 600)
  instead of browser defaults, which render h1 comically large
- widows/orphans control so headings never strand at page breaks
- footnote asides and figure captions in a clearly subordinate size
- Arabic blocks slightly larger with generous line height; embedded FiraGO
  (SIL OFL — redistributable) when the packager includes it

The CSS is strictly reflowable: no absolute positioning, no fixed dimensions.
"""

STYLESHEET = """\
/* Reflow — reflowable EPUB stylesheet */
body {
  font-family: serif;
  line-height: 1.6;
  margin: 0.4em 0.9em;
  color: #111111;
}

h1, h2, h3, h4, h5, h6 {
  font-family: sans-serif;
  font-weight: 600;
  line-height: 1.25;
  margin: 1.6em 0 0.5em 0;
  text-align: left;
  widows: 2;
  orphans: 2;
}

h1 { font-size: 1.85em; }
h2 { font-size: 1.5em; }
h3 { font-size: 1.3em; }
h4 { font-size: 1.15em; }
h5 { font-size: 1.05em; }
h6 { font-size: 0.95em; letter-spacing: 0.02em; }

/* Latin body: book-style justification with automatic hyphenation; the
   per-element lang attributes let renderers pick the right hyphenation
   dictionary. */
p {
  margin: 0 0 0.85em 0;
  text-align: justify;
  hyphens: auto;
  -webkit-hyphens: auto;
  -epub-hyphens: auto;
  widows: 2;
  orphans: 2;
}

/* RTL paragraphs: start-aligned, larger, with generous line height. */
[dir="rtl"] {
  text-align: right;
  font-size: 1.15em;
  line-height: 1.9;
  hyphens: none;
  -webkit-hyphens: none;
  -epub-hyphens: none;
}

p.arabic, blockquote.arabic {
  font-family: "FiraGO", "Arabic Typesetting", serif;
}

blockquote {
  margin: 1em 1.4em;
  line-height: 1.6;
}

blockquote.arabic {
  text-align: right;
}

/* Footnotes: subordinate to the body flow. */
aside {
  font-size: 0.85em;
  line-height: 1.5;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
  margin-top: 1.4em;
  padding-top: 0.6em;
}

figure {
  margin: 1.1em 0;
  text-align: center;
}

figure img {
  max-width: 100%;
  height: auto;
}

figcaption {
  font-size: 0.85em;
  color: #615d59;
  margin-top: 0.4em;
}

table {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
}

td, th {
  border: 1px solid rgba(0, 0, 0, 0.15);
  padding: 0.35em 0.6em;
  text-align: left;
}

ol, ul {
  margin: 0.8em 0 0.8em 1.6em;
}

li {
  margin-bottom: 0.3em;
}
"""

# Appended by the renderer only when the Arabic font is actually embedded —
# a reference without the file trips epubcheck RSC-007. The URL placeholder
# is swapped for the real font file name at render time.
FONT_FACE_CSS = """\
@font-face {
  font-family: "FiraGO";
  font-weight: normal;
  font-style: normal;
  src: url("fonts/FiraGO-Regular.ttf");
}
"""

FONT_ID = "font-firago"

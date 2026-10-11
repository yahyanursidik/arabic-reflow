"""Reflowable EPUB stylesheet (backlog M4-01) and font embedding (M4-04).

Book typography rules for comfortable Latin and Arabic reading:

- start-aligned body text without stretched word spacing, a bounded measure,
  and explicit source line breaks retained
- restrained heading scale (h1 1.85x body down to h6 0.95x, weight 600)
  instead of browser defaults, which render h1 comically large
- widows/orphans control so headings never strand at page breaks
- readable footnote asides with linked references and return links
- Arabic blocks slightly larger with generous line height; embedded FiraGO
  (SIL OFL — redistributable) when the packager includes it

The CSS is strictly reflowable: no absolute positioning, no fixed dimensions.
"""

STYLESHEET = """\
/* Reflow — reflowable EPUB stylesheet */
body {
  font-family: "Source Serif 4", Georgia, "Times New Roman", serif;
  font-size: 1.125em;
  line-height: 1.7;
  max-width: 38em;
  margin: 0 auto;
  padding: 0.5em 0.9em;
  color: inherit;
}

h1, h2, h3, h4, h5, h6 {
  font-family: sans-serif;
  font-weight: 600;
  line-height: 1.35;
  margin: 1.4em 0 0.65em;
  text-align: start;
  overflow-wrap: break-word;
  widows: 2;
  orphans: 2;
  break-after: avoid;
  page-break-after: avoid;
}

h1 { font-size: 1.85em; }
h2 { font-size: 1.5em; }
h3 { font-size: 1.3em; }
h4 { font-size: 1.15em; }
h5 { font-size: 1.05em; }
h6 { font-size: 0.95em; letter-spacing: 0.02em; }

/* A paragraph gap instead of an indent; never stretch mixed-script spacing.
   Source newlines (credits, contents, verse) remain visible without editing text. */
p {
  margin: 0 0 0.85em 0;
  text-align: start;
  text-indent: 0;
  word-spacing: normal;
  letter-spacing: normal;
  hyphens: none;
  -webkit-hyphens: none;
  -epub-hyphens: none;
  widows: 2;
  orphans: 2;
  overflow-wrap: break-word;
  white-space: pre-line;
}

/* RTL paragraphs: start-aligned, larger, with generous line height. */
p[dir="rtl"], blockquote[dir="rtl"] {
  text-align: right;
  font-size: 1.15em;
  line-height: 1.9;
  hyphens: none;
  -webkit-hyphens: none;
  -epub-hyphens: none;
}

[lang="ar"], .arabic {
  font-family: "FiraGO", "Arabic Typesetting", serif;
  letter-spacing: normal;
  word-break: normal;
}

bdi[lang="ar"] {
  font-size: 1.15em;
  line-height: 1.9;
}

[lang="ar"] [lang="ar"], [dir="rtl"] bdi {
  font-size: inherit;
}

blockquote {
  margin: 1em 0.8em;
  line-height: 1.7;
  white-space: pre-line;
  overflow-wrap: break-word;
}

blockquote.arabic {
  text-align: right;
}

/* Footnotes: subordinate to the body flow. */
aside {
  font-size: 0.95em;
  line-height: 1.7;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
  margin-top: 1.4em;
  padding-top: 0.85em;
  text-align: start;
  overflow-wrap: break-word;
  scroll-margin-top: 1em;
}

.footnote-label {
  font-family: sans-serif;
  font-size: 1em;
  font-weight: 600;
  margin: 0 0 0.65em;
  break-after: avoid;
  page-break-after: avoid;
}

.endnotes {
  margin-top: 2em;
  break-before: page;
  page-break-before: always;
}

.endnotes aside p {
  text-align: start;
}

.inline-source {
  display: inline;
  height: 1.5em;
  width: auto;
  max-width: 100%;
  vertical-align: -0.35em;
  object-fit: contain;
}

a {
  color: inherit;
}

.noteref {
  text-decoration: none;
  border-bottom: 1px solid currentColor;
  padding: 0 0.15em;
  white-space: nowrap;
}

.image-actions, .note-actions {
  font-family: sans-serif;
  font-size: 0.88em;
  line-height: 1.5;
  text-align: start;
  margin: 0.45em 0 0.9em;
}

.image-actions a, .note-actions a {
  display: inline-block;
  padding: 0.6em 0.2em;
}

figure {
  margin: 1.1em 0;
  text-align: center;
  break-inside: avoid;
  page-break-inside: avoid;
}

figure img, .image-heading img {
  max-width: 100%;
  height: auto;
  width: auto;
  display: block;
  margin: 0 auto;
  object-fit: contain;
  break-inside: avoid;
  page-break-inside: avoid;
}

.image-heading {
  text-align: center;
  break-inside: avoid;
  page-break-inside: avoid;
}

.source-image img, .source-image-heading img {
  width: 100%;
  max-height: none;
}

.source-image-link { display: block; }

.image-enlarged {
  overflow: auto;
  margin: 0.8em 0 1.2em;
  border: 1px solid currentColor;
}

.image-enlarged img {
  display: block;
  width: 200%;
  max-width: none;
  max-height: none;
  height: auto;
}

.image-view .image-help {
  font-family: sans-serif;
  font-size: 0.95em;
  line-height: 1.6;
  white-space: normal;
}

.image-view .image-fit img {
  width: 100%;
  max-height: none;
}

.image-original {
  overflow: auto;
  margin-top: 1em;
  font-size: 1em;
  line-height: inherit;
}

.image-original img {
  display: block;
  max-width: none;
  max-height: none;
  width: auto;
  height: auto;
}

.image-view summary { padding: 0.8em 0; }

figcaption {
  font-size: 0.85em;
  color: inherit;
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
  text-align: start;
  overflow-wrap: break-word;
}

ol, ul {
  margin: 0.8em 0;
  padding-inline-start: 1.5em;
}

li {
  margin-bottom: 0.3em;
}

@media (max-width: 480px) {
  body { padding: 0.45em 0.6em; }
  p, blockquote { text-align: start; hyphens: none; -webkit-hyphens: none; }
  h1, h2, h3, h4, h5, h6 { overflow-wrap: break-word; line-height: 1.35; }
  h1 { font-size: 1.65em; }
  h2 { font-size: 1.35em; }
  blockquote { margin-inline: 0.65em; }
  figure { margin: 1.2em 0; }
  aside { font-size: 1em; }
  .image-actions a, .note-actions a { padding: 0.8em 0.2em; }
  [dir="rtl"] { text-align: right; }
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

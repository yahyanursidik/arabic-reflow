"""Reflowable EPUB stylesheet (backlog M4-01) and font embedding (M4-04).

The CSS is deliberately reflowable: no absolute positioning, no fixed
dimensions. Arabic content scales slightly larger for readability and uses
the embedded FiraGO (SIL OFL — redistributable) when the packager includes it.
"""

STYLESHEET = """\
/* Reflow — reflowable EPUB stylesheet */
body {
  font-family: serif;
  line-height: 1.6;
  margin: 0.4em 0.8em;
}

h1, h2, h3, h4, h5, h6 {
  line-height: 1.3;
  margin: 1em 0 0.4em 0;
}

p {
  margin: 0.6em 0;
}

blockquote {
  margin: 0.8em 1.2em;
}

figure {
  margin: 0.8em 0;
}

figure img {
  max-width: 100%;
  height: auto;
}

/* Arabic blocks and quotes: embedded Arabic font, slightly larger */
p.arabic, blockquote.arabic, [dir="rtl"] {
  font-family: "FiraGO", "Arabic Typesetting", serif;
  font-size: 1.1em;
}

@font-face {
  font-family: "FiraGO";
  font-weight: normal;
  font-style: normal;
  src: url("fonts/FiraGO-Regular.ttf");
}
"""

FONT_ID = "font-firago"
FONT_FILENAME = "fonts/FiraGO-Regular.ttf"
FONT_MEDIA_TYPE = "application/vnd.ms-opentype"

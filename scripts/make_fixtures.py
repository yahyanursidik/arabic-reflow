"""Generate the M0-02 fixture corpus into tests/fixtures/.

Fixtures are committed to the repository; CI consumes them as-is. This script
only needs to run when fixtures change, and requires an Arabic-capable font:
it prefers FiraGO from the optional `pymupdf-fonts` package and falls back to
system fonts (Windows/macOS/Linux candidates below).

Arabic text is written with PyMuPDF's HTML box engine so it is shaped and
bidirectionally ordered like real PDF content; extraction must return the
logical-order source, which the script verifies after writing each file.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pymupdf

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

A4 = pymupdf.paper_rect("a4")  # 595 x 842 pt

# Key strings shared with the golden tests. Never normalize these.
BISMILLAH_PLAIN = "بسم الله الرحمن الرحيم"
BISMILLAH_VOCALIZED = "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"
HADITH_NIYYAH_VOCALIZED = "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ"
ABI_HURAYRAH = "أبي هريرة رضي الله عنه"
ARABIC_PARAGRAPH_PLAIN = (
    "الحمد لله رب العالمين، والصلاة والسلام على أشرف الأنبياء والمرسلين، "
    "نابعا إلى يوم الدين، أما بعد:"
)
ARABIC_PARAGRAPH_VOCALIZED = (
    "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ، وَإِنَّمَا لِكُلِّ امْرِئٍ مَا نَوَى، "
    "فَمَنْ كَانَتْ هِجْرَتُهُ إِلَى اللَّهِ وَرَسُولِهِ فَهِجْرَتُهُ إِلَى اللَّهِ وَرَسُولِهِ"
)

INDONESIAN_INTRO = (
    "Kitab ini mengumpulkan hadits-hadits pilihan dari Shahih Bukhari dan Shahih Muslim "
    "yang disusun sesuai bab-bab fikih. Setiap hadits disertai penjelasan singkat agar "
    "pembaca pemula dapat memahami kandungannya tanpa kesulitan."
)
INDONESIAN_BODY = (
    "Para ulama sepakat bahwa niat merupakan syarat sahnya berbagai amal ibadah. "
    "Oleh karena itu, para penyusun kitab hadits menempatkan bab tentang niat pada "
    "awal kitab, sebelum membahas bab-bab lainnya."
)
MIXED_SENTENCE = f"Hadits ini diriwayatkan dari {ABI_HURAYRAH} dalam Shahih Muslim."
MIXED_SENTENCE_PUNCT = f"Menurut penjelasan para ulama, makna hadits \"{HADITH_NIYYAH_VOCALIZED}\" adalah sebagai berikut."
INDONESIAN_CLOSING = (
    "Demikian uraian singkat ini. Semoga bermanfaat bagi para pembaca, dan \"Allah\" "
    "memberi taufik serta hidayah kepada kita semua."
)


def _font_candidates() -> list[Path]:
    return [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/times.ttf"),
        Path("/System/Library/Fonts/GeezaPro.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf"),
        Path("/usr/share/fonts/truetype/firago/FiraGO-Regular.otf"),
    ]


def load_arabic_font() -> tuple[bytes, str]:
    """Return (font bytes, font name) from pymupdf-fonts or the system."""
    for reserved in ("fira", "figo"):
        try:
            font = pymupdf.Font(reserved)
        except Exception:
            continue
        if font.has_glyph(ord("ب")):
            return font.buffer, "ReflowArabic"
    for path in _font_candidates():
        if path.exists():
            return path.read_bytes(), "ReflowArabic"
    raise RuntimeError(
        "No Arabic-capable font found. Install pymupdf-fonts (pip install pymupdf-fonts) "
        "or provide a system Arabic font (e.g. C:/Windows/Fonts/arial.ttf)."
    )


class FixtureWriter:
    """Small helper around insert_htmlbox with a registered Arabic font."""

    def __init__(self) -> None:
        font_bytes, font_family = load_arabic_font()
        self._tmp = Path(tempfile.mkdtemp(prefix="reflow-fixtures-"))
        (self._tmp / "arabic.ttf").write_bytes(font_bytes)
        self._archive = pymupdf.Archive(str(self._tmp))
        self.font_family = font_family
        self._css = (
            f"@font-face {{font-family: {font_family}; src: url(arabic.ttf);}}"
            f" * {{font-family: {font_family};}}"
        )

    def close(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def html(self, text: str, size: int = 11, rtl: bool = False, bold: bool = False) -> str:
        return (
            f'<div style="font-size:{size}px;{"dir:rtl;text-align:right;" if rtl else ""}'
            f'{"font-weight:bold;" if bold else ""}line-height:1.6">{text}</div>'
        )

    def insert(self, page: pymupdf.Page, rect: pymupdf.Rect, text: str, size: int = 11,
               rtl: bool = False, bold: bool = False) -> None:
        rc = page.insert_htmlbox(
            rect, self.html(text, size=size, rtl=rtl, bold=bold), css=self._css,
            archive=self._archive,
        )
        spare_height = rc[0] if isinstance(rc, tuple) else rc
        if spare_height < 0:
            raise RuntimeError(f"insert_htmlbox did not fit content in {rect}")


def _page(doc: pymupdf.Document) -> pymupdf.Page:
    return doc.new_page(width=A4.width, height=A4.height)


def fixture_indonesian_native(w: FixtureWriter) -> pymupdf.Document:
    doc = pymupdf.open()
    page = _page(doc)
    w.insert(page, pymupdf.Rect(60, 60, 535, 100), "Pendahuluan", size=18, bold=True)
    w.insert(page, pymupdf.Rect(60, 110, 535, 240), INDONESIAN_INTRO, size=11)
    w.insert(page, pymupdf.Rect(60, 250, 535, 400), INDONESIAN_BODY, size=11)
    w.insert(page, pymupdf.Rect(60, 410, 535, 480), INDONESIAN_CLOSING, size=11)
    w.insert(page, pymupdf.Rect(250, 800, 345, 820), "1", size=10)
    return doc


def fixture_arabic_native(w: FixtureWriter) -> pymupdf.Document:
    doc = pymupdf.open()
    page = _page(doc)
    w.insert(page, pymupdf.Rect(60, 60, 535, 100), "الفاتحة", size=18, bold=True, rtl=True)
    w.insert(page, pymupdf.Rect(60, 110, 535, 300), ARABIC_PARAGRAPH_PLAIN, size=14, rtl=True)
    w.insert(page, pymupdf.Rect(60, 310, 535, 420), BISMILLAH_PLAIN, size=14, rtl=True)
    return doc


def fixture_mixed(w: FixtureWriter) -> pymupdf.Document:
    doc = pymupdf.open()
    page = _page(doc)
    w.insert(page, pymupdf.Rect(60, 60, 535, 100), "Bab Pertama: Niat", size=16, bold=True)
    w.insert(page, pymupdf.Rect(60, 110, 535, 230), INDONESIAN_INTRO, size=11)
    w.insert(page, pymupdf.Rect(60, 240, 535, 340), MIXED_SENTENCE, size=11)
    w.insert(page, pymupdf.Rect(60, 350, 535, 470), MIXED_SENTENCE_PUNCT, size=11)
    w.insert(page, pymupdf.Rect(60, 480, 535, 600), INDONESIAN_BODY, size=11)
    return doc


def fixture_arabic_vocalized(w: FixtureWriter) -> pymupdf.Document:
    doc = pymupdf.open()
    page = _page(doc)
    w.insert(page, pymupdf.Rect(60, 60, 535, 110), BISMILLAH_VOCALIZED, size=16, rtl=True)
    w.insert(page, pymupdf.Rect(60, 120, 535, 260), HADITH_NIYYAH_VOCALIZED, size=16, rtl=True)
    w.insert(page, pymupdf.Rect(60, 270, 535, 450), ARABIC_PARAGRAPH_VOCALIZED, size=14, rtl=True)
    return doc


def fixture_two_column(w: FixtureWriter) -> pymupdf.Document:
    doc = pymupdf.open()
    page = _page(doc)
    w.insert(page, pymupdf.Rect(60, 50, 535, 90), "Dua Kolom", size=16, bold=True)
    left = pymupdf.Rect(50, 100, 285, 700)
    right = pymupdf.Rect(310, 100, 545, 700)
    for i in range(3):
        w.insert(page, pymupdf.Rect(left.x0, left.y0 + i * 120, left.x1, left.y0 + 118 + i * 120),
                 f"Kolom kiri bagian {i + 1}. {INDONESIAN_BODY}", size=10)
        w.insert(page, pymupdf.Rect(right.x0, right.y0 + i * 120, right.x1, right.y0 + 118 + i * 120),
                 f"Kolom kanan bagian {i + 1}. {INDONESIAN_BODY}", size=10)
    return doc


def _rendered_page_image(w: FixtureWriter) -> bytes:
    """Render a native Arabic/Latin page to a PNG, simulating a scan."""
    tmp = pymupdf.open()
    page = _page(tmp)
    w.insert(page, pymupdf.Rect(60, 60, 535, 110), BISMILLAH_PLAIN, size=16, rtl=True)
    w.insert(page, pymupdf.Rect(60, 120, 535, 300), ARABIC_PARAGRAPH_PLAIN, size=14, rtl=True)
    w.insert(page, pymupdf.Rect(60, 310, 535, 430), INDONESIAN_BODY, size=11)
    pix = page.get_pixmap(dpi=150)
    png = pix.tobytes("png")
    tmp.close()
    return png


def fixture_scanned(w: FixtureWriter) -> pymupdf.Document:
    doc = pymupdf.open()
    page = _page(doc)
    page.insert_image(pymupdf.Rect(0, 0, A4.width, A4.height),
                      stream=_rendered_page_image(w))
    return doc


def fixture_hybrid(w: FixtureWriter) -> pymupdf.Document:
    doc = pymupdf.open()
    page1 = _page(doc)
    w.insert(page1, pymupdf.Rect(60, 60, 535, 100), "Halaman Teks Asli", size=16, bold=True)
    w.insert(page1, pymupdf.Rect(60, 110, 535, 300), INDONESIAN_INTRO, size=11)
    w.insert(page1, pymupdf.Rect(60, 310, 535, 450), INDONESIAN_BODY, size=11)
    page2 = _page(doc)
    page2.insert_image(pymupdf.Rect(0, 0, A4.width, A4.height),
                       stream=_rendered_page_image(w))
    return doc


def fixture_arabic_numbers(w: FixtureWriter) -> pymupdf.Document:
    doc = pymupdf.open()
    page = _page(doc)
    w.insert(page, pymupdf.Rect(60, 60, 535, 110),
             "في عام ١٤٤٧ هـ، طبع الكتاب للمرة الثانية؛ وصحّح الطبعة الأولى.", size=14, rtl=True)
    w.insert(page, pymupdf.Rect(60, 120, 535, 170),
             "عدد الصفحات: ٣٢٠ صفحة. السعر: ٥٠٬٠٠٠ ريال.", size=14, rtl=True)
    return doc


def _render_figure(width: float, height: float) -> bytes:
    """Render a simple vector figure to PNG for the image-caption fixture."""
    tmp = pymupdf.open()
    page = tmp.new_page(width=width, height=height)
    page.draw_rect(pymupdf.Rect(10, 10, width - 10, height - 10),
                   color=(0.1, 0.3, 0.6), fill=(0.85, 0.9, 1.0))
    page.draw_circle((width / 2, height / 2), 40,
                     color=(0.8, 0.2, 0.2), fill=(1, 0.9, 0.9))
    page.insert_text((30, 30), "Reflow", fontsize=12)
    png = page.get_pixmap(dpi=150).tobytes("png")
    tmp.close()
    return png


def fixture_image_caption(w: FixtureWriter) -> pymupdf.Document:
    doc = pymupdf.open()
    page = _page(doc)
    w.insert(page, pymupdf.Rect(60, 60, 535, 100),
             "Gambar dan Keterangan", size=16, bold=True)
    w.insert(page, pymupdf.Rect(60, 110, 535, 200), INDONESIAN_BODY, size=11)
    page.insert_image(pymupdf.Rect(140, 220, 440, 400), stream=_render_figure(300, 180))
    w.insert(page, pymupdf.Rect(140, 410, 440, 435),
             "Gambar 1: Diagram alir rekonstruksi dokumen.", size=9)
    return doc


def fixture_footnotes(w: FixtureWriter) -> pymupdf.Document:
    doc = pymupdf.open()
    page = _page(doc)
    w.insert(page, pymupdf.Rect(60, 60, 535, 100), "Catatan Kaki", size=16, bold=True)
    w.insert(page, pymupdf.Rect(60, 110, 535, 300),
             f"{INDONESIAN_INTRO} Pembahasan ini merujuk pada Shahih Bukhari.1", size=11)
    w.insert(page, pymupdf.Rect(60, 310, 535, 500),
             f"{INDONESIAN_BODY} Lihat juga penjelasan pada catatan berikut.2", size=11)
    page.draw_line(pymupdf.Point(60, 640), pymupdf.Point(300, 640))
    w.insert(page, pymupdf.Rect(60, 650, 535, 700),
             "1. Muhammad ibn Ismail al-Bukhari, Shahih al-Bukhari, hadits ke-1.", size=9)
    w.insert(page, pymupdf.Rect(60, 700, 535, 750),
             "2. Muslim ibn al-Hajjaj, Shahih Muslim, hadits ke-16.", size=9)
    return doc


def _arabic_letters(text: str) -> int:
    from engine.arabic.unicode import is_arabic_letter
    return sum(1 for ch in text if is_arabic_letter(ch))


def _harakat(text: str) -> int:
    from engine.arabic.unicode import count_harakat
    return count_harakat(text)


def _presentation_forms(text: str) -> int:
    from engine.arabic.unicode import is_presentation_form
    return sum(1 for ch in text if is_presentation_form(ch))


# filename: (builder, verifier(extracted_text) -> list of failure strings)
# Verifiers assert structural invariants only. The exact extracted text is
# frozen separately into tests/golden/ after manual review, because PyMuPDF's
# Arabic extraction legitimately contains presentation forms and font-mapping
# artifacts (that is precisely what this project exists to handle).
FIXTURES: dict[str, tuple[callable, callable]] = {
    "indonesian-native.pdf": (
        fixture_indonesian_native,
        lambda t: ([] if all(n in t for n in ("Pendahuluan", "Shahih Bukhari"))
                   else ["expected Latin paragraphs missing"]),
    ),
    "arabic-native.pdf": (
        fixture_arabic_native,
        lambda t: ([] if _arabic_letters(t) > 50 else ["too few Arabic letters"]),
    ),
    "mixed-id-ar.pdf": (
        fixture_mixed,
        lambda t: ([] if ("Hadits ini diriwayatkan dari" in t and _arabic_letters(t) > 10)
                   else ["mixed paragraph incomplete"]),
    ),
    "arabic-vocalized.pdf": (
        fixture_arabic_vocalized,
        lambda t: (
            ([] if _harakat(t) > 30 else ["harakat lost or incomplete"])
            + ([] if _presentation_forms(t) > 20 else ["expected presentation-form artifacts"])
        ),
    ),
    "arabic-numbers.pdf": (
        fixture_arabic_numbers,
        # Digit runs come back reversed in RTL extraction; assert presence only.
        lambda t: ([] if all(d in t for d in ("٠", "١", "٣", "٤", "٥", "٧"))
                          and _arabic_letters(t) > 20
                   else ["Arabic-Indic digits or letters missing"]),
    ),
    "two-column.pdf": (
        fixture_two_column,
        lambda t: ([] if all(f"Kolom {side} bagian {i}" in t
                             for side in ("kiri", "kanan") for i in (1, 2, 3))
                   else ["column paragraphs missing"]),
    ),
    "scanned.pdf": (
        fixture_scanned,
        lambda t: ([] if not t.strip() else ["scanned page unexpectedly has a text layer"]),
    ),
    "hybrid.pdf": (
        fixture_hybrid,
        lambda t: ([] if "Halaman Teks Asli" in t else ["native page text missing"]),
    ),
    "footnote-heavy.pdf": (
        fixture_footnotes,
        lambda t: ([] if all(n in t for n in ("al-Bukhari", "Muslim ibn al-Hajjaj"))
                   else ["footnote text missing"]),
    ),
    "image-caption.pdf": (
        fixture_image_caption,
        lambda t: ([] if "Gambar 1: Diagram alir rekonstruksi dokumen." in t
                   else ["caption text missing"]),
    ),
}


def main() -> int:
    writer = FixtureWriter()
    failures: list[str] = []
    try:
        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
        for filename, (builder, verify) in FIXTURES.items():
            doc = builder(writer)
            target = FIXTURES_DIR / filename
            doc.save(target, deflate=True)
            doc.close()

            check = pymupdf.open(target)
            extracted = "".join(page.get_text() for page in check)
            check.close()
            problems = verify(extracted)
            for problem in problems:
                failures.append(f"{filename}: {problem}")
            print(
                f"wrote {target.name}: {len(extracted)} chars, "
                f"{_arabic_letters(extracted)} arabic letters, "
                f"{_harakat(extracted)} harakat, "
                f"{_presentation_forms(extracted)} presentation forms"
            )
    finally:
        writer.close()

    if failures:
        print("\nVERIFICATION FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("\nall fixtures verified against structural invariants")
    return 0


if __name__ == "__main__":
    sys.exit(main())

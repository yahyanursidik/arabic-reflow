# Contributing to Reflow

Terima kasih ingin berkontribusi! Dokumen ini merangkum cara kerja proyek.
Dokumen tata kelola lengkap ada di root repo — **baca dulu sebelum menulis
kode** (lihat `VIBE-CODING-INSTRUCTIONS.md`):

1. `PRD.md` — produk dan batasan MVP
2. `ARCHITECTURE.md` — batas arsitektur dan kontrak pipeline
3. `REFLOWDOC-SPEC.md` — model dokumen kanonik
4. `ARABIC-ENGINE.md` — aturan pemrosesan Arab
5. `MVP-BACKLOG.md` — milestone dan release gate

## Prinsip inti

> Preserve first. Reconstruct second. Never invent.

- Dilarang memakai AI generatif untuk memperbaiki/menulis ulang teks sumber
  secara diam-diam, terutama teks Al-Qur'an, hadits, dan sitasi.
- Ketika tidak pasti: keluarkan *warning* dengan confidence, jangan menebak.
- Setiap transformasi wajib menyimpan provenance (`source_text`,
  `transformations`).

## Batas arsitektur

```text
Input Adapter (PDF/OCR) → ReflowDoc → Output Renderer (EPUB/preview/JSON)
```

- Renderer tidak boleh bergantung pada internal PDF.
- Parser tidak boleh tahu soal EPUB.
- Semua stage menerima/mengembalikan tipe data yang jelas.
- OCR adalah fallback, bukan default; adapter harus di balik interface.

## Setup pengembangan

Python 3.11+ (target 3.14) dan Node 20+.

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[api,dev]"
pytest                                                  # semua test
python scripts/make_fixtures.py                          # regenerasi fixture (jarang)
python scripts/update_golden.py                          # hanya saat memang disengaja
```

## Alur kerja per backlog item

1. Restate perilaku yang dimaksud.
2. Identifikasi modul yang terdampak.
3. Pilih/tambah fixture representatif.
4. Tulis test lebih dulu bila memungkinkan.
5. Implementasi perubahan sekecil mungkin yang koheren.
6. Jalankan unit test.
7. Jalankan regresi Arabic (golden).
8. Jalankan snapshot ReflowDoc.
9. Perbarui dokumentasi bila kontrak berubah.
10. Rangkum risiko dan edge case yang tersisa.

## Aturan test

- Perubahan sensitif-Arab wajib mengetes: Arab tanpa harakat, Arab berharakat,
  campuran Indonesia+Arab, tanda baca dekat Arab, dan satu golden fixture.
- Perubahan reading-order wajib mengetes: satu kolom, multi-kolom, halaman
  footnote.
- Perubahan EPUB wajib menghasilkan XHTML valid dan mempertahankan
  `lang`/`dir`.
- **Release gate**: rilis diblokir bila fixture golden kehilangan karakter,
  harakat, atau urutan baca (lihat `MVP-BACKLOG.md`).

## Gaya kode

- Python: type hints, Pydantic/dataclass untuk model domain, tanpa state
  global tersembunyi, pisahkan transformasi murni dari I/O.
- TypeScript: strict, jangan duplikasi model backend secara manual, state UI
  terpisah dari state ReflowDoc kanonik.
- UI: dokumen tool, bukan dashboard dekoratif — tipografi tenang, bahasa
  warning yang jelas.

## Commit & rilis

- Satu milestone = satu commit `feat: Milestone N — ... v0.x.0` + tag
  `v0.x.0` + GitHub Release dengan changelog.
- CI harus hijau (engine tests + schema check + web build) sebelum rilis.

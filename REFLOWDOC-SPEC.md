# ReflowDoc Specification v0.1

## 1. Purpose

ReflowDoc is the canonical intermediate document representation used between extraction/reconstruction and output rendering.

It must be independent from:

- PDF coordinates,
- EPUB packaging,
- web UI implementation.

It may retain source-location metadata for diagnostics, but semantic content must remain portable.

## 2. Top-Level Shape

```json
{
  "schema_version": "0.1",
  "document_id": "uuid",
  "metadata": {},
  "chapters": [],
  "resources": [],
  "warnings": []
}
```

## 3. Metadata

```json
{
  "title": "",
  "author": [],
  "publisher": null,
  "languages": ["id", "ar"],
  "description": null,
  "identifier": null,
  "source_filename": "book.pdf"
}
```

## 4. Chapter

```json
{
  "id": "chapter-001",
  "title": "Pendahuluan",
  "level": 1,
  "blocks": []
}
```

A document may temporarily contain an ungrouped chapter before chapter detection is complete.

## 5. Base Block Fields

Every block should support:

```json
{
  "id": "block-001",
  "type": "paragraph",
  "source": {
    "page": 3,
    "bbox": [72, 120, 500, 180]
  },
  "lang": "id",
  "script": "Latin",
  "dir": "ltr",
  "confidence": 0.98,
  "warnings": [],
  "modified_by_user": false
}
```

## 6. Block Types

Initial block types:

- heading
- paragraph
- quote
- list
- image
- caption
- table
- footnote
- page_break

Future:

- quran
- hadith
- poetry
- formula
- code
- bibliography

## 7. Paragraph Block

```json
{
  "type": "paragraph",
  "content": [
    {
      "type": "text",
      "text": "Hadits ini diriwayatkan dari "
    },
    {
      "type": "span",
      "text": "أبي هريرة رضي الله عنه",
      "lang": "ar",
      "script": "Arabic",
      "dir": "rtl"
    },
    {
      "type": "text",
      "text": " dalam Shahih Muslim."
    }
  ]
}
```

This span-level model is required for mixed-direction paragraphs.

## 8. Arabic Quote Block

```json
{
  "id": "block-002",
  "type": "quote",
  "subtype": "arabic",
  "lang": "ar",
  "script": "Arabic",
  "dir": "rtl",
  "text": "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ",
  "confidence": 0.99
}
```

## 9. Heading Block

```json
{
  "type": "heading",
  "level": 2,
  "text": "Pengertian Tauhid",
  "lang": "id",
  "dir": "ltr"
}
```

## 10. List Block

```json
{
  "type": "list",
  "ordered": true,
  "items": [
    {"blocks": []},
    {"blocks": []}
  ]
}
```

## 11. Image Block

```json
{
  "type": "image",
  "resource_id": "img-001",
  "alt": null,
  "caption_block_id": "block-042"
}
```

## 12. Footnote Block

```json
{
  "type": "footnote",
  "id": "fn-12",
  "marker": "12",
  "blocks": []
}
```

References inside body content should point to the footnote ID.

## 13. Table Block

```json
{
  "type": "table",
  "rows": [
    [
      {"text": "Column A"},
      {"text": "Column B"}
    ]
  ],
  "confidence": 0.88,
  "fallback_resource_id": null
}
```

## 14. Source Text Preservation

Where transformations occur, preserve extraction provenance.

Recommended:

```json
{
  "text": "pembelajaran",
  "source_text": "pembe-\nlajaran",
  "transformations": ["dehyphenation"]
}
```

For Arabic, `source_text` must be retained when any normalization occurs.

## 15. Arabic Diagnostic Metadata

Optional:

```json
{
  "arabic_integrity": {
    "score": 0.94,
    "presentation_forms_detected": false,
    "suspicious_spacing": false,
    "combining_mark_warnings": 0,
    "bidi_warning": false
  }
}
```

## 16. Warnings

```json
{
  "code": "READING_ORDER_UNCERTAIN",
  "severity": "warning",
  "message": "Column boundary is ambiguous.",
  "source_page": 14,
  "block_ids": ["block-12", "block-13"]
}
```

## 17. Versioning Rules

Use a top-level `schema_version`.

Breaking structure changes require a new minor or major schema version and migration strategy.

## 18. Renderer Contract

An output renderer may consume ReflowDoc but may not mutate its source content silently.

For EPUB:

- `lang` maps to XHTML `lang`.
- `dir` maps to XHTML `dir`.
- mixed Arabic spans render with `bdi` or equivalent safe bidi isolation.
- semantic block types map to semantic XHTML elements.

## 19. Design Rule

ReflowDoc must answer:

> What is this content and how should it be read?

It should not attempt to answer:

> At which exact PDF pixel should this content appear?

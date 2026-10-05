# Arabic Engine Specification

## 1. Goal

Provide a dedicated Arabic-aware processing layer that detects and reports extraction problems without inventing source text.

## 2. Non-Goals

The Arabic Engine must not:

- translate Arabic,
- rewrite Arabic,
- infer missing Qur'anic text using a language model,
- silently remove harakat,
- silently normalize orthographic distinctions in the final source text.

## 3. Modules

```text
arabic/
├── detector.py
├── unicode.py
├── bidi.py
├── spacing.py
├── combining_marks.py
├── integrity.py
├── normalization.py
└── report.py
```

## 4. Script Detection

Detect whether a span is predominantly:

- Arabic,
- Latin,
- mixed,
- numeric,
- neutral/punctuation.

Direction should be inferred at span and block level.

## 5. Unicode Diagnostics

Detect:

- core Arabic blocks,
- Arabic Supplement,
- Arabic Extended blocks,
- Arabic Presentation Forms-A/B,
- combining marks,
- unusual private-use characters.

Presentation forms are not automatically an error, but must be surfaced because they commonly indicate extraction artifacts.

## 6. Harakat Preservation

Track combining marks before and after transformations.

Minimum requirements:

- do not strip harakat,
- do not reorder combining marks arbitrarily,
- preserve shadda + vowel combinations,
- preserve Qur'anic annotation marks when present.

## 7. Suspicious Spacing Detection

Flag patterns such as:

```text
ا ل س ل ا م
```

Possible heuristics:

- single Arabic characters separated by spaces at abnormal frequency,
- repeated isolated forms,
- per-glyph PDF extraction artifacts.

Do not auto-merge unless transformation confidence is extremely high and source text is retained.

## 8. BiDi Diagnostics

Check:

- Arabic block in LTR context without isolation,
- punctuation jumping across script boundaries,
- reversed-looking token sequences,
- mixed script spans requiring `bdi`,
- numbers adjacent to Arabic punctuation.

## 9. Mixed Inline Arabic

Input:

```text
Hadits ini berasal dari أبي هريرة رضي الله عنه dan diriwayatkan...
```

ReflowDoc should contain separate inline spans so rendering can safely produce:

```html
<p lang="id" dir="ltr">
  Hadits ini berasal dari
  <bdi lang="ar" dir="rtl">أبي هريرة رضي الله عنه</bdi>
  dan diriwayatkan...
</p>
```

## 10. Integrity Score

Proposed weighted dimensions:

- valid Unicode coverage,
- suspicious-spacing rate,
- presentation-form rate,
- combining-mark anomalies,
- bidi anomalies,
- extraction confidence.

Example result:

```json
{
  "score": 0.91,
  "level": "good",
  "issues": [
    {
      "code": "PRESENTATION_FORMS_DETECTED",
      "severity": "info"
    }
  ]
}
```

Recommended UI labels:

- Healthy
- Review recommended
- Extraction problem likely

Avoid false precision in user-facing UI.

## 11. Source vs Search Normalization

Keep two concepts separate.

### Source Text
Used for EPUB and preview.

### Search-Normalized Text
May remove harakat or normalize selected characters for search/indexing only.

Example:

```json
{
  "source": "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ",
  "search_normalized": "انما الاعمال بالنيات"
}
```

Never replace the source with the search-normalized form.

## 12. OCR Interaction

Arabic Engine should be able to recommend page/block OCR when extracted Arabic looks corrupted.

Example decision:

```text
Native extraction
↓
Arabic integrity 0.38
↓
OCR candidate
↓
Compare extraction candidates
↓
Select higher-confidence source without generative rewriting
```

The original extraction must remain available for diagnostics.

## 13. Testing Requirements

Fixture categories:

- Arabic without harakat.
- Arabic with full harakat.
- Qur'anic annotation marks.
- Arabic Presentation Forms.
- Mixed Arabic + Indonesian.
- Arabic numbers.
- Arabic punctuation.
- Multi-line Arabic quotation.
- Fonts with unusual glyph mapping.

## 14. Regression Rule

A release must be blocked if a previously approved Arabic golden fixture loses source characters, harakat, or reading order without an explicit schema/behavior change.

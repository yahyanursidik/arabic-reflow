# Arabic Integrity Engine (Milestone 3)

The dedicated Arabic-aware layer that **detects and reports** extraction
problems without inventing or repairing text (ARABIC-ENGINE.md). Modules in
`engine/arabic/`:

| Module | Backlog | Purpose |
| --- | --- | --- |
| `unicode.py` | M3-01 | Range knowledge: Arabic blocks, harakat, Qur'anic marks, presentation forms, bidi controls |
| `detector.py` | M1-03/04 | Script classification and direction (built in Milestone 1) |
| `spacing.py` | M3-03 | Suspicious isolated-letter spacing ("ا ل س ل ا م") |
| `combining_marks.py` | M3-04 | Harakat/shadda/Qur'anic counts, orphan-mark detection |
| `bidi.py` | M3-05 | Punctuation jumps, unisolated mixtures, bidi controls, digit/punct adjacency |
| `integrity.py` | M3-06 | Weighted score + issue codes |
| `normalization.py` | §11 | Search-normalized form (never replaces source) |
| `report.py` | M3-06 | Block/page/document health; pipeline hook |

## Scoring

`inspect_text(text, mixed_isolated)` starts at 1.0 and subtracts documented
penalties: presentation-form rate (≤ 0.25, info — presentation forms are
common in real-world extraction and are not an error by themselves),
unusual letters outside Arabic/Latin such as the Georgian-range ligature
artifacts (≤ 0.3), suspicious spacing (0.25), orphan combining marks (≤ 0.2),
and severe bidi anomalies (0.1 each).

Review levels: `good` (≥ 0.85), `review_recommended` (≥ 0.6), else
`problem_likely`. Avoid presenting the score with false precision.

## Pipeline wiring

`engine.arabic.report.attach_integrity` runs inside
`reconstruct_semantics`: blocks carrying Arabic get an `arabic_integrity`
payload (`score`, `presentation_forms_detected`, `suspicious_spacing`,
`combining_mark_warnings`, `bidi_warning`); blocks below `problem_likely`
gain the `LOW_ARABIC_CONFIDENCE` block warning and a document-level
`LOW_ARABIC_CONFIDENCE` warning listing the block ids. Mixed blocks are
checked for span isolation: an Arabic/Latin mixture without `SpanNode`
isolation raises `UNISOLATED_MIXTURE`.

`document_report(document)` aggregates: document score, per-page average
scores, low-confidence block ids, and the set of issue codes.

## Source vs search normalization

`search_normalized(text)` = NFKC (folds presentation forms and ligatures) →
alef variant folding (أ إ آ ٱ → ا) → combining marks and tatweel removed.
It exists for search/indexing only. The source text is never replaced —
golden tests pin the source byte-for-byte.

## Non-goals (enforced by tests and review)

No translation, no rewriting, no model-driven completion of Qur'anic text,
no silent harakat removal, no silent orthographic normalization of source
content. Auto-merging of suspiciously spaced letters is explicitly **not**
implemented; it stays a reported artifact.

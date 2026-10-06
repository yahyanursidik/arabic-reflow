/**
 * Friendly Indonesian labels for engine warning codes, plus helpers to keep
 * the review UI honest but readable: codes stay in tooltips/data, people see
 * plain language. Duplicate warnings are collapsed with a count.
 */

export interface WarningCodeInfo {
  label: string;
  /** true when the code means "something needs your review" */
  needsReview: boolean;
}

const CODES: Record<string, WarningCodeInfo> = {
  LOW_ARABIC_CONFIDENCE: { label: "Integritas Arab rendah", needsReview: true },
  ARABIC_RENDERED_AS_IMAGE: { label: "Dirender sebagai gambar", needsReview: false },
  PARAGRAPH_MERGE_UNCERTAIN: { label: "Penggabungan paragraf ragu", needsReview: true },
  READING_ORDER_UNCERTAIN: { label: "Urutan baca ragu", needsReview: true },
  FOOTNOTE_UNCERTAIN: { label: "Catatan kaki heuristik", needsReview: true },
  TABLE_FALLBACK_IMAGE: { label: "Tabel dijadikan gambar", needsReview: true },
  TABLE_DETECTED: { label: "Tabel terdeteksi", needsReview: false },
  UNISOLATED_MIXTURE: { label: "Campuran skrip tak terisolasi", needsReview: true },
  OCR_USED: { label: "Dikenali via OCR", needsReview: false },
  OCR_LOW_CONFIDENCE: { label: "Keyakinan OCR rendah", needsReview: true },
  FURNITURE_REMOVED: { label: "Header/footer dihapus", needsReview: false },
  PAGE_NUMBERS_REMOVED: { label: "Nomor halaman dihapus", needsReview: false },
};

const FALLBACK: WarningCodeInfo = { label: "", needsReview: true };

export function warningInfo(code: string): WarningCodeInfo {
  return CODES[code] ?? { ...FALLBACK, label: code };
}

export interface CollapsedWarning {
  code: string;
  label: string;
  needsReview: boolean;
  count: number;
}

export function collapseWarnings(codes: string[]): CollapsedWarning[] {
  const order: string[] = [];
  const counts = new Map<string, number>();
  for (const code of codes) {
    if (!counts.has(code)) order.push(code);
    counts.set(code, (counts.get(code) ?? 0) + 1);
  }
  return order.map((code) => {
    const info = warningInfo(code);
    return { code, label: info.label, needsReview: info.needsReview, count: counts.get(code) ?? 1 };
  });
}

/** [3, 4, 6, 8, 9, 10] -> "hlm 3–4, 6, 8–10" (already-sorted list). */
export function formatPageRanges(pages: number[]): string {
  const sorted = [...pages].sort((a, b) => a - b);
  if (sorted.length === 0) return "";
  const parts: string[] = [];
  let start = sorted[0] as number;
  let previous = sorted[0] as number;
  for (const page of sorted.slice(1)) {
    if (page === previous + 1) {
      previous = page;
      continue;
    }
    parts.push(start === previous ? `${start}` : `${start}–${previous}`);
    start = page;
    previous = page;
  }
  parts.push(start === previous ? `${start}` : `${start}–${previous}`);
  return `hlm ${parts.join(", ")}`;
}

/** Compact "pages [3, 4, ...]" lists embedded in backend warning messages. */
export function compactMessage(message: string): string {
  const match = /pages \[([0-9,\s]+)\]/.exec(message);
  if (!match) return message;
  const pages = (match[1] ?? "")
    .split(",")
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isFinite(value));
  if (pages.length === 0) return message;
  return message.replace(match[0], formatPageRanges(pages));
}

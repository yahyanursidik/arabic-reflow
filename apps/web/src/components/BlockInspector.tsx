"use client";

import { useMemo, useState } from "react";

import { UiBlock, UiReflow, UiReport } from "@/lib/contract";
import { collapseWarnings, compactMessage, warningInfo } from "@/lib/warnings";

type Filter =
  | "all"
  | "arabic-issues"
  | "reading-order"
  | "ocr"
  | "footnotes"
  | "edited";

const TYPE_LABELS: Record<string, string> = {
  paragraph: "Paragraf",
  heading: "Judul",
  quote: "Kutipan",
  list: "Daftar",
  image: "Gambar",
  table: "Tabel",
  footnote: "Catatan kaki",
  page_break: "Pemisah halaman",
};

function typeLabel(block: UiBlock): string {
  return TYPE_LABELS[block.type] ?? block.type;
}

function needsReview(block: UiBlock, lowConfidence: Set<string>): boolean {
  return (
    lowConfidence.has(block.id) ||
    (block.integrityScore !== undefined && block.integrityScore < 0.85) ||
    block.warnings.some((code) => warningInfo(code).needsReview)
  );
}

function matches(block: UiBlock, filter: Filter, lowConfidence: Set<string>): boolean {
  switch (filter) {
    case "all":
      return true;
    case "arabic-issues":
      return (
        (block.integrityScore !== undefined && block.integrityScore < 0.85) ||
        block.warnings.some((w) => w.includes("ARABIC"))
      );
    case "reading-order":
      return block.warnings.some((w) => w.includes("READING_ORDER"));
    case "ocr":
      return block.warnings.some((w) => w.includes("OCR"));
    case "footnotes":
      return block.type === "footnote";
    case "edited":
      return block.modifiedByUser;
  }
}

/** Short single-line excerpt that survives Arabic/RTL blocks. */
function excerpt(block: UiBlock, max = 56): string {
  const text = block.text.replace(/\s+/g, " ").trim();
  if (!text) return typeLabel(block);
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

export function BlockInspector({
  blocks,
  report,
  reflow,
  selectedId,
  onSelect,
  onSave,
  onRenderImage,
  onRestoreText,
  onNormalizeArabic,
}: {
  blocks: UiBlock[];
  report: UiReport | null;
  reflow: UiReflow;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onSave: (
    blockId: string,
    update: { text?: string; lang?: string; dir?: string },
  ) => Promise<void>;
  onRenderImage: (blockId: string) => Promise<void>;
  onRestoreText: (blockId: string) => Promise<void>;
  onNormalizeArabic: (blockId: string) => Promise<void>;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const [saving, setSaving] = useState(false);
  const [acting, setActing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lowConfidence = useMemo(
    () => new Set(report?.integrity?.lowConfidenceBlockIds ?? []),
    [report],
  );

  const selected = useMemo(
    () => blocks.find((b) => b.id === selectedId) ?? null,
    [blocks, selectedId],
  );
  const visible = useMemo(
    () => blocks.filter((b) => matches(b, filter, lowConfidence)),
    [blocks, filter, lowConfidence],
  );

  const counts = useMemo(() => {
    const result: Record<Filter, number> = {
      all: blocks.length,
      "arabic-issues": 0,
      "reading-order": 0,
      ocr: 0,
      footnotes: 0,
      edited: 0,
    };
    for (const block of blocks) {
      for (const option of Object.keys(result) as Filter[]) {
        if (option !== "all" && matches(block, option, lowConfidence)) {
          result[option] += 1;
        }
      }
    }
    return result;
  }, [blocks, lowConfidence]);

  const [draftText, setDraftText] = useState<string | null>(null);
  const [draftLang, setDraftLang] = useState<string | null>(null);
  const [draftDir, setDraftDir] = useState<string | null>(null);
  const [editedId, setEditedId] = useState<string | null>(null);

  function select(block: UiBlock | null) {
    onSelect(block?.id ?? null);
    setEditedId(block?.id ?? null);
    setDraftText(block?.text ?? null);
    setDraftLang(block?.lang ?? null);
    setDraftDir(block?.dir ?? null);
    setError(null);
  }

  async function save() {
    if (!selected || editedId !== selected.id) return;
    setSaving(true);
    setError(null);
    try {
      const update: { text?: string; lang?: string; dir?: string } = {};
      if (draftText !== null && draftText !== selected.text) update.text = draftText;
      if (draftLang !== null && draftLang !== selected.lang) update.lang = draftLang;
      if (draftDir !== null && draftDir !== selected.dir) update.dir = draftDir;
      if (Object.keys(update).length === 0) return;
      await onSave(selected.id, update);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "gagal menyimpan");
    } finally {
      setSaving(false);
    }
  }

  const hasArabic =
    selected !== null && /[\u0600-\u06FF\uFB50-\uFEFF]/.test(selected.text);
  const renderedAsImage =
    selected !== null &&
    selected.type === "image" &&
    selected.warnings.includes("ARABIC_RENDERED_AS_IMAGE");
  const selectedWarnings = selected ? collapseWarnings(selected.warnings) : [];

  async function runAction(action: () => Promise<void>) {
    setActing(true);
    setError(null);
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "aksi gagal");
    } finally {
      setActing(false);
    }
  }

  const filters: { id: Filter; label: string }[] = [
    { id: "all", label: "Semua" },
    { id: "arabic-issues", label: "Masalah Arab" },
    { id: "reading-order", label: "Urutan baca" },
    { id: "ocr", label: "OCR" },
    { id: "footnotes", label: "Catatan kaki" },
    { id: "edited", label: "Disunting" },
  ];

  return (
    <div className="flex max-h-[70vh] flex-col rounded-card border border-black/8 bg-pure-white text-sm">
      <div className="border-b border-black/8 p-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-caption font-semibold uppercase tracking-wide text-stone">
            Inspektur blok
          </h2>
          <span className="text-[11px] text-stone">
            {visible.length} dari {blocks.length} blok
          </span>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {filters.map((option) => (
            <button
              className={
                "rounded-pill px-2.5 py-0.5 text-xs font-medium " +
                (filter === option.id
                  ? "bg-notion-blue text-pure-white"
                  : "bg-paper-warmth text-ink-black/90 hover:bg-sky-tint hover:text-notion-blue")
              }
              key={option.id}
              onClick={() => setFilter(option.id)}
              type="button"
            >
              {option.label}
              {counts[option.id] > 0 ? (
                <span
                  className={
                    "ml-1 " +
                    (filter === option.id ? "text-pure-white/80" : "text-stone")
                  }
                >
                  {counts[option.id]}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      </div>

      {/* Block list: grows with the pane, always scrollable */}
      <ul className="min-h-32 flex-1 overflow-y-auto border-b border-black/8">
        {visible.map((block) => {
          const flagged = needsReview(block, lowConfidence);
          const isSelected = selectedId === block.id;
          return (
            <li key={block.id}>
              <button
                aria-current={isSelected ? "true" : undefined}
                className={
                  "flex w-full items-center gap-2 border-l-2 px-3 py-1.5 text-left transition-colors " +
                  (isSelected
                    ? "border-notion-blue bg-sky-tint/60"
                    : "border-transparent hover:bg-paper-warmth")
                }
                onClick={() => select(block)}
                type="button"
              >
                <span
                  aria-hidden
                  className={
                    "h-2 w-2 shrink-0 rounded-full " +
                    (flagged
                      ? "bg-vermillion"
                      : block.warnings.length > 0
                        ? "bg-saffron"
                        : block.modifiedByUser
                          ? "bg-notion-blue"
                          : "bg-black/15")
                  }
                  title={
                    flagged
                      ? "Perlu ditinjau"
                      : block.warnings.length > 0
                        ? "Ada catatan"
                        : block.modifiedByUser
                          ? "Disunting"
                          : "Sehat"
                  }
                />
                <span
                  className={
                    "min-w-0 flex-1 truncate " +
                    (isSelected ? "text-ink-black" : "text-ink-black/90")
                  }
                  dir={block.dir ?? undefined}
                >
                  {excerpt(block)}
                </span>
                <span className="shrink-0 text-[11px] text-stone">
                  {typeLabel(block)}
                  {block.page ? ` · hlm ${block.page}` : ""}
                </span>
              </button>
            </li>
          );
        })}
        {visible.length === 0 ? (
          <li className="px-4 py-3 text-stone">Tidak ada blok pada filter ini.</li>
        ) : null}
      </ul>

      {selected ? (
        <div className="space-y-3 overflow-y-auto p-4">
          <div className="flex items-baseline justify-between">
            <p className="font-notioninter text-xs font-semibold text-ink-black">
              {typeLabel(selected)}
              {selected.page ? ` · halaman ${selected.page}` : ""}
            </p>
            <p className="font-notioninter text-[11px] text-stone">{selected.id}</p>
          </div>
          <dl className="grid grid-cols-3 gap-x-4 gap-y-1 text-xs text-stone">
            <div>
              <dt className="inline">Bahasa </dt>
              <dd className="inline font-medium text-ink-black/90">{selected.lang ?? "-"}</dd>
            </div>
            <div>
              <dt className="inline">Arah </dt>
              <dd className="inline font-medium text-ink-black/90">{selected.dir ?? "-"}</dd>
            </div>
            <div>
              <dt className="inline">Keyakinan </dt>
              <dd className="inline font-medium text-ink-black/90">
                {selected.confidence !== undefined
                  ? `${Math.round(selected.confidence * 100)}%`
                  : "-"}
              </dd>
            </div>
          </dl>

          {selectedWarnings.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {selectedWarnings.map((warning) => (
                <span
                  className={
                    "rounded-pill px-2 py-0.5 text-[11px] font-medium " +
                    (warning.needsReview
                      ? "bg-[#fdf0e5] text-[#b25e09]"
                      : "bg-paper-warmth text-stone")
                  }
                  key={warning.code}
                  title={warning.code}
                >
                  {warning.label}
                  {warning.count > 1 ? ` ×${warning.count}` : ""}
                </span>
              ))}
            </div>
          ) : null}

          {renderedAsImage ? (
            <div className="space-y-2">
              <p className="text-xs text-graphite">
                Blok ini dirender sebagai gambar dari halaman sumber (piksel
                apa adanya). Teks asli tersimpan dan bisa dikembalikan.
              </p>
              <button
                className="rounded-button bg-sky-tint px-3 py-1.5 text-xs font-medium text-notion-blue hover:opacity-80 disabled:opacity-40"
                disabled={acting}
                onClick={() => void runAction(() => onRestoreText(selected.id))}
                type="button"
              >
                Kembalikan ke teks
              </button>
            </div>
          ) : null}

          {hasArabic && ["paragraph", "heading", "quote"].includes(selected.type) ? (
            <div className="space-y-2 rounded-small border border-black/8 bg-paper-warmth p-3">
              <p className="text-xs text-graphite">
                Perbaikan Arab (eksplisit, bisa dibatalkan):
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  className="rounded-button bg-sky-tint px-3 py-1.5 text-xs font-medium text-notion-blue hover:opacity-80 disabled:opacity-40"
                  disabled={acting}
                  onClick={() =>
                    void runAction(() => onNormalizeArabic(selected.id))
                  }
                  type="button"
                  title="Lipat presentation forms ke huruf inti; harakat tetap utuh, teks asli disimpan"
                >
                  Normalisasi Arab (NFKC)
                </button>
                <button
                  className="rounded-button bg-sky-tint px-3 py-1.5 text-xs font-medium text-notion-blue hover:opacity-80 disabled:opacity-40"
                  disabled={acting}
                  onClick={() =>
                    void runAction(() => onRenderImage(selected.id))
                  }
                  type="button"
                  title="Potong region ini dari halaman sumber menjadi gambar — piksel tidak berubah"
                >
                  Render sebagai gambar
                </button>
              </div>
              <p className="text-[11px] text-stone">
                Normalisasi menjaga teks tetap reflowable dan bisa dicari;
                render sebagai gambar mempertahankan tampilan persis tetapi
                teksnya tidak bisa dicari.
              </p>
            </div>
          ) : null}

          {["paragraph", "heading", "quote"].includes(selected.type) ? (
            <div className="space-y-2">
              <label className="block text-xs text-stone" htmlFor="block-text">
                Teks (perubahan ditandai sebagai suntingan pengguna)
              </label>
              <textarea
                className="w-full rounded-button border border-black/15 p-2 text-sm text-ink-black focus:border-notion-blue focus:outline-none"
                id="block-text"
                dir={selected.dir ?? undefined}
                lang={selected.lang ?? undefined}
                onChange={(event) => setDraftText(event.target.value)}
                rows={4}
                value={draftText ?? ""}
              />
              <div className="flex gap-2">
                <input
                  className="w-24 rounded-button border border-black/15 p-1 text-xs focus:border-notion-blue focus:outline-none"
                  id="block-lang"
                  onChange={(event) => setDraftLang(event.target.value)}
                  placeholder="lang"
                  value={draftLang ?? ""}
                />
                <select
                  className="rounded-button border border-black/15 p-1 text-xs text-ink-black focus:border-notion-blue focus:outline-none"
                  onChange={(event) => setDraftDir(event.target.value)}
                  value={draftDir ?? ""}
                >
                  <option value="">arah: (warisi)</option>
                  <option value="ltr">ltr</option>
                  <option value="rtl">rtl</option>
                </select>
                <button
                  className="ml-auto rounded-button bg-notion-blue px-3 py-1 text-xs font-medium text-pure-white hover:opacity-90 disabled:opacity-40"
                  disabled={saving}
                  onClick={() => void save()}
                  type="button"
                >
                  {saving ? "Menyimpan…" : "Simpan"}
                </button>
              </div>
              {error ? (
                <p className="rounded-small border-l-2 border-coral pl-2 text-xs text-vermillion">
                  {error}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : (
        <p className="p-4 text-graphite">
          Pilih blok dari pratinjau atau daftar untuk memeriksa detail.
        </p>
      )}

      {report?.warnings.length ? (
        <div className="max-h-44 overflow-y-auto border-t border-black/8 p-4">
          <h3 className="text-caption font-semibold uppercase tracking-wide text-stone">
            Peringatan dokumen
          </h3>
          <ul className="mt-1.5 space-y-1">
            {collapseWarnings(report.warnings.map((w) => w.code)).map(
              (warning) => {
                const first = report.warnings.find((w) => w.code === warning.code);
                return (
                  <li className="flex gap-1.5 text-xs" key={warning.code}>
                    <span
                      aria-hidden
                      className={
                        "mt-1 h-1.5 w-1.5 shrink-0 rounded-full " +
                        (first?.severity === "error"
                          ? "bg-vermillion"
                          : first?.severity === "warning"
                            ? "bg-saffron"
                            : "bg-black/20")
                      }
                    />
                    <span className="text-graphite">
                      <span className="font-medium text-ink-black/90">
                        {warning.label}
                        {warning.count > 1 ? ` ×${warning.count}` : ""}
                      </span>
                      {first?.message ? (
                        <> — {compactMessage(first.message)}</>
                      ) : null}
                    </span>
                  </li>
                );
              },
            )}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

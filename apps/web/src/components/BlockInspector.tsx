"use client";

import { useMemo, useState } from "react";

import { UiBlock, UiReflow, UiReport } from "@/lib/contract";

type Filter =
  | "all"
  | "arabic-issues"
  | "reading-order"
  | "ocr"
  | "footnotes"
  | "edited";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "Semua" },
  { id: "arabic-issues", label: "Masalah Arab" },
  { id: "reading-order", label: "Urutan baca" },
  { id: "ocr", label: "OCR" },
  { id: "footnotes", label: "Catatan kaki" },
  { id: "edited", label: "Disunting" },
];

function matches(block: UiBlock, filter: Filter): boolean {
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
      return block.text.includes("OcrSynthesized") ||
        block.warnings.some((w) => w.includes("OCR"));
    case "footnotes":
      return block.type === "footnote";
    case "edited":
      return block.modifiedByUser;
  }
}

export function BlockInspector({
  blocks,
  report,
  reflow,
  selectedId,
  onSelect,
  onSave,
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
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected = useMemo(
    () => blocks.find((b) => b.id === selectedId) ?? null,
    [blocks, selectedId],
  );
  const visible = useMemo(() => blocks.filter((b) => matches(b, filter)), [blocks, filter]);

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

  const lowConfidence = new Set(report?.integrity?.lowConfidenceBlockIds ?? []);

  return (
    <div className="flex max-h-[70vh] flex-col border border-neutral-200 text-sm">
      <div className="border-b border-neutral-200 p-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Inspektur blok
        </h2>
        <div className="mt-2 flex flex-wrap gap-1">
          {FILTERS.map((option) => (
            <button
              className={
                "border px-2 py-0.5 text-xs " +
                (filter === option.id
                  ? "border-neutral-900 bg-neutral-900 text-white"
                  : "border-neutral-300 text-neutral-700 hover:bg-neutral-50")
              }
              key={option.id}
              onClick={() => setFilter(option.id)}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <ul className="max-h-56 overflow-y-auto border-b border-neutral-200">
        {visible.map((block) => (
          <li key={block.id}>
            <button
              className={
                "flex w-full items-baseline justify-between gap-2 px-3 py-1.5 text-left hover:bg-neutral-50 " +
                (selectedId === block.id ? "bg-neutral-100" : "")
              }
              onClick={() => select(block)}
              type="button"
            >
              <span className="truncate">
                {lowConfidence.has(block.id) ? "[!] " : ""}
                {block.modifiedByUser ? "[disunting] " : ""}
                {block.text.slice(0, 60) || `[${block.type}]`}
              </span>
              <span className="shrink-0 text-xs text-neutral-500">
                {block.type}
                {block.page ? ` · hlm ${block.page}` : ""}
              </span>
            </button>
          </li>
        ))}
        {visible.length === 0 ? (
          <li className="px-3 py-2 text-neutral-500">Tidak ada blok pada filter ini.</li>
        ) : null}
      </ul>

      {selected ? (
        <div className="space-y-3 overflow-y-auto p-3">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-neutral-600">
            <div>
              <dt className="inline text-neutral-500">ID </dt>
              <dd className="inline font-mono">{selected.id}</dd>
            </div>
            <div>
              <dt className="inline text-neutral-500">Tipe </dt>
              <dd className="inline">{selected.type}</dd>
            </div>
            <div>
              <dt className="inline text-neutral-500">Bahasa </dt>
              <dd className="inline">{selected.lang ?? "-"}</dd>
            </div>
            <div>
              <dt className="inline text-neutral-500">Arah </dt>
              <dd className="inline">{selected.dir ?? "-"}</dd>
            </div>
            <div>
              <dt className="inline text-neutral-500">Confidence </dt>
              <dd className="inline">
                {selected.confidence !== undefined
                  ? `${Math.round(selected.confidence * 100)}%`
                  : "-"}
              </dd>
            </div>
            <div>
              <dt className="inline text-neutral-500">Halaman </dt>
              <dd className="inline">{selected.page ?? "-"}</dd>
            </div>
          </dl>

          {selected.warnings.length > 0 ? (
            <p className="text-xs text-amber-700">{selected.warnings.join(", ")}</p>
          ) : null}

          {["paragraph", "heading", "quote"].includes(selected.type) ? (
            <div className="space-y-2">
              <label className="block text-xs text-neutral-500" htmlFor="block-text">
                Teks (perubahan ditandai sebagai suntingan pengguna)
              </label>
              <textarea
                className="w-full border border-neutral-300 p-2 text-sm"
                id="block-text"
                onChange={(event) => setDraftText(event.target.value)}
                rows={4}
                value={draftText ?? ""}
              />
              <div className="flex gap-2">
                <input
                  className="w-24 border border-neutral-300 p-1 text-xs"
                  id="block-lang"
                  onChange={(event) => setDraftLang(event.target.value)}
                  placeholder="lang"
                  value={draftLang ?? ""}
                />
                <select
                  className="border border-neutral-300 p-1 text-xs"
                  onChange={(event) => setDraftDir(event.target.value)}
                  value={draftDir ?? ""}
                >
                  <option value="">arah: (warisi)</option>
                  <option value="ltr">ltr</option>
                  <option value="rtl">rtl</option>
                </select>
                <button
                  className="ml-auto border border-neutral-900 bg-neutral-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-40"
                  disabled={saving}
                  onClick={() => void save()}
                  type="button"
                >
                  {saving ? "Menyimpan…" : "Simpan"}
                </button>
              </div>
              {error ? <p className="text-xs text-red-700">{error}</p> : null}
            </div>
          ) : null}
        </div>
      ) : (
        <p className="p-3 text-neutral-500">
          Pilih blok dari pratinjau atau daftar untuk memeriksa detail.
        </p>
      )}

      {report?.warnings.length ? (
        <div className="border-t border-neutral-200 p-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
            Peringatan dokumen
          </h3>
          <ul className="mt-1 space-y-0.5 text-xs text-neutral-600">
            {report.warnings.map((warning, index) => (
              <li key={index}>
                [{warning.code}]
                {warning.page ? ` (hlm ${warning.page})` : ""} {warning.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

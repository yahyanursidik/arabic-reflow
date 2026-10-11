"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { BlockUpdate, TextRepairResult, UiBlock, UiReflow, UiReport } from "@/lib/contract";
import { needsReview, repairCandidates, searchKey } from "@/lib/review";
import { collapseWarnings, compactMessage } from "@/lib/warnings";
import { ErrorNotice } from "./Feedback";
import { ImageAltEditor } from "./ImageAltEditor";

type Update = BlockUpdate;
type Filter = "all" | "review" | "arabic" | "ocr" | "edited";
const labels: Record<string, string> = {
  paragraph: "Paragraf",
  heading: "Judul",
  quote: "Kutipan",
  list: "Daftar",
  image: "Gambar",
  table: "Tabel",
  footnote: "Catatan kaki",
  page_break: "Pemisah halaman",
};

function BlockEditor({
  block,
  disabled,
  onSave,
  onDirtyChange,
}: {
  block: UiBlock;
  disabled: boolean;
  onSave: (id: string, update: Update) => Promise<void>;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [text, setText] = useState(block.text);
  const [lang, setLang] = useState(block.lang ?? "unknown");
  const [dir, setDir] = useState(block.dir ?? "ltr");
  const [kind, setKind] = useState<"paragraph" | "heading" | "quote">(
    block.type as "paragraph" | "heading" | "quote",
  );
  const [level, setLevel] = useState(block.level ?? 2);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const dirty =
    text !== block.text ||
    lang !== (block.lang ?? "unknown") ||
    dir !== (block.dir ?? "ltr") ||
    kind !== block.type ||
    (kind === "heading" && level !== (block.level ?? 2));
  useEffect(() => {
    onDirtyChange(dirty);
    return () => onDirtyChange(false);
  }, [dirty, onDirtyChange]);

  async function save() {
    if (!dirty || busy || disabled) return;
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const update: Update = {};
      if (text !== block.text) update.text = text;
      if (lang !== (block.lang ?? "unknown")) update.lang = lang;
      if (dir !== (block.dir ?? "ltr")) update.dir = dir;
      if (kind !== block.type) update.type = kind;
      if (kind === "heading" && (kind !== block.type || level !== block.level))
        update.level = level;
      await onSave(block.id, update);
      setSaved(true);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Suntingan gagal disimpan.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="mt-5 space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
      aria-busy={busy}
    >
      <div className="grid gap-3 min-[440px]:grid-cols-2">
        <div className="text-sm text-stone">
          <label htmlFor="block-type">Jenis blok</label>
          <select
            id="block-type"
            className="field mt-1"
            value={kind}
            disabled={busy || disabled}
            onChange={(event) => setKind(event.target.value as typeof kind)}
          >
            <option value="paragraph">Paragraf</option>
            <option value="heading">Judul / subjudul</option>
            <option value="quote">Kutipan</option>
          </select>
        </div>
        {kind === "heading" ? (
          <div className="text-sm text-stone">
            <label htmlFor="heading-level">Level judul</label>
            <select
              id="heading-level"
              className="field mt-1"
              value={level}
              disabled={busy || disabled}
              onChange={(event) => setLevel(Number(event.target.value))}
            >
              {[1, 2, 3, 4, 5, 6].map((value) => (
                <option value={value} key={value}>
                  {value === 1 ? "H1 — judul utama" : `H${value} — subjudul`}
                </option>
              ))}
            </select>
          </div>
        ) : null}
      </div>
      <label className="block text-sm font-medium" htmlFor="block-text">
        Teks hasil ekstraksi
      </label>
      <textarea
        id="block-text"
        className="field min-h-48 text-base leading-relaxed"
        dir={dir}
        lang={lang}
        rows={5}
        value={text}
        disabled={busy || disabled}
        onChange={(event) => {
          setText(event.target.value);
          setSaved(false);
        }}
      />
      <div className="grid gap-3 min-[440px]:grid-cols-2">
        <label className="text-sm text-stone" htmlFor="block-lang">
          Kode bahasa
          <input
            id="block-lang"
            className="field mt-1"
            value={lang}
            placeholder="id, ar, en"
            disabled={busy || disabled}
            onChange={(event) => setLang(event.target.value)}
          />
        </label>
        <label className="text-sm text-stone" htmlFor="block-direction">
          Arah baca
          <select
            id="block-direction"
            className="field mt-1"
            value={dir}
            disabled={busy || disabled}
            onChange={(event) => setDir(event.target.value)}
          >
            <option value="ltr">Kiri → kanan</option>
            <option value="rtl">Kanan → kiri</option>
          </select>
        </label>
      </div>
      <p className="text-sm leading-relaxed text-stone">
        Suntingan ini hanya mengubah hasil EPUB, bukan PDF sumber. Teks campuran
        tetap diberi penanda arah baca.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          className="btn-primary"
          type="submit"
          disabled={!dirty || !text.trim() || !lang.trim() || busy || disabled}
        >
          {busy ? "Menyimpan…" : "Simpan suntingan"}
        </button>
        <button
          className="btn-secondary"
          type="button"
          disabled={!dirty || busy || disabled}
          onClick={() => {
            setText(block.text);
            setLang(block.lang ?? "unknown");
            setDir(block.dir ?? "ltr");
            setKind(block.type as typeof kind);
            setLevel(block.level ?? 2);
            setError(null);
          }}
        >
          Batalkan perubahan
        </button>
      </div>
      <p role="status" className="text-xs text-graphite">
        {dirty
          ? "Ada perubahan yang belum disimpan."
          : saved
            ? "Suntingan tersimpan."
            : "Tidak ada perubahan yang belum disimpan."}
      </p>
      {error ? <ErrorNotice message={error} /> : null}
    </form>
  );
}

export function BlockInspector({
  blocks,
  report,
  selectedId,
  onSelect,
  onSave,
  onRenderImage,
  onRestoreText,
  onRepairText,
  onRepairProblems,
  onDirtyChange,
  onMove,
  disabled = false,
}: {
  blocks: UiBlock[];
  report: UiReport | null;
  reflow: UiReflow;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onSave: (id: string, update: Update) => Promise<void>;
  onRenderImage: (id: string) => Promise<void>;
  onRestoreText: (id: string) => Promise<void>;
  onRepairText: (id: string) => Promise<TextRepairResult>;
  onRepairProblems: (ids: string[]) => Promise<TextRepairResult>;
  onDirtyChange: (dirty: boolean) => void;
  onMove: (id: string, direction: "up" | "down") => Promise<void>;
  disabled?: boolean;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [acting, setActing] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const selected = blocks.find((block) => block.id === selectedId);
  const low = useMemo(
    () =>
      new Set([
        ...(report?.integrity?.lowConfidenceBlockIds ?? []),
        ...(report?.quality?.reviewBlockIds ?? []),
      ]),
    [report],
  );
  const filters: { id: Filter; label: string }[] = [
    { id: "all", label: "Semua" },
    { id: "review", label: "Perlu ditinjau" },
    { id: "arabic", label: "Arab" },
    { id: "ocr", label: "OCR" },
    { id: "edited", label: "Disunting" },
  ];
  const match = (block: UiBlock, value: Filter) =>
    value === "all" ||
    (value === "review" && needsReview(block, low)) ||
    (value === "arabic" && (
      /\p{Script=Arabic}/u.test(block.text) ||
      block.warnings.includes("ARABIC_RENDERED_AS_IMAGE")
    )) ||
    (value === "ocr" && block.warnings.some((w) => w.includes("OCR"))) ||
    (value === "edited" && block.modifiedByUser);
  const visible = blocks.filter(
    (block) =>
      match(block, filter) &&
      searchKey(
        `${block.text} ${block.alt ?? ""} ${labels[block.type]} ${block.page ?? ""}`,
      ).includes(searchKey(query)),
  );
  const editable =
    selected && ["paragraph", "heading", "quote"].includes(selected.type)
    && !selected.nodes.some((node) => node.kind === "image");
  const asImage = selected?.warnings.includes("ARABIC_RENDERED_AS_IMAGE");
  const locked = disabled || acting;
  const candidates = repairCandidates(blocks, low);
  const selectedIndex = visible.findIndex((block) => block.id === selectedId);
  const previous = visible[selectedIndex - 1];
  const next = visible[selectedIndex + 1];

  useEffect(() => {
    const list = listRef.current;
    const row = list?.querySelector<HTMLButtonElement>('[aria-current="true"]');
    if (!list || !row || !list.clientHeight) return;
    // Scroll only the block list. Selecting a block must not jump the page.
    list.scrollTop = Math.max(0, row.offsetTop - (list.clientHeight - row.offsetHeight) / 2);
  }, [selectedId, filter, query]);

  function choose(id: string) {
    onSelect(id);
    setError(null);
    setMessage(null);
  }

  // Stable callback so the editor's dirty-state effect does not rerun on each
  // parent render (polls, search, selection).
  const dirtyCallback = useMemo(
    () => (value: boolean) => {
      setDirty(value);
      onDirtyChange(value);
    },
    [onDirtyChange],
  );

  async function action(run: () => Promise<void | TextRepairResult>, description: string) {
    if (locked || dirty) return;
    setActing(true);
    setError(null);
    setMessage(null);
    try {
      const result = await run();
      setMessage(result
        ? `${result.changedBlockIds.length} blok diperbaiki. ${result.unchangedBlockIds.length} blok tanpa perubahan yang aman. ${result.skippedBlockIds.length} blok dilewati. ${result.reviewBlockIds.length} blok tetap perlu ditinjau. Teks awal blok yang diubah dapat dipulihkan.`
        : description);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Tindakan gagal. Coba lagi.",
      );
    } finally {
      setActing(false);
    }
  }

  return (
    <div className="block-inspector min-w-0 rounded-card border border-black/10 bg-white text-base">
      <div className="border-b border-black/10 p-5 sm:p-6">
        <h2 className="text-lg font-semibold">Periksa & sunting blok</h2>
        <label className="sr-only" htmlFor="block-search">
          Cari teks, jenis blok, atau halaman
        </label>
        <input
          id="block-search"
          type="search"
          className="field mt-4 text-base"
          placeholder="Cari teks atau halaman…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <div className="mt-4 flex flex-wrap gap-2">
          {filters.map((option) => (
            <button
              key={option.id}
              type="button"
              aria-pressed={filter === option.id}
              onClick={() => setFilter(option.id)}
              className={`min-h-11 whitespace-nowrap rounded-button px-3 py-2 text-sm font-medium ${filter === option.id ? "bg-notion-blue text-white" : "bg-paper-warmth text-graphite hover:bg-sky-tint"}`}
            >
              {option.label}{" "}
              <span>
                {blocks.filter((block) => match(block, option.id)).length}
              </span>
            </button>
          ))}
        </div>
        <p className="mt-3 text-sm text-stone">
          {visible.length} dari {blocks.length} blok
        </p>
        <button
          type="button"
          className="btn-secondary mt-4 w-full"
          disabled={locked || dirty || candidates.length === 0}
          onClick={() => void action(
            () => onRepairProblems(candidates.map((block) => block.id)),
            "Perbaikan otomatis selesai.",
          )}
        >
          {acting ? "Memproses…" : `Perbaiki otomatis (${candidates.length})`}
        </button>
        <p className="mt-3 text-sm leading-relaxed text-stone">
          Mencakup seluruh dokumen, melewati blok yang sudah disunting. Kata OCR
          yang meragukan tetap perlu diperiksa.
        </p>
        {message ? <p role="status" className="mt-3 text-xs text-notion-blue">{message}</p> : null}
        {error ? <div className="mt-3"><ErrorNotice message={error} /></div> : null}
      </div>
      <ul ref={listRef} aria-label="Daftar blok" className="relative max-h-72 min-h-24 overflow-y-auto overscroll-contain border-b border-black/10 py-2">
        {visible.map((block) => (
          <li key={block.id}>
            <button
              type="button"
              disabled={locked}
              aria-current={block.id === selectedId ? "true" : undefined}
              onClick={() => choose(block.id)}
              className={`flex min-h-16 w-full items-start gap-3 border-l-2 px-4 py-3 text-left ${block.id === selectedId ? "border-notion-blue bg-sky-tint" : "border-transparent hover:bg-paper-warmth"}`}
            >
              <span
                className={`mt-2 h-2 w-2 shrink-0 rounded-full ${needsReview(block, low) ? "bg-vermillion" : "bg-black/20"}`}
                aria-hidden="true"
              />
              <span className="min-w-0 flex-1">
                <span className="block line-clamp-2 break-words leading-relaxed" dir="auto">
                  {block.text.replace(/\s+/g, " ").trim() || block.alt || labels[block.type]}
                </span>
                <span className="mt-1 block text-sm text-stone">
                  {labels[block.type]}{block.page ? ` · Hlm ${block.page}` : ""}
                </span>
              </span>
              {needsReview(block, low) ? (
                <span className="sr-only">Perlu ditinjau</span>
              ) : null}
            </button>
          </li>
        ))}
        {!visible.length ? (
          <li className="p-4 text-sm text-stone">
            Tidak ada blok yang cocok. Coba kata kunci atau filter lain.
          </li>
        ) : null}
      </ul>
      <div className="p-5 sm:p-6">
        <nav aria-label="Navigasi blok" className="mb-5 border-b border-black/10 pb-5">
          <div className="grid gap-3 min-[440px]:grid-cols-2">
            <button type="button" className="btn-secondary whitespace-nowrap" aria-label="Blok sebelumnya"
              disabled={locked || !previous} onClick={() => previous && choose(previous.id)}>
              ← Sebelumnya
            </button>
            <button type="button" className="btn-secondary whitespace-nowrap" aria-label="Blok berikutnya"
              disabled={locked || !next} onClick={() => next && choose(next.id)}>
              Berikutnya →
            </button>
          </div>
          <p className="mt-3 text-sm text-stone" aria-live="polite">
            {selectedIndex >= 0 ? `Blok ${selectedIndex + 1} dari ${visible.length}`
              : selected ? "Pilihan saat ini di luar hasil pencarian." : "Pilih blok dari daftar atau pratinjau."}
          </p>
        </nav>
        {selected ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-lg font-semibold">
                {labels[selected.type]}
                {selected.page ? ` · halaman ${selected.page}` : ""}
              </h3>
              {selected.modifiedByUser ? (
                <span className="text-xs text-notion-blue">
                  Disunting pengguna
                </span>
              ) : null}
            </div>
            <p className="mt-2 text-sm leading-relaxed text-stone">
              Bahasa: {selected.lang ?? "belum diketahui"} · Arah:{" "}
              {selected.dir === "rtl" ? "kanan ke kiri" : "kiri ke kanan"}
            </p>
            <section aria-label="Perbaikan blok" className="mt-5 border-y border-black/10 py-5">
              <div className="grid gap-3 min-[440px]:grid-cols-2">
                <button
                  type="button"
                  className="btn-primary whitespace-nowrap"
                  disabled={locked || dirty || !editable}
                  onClick={() => void action(() => onRepairText(selected.id), "Perbaikan selesai.")}
                >
                  Perbaiki teks
                </button>
                <button
                  type="button"
                  className="btn-secondary whitespace-nowrap"
                  disabled={locked || dirty || !editable || !selected.page}
                  onClick={() => void action(() => onRenderImage(selected.id), "Blok dijadikan gambar dari PDF. Gunakan Pulihkan teks awal untuk kembali ke teks.")}
                >
                  Jadikan gambar
                </button>
                <button
                  type="button"
                  className="btn-secondary whitespace-nowrap min-[440px]:col-span-2"
                  disabled={locked || dirty || !report?.restorableBlockIds.includes(selected.id)}
                  onClick={() => void action(() => onRestoreText(selected.id), "Teks sebelum suntingan pertama dipulihkan.")}
                >
                  Pulihkan teks awal
                </button>
              </div>
              <p className="mt-4 text-sm leading-relaxed text-stone">
                Perbaiki teks menangani bentuk huruf, karakter tak valid, dan arah
                teks tanpa menebak kata. Gambar mengikuti PDF, tetapi tidak bisa
                dicari atau mengalir. Teks awal disimpan sebelum perubahan.
              </p>
              {!editable ? <p className="mt-2 text-xs text-stone">{selected.nodes.some((node) => node.kind === "image") ? "Paragraf ini memuat gambar Arab dari PDF sumber. Pulihkan teks awal pada catatan induknya sebelum menyunting teks." : "Pilih paragraf, judul, atau kutipan untuk memperbaiki teks atau menjadikannya gambar."}</p> : null}
              {dirty ? <p className="mt-2 text-xs text-stone">Simpan atau batalkan suntingan sebelum menjalankan perbaikan.</p> : null}
            </section>
            {collapseWarnings(selected.warnings).length ? (
              <ul className="mt-3 space-y-1 text-xs text-graphite">
                {collapseWarnings(selected.warnings).map((warning) => (
                  <li key={warning.code}>
                    • {warning.label}
                    {warning.needsReview ? " — bandingkan dengan sumber" : ""}
                  </li>
                ))}
              </ul>
            ) : null}
            {editable ? (
              <BlockEditor
                key={`${selected.id}:${selected.text}:${selected.lang}:${selected.dir}:${selected.type}:${selected.level}`}
                block={selected}
                disabled={locked}
                onSave={onSave}
                onDirtyChange={dirtyCallback}
              />
            ) : selected.type === "image" ? (
              <ImageAltEditor
                key={`${selected.id}:${selected.alt}`}
                block={selected}
                disabled={locked}
                onSave={onSave}
                onDirtyChange={dirtyCallback}
              />
            ) : (
              <p className="mt-3 text-sm text-graphite">
                {asImage
                  ? "Teks disimpan sebagai gambar sumber. Anda dapat mengembalikannya ke teks."
                  : "Blok ini dapat ditinjau di pratinjau; penyuntingan teks hanya tersedia untuk paragraf, judul, dan kutipan."}
              </p>
            )}
            <div className="mt-5 border-t border-black/10 pt-5">
              <p className="mb-3 text-sm font-medium">Atur urutan baca</p>
              <div className="grid gap-3">
                <button
                  type="button"
                  className="btn-secondary whitespace-nowrap"
                  disabled={locked || dirty || selected.canMoveUp === false}
                  onClick={() =>
                    void action(
                      () => onMove(selected.id, "up"),
                      "Blok dipindahkan satu posisi ke atas.",
                    )
                  }
                >
                  Pindahkan ke atas
                </button>
                <button
                  type="button"
                  className="btn-secondary whitespace-nowrap"
                  disabled={locked || dirty || selected.canMoveDown === false}
                  onClick={() =>
                    void action(
                      () => onMove(selected.id, "down"),
                      "Blok dipindahkan satu posisi ke bawah.",
                    )
                  }
                >
                  Pindahkan ke bawah
                </button>
              </div>
              <p className="mt-2 text-xs text-stone">
                Pemindahan hanya dalam kelompok yang sama. PDF sumber tidak
                berubah.
              </p>
            </div>
          </>
        ) : (
          <p className="text-sm leading-relaxed text-graphite">
            Klik teks di pratinjau atau pilih blok dari daftar. Halaman sumber
            akan mengikuti pilihan Anda.
          </p>
        )}
      </div>
      {report?.warnings.length ? (
        <details className="border-t border-black/10 p-5 sm:p-6">
          <summary className="cursor-pointer text-sm font-medium">
            Catatan dokumen ({report.warnings.length})
          </summary>
          <ul className="mt-2 max-h-32 space-y-2 overflow-y-auto text-xs text-graphite">
            {collapseWarnings(
              report.warnings.map((warning) => warning.code),
            ).map((warning) => (
              <li key={warning.code}>
                <strong>
                  {warning.label}
                  {warning.count > 1 ? ` ×${warning.count}` : ""}
                </strong>{" "}
                —{" "}
                {compactMessage(
                  report.warnings.find((item) => item.code === warning.code)
                    ?.message ?? "",
                )}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

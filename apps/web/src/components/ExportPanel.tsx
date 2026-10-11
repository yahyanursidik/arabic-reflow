"use client";

import { useEffect, useRef, useState } from "react";
import { api, bookApi } from "@/lib/api";
import { Profile, UiReflow, UiReport } from "@/lib/contract";
import { flattenBlocks } from "@/lib/review";
import { ErrorNotice } from "./Feedback";
import { ImageViewer } from "./ImageViewer";

type Operation = "metadata" | "cover" | "epub" | "json";

function saveDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export function ExportPanel({
  documentId, reflow, report, profile, onBookChanged,
  onDirtyChange, onBusyChange, disabled = false,
}: {
  documentId: string;
  reflow: UiReflow;
  report: UiReport | null;
  profile: Profile | null;
  onBookChanged: () => Promise<void>;
  onDirtyChange: (dirty: boolean) => void;
  onBusyChange: (busy: boolean) => void;
  disabled?: boolean;
}) {
  const [title, setTitle] = useState(reflow.title);
  const [authors, setAuthors] = useState(reflow.author.join(", "));
  const [coverPage, setCoverPage] = useState("1");
  const [previewCover, setPreviewCover] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [operation, setOperation] = useState<Operation | null>(null);
  const [feedbackFor, setFeedbackFor] = useState<Operation | null>(null);
  const [epubcheckAvailable, setEpubcheckAvailable] = useState(false);
  const [w3c, setW3c] = useState(false);
  const pending = useRef(false);

  useEffect(() => {
    let cancelled = false;
    void api.getCapabilities().then((value) => {
      if (!cancelled) setEpubcheckAvailable(value.epubcheckAvailable);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const busy = operation !== null;
  const dirty = title !== reflow.title || authors !== reflow.author.join(", ");
  const hasContent = reflow.blocks.some((block) => block.type !== "page_break");
  const locked = busy || disabled;
  const coverNumber = Number(coverPage);
  const validCover = coverPage.trim() !== "" && Number.isInteger(coverNumber)
    && coverNumber >= 1 && coverNumber <= (profile?.pageCount ?? 0);
  const blockCount = report?.quality?.blockCount ?? flattenBlocks(reflow.blocks).length;
  const reviewCount = report?.quality?.reviewBlockIds.length;
  const blockedReason = !hasContent
    ? "Belum ada isi buku. Aktifkan OCR untuk PDF pindai lalu konversi ulang."
    : report?.quality?.canExport === false
      ? "Ada masalah yang menghalangi ekspor. Periksa hasil konversi sebelum mengunduh."
      : dirty
        ? "Simpan atau batalkan perubahan identitas buku sebelum mengunduh."
        : !title.trim()
          ? "Isi judul buku sebelum mengunduh."
          : disabled
            ? "Selesaikan proses atau simpan suntingan blok sebelum mengunduh."
            : null;

  useEffect(() => {
    onDirtyChange(dirty);
    return () => onDirtyChange(false);
  }, [dirty, onDirtyChange]);

  async function run(kind: Operation, action: () => Promise<unknown>, success: string, refresh = false) {
    if (pending.current || disabled) return;
    pending.current = true;
    setOperation(kind);
    setFeedbackFor(kind);
    onBusyChange(true);
    setFailure(null);
    setMessage(null);
    try {
      await action();
      if (refresh) await onBookChanged();
      setMessage(success);
    } catch (cause) {
      setFailure(cause instanceof Error ? cause.message : "Tindakan gagal. Coba lagi.");
    } finally {
      pending.current = false;
      setOperation(null);
      onBusyChange(false);
    }
  }

  function feedback(kind: Operation) {
    if (feedbackFor !== kind) return null;
    return <>
      {message ? <p role="status" className="mt-4 text-sm leading-relaxed text-notion-blue">{message}</p> : null}
      {failure ? <div className="mt-4"><ErrorNotice message={failure} /></div> : null}
    </>;
  }

  return (
    <section id="ekspor" className="export-panel scroll-mt-6 rounded-card border border-black/10 bg-white p-4 py-6 sm:p-6"
      aria-busy={busy} aria-labelledby="export-heading">
      <header className="mb-6">
        <p className="text-sm font-medium text-notion-blue">Langkah terakhir</p>
        <h2 id="export-heading" className="mt-2 text-2xl font-semibold">Siapkan buku & unduh</h2>
        <p className="mt-2 text-sm leading-relaxed text-graphite">
          Atur identitas dan sampul bila perlu, lalu unduh buku. Suntingan yang
          sudah disimpan akan disertakan dalam EPUB.
        </p>
      </header>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <section id="epub-download" aria-labelledby="download-heading"
          className="min-w-0 scroll-mt-6 rounded-card border border-notion-blue/20 bg-sky-tint/40 p-4 sm:p-5 lg:col-start-2 lg:row-start-1 lg:sticky lg:top-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 id="download-heading" className="text-xl font-semibold">Unduh EPUB</h3>
            <p role="status" className={`rounded-button px-3 py-2 text-sm font-medium ${blockedReason ? "bg-paper-warmth text-graphite" : "bg-sky-tint text-notion-blue"}`}>
              {operation === "epub" ? "Menyiapkan EPUB…" : busy ? "Proses berlangsung…" : blockedReason ? "Belum siap" : "Siap diunduh"}
            </p>
          </div>
          <p className="mt-4 break-words text-lg font-semibold">{reflow.title}</p>
          <p className="mt-1 break-words text-sm leading-relaxed text-graphite">
            {reflow.author.length ? reflow.author.join(", ") : "Penulis belum diisi"}
          </p>
          <dl className="my-5 grid grid-cols-2 gap-3 border-y border-black/10 py-4">
            <div><dt className="text-sm text-stone">Isi buku</dt><dd className="mt-1 text-lg font-semibold">{blockCount} blok</dd></div>
            <div><dt className="text-sm text-stone">Perlu ditinjau</dt><dd className="mt-1 text-lg font-semibold">{reviewCount ?? "Belum diperiksa"}</dd></div>
          </dl>
          {blockedReason ? (
            <p className="mb-4 text-sm leading-relaxed text-graphite">{blockedReason}</p>
          ) : reviewCount ? (
            <p className="mb-4 text-sm leading-relaxed text-graphite">Masih ada {reviewCount} blok yang ditandai. Bandingkan dengan PDF sebelum mengunduh.</p>
          ) : null}
          {report?.warnings.some((warning) => warning.severity === "error") ? (
            <p className="mb-4 text-sm leading-relaxed text-vermillion">Ada peringatan berat. Periksa catatan dokumen sebelum mengunduh.</p>
          ) : null}
          <div className="rounded-button border border-black/10 bg-white p-3">
            <label className="flex min-h-12 cursor-pointer items-start gap-3 text-sm leading-relaxed text-graphite">
              <input type="checkbox" className="mt-1 h-5 w-5 shrink-0 accent-notion-blue" checked={w3c}
                disabled={locked || dirty || !epubcheckAvailable} onChange={(event) => setW3c(event.target.checked)} />
              <span>Validasi tambahan EPUBCheck W3C</span>
            </label>
            <p className="mt-2 text-sm leading-relaxed text-stone">
              {epubcheckAvailable ? "Tersedia. Pemeriksaan kompatibilitas tambahan dapat memerlukan beberapa detik."
                : "Belum tersedia. Pemeriksaan struktur EPUB tetap dijalankan saat unduh."}
            </p>
          </div>
          <button className="btn-primary export-download mt-5 w-full" type="button"
            disabled={locked || Boolean(blockedReason)}
            onClick={() => void run("epub", async () => {
              const data = await api.downloadEpub(documentId, w3c);
              saveDownload(data.blob, data.filename);
            }, "EPUB siap. Unduhan telah dimulai; periksa folder unduhan browser.")}>
            {operation === "epub" ? "Menyiapkan EPUB…" : "Unduh EPUB 3 ↓"}
          </button>
          <p className="mt-3 text-center text-sm text-stone">Format EPUB 3 · Bisa dibuka di aplikasi pembaca EPUB</p>
          {feedback("epub")}
          <nav aria-label="Pengaturan dan peninjauan buku" className="mt-4 grid gap-2 min-[440px]:grid-cols-2">
            <a href="#book-settings" className="btn-secondary">Atur buku ↓</a>
            <a href="#review" className="btn-secondary">Tinjau isi ↑</a>
          </nav>
          <details className="mt-5 border-t border-black/10 pt-2">
            <summary className="flex min-h-12 cursor-pointer items-center text-sm font-medium">Laporan & data tambahan ▾</summary>
            <div className="mt-2 grid gap-3">
              {(["reflow", "report"] as const).map((kind) => (
                <button className="btn-secondary w-full" key={kind} type="button" disabled={locked || dirty}
                  onClick={() => void run("json", async () => saveDownload(
                    await api.downloadJson(documentId, kind), `${kind}-${documentId.slice(0, 8)}.json`,
                  ), "Unduhan JSON dimulai.")}>
                  {kind === "reflow" ? "ReflowDoc JSON" : "Laporan kualitas"}
                </button>
              ))}
            </div>
            {feedback("json")}
          </details>
        </section>
        <div id="book-settings" className="min-w-0 space-y-5 scroll-mt-6 lg:col-start-1 lg:row-start-1">
          <form className="space-y-4 rounded-card border border-black/10 p-4 sm:p-5" aria-labelledby="book-settings-heading"
            onSubmit={(event) => {
              event.preventDefault();
              if (locked || !dirty || !title.trim()) return;
              void run("metadata", async () => {
                const saved = await bookApi.updateMetadata(documentId, {
                  title: title.trim(),
                  author: authors.split(",").map((author) => author.trim()).filter(Boolean),
                });
                setTitle(saved.title);
                setAuthors(saved.author.join(", "));
              }, "Identitas buku tersimpan.", true);
            }}>
            <h3 id="book-settings-heading" className="text-lg font-semibold">1. Identitas buku</h3>
            <p className="text-sm leading-relaxed text-stone">Judul dan penulis akan tampil di perpustakaan aplikasi pembaca.</p>
            <label className="block text-sm font-medium" htmlFor="book-title">
              Judul buku
              <input id="book-title" className="field mt-2" required value={title} maxLength={500}
                aria-invalid={!title.trim()} aria-describedby={!title.trim() ? "book-title-error" : undefined}
                disabled={locked} onChange={(event) => setTitle(event.target.value)} placeholder="Judul buku" />
            </label>
            {!title.trim() ? <p id="book-title-error" className="text-sm text-vermillion">Judul buku wajib diisi.</p> : null}
            <label className="block text-sm font-medium" htmlFor="book-authors">
              Penulis (pisahkan dengan koma)
              <input id="book-authors" className="field mt-2" value={authors}
                disabled={locked} onChange={(event) => setAuthors(event.target.value)} placeholder="Nama penulis" />
            </label>
            <div className="grid gap-3 min-[440px]:grid-cols-2">
              <button className="btn-secondary" type="submit" disabled={locked || !dirty || !title.trim()}>
                {operation === "metadata" ? "Menyimpan…" : "Simpan identitas"}
              </button>
              {dirty ? <button type="button" className="btn-secondary" disabled={locked}
                onClick={() => { setTitle(reflow.title); setAuthors(reflow.author.join(", ")); }}>Batalkan</button> : null}
            </div>
            {dirty ? <p role="status" className="text-sm leading-relaxed text-graphite">
              Simpan atau batalkan identitas sebelum mengunduh.
            </p> : null}
            {feedback("metadata")}
          </form>
          <details className="rounded-card border border-black/10 p-4 sm:p-5">
            <summary className="flex min-h-12 cursor-pointer flex-wrap items-center justify-between gap-2 text-lg font-semibold">
              <span>2. Sampul buku ▾</span><span className="text-sm font-normal text-stone">Opsional</span>
            </summary>
            <p className="mt-2 text-sm text-stone">{reflow.coverResourceId ? "Sampul sudah tersimpan." : "Belum ada sampul; buku tetap dapat diunduh."}</p>
            <div className="mt-4 space-y-4">
              <p className="text-sm leading-relaxed text-graphite">Gunakan salah satu halaman PDF sebagai sampul.</p>
              {profile && profile.pageCount > 0 ? <>
                <label className="block text-sm font-medium" htmlFor="cover-page">
                  Halaman sampul
                  <input id="cover-page" className="field mt-2" type="number" min={1} max={profile.pageCount}
                    inputMode="numeric" value={coverPage} disabled={locked || dirty}
                    aria-invalid={coverPage !== "" && !validCover} aria-describedby="cover-page-help"
                    onChange={(event) => setCoverPage(event.target.value)} />
                </label>
                <p id="cover-page-help" className={`text-sm ${coverPage !== "" && !validCover ? "text-vermillion" : "text-stone"}`}>
                  Pilih halaman 1–{profile.pageCount} dari PDF sumber.
                </p>
                <button type="button" className="btn-secondary w-full" aria-haspopup="dialog"
                  disabled={locked || !validCover} onClick={() => setPreviewCover(true)}>Lihat halaman sampul</button>
                <div className="grid gap-3">
                  <button className="btn-secondary" type="button" disabled={locked || dirty || !validCover}
                    onClick={() => void run("cover", () => bookApi.setCover(documentId, coverNumber),
                      `Halaman ${coverNumber} dipilih sebagai sampul.`, true)}>
                    {operation === "cover" ? "Menyimpan…" : "Gunakan sebagai sampul"}
                  </button>
                  {reflow.coverResourceId ? <button className="btn-secondary" type="button" disabled={locked || dirty}
                    onClick={() => void run("cover", () => bookApi.clearCover(documentId), "Sampul dihapus.", true)}>
                    Hapus sampul
                  </button> : null}
                </div>
              </> : null}
              {reflow.coverResourceId && reflow.resources[reflow.coverResourceId]?.dataUrl ? (
                <figure className="rounded-button border border-black/10 bg-paper-warmth p-4">
                  <img alt="Sampul buku yang dipilih" src={reflow.resources[reflow.coverResourceId]?.dataUrl}
                    className="mx-auto h-auto max-h-56 max-w-full rounded-small object-contain" />
                  <figcaption className="mt-3 text-center text-sm text-stone">Sampul yang sudah tersimpan</figcaption>
                </figure>
              ) : null}
              {feedback("cover")}
            </div>
          </details>
          <a href="#epub-download" className="btn-secondary w-full">↑ Kembali ke tombol unduh</a>
        </div>
      </div>
      {previewCover && validCover ? <ImageViewer src={api.sourcePageUrl(documentId, coverNumber)}
        alt={`Calon sampul dari halaman ${coverNumber} PDF sumber`} title={`Pratinjau sampul · halaman ${coverNumber}`}
        onClose={() => setPreviewCover(false)} /> : null}
    </section>
  );
}

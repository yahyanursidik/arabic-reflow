"use client";

import { useState } from "react";

import { ApiError, api, bookApi } from "@/lib/api";
import { Profile, UiReflow, UiReport } from "@/lib/contract";

export function ExportPanel({
  documentId,
  reflow,
  report,
  profile,
  onBookChanged,
}: {
  documentId: string;
  reflow: UiReflow | null;
  report: UiReport | null;
  profile: Profile | null;
  onBookChanged: () => Promise<void>;
}) {
  const blocking = (report?.warnings ?? []).filter((w) => w.severity === "error");
  const [title, setTitle] = useState(reflow?.title ?? "");
  const [authors, setAuthors] = useState((reflow?.author ?? []).join(", "));
  const [coverPage, setCoverPage] = useState(1);
  const [saved, setSaved] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function download() {
    const response = await fetch(
      `${api.baseUrl}/api/v1/documents/${documentId}/export/epub`,
      { method: "POST" },
    );
    if (!response.ok) {
      alert(`Ekspor gagal (${response.status}).`);
      return;
    }
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") ?? "";
    const match = /filename="?([^";]+)"?/.exec(disposition);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = match?.[1] ?? "document.epub";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setSaved(null);
    setFailure(null);
    try {
      await action();
      await onBookChanged();
      setSaved(message);
    } catch (cause) {
      setFailure(
        cause instanceof ApiError || cause instanceof Error
          ? cause.message
          : "gagal menyimpan",
      );
    } finally {
      setBusy(false);
    }
  }

  const hasCover = Boolean(reflow?.coverResourceId);

  return (
    <section className="rounded-card border border-black/8 bg-pure-white p-6 text-sm">
      <h2 className="text-caption font-semibold uppercase tracking-wide text-stone">
        Buku &amp; Ekspor
      </h2>

      <div className="mt-3 space-y-2">
        <label className="block">
          <span className="text-xs text-stone">Judul buku</span>
          <input
            className="mt-0.5 w-full rounded-button border border-black/15 px-2 py-1.5 text-sm"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Judul dari PDF (bisa disunting)"
          />
        </label>
        <label className="block">
          <span className="text-xs text-stone">Penulis (pisahkan dengan koma)</span>
          <input
            className="mt-0.5 w-full rounded-button border border-black/15 px-2 py-1.5 text-sm"
            value={authors}
            onChange={(event) => setAuthors(event.target.value)}
            placeholder="Imam Muslim, an-Nawawi"
          />
        </label>
        <div className="flex items-center gap-2">
          <button
            className="rounded-button bg-notion-blue px-3 py-1.5 text-xs font-medium text-pure-white hover:opacity-90 disabled:opacity-50"
            disabled={busy || !reflow}
            onClick={() =>
              void run(
                () =>
                  bookApi.updateMetadata(documentId, {
                    title: title,
                    author: authors
                      .split(",")
                      .map((a) => a.trim())
                      .filter(Boolean),
                  }),
                "Metadata tersimpan.",
              )
            }
            type="button"
          >
            Simpan metadata
          </button>
          {profile && profile.pageCount > 0 ? (
            <>
              <select
                className="rounded-button border border-black/15 p-1 text-xs"
                value={coverPage}
                onChange={(event) => setCoverPage(Number(event.target.value))}
              >
                {Array.from({ length: profile.pageCount }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>
                    hlm {n}
                  </option>
                ))}
              </select>
              <button
                className="rounded-button border border-black/15 px-3 py-1.5 text-xs hover:bg-paper-warmth disabled:opacity-50"
                disabled={busy || !reflow}
                onClick={() => void run(() => bookApi.setCover(documentId, coverPage), `Sampul: halaman ${coverPage}.`)}
                type="button"
              >
                Jadikan sampul
              </button>
              {hasCover ? (
                <button
                  className="rounded-button border border-black/15 px-3 py-1.5 text-xs hover:bg-paper-warmth disabled:opacity-50"
                  disabled={busy || !reflow}
                  onClick={() => void run(() => bookApi.clearCover(documentId), "Sampul dihapus.")}
                  type="button"
                >
                  Hapus sampul
                </button>
              ) : null}
            </>
          ) : null}
        </div>
        {hasCover ? (
          <p className="text-xs text-graphite">
            Sampul aktif dari halaman sumber — ikut dalam paket EPUB.
          </p>
        ) : null}
        {saved ? <p className="text-xs text-graphite">{saved}</p> : null}
        {failure ? (
          <p className="text-xs text-vermillion">{failure}</p>
        ) : null}
      </div>

      <p className="mt-3 text-graphite">
        EPUB 3 divalidasi sebelum diunduh. Suntingan Anda pada blok dan buku
        ikut dalam paket.
      </p>
      {blocking.length > 0 ? (
        <p className="mt-2 rounded-small border-l-2 border-coral bg-paper-warmth px-3 py-2 text-vermillion">
          {blocking.length} peringatan berat — periksa sebelum mengekspor.
        </p>
      ) : null}
      <button
        className="mt-4 rounded-button bg-notion-blue px-4 py-2 text-sm font-medium text-pure-white hover:opacity-90"
        onClick={() => void download()}
        type="button"
      >
        Unduh EPUB
      </button>
    </section>
  );
}

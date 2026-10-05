"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, api } from "@/lib/api";

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(selected: File) {
    setBusy(true);
    setError(null);
    try {
      const meta = await api.upload(selected);
      router.push(`/documents/${meta.id}`);
    } catch (cause) {
      setError(
        cause instanceof ApiError || cause instanceof Error
          ? cause.message
          : "gagal mengunggah",
      );
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-24">
      <p className="text-caption font-medium uppercase tracking-wide text-stone">
        Reflow — mesin rekonstruksi dokumen
      </p>
      <h1 className="mt-4 text-5xl font-semibold tracking-[-1.89px] text-ink-black">
        Ubah PDF jadi{" "}
        <span className="inline-block rounded-pill bg-peach px-6 py-1 text-ink-black">
          EPUB 3
        </span>{" "}
        yang mengalir.
      </h1>
      <p className="mt-5 max-w-xl font-lyon-text text-lg leading-relaxed text-graphite">
        Konversi dokumen campuran Arab&#8211;Latin menjadi buku digital yang
        bersih, semantik, dan enak dibaca di ukuran layar apa pun.
      </p>

      <form
        className="mt-12 rounded-card border border-black/8 bg-pure-white p-6"
        onSubmit={(event) => {
          event.preventDefault();
          if (file) void submit(file);
        }}
      >
        <label
          className="block text-sm font-medium text-ink-black"
          htmlFor="pdf-input"
        >
          Unggah dokumen PDF
        </label>
        <p className="mt-1 text-sm text-stone">
          Hanya PDF asli (maks. 100 MB). PDF terenkripsi tidak diterima.
        </p>
        <input
          id="pdf-input"
          className="mt-4 block w-full rounded-button text-sm text-ink-black file:mr-3 file:rounded-button file:border file:border-black/15 file:bg-pure-white file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink-black hover:file:bg-sky-tint"
          type="file"
          accept="application/pdf,.pdf"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <div className="mt-5 flex items-center gap-3">
          <button
            className="rounded-button bg-notion-blue px-4 py-2 text-sm font-medium text-pure-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            disabled={!file || busy}
            type="submit"
          >
            {busy ? "Mengunggah…" : "Unggah & buka dokumen"}
          </button>
          {file ? (
            <span className="text-sm text-stone">{file.name}</span>
          ) : null}
        </div>
        {error ? (
          <p className="mt-4 rounded-small border-l-2 border-coral bg-pure-white px-3 py-2 text-sm text-vermillion">
            {error}
          </p>
        ) : null}
      </form>
    </main>
  );
}

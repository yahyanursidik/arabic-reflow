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
    <main className="mx-auto max-w-2xl px-6 py-24">
      <h1 className="text-2xl font-semibold tracking-tight">Reflow</h1>
      <p className="mt-3 leading-relaxed text-neutral-700">
        Konversi PDF campuran Arab&#8211;Latin menjadi EPUB 3 yang bersih,
        semantik, dan reflowable.
      </p>
      <p className="mt-1 leading-relaxed text-neutral-500">
        Pertahankan sumber. Rekonstruksi struktur. Jangan mengarang.
      </p>

      <form
        className="mt-10 border border-dashed border-neutral-300 p-8"
        onSubmit={(event) => {
          event.preventDefault();
          if (file) void submit(file);
        }}
      >
        <label className="block text-sm font-medium text-neutral-900" htmlFor="pdf-input">
          Unggah dokumen PDF
        </label>
        <p className="mt-1 text-sm text-neutral-500">
          Hanya PDF asli (maks. 100 MB). PDF terenkripsi tidak diterima.
        </p>
        <input
          id="pdf-input"
          className="mt-4 block w-full text-sm text-neutral-900 file:mr-3 file:border file:border-neutral-300 file:bg-white file:px-3 file:py-2 file:text-sm hover:file:bg-neutral-50"
          type="file"
          accept="application/pdf,.pdf"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <button
          className="mt-4 border border-neutral-900 bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
          disabled={!file || busy}
          type="submit"
        >
          {busy ? "Mengunggah…" : "Unggah & buka dokumen"}
        </button>
        {error ? (
          <p className="mt-4 border-l-2 border-red-600 pl-3 text-sm text-red-700">
            {error}
          </p>
        ) : null}
      </form>
    </main>
  );
}

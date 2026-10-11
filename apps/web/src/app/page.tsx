"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ErrorNotice, WorkflowSteps } from "@/components/Feedback";
import { api } from "@/lib/api";
import { DocumentMeta } from "@/lib/contract";
import { formatBytes, validatePdf } from "@/lib/files";
import { recentDocuments, rememberDocument } from "@/lib/history";

export default function UploadPage() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<DocumentMeta[]>([]);
  useEffect(() => setRecent(recentDocuments()), []);

  function choose(selected: File | null) {
    if (submitting.current) return;
    const problem = selected ? validatePdf(selected) : null;
    setError(problem);
    setFile(problem ? null : selected);
    if (problem && input.current) input.current.value = "";
  }

  async function submit() {
    if (!file || submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError(null);
    try {
      const meta = await api.upload(file);
      rememberDocument(meta);
      router.push(`/documents/${meta.id}`);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unggah gagal. Silakan coba lagi.",
      );
      submitting.current = false;
      setBusy(false);
    }
  }

  return (
    <main
      id="main-content"
      className="mx-auto max-w-5xl px-4 py-10 sm:px-8 sm:py-16"
    >
      <WorkflowSteps step={1} />
      <div className="grid grid-cols-1 items-start gap-8 lg:grid-cols-[1.35fr_1fr] lg:gap-12">
        <section className="min-w-0">
          <p className="text-sm font-medium text-notion-blue">
            Dokumen Arab–Latin, lebih nyaman dibaca
          </p>
          <h1 className="mt-3 text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
            Dari PDF ke buku
            <br className="hidden sm:block" /> yang mengalir.
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-graphite">
            Ubah PDF menjadi EPUB yang menyesuaikan layar. Tinjau teks,
            bandingkan dengan sumber, lalu unduh buku Anda.
          </p>
          <form
            className="panel mt-7"
            aria-busy={busy}
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
          >
            <h2 className="font-semibold">Mulai dengan PDF Anda</h2>
            <p
              id="upload-help"
              className="mt-1 text-sm leading-relaxed text-stone"
            >
              Maksimal 100 MB. PDF dengan kata sandi tidak didukung.
            </p>
            <div
              className={`mt-4 rounded-button border-2 border-dashed p-5 text-center ${dragging ? "border-notion-blue bg-sky-tint" : "border-black/15 bg-paper-warmth/50"}`}
              onDragOver={(event) => {
                event.preventDefault();
                if (!busy) setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                if (event.dataTransfer.files.length > 1) {
                  setError("Unggah satu PDF setiap kali.");
                  return;
                }
                choose(event.dataTransfer.files[0] ?? null);
              }}
            >
              <p className="mb-3 text-sm text-graphite">
                Tarik PDF ke sini atau pilih dari perangkat
              </p>
              <label className="sr-only" htmlFor="pdf-input">
                Pilih dokumen PDF
              </label>
              <input
                ref={input}
                id="pdf-input"
                type="file"
                accept="application/pdf,.pdf"
                disabled={busy}
                aria-describedby="upload-help"
                className="block w-full text-sm file:mr-3 file:rounded-button file:border file:border-black/15 file:bg-white file:px-3 file:py-2 file:text-sm"
                onChange={(event) => choose(event.target.files?.[0] ?? null)}
              />
            </div>
            {file ? (
              <div className="mt-4 flex items-center justify-between gap-3 rounded-button bg-paper-warmth p-3 text-sm">
                <div className="min-w-0">
                  <p className="break-all font-medium">{file.name}</p>
                  <p className="mt-1 text-xs text-stone">
                    {formatBytes(file.size)} · Siap diunggah
                  </p>
                </div>
                <button
                  type="button"
                  className="shrink-0 text-notion-blue"
                  disabled={busy}
                  onClick={() => {
                    choose(null);
                    if (input.current) input.current.value = "";
                  }}
                >
                  Ganti
                </button>
              </div>
            ) : null}
            {error ? (
              <div className="mt-4">
                <ErrorNotice message={error} />
              </div>
            ) : null}
            <button
              className="btn-primary mt-5 w-full"
              disabled={!file || busy}
              type="submit"
            >
              {busy ? "Mengunggah PDF…" : "Unggah & lanjutkan →"}
            </button>
            <p
              role="status"
              className="mt-3 text-xs leading-relaxed text-stone"
            >
              {busy
                ? "Tunggu hingga unggahan selesai. Dokumen akan terbuka otomatis."
                : "Dokumen diproses oleh server Reflow yang Anda gunakan, tanpa layanan AI eksternal."}
            </p>
          </form>
        </section>
        <aside id="panduan" className="min-w-0 scroll-mt-6 lg:pt-2">
          <img src="/brand/arabic-reflow-logo.png" alt="Logo Arabic Reflow" width={1254} height={1254}
            className="mx-auto mb-6 h-auto w-52 max-w-full" />
          <h2 className="text-lg font-semibold">Bagaimana cara kerjanya?</h2>
          <ol className="mt-5 space-y-5">
            {[
              [
                "1",
                "Unggah & konversi",
                "Analisis jenis PDF. Aktifkan OCR jika dokumen berisi halaman pindai.",
              ],
              [
                "2",
                "Tinjau dengan sumber",
                "Pilih teks di pratinjau untuk melihat halaman asal dan memperbaiki hasil ekstraksi.",
              ],
              [
                "3",
                "Siapkan & unduh buku",
                "Atur judul, penulis, dan sampul. Unduh EPUB setelah memeriksa hasilnya.",
              ],
            ].map(([number, title, description]) => (
              <li key={number} className="flex gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-black/15 text-xs font-semibold">
                  {number}
                </span>
                <div>
                  <h3 className="text-sm font-semibold">{title}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-graphite">
                    {description}
                  </p>
                </div>
              </li>
            ))}
          </ol>
          <div className="mt-7 border-t border-black/10 pt-5 text-sm leading-relaxed text-graphite">
            <p className="font-medium text-charcoal">
              Bukan salinan tata letak PDF
            </p>
            <p className="mt-1">
              EPUB menyusun ulang teks agar nyaman dibaca. Teks Arab dan harakat
              tidak ditulis ulang otomatis. OCR memerlukan mesin yang terpasang
              di server.
            </p>
          </div>
          {recent.length ? (
            <section className="mt-7 border-t border-black/10 pt-5">
              <h2 className="text-sm font-semibold">Buka kembali dokumen</h2>
              <p className="mt-1 text-xs text-stone">
                Riwayat browser ini; tersedia selama berkas masih ada di server.
              </p>
              <ul className="mt-3 space-y-2">
                {recent.map((item) => (
                  <li key={item.id}>
                    <Link
                      href={`/documents/${item.id}`}
                      className="flex min-h-11 items-center justify-between gap-2 rounded-button border border-black/10 bg-white px-3 py-2 text-sm hover:border-notion-blue"
                    >
                      <span className="truncate">{item.filename}</span>
                      <span aria-hidden="true">→</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </aside>
      </div>
    </main>
  );
}

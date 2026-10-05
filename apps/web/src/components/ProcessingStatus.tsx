"use client";

import { useState } from "react";

import { Job } from "@/lib/contract";

const STAGE_LABELS: Record<string, string> = {
  uploaded: "Diunggah",
  analyzing: "Menganalisis",
  extracting: "Mengekstrak",
  ocr: "OCR",
  layout: "Tata letak",
  reading_order: "Urutan baca",
  arabic_analysis: "Analisis Arab",
  reconstruction: "Rekonstruksi",
  review_ready: "Siap direview",
  rendering: "Merender EPUB",
  validating: "Memvalidasi",
  completed: "Selesai",
  failed: "Gagal",
};

export function ProcessingStatus({
  job,
  onConvert,
}: {
  job: Job | null;
  onConvert: (ocr: boolean) => void;
}) {
  const [ocr, setOcr] = useState(false);
  const active = job?.status === "queued" || job?.status === "processing";

  return (
    <section className="border border-neutral-200 p-4 text-sm">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Konversi
      </h2>

      {!job || job.status === "completed" ? (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            className="border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
            disabled={active}
            onClick={() => onConvert(ocr)}
            type="button"
          >
            {job?.status === "completed" ? "Konversi ulang" : "Mulai konversi"}
          </button>
          <label className="flex items-center gap-2 text-neutral-700">
            <input
              checked={ocr}
              onChange={(event) => setOcr(event.target.checked)}
              type="checkbox"
            />
            OCR untuk halaman pindai
          </label>
        </div>
      ) : null}

      {active ? (
        <div className="mt-3">
          <p className="text-neutral-700">
            {STAGE_LABELS[job.stage] ?? job.stage} — {job.progress}%
          </p>
          <div className="mt-1 h-1 w-full bg-neutral-200">
            <div
              className="h-1 bg-neutral-900"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      ) : null}

      {job?.status === "failed" ? (
        <p className="mt-3 border-l-2 border-red-600 pl-3 text-red-700">
          Konversi gagal: {job.error ?? "penyebab tidak diketahui"}
        </p>
      ) : null}

      {job?.status === "completed" ? (
        <p className="mt-3 text-neutral-600">
          Selesai — {job.warnings.length} peringatan. Periksa pratinjau dan
          blok bermasalah sebelum mengekspor.
        </p>
      ) : null}
    </section>
  );
}

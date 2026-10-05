"use client";

import { useState } from "react";

import { Job, UiReflow } from "@/lib/contract";

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
  hasResults,
  onConvert,
}: {
  job: Job | null;
  hasResults: boolean;
  onConvert: (ocr: boolean) => void;
}) {
  const [ocr, setOcr] = useState(false);
  const active = job?.status === "queued" || job?.status === "processing";
  // Single chromatic action per screen: conversion is primary before results
  // exist; once results are in, re-conversion becomes the ghost alternative.
  const primary = !hasResults;

  return (
    <section className="rounded-card border border-black/8 bg-pure-white p-6 text-sm">
      <h2 className="text-caption font-semibold uppercase tracking-wide text-stone">
        Konversi
      </h2>

      {!job || job.status === "completed" ? (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            className={
              primary
                ? "rounded-button bg-notion-blue px-4 py-2 text-sm font-medium text-pure-white hover:opacity-90 disabled:opacity-40"
                : "rounded-button bg-sky-tint px-4 py-2 text-sm font-medium text-notion-blue hover:opacity-80 disabled:opacity-40"
            }
            disabled={active}
            onClick={() => onConvert(ocr)}
            type="button"
          >
            {job?.status === "completed" ? "Konversi ulang" : "Mulai konversi"}
          </button>
          <label className="flex items-center gap-2 text-graphite">
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
        <div className="mt-4">
          <p className="text-graphite">
            {STAGE_LABELS[job.stage] ?? job.stage} — {job.progress}%
          </p>
          <div className="mt-1.5 h-1 w-full rounded-pill bg-black/10">
            <div
              className="h-1 rounded-pill bg-notion-blue"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      ) : null}

      {job?.status === "failed" ? (
        <p className="mt-4 rounded-small border-l-2 border-coral bg-paper-warmth px-3 py-2 text-vermillion">
          Konversi gagal: {job.error ?? "penyebab tidak diketahui"}
        </p>
      ) : null}

      {job?.status === "completed" ? (
        <p className="mt-4 text-graphite">
          Selesai — {job.warnings.length} peringatan. Periksa pratinjau dan
          blok bermasalah sebelum mengekspor.
        </p>
      ) : null}
    </section>
  );
}

export type { UiReflow };

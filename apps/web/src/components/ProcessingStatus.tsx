"use client";

import { useEffect, useState } from "react";

import { Capabilities, ConversionOptions, Job, UiReflow } from "@/lib/contract";
import { api } from "@/lib/api";

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
  starting = false,
  disabled = false,
  scanned = false,
}: {
  job: Job | null;
  hasResults: boolean;
  onConvert: (options: ConversionOptions) => void;
  starting?: boolean;
  disabled?: boolean;
  scanned?: boolean;
}) {
  const [ocr, setOcr] = useState(false);
  const [mode, setMode] = useState<"auto" | "force">("auto");
  const [engine, setEngine] = useState<"" | "paddle" | "tesseract">("");
  const [languages, setLanguages] = useState<ConversionOptions["languages"]>([
    "ar",
    "id",
    "en",
  ]);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [capabilityError, setCapabilityError] = useState(false);
  const [probe, setProbe] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setCapabilityError(false);
    void api
      .getCapabilities()
      .then((data) => {
        if (!cancelled) setCapabilities(data);
      })
      .catch(() => {
        if (!cancelled) setCapabilityError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [probe]);
  const usable =
    capabilities?.ocr.engines.filter(
      (item) =>
        languages.every((language) => item.languages.includes(language)) &&
        (item.available || item.languages.length > 0),
    ) ?? [];
  const ocrReady = engine
    ? usable.some((item) => item.name === engine)
    : usable.length > 0;
  const active =
    starting || job?.status === "queued" || job?.status === "processing";
  // Single chromatic action per screen: conversion is primary before results
  // exist; once results are in, re-conversion becomes the ghost alternative.
  const primary = !hasResults;

  return (
    <section className="rounded-card border border-black/8 bg-pure-white p-6 text-sm">
      <h2 className="text-caption font-semibold uppercase tracking-wide text-stone">
        Konversi
      </h2>

      {!active ? (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            className={
              primary
                ? "rounded-button bg-notion-blue px-4 py-2 text-sm font-medium text-pure-white hover:opacity-90 disabled:opacity-40"
                : "rounded-button bg-sky-tint px-4 py-2 text-sm font-medium text-notion-blue hover:opacity-80 disabled:opacity-40"
            }
            disabled={active || disabled || (ocr && !ocrReady)}
            onClick={() =>
              onConvert({
                mode: ocr ? mode : "native",
                engine: engine || undefined,
                languages,
              })
            }
            type="button"
          >
            {hasResults
              ? "Konversi ulang"
              : job?.status === "failed"
                ? "Coba konversi lagi"
                : "Mulai konversi →"}
          </button>
          <label className="flex items-center gap-2 text-graphite">
            <input
              checked={ocr}
              disabled={active || disabled}
              onChange={(event) => setOcr(event.target.checked)}
              type="checkbox"
            />
            OCR untuk halaman pindai / teks rusak
          </label>
        </div>
      ) : null}

      {ocr && !active ? (
        <div className="mt-4 space-y-3 border-t border-black/10 pt-4">
          <label className="block text-xs text-stone" htmlFor="ocr-mode">
            Mode OCR
            <select
              id="ocr-mode"
              className="field mt-1"
              value={mode}
              disabled={disabled}
              onChange={(event) =>
                setMode(event.target.value as "auto" | "force")
              }
            >
              <option value="auto">Otomatis — hanya halaman yang perlu</option>
              <option value="force">
                Paksa — semua halaman dari gambar sumber
              </option>
            </select>
          </label>
          <label className="block text-xs text-stone" htmlFor="ocr-engine">
            Mesin OCR
            <select
              id="ocr-engine"
              className="field mt-1"
              value={engine}
              disabled={disabled}
              onChange={(event) =>
                setEngine(event.target.value as typeof engine)
              }
            >
              <option value="">Pilih otomatis dari mesin yang siap</option>
              {capabilities?.ocr.engines.map((item) => (
                <option value={item.name} key={item.name}>
                  {item.name === "paddle" ? "PaddleOCR" : "Tesseract"}
                  {usable.includes(item)
                    ? " — siap"
                    : " — belum siap untuk bahasa ini"}
                </option>
              ))}
            </select>
          </label>
          <fieldset disabled={disabled}>
            <legend className="mb-2 text-xs text-stone">
              Bahasa OCR (pilih minimal satu)
            </legend>
            <div className="flex flex-wrap gap-3">
              {(["ar", "id", "en"] as const).map((language) => (
                <label
                  className="flex min-h-9 items-center gap-2 text-xs"
                  key={language}
                >
                  <input
                    type="checkbox"
                    checked={languages.includes(language)}
                    disabled={
                      languages.length === 1 && languages.includes(language)
                    }
                    onChange={(event) =>
                      setLanguages(
                        event.target.checked
                          ? [...languages, language]
                          : languages.filter((value) => value !== language),
                      )
                    }
                  />
                  {{ ar: "Arab", id: "Indonesia", en: "Inggris" }[language]}
                </label>
              ))}
            </div>
          </fieldset>
          {mode === "force" ? (
            <p className="text-xs leading-relaxed text-[#a82a17]">
              Mode paksa mengganti hasil ekstraksi native dengan OCR pada semua
              halaman. Teks sumber PDF tetap utuh; hasil OCR harus diperiksa
              ulang.
            </p>
          ) : null}
          {!ocrReady ? (
            <p role="status" className="text-xs text-[#a82a17]">
              {capabilityError
                ? "Kesiapan OCR belum dapat diperiksa."
                : capabilities
                  ? "OCR belum siap untuk bahasa yang dipilih. Lengkapi mesin/data bahasa di server atau ubah pilihan bahasa."
                  : "Memeriksa kesiapan OCR…"}
            </p>
          ) : (
            <p className="text-xs text-graphite">
              Mesin siap untuk bahasa terpilih. Kualitas teks tetap perlu
              ditinjau.
            </p>
          )}
          <details>
            <summary className="cursor-pointer text-xs text-graphite">
              Status mesin & petunjuk pemasangan
            </summary>
            <ul className="mt-2 space-y-2 text-xs text-stone">
              {capabilities?.ocr.engines.map((item) => (
                <li key={item.name}>
                  <strong>{item.name}</strong>: {item.message}
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="mt-2 min-h-9 text-xs text-notion-blue underline"
              onClick={() => setProbe((value) => value + 1)}
            >
              Periksa kesiapan lagi
            </button>
          </details>
        </div>
      ) : null}

      {scanned && !active ? (
        <p className="mt-3 text-sm text-graphite">
          Ada halaman pindai. Aktifkan OCR agar teksnya terbaca; mesin OCR harus
          terpasang di server.
        </p>
      ) : null}
      {hasResults && !active ? (
        <p className="mt-3 text-xs text-stone">
          Konversi ulang mengganti hasil dan suntingan yang sudah disimpan. Anda
          akan diminta mengonfirmasi.
        </p>
      ) : null}

      {active ? (
        <div className="mt-4" role="status">
          <p className="text-graphite">
            {starting
              ? "Memulai konversi…"
              : job
                ? `${STAGE_LABELS[job.stage] ?? job.stage} — ${job.progress}%`
                : "Memproses…"}
          </p>
          <div
            role="progressbar"
            aria-label="Progres konversi"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={job?.progress ?? 0}
            className="mt-1.5 h-1 w-full rounded-pill bg-black/10"
          >
            <div
              className="h-1 rounded-pill bg-notion-blue"
              style={{ width: `${job?.progress ?? 0}%` }}
            />
          </div>
          <p className="mt-3 text-xs text-stone">
            Anda boleh tetap di halaman ini. Hasil ditampilkan otomatis saat
            proses selesai.
          </p>
        </div>
      ) : null}

      {job?.status === "failed" ? (
        <p
          role="alert"
          className="mt-4 rounded-small border-l-2 border-coral bg-paper-warmth px-3 py-2 text-vermillion"
        >
          Konversi gagal: {job.error ?? "penyebab tidak diketahui"}
        </p>
      ) : null}

      {job?.status === "completed" ? (
        <p className="mt-4 text-graphite">
          Konversi selesai. Periksa pratinjau dan blok yang ditandai perlu
          ditinjau sebelum mengekspor.
        </p>
      ) : null}
    </section>
  );
}

export type { UiReflow };

"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AnalysisSummary } from "@/components/AnalysisSummary";
import { BlockInspector } from "@/components/BlockInspector";
import { ExportPanel } from "@/components/ExportPanel";
import { ProcessingStatus } from "@/components/ProcessingStatus";
import { ReflowPreview } from "@/components/ReflowPreview";
import { ApiError, api } from "@/lib/api";
import {
  DocumentMeta,
  Job,
  Profile,
  UiReflow,
  UiReport,
} from "@/lib/contract";

export default function DocumentWorkspace() {
  const params = useParams<{ id: string }>();
  const documentId = params.id;

  const [meta, setMeta] = useState<DocumentMeta | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [reflow, setReflow] = useState<UiReflow | null>(null);
  const [report, setReport] = useState<UiReport | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadResults = useCallback(async () => {
    try {
      const [reflowData, reportData] = await Promise.all([
        api.getReflow(documentId),
        api.getReport(documentId),
      ]);
      setReflow(reflowData);
      setReport(reportData);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "gagal memuat hasil");
    }
  }, [documentId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [metaData, profileData, jobData] = await Promise.all([
          api.getDocument(documentId),
          api.getProfile(documentId),
          api.getDocumentJob(documentId),
        ]);
        if (cancelled) return;
        setMeta(metaData);
        setProfile(profileData);
        setJob(jobData);
        if (jobData?.status === "completed") {
          await loadResults();
        }
      } catch (cause) {
        if (!cancelled) {
          setLoadError(
            cause instanceof ApiError && cause.status === 404
              ? "Dokumen tidak ditemukan di server API."
              : cause instanceof Error
                ? cause.message
                : "gagal memuat dokumen",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [documentId, loadResults]);

  // Poll while a conversion runs (M8-03).
  useEffect(() => {
    if (!job || (job.status !== "queued" && job.status !== "processing")) {
      return;
    }
    const timer = setInterval(async () => {
      try {
        const updated = await api.getDocumentJob(documentId);
        setJob(updated);
        if (updated?.status === "completed") {
          await loadResults();
        }
      } catch {
        // transient polling errors are tolerated; next tick retries
      }
    }, 700);
    return () => clearInterval(timer);
  }, [job, documentId, loadResults]);

  async function runAnalyze() {
    setError(null);
    try {
      setProfile(await api.analyze(documentId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "analisis gagal");
    }
  }

  async function runConvert(ocr: boolean) {
    setError(null);
    setReflow(null);
    setReport(null);
    try {
      const { jobId } = await api.convert(documentId, ocr);
      setJob(await api.getJob(jobId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "konversi gagal dimulai");
    }
  }

  async function saveBlock(
    blockId: string,
    update: { text?: string; lang?: string; dir?: string },
  ) {
    await api.updateBlock(documentId, blockId, update);
    await loadResults();
  }

  if (loadError) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-24">
        <p className="rounded-card border border-black/8 bg-pure-white p-4 text-vermillion">
          {loadError}
        </p>
        <a
          className="mt-4 inline-block rounded-button px-2 py-1 text-sm text-ink-black/60 hover:text-ink-black"
          href="/"
        >
          ← kembali ke unggahan
        </a>
      </main>
    );
  }

  const converting = job?.status === "queued" || job?.status === "processing";

  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-heading-sm font-semibold text-ink-black">
            {meta?.filename ?? "…"}
          </h1>
          <p className="text-caption text-stone">
            {meta ? `${Math.round(meta.size / 1024)} KB · ${meta.id.slice(0, 8)}` : ""}
          </p>
        </div>
        <a
          className="rounded-button px-2 py-1 text-sm text-ink-black/60 hover:text-ink-black"
          href="/"
        >
          ← dokumen lain
        </a>
      </header>

      {error ? (
        <p className="mt-4 rounded-small border-l-2 border-coral bg-pure-white px-3 py-2 text-sm text-vermillion">
          {error}
        </p>
      ) : null}

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {profile ? (
          <AnalysisSummary profile={profile} />
        ) : (
          <section className="rounded-card border border-black/8 bg-pure-white p-6 text-sm">
            <h2 className="text-caption font-semibold uppercase tracking-wide text-stone">
              Ringkasan analisis
            </h2>
            <p className="mt-2 text-graphite">Dokumen belum dianalisis.</p>
            <button
              className="mt-4 rounded-button bg-sky-tint px-4 py-2 text-sm font-medium text-notion-blue hover:opacity-80"
              onClick={() => void runAnalyze()}
              type="button"
            >
              Analisis dokumen
            </button>
          </section>
        )}
        <ProcessingStatus
          hasResults={reflow !== null}
          job={job}
          onConvert={(ocr) => void runConvert(ocr)}
        />
      </div>

      {reflow ? (
        <>
          <div className="mt-8 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-heading-sm font-semibold text-ink-black">
              Review: sumber · pratinjau · inspektur
            </h2>
            <ExportPanel report={report} />
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <section className="text-sm">
              <div className="flex items-center gap-2">
                <h3 className="text-caption font-semibold uppercase tracking-wide text-stone">
                  Sumber
                </h3>
                {profile && profile.pageCount > 1 ? (
                  <select
                    className="rounded-button border border-black/15 p-0.5 text-xs"
                    onChange={(event) => setPage(Number(event.target.value))}
                    value={page}
                  >
                    {Array.from({ length: profile.pageCount }, (_, i) => i + 1).map((n) => (
                      <option key={n} value={n}>
                        hlm {n}
                      </option>
                    ))}
                  </select>
                ) : null}
              </div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                alt={`Halaman ${page} dokumen sumber`}
                className="mt-1 w-full rounded-card border border-black/8 bg-pure-white"
                src={api.sourcePageUrl(documentId, page)}
              />
            </section>
            <section>
              <h3 className="text-caption font-semibold uppercase tracking-wide text-stone">
                Pratinjau reflow
              </h3>
              <div className="mt-1">
                <ReflowPreview
                  onSelect={setSelectedId}
                  reflow={reflow}
                  selectedId={selectedId}
                />
              </div>
            </section>
            <section>
              <BlockInspector
                blocks={reflow.blocks}
                onSelect={setSelectedId}
                onSave={saveBlock}
                reflow={reflow}
                report={report}
                selectedId={selectedId}
              />
            </section>
          </div>
        </>
      ) : null}

      {converting ? null : !reflow && job?.status !== "failed" ? (
        <p className="mt-4 text-sm text-stone">
          Jalankan konversi untuk melihat pratinjau reflow.
        </p>
      ) : null}
    </main>
  );
}

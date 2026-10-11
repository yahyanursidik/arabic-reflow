"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AnalysisSummary } from "@/components/AnalysisSummary";
import { BlockInspector } from "@/components/BlockInspector";
import { ExportPanel } from "@/components/ExportPanel";
import {
  EmptyDocument,
  ErrorNotice,
  WorkflowSteps,
} from "@/components/Feedback";
import { ProcessingStatus } from "@/components/ProcessingStatus";
import { ReflowPreview } from "@/components/ReflowPreview";
import { SourcePage } from "@/components/SourcePage";
import { ApiError, api } from "@/lib/api";
import {
  ConversionOptions,
  DocumentMeta,
  Job,
  Profile,
  UiReflow,
  UiReport,
} from "@/lib/contract";
import { formatBytes } from "@/lib/files";
import { rememberDocument } from "@/lib/history";
import { flattenBlocks, needsReview } from "@/lib/review";
import { QualitySummary } from "@/components/QualitySummary";

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>();
  return <DocumentWorkspace key={id} documentId={id} />;
}

function DocumentWorkspace({ documentId }: { documentId: string }) {
  const [meta, setMeta] = useState<DocumentMeta | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [reflow, setReflow] = useState<UiReflow | null>(null);
  const [report, setReport] = useState<UiReport | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [resultError, setResultError] = useState<string | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [starting, setStarting] = useState(false);
  const [mutating, setMutating] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [blockDirty, setBlockDirty] = useState(false);
  const [bookDirty, setBookDirty] = useState(false);
  const [reload, setReload] = useState(0);
  const [mobilePane, setMobilePane] = useState("preview");
  const [pageOnly, setPageOnly] = useState(true);
  const readingPane = useRef<HTMLDivElement>(null);
  const mounted = useRef(false);
  const actionPending = useRef(false);
  const blockDirtyRef = useRef(false);
  const dirty = blockDirty || bookDirty;
  const allBlocks = flattenBlocks(reflow?.blocks ?? []);
  const active = job?.status === "queued" || job?.status === "processing";
  const locked = starting || active || mutating || exportBusy;

  const onBlockDirty = useCallback((value: boolean) => {
    blockDirtyRef.current = value;
    setBlockDirty(value);
  }, []);
  const onBookDirty = useCallback((value: boolean) => setBookDirty(value), []);
  const onExportBusy = useCallback(
    (value: boolean) => setExportBusy(value),
    [],
  );

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    const warnNavigation = (event: MouseEvent) => {
      if (
        event.button !== 0 ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.altKey
      )
        return;
      const link = (event.target as Element)?.closest<HTMLAnchorElement>(
        "a[href]",
      );
      if (
        !link ||
        link.target === "_blank" ||
        link.getAttribute("href")?.startsWith("#")
      )
        return;
      const destination = new URL(link.href, location.href);
      if (destination.pathname === location.pathname) return;
      if (
        !confirm("Ada perubahan yang belum disimpan. Tinggalkan dokumen ini?")
      ) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    document.addEventListener("click", warnNavigation, true);
    return () => {
      window.removeEventListener("beforeunload", warn);
      document.removeEventListener("click", warnNavigation, true);
    };
  }, [dirty]);

  const loadResults = useCallback(async () => {
    const [data, quality] = await Promise.all([
      api.getReflow(documentId),
      api.getReport(documentId),
    ]);
    if (!mounted.current) return;
    setReflow(data);
    setReport(quality);
    setResultError(null);
  }, [documentId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    (async () => {
      try {
        const [info, analysis, current] = await Promise.all([
          api.getDocument(documentId),
          api.getProfile(documentId),
          api.getDocumentJob(documentId),
        ]);
        if (cancelled) return;
        setMeta(info);
        rememberDocument(info);
        setProfile(analysis);
        setJob(current);
        setLoading(false);
        if (current?.status === "completed" || current?.status === "failed") {
          try {
            await loadResults();
          } catch (cause) {
            if (
              !cancelled &&
              !(
                current.status === "failed" &&
                cause instanceof ApiError &&
                cause.status === 404
              )
            )
              setResultError(
                cause instanceof Error
                  ? cause.message
                  : "Hasil belum dapat dimuat.",
              );
          }
        }
        if (
          !analysis &&
          current?.status !== "queued" &&
          current?.status !== "processing"
        ) {
          setAnalyzing(true);
          try {
            const analyzed = await api.analyze(documentId);
            if (!cancelled) setProfile(analyzed);
          } catch (cause) {
            if (!cancelled)
              setError(
                cause instanceof Error ? cause.message : "Analisis gagal.",
              );
          } finally {
            if (!cancelled) setAnalyzing(false);
          }
        }
      } catch (cause) {
        if (!cancelled) {
          setLoading(false);
          setLoadError(
            cause instanceof ApiError && cause.status === 404
              ? "Dokumen tidak ditemukan. Berkas mungkin sudah dihapus dari penyimpanan server. Unggah PDF kembali."
              : cause instanceof Error
                ? cause.message
                : "Dokumen gagal dimuat.",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [documentId, loadResults, reload]);

  // Sequential polling: no overlapping requests or silently stuck progress.
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;
    async function poll() {
      try {
        const updated = await api.getDocumentJob(documentId);
        if (cancelled) return;
        if (!updated)
          throw new Error(
            "Status konversi tidak ditemukan. Muat ulang halaman untuk mencoba lagi.",
          );
        failures = 0;
        setPollError(null);
        if (updated.status === "completed") {
          const analysis = await api.getProfile(documentId);
          if (cancelled) return;
          setProfile(analysis);
          try {
            await loadResults();
          } catch (cause) {
            if (!cancelled)
              setResultError(
                cause instanceof Error ? cause.message : "Hasil gagal dimuat.",
              );
          }
          if (!cancelled) setJob(updated);
          return;
        }
        setJob(updated);
        if (updated.status === "failed") return;
      } catch (cause) {
        if (cancelled) return;
        failures += 1;
        if (failures >= 3)
          setPollError(
            "Koneksi terputus. Status akan dicoba kembali otomatis; konversi di server tidak dibatalkan.",
          );
      }
      if (!cancelled)
        timer = setTimeout(() => void poll(), failures ? 2500 : 1000);
    }
    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [active, documentId, job?.id, loadResults]);

  async function analyze() {
    if (analyzing || locked) return;
    setAnalyzing(true);
    setError(null);
    try {
      setProfile(await api.analyze(documentId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Analisis gagal.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function convert(options: ConversionOptions) {
    if (actionPending.current || locked || analyzing || dirty) return;
    if (
      (reflow || options.mode === "force") &&
      !confirm(
        options.mode === "force"
          ? "OCR paksa akan membaca ulang semua halaman dari gambar PDF dan mengganti hasil native serta suntingan tersimpan. Lanjutkan?"
          : "Konversi ulang akan mengganti hasil, suntingan, identitas buku, dan sampul yang sudah disimpan. Lanjutkan?",
      )
    )
      return;
    actionPending.current = true;
    setStarting(true);
    setError(null);
    setResultError(null);
    try {
      const { jobId } = await api.convert(documentId, options);
      const current = await api.getJob(jobId);
      setSelectedId(null);
      setReflow(null);
      setReport(null);
      setJob(current);
      if (current.status === "completed") {
        setProfile(await api.getProfile(documentId));
        await loadResults();
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Konversi gagal dimulai.",
      );
      // The POST may have succeeded even if fetching its job failed.
      try {
        const recovered = await api.getDocumentJob(documentId);
        setJob(recovered);
        if (recovered?.status === "completed") {
          setProfile(await api.getProfile(documentId));
          await loadResults();
        }
      } catch {
        /* visible error remains */
      }
    } finally {
      actionPending.current = false;
      setStarting(false);
    }
  }

  async function mutate<T>(action: () => Promise<T>): Promise<T> {
    if (actionPending.current || active || exportBusy)
      throw new Error("Tunggu hingga proses saat ini selesai.");
    actionPending.current = true;
    setMutating(true);
    try {
      const result = await action();
      await loadResults();
      return result;
    } finally {
      actionPending.current = false;
      setMutating(false);
    }
  }

  function select(id: string | null) {
    if (locked || id === selectedId) return;
    if (
      blockDirtyRef.current &&
      !confirm(
        "Ada suntingan blok yang belum disimpan. Buang perubahan dan pindah ke blok lain?",
      )
    )
      return;
    onBlockDirty(false);
    setSelectedId(id);
    if (matchMedia("(max-width: 1279px)").matches) setMobilePane("inspector");
    const sourcePage = allBlocks.find((block) => block.id === id)?.page;
    if (sourcePage) {
      setPage(sourcePage);
      setPageInput(String(sourcePage));
    }
  }

  function goPage(value: number) {
    const target = Math.min(
      Math.max(Number.isFinite(value) ? Math.round(value) : page, 1),
      profile?.pageCount ?? 1,
    );
    setPage(target);
    setPageInput(String(target));
    if (target !== page && matchMedia("(max-width: 1279px)").matches) {
      readingPane.current?.scrollIntoView({ block: "start", behavior: "instant" });
    }
  }

  if (loadError)
    return (
      <main id="main-content" className="px-4 py-12">
        <EmptyDocument message={loadError} />
        <div className="mt-4 text-center">
          <button
            className="btn-secondary"
            onClick={() => setReload((value) => value + 1)}
            type="button"
          >
            Coba muat ulang
          </button>
        </div>
      </main>
    );
  if (loading)
    return (
      <main id="main-content" className="mx-auto max-w-5xl px-4 py-12">
        <WorkflowSteps step={2} />
        <div role="status" className="panel">
          Memuat dokumen dan status konversi…
        </div>
      </main>
    );

  const low = new Set([
    ...(report?.integrity?.lowConfidenceBlockIds ?? []),
    ...(report?.quality?.reviewBlockIds ?? []),
  ]);
  const flagged = allBlocks.filter((block) => needsReview(block, low));
  const flaggedIndex = flagged.findIndex((block) => block.id === selectedId);
  const previewDoc =
    reflow && pageOnly
      ? {
          ...reflow,
          blocks: reflow.blocks.filter(
            (block) => block.page === page || !block.page,
          ),
        }
      : reflow;

  return (
    <main
      id="main-content"
      className="mx-auto max-w-[1500px] px-4 py-8 sm:px-8"
    >
      <WorkflowSteps step={reflow ? 3 : 2} />
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs text-stone">Dokumen sumber</p>
          <h1 className="mt-1 break-all text-2xl font-semibold">
            {meta?.filename}
          </h1>
          <p className="mt-1 text-xs text-stone">
            {meta ? formatBytes(meta.size) : ""}
            {profile ? ` · ${profile.pageCount} halaman` : ""}
          </p>
        </div>
        <Link className="btn-secondary" href="/">
          ← Unggah PDF lain
        </Link>
      </header>
      {error ? (
        <div className="mt-5">
          <ErrorNotice message={error} />
        </div>
      ) : null}
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {profile ? (
          <AnalysisSummary profile={profile} />
        ) : (
          <section className="panel">
            <h2 className="text-sm font-semibold">Analisis dokumen</h2>
            <p className="mt-2 text-sm text-graphite" role="status">
              {analyzing
                ? "Memeriksa halaman, lapisan teks, dan kebutuhan OCR…"
                : "Analisis membantu memilih pengaturan konversi."}
            </p>
            <button
              className="btn-secondary mt-4"
              disabled={analyzing || locked}
              onClick={() => void analyze()}
              type="button"
            >
              {analyzing ? "Menganalisis…" : "Coba analisis"}
            </button>
          </section>
        )}
        <ProcessingStatus
          job={job}
          hasResults={Boolean(reflow)}
          onConvert={(ocr) => void convert(ocr)}
          starting={starting}
          disabled={loading || analyzing || dirty || mutating || exportBusy}
          scanned={Boolean(profile?.scannedPages.length)}
        />
      </div>
      {dirty ? (
        <p
          role="status"
          className="mt-4 rounded-button border border-[#d5bb78] bg-[#fff9e8] px-4 py-3 text-sm text-[#6f531b]"
        >
          Ada perubahan belum disimpan. Simpan atau batalkan sebelum konversi
          ulang atau unduh.
        </p>
      ) : null}
      {pollError ? (
        <div className="mt-4">
          <ErrorNotice message={pollError} />
        </div>
      ) : null}
      {resultError ? (
        <div className="mt-4">
          <ErrorNotice
            message={`Konversi selesai, tetapi hasil belum dapat ditampilkan. ${resultError}`}
            onRetry={() => {
              void loadResults().catch((cause) =>
                setResultError(
                  cause instanceof Error
                    ? cause.message
                    : "Hasil gagal dimuat.",
                ),
              );
            }}
          />
        </div>
      ) : null}
      {reflow && previewDoc ? (
        <>
          <section id="review" className="mt-8 scroll-mt-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-heading-sm font-semibold">
                  Tinjau hasil konversi
                </h2>
                <p className="mt-1 text-sm text-graphite">
                  Pilih blok untuk membandingkan teks dengan halaman sumber.
                </p>
              </div>
              <a href="#ekspor" className="btn-secondary">
                Lanjut ke unduh ↓
              </a>
            </div>
            <QualitySummary
              report={report}
              reflow={reflow}
              onSelect={select}
              onPage={goPage}
              disabled={locked || bookDirty}
            />
            <div className="review-navigation sticky top-0 z-10 mt-4 space-y-2 bg-paper-warmth py-2 xl:static">
              <nav
                className="grid grid-cols-3 gap-2 xl:hidden"
                aria-label="Panel peninjauan"
              >
                {[
                  { id: "source", label: "PDF sumber" },
                  { id: "preview", label: "Pratinjau" },
                  { id: "inspector", label: "Sunting blok" },
                ].map((pane) => (
                  <button
                    key={pane.id}
                    type="button"
                    className={`min-h-12 rounded-button px-2 py-3 text-sm font-medium ${mobilePane === pane.id ? "bg-notion-blue text-white" : "border border-black/15 bg-white"}`}
                    aria-pressed={mobilePane === pane.id}
                    onClick={() => {
                      setMobilePane(pane.id);
                      readingPane.current?.scrollIntoView({ block: "start", behavior: "instant" });
                    }}
                  >
                    {pane.label}
                  </button>
                ))}
              </nav>
              <nav aria-label="Navigasi halaman PDF"
                className="reading-controls grid grid-cols-[3rem_minmax(0,1fr)_3rem] items-center gap-2 rounded-card border border-black/10 bg-white p-3 sm:flex sm:gap-3">
                <button
                  className="btn-secondary px-0 text-xl sm:px-4"
                  type="button"
                  disabled={page <= 1}
                  aria-label="Halaman sumber sebelumnya"
                  onClick={() => goPage(page - 1)}
                >
                  ←<span className="ml-2 hidden text-base sm:inline">Sebelumnya</span>
                </button>
                <div className="flex min-w-0 items-center justify-center gap-2 sm:gap-3">
                <label htmlFor="source-page" className="sr-only text-sm text-stone sm:not-sr-only">
                  Halaman
                </label>
                <input
                  id="source-page"
                  type="number"
                  min={1}
                  max={profile?.pageCount ?? 1}
                  className="field w-16 px-2 text-center sm:w-20"
                  inputMode="numeric"
                  aria-describedby="source-page-count"
                  value={pageInput}
                  onChange={(event) => setPageInput(event.target.value)}
                  onBlur={() => goPage(pageInput ? Number(pageInput) : page)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter")
                      goPage(pageInput ? Number(pageInput) : page);
                  }}
                />
                <span id="source-page-count" className="shrink-0 text-sm text-stone">
                  dari {profile?.pageCount ?? "?"}
                </span>
                </div>
                <button
                  className="btn-secondary px-0 text-xl sm:px-4"
                  type="button"
                  disabled={page >= (profile?.pageCount ?? 1)}
                  aria-label="Halaman sumber berikutnya"
                  onClick={() => goPage(page + 1)}
                >
                  <span className="mr-2 hidden text-base sm:inline">Berikutnya</span>→
                </button>
              </nav>
            </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-stone">
                  {flagged.length
                    ? `${flagged.length} blok perlu ditinjau`
                    : "Tidak ada blok yang ditandai bermasalah"}
                </span>
                {flagged.length ? (
                  <button
                    className="btn-secondary"
                    disabled={locked}
                    type="button"
                    onClick={() => {
                      const next = flagged[(flaggedIndex + 1) % flagged.length];
                      if (next) select(next.id);
                      setMobilePane("inspector");
                    }}
                  >
                    Tinjau masalah berikutnya
                  </button>
                ) : null}
              </div>
            <div ref={readingPane} className="reading-panes mt-5 grid scroll-mt-48 items-start gap-6 xl:scroll-mt-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)_minmax(24rem,1.25fr)]">
              <section
                aria-label="PDF sumber"
                className={`min-w-0 xl:sticky xl:top-6 ${mobilePane === "source" ? "" : "hidden xl:block"}`}
              >
                <h3 className="mb-3 text-sm font-semibold text-stone">
                  PDF sumber · halaman {page}
                </h3>
                <SourcePage
                  key={documentId}
                  documentId={documentId}
                  page={page}
                />
              </section>
              <section
                aria-label="Pratinjau EPUB"
                className={`min-w-0 xl:sticky xl:top-6 ${mobilePane === "preview" ? "" : "hidden xl:block"}`}
              >
                <h3 className="mb-3 text-sm font-semibold text-stone">
                  Pratinjau EPUB ·{" "}
                  {pageOnly ? `halaman ${page}` : "seluruh dokumen"}
                </h3>
                <ReflowPreview
                  reflow={previewDoc}
                  selectedId={selectedId}
                  onSelect={select}
                  pageOnly={pageOnly}
                  onPageOnlyChange={setPageOnly}
                  viewKey={pageOnly ? `page:${page}` : "all"}
                  emptyMessage={
                    pageOnly && reflow.blocks.length
                      ? "Tidak ada blok hasil ekstraksi untuk halaman ini. Coba halaman lain atau tampilkan seluruh dokumen."
                      : undefined
                  }
                />
              </section>
              <section
                aria-label="Editor blok"
                className={`min-w-0 ${mobilePane === "inspector" ? "" : "hidden xl:block"}`}
              >
                <h3 className="mb-3 text-sm font-semibold text-stone">
                  Editor blok
                </h3>
                <BlockInspector
                  blocks={allBlocks}
                  reflow={reflow}
                  report={report}
                  selectedId={selectedId}
                  onSelect={select}
                  onDirtyChange={onBlockDirty}
                  onMove={(id, direction) =>
                    mutate(() => api.moveBlock(documentId, id, direction))
                  }
                  disabled={locked || bookDirty}
                  onSave={(id, update) =>
                    mutate(() => api.updateBlock(documentId, id, update)).then(() => undefined)
                  }
                  onRenderImage={(id) =>
                    mutate(() => api.renderBlockAsImage(documentId, id)).then(() => undefined)
                  }
                  onRestoreText={(id) =>
                    mutate(() => api.restoreBlockText(documentId, id)).then(() => undefined)
                  }
                  onRepairText={(id) =>
                    mutate(() => api.repairText(documentId, id))
                  }
                  onRepairProblems={(ids) =>
                    mutate(() => api.repairProblemBlocks(documentId, ids))
                  }
                />
              </section>
            </div>
          </section>
          <div className="mt-8">
            <ExportPanel
              documentId={documentId}
              reflow={reflow}
              report={report}
              profile={profile}
              onBookChanged={loadResults}
              onDirtyChange={onBookDirty}
              onBusyChange={onExportBusy}
              disabled={active || starting || mutating || blockDirty}
            />
          </div>
          <a
            href="#review"
            className="mt-4 inline-flex min-h-11 items-center text-sm text-notion-blue"
          >
            ↑ Kembali ke peninjauan
          </a>
        </>
      ) : !active && !starting && !resultError ? (
        <section className="panel mt-6 text-sm leading-relaxed text-graphite">
          <h2 className="font-semibold text-charcoal">Langkah selanjutnya</h2>
          <p className="mt-1">
            {job?.status === "failed"
              ? "Periksa penyebab kegagalan di atas, sesuaikan pilihan OCR bila perlu, lalu coba konversi lagi."
              : "Klik “Mulai konversi” untuk menyusun teks PDF menjadi buku. Setelah selesai, Anda dapat meninjau dan mengunduh hasilnya."}
          </p>
        </section>
      ) : null}
    </main>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { ErrorNotice } from "./Feedback";
import { ImageViewer, ImageZoomControls } from "./ImageViewer";

export function SourcePage({
  documentId,
  page,
}: {
  documentId: string;
  page: number;
}) {
  const [imageState, setImageState] = useState({ page, loaded: false, failed: false });
  const [attempt, setAttempt] = useState(0);
  const [zoom, setZoom] = useState(100);
  const [expanded, setExpanded] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);
  const loaded = imageState.page === page && imageState.loaded;
  const failed = imageState.page === page && imageState.failed;
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const center = () => {
      if (canvas.clientWidth) canvas.scrollLeft = (canvas.scrollWidth - canvas.clientWidth) / 2;
    };
    const observer = new ResizeObserver(center);
    observer.observe(canvas);
    center();
    return () => observer.disconnect();
  }, [page, zoom, loaded]);
  useEffect(() => {
    canvasRef.current?.scrollTo({ top: 0, behavior: "instant" });
  }, [page]);
  return (
    <div className="source-reader overflow-hidden rounded-card border border-black/10 bg-white">
      <div className="border-b border-black/10 p-4">
        <ImageZoomControls zoom={zoom} onZoom={setZoom} name="PDF sumber" disabled={!loaded} />
        {zoom > 100 ? <p className="mt-3 text-sm text-stone">Geser gambar ke samping untuk membaca bagian lainnya.</p> : null}
      </div>
      <div ref={canvasRef} role="region" tabIndex={loaded ? 0 : -1}
        aria-label={`Gambar PDF sumber halaman ${page}`}
        className="min-h-60 overflow-x-auto overscroll-x-contain p-2 xl:max-h-[65vh] xl:overflow-y-auto">
      {!loaded && !failed ? (
        <p role="status" className="p-4 text-sm text-stone">
          Memuat halaman {page}…
        </p>
      ) : null}
      {failed ? (
        <ErrorNotice
          message="Halaman sumber gagal dimuat. Periksa koneksi server."
          onRetry={() => {
            setImageState({ page, failed: false, loaded: false });
            setAttempt((value) => value + 1);
          }}
        />
      ) : null}
      <div style={{ width: `${zoom}%` }} className={failed ? "hidden" : "block"}>
        <img
          key={`${page}:${attempt}`}
          alt={`Halaman ${page} PDF sumber`}
          src={`${api.sourcePageUrl(documentId, page)}?attempt=${attempt}`}
          className={`h-auto w-full ${loaded ? "" : "hidden"}`}
          onLoad={() => setImageState({ page, loaded: true, failed: false })}
          onError={() => setImageState({ page, loaded: false, failed: true })}
        />
      </div>
      </div>
      {loaded ? (
        <div className="reading-controls border-t border-black/10 p-4">
          <button type="button" className="btn-secondary w-full" aria-haspopup="dialog"
            aria-expanded={expanded} onClick={() => setExpanded(true)}>
            Lihat PDF layar penuh
          </button>
        </div>
      ) : null}
      {expanded ? <ImageViewer src={api.sourcePageUrl(documentId, page)} alt={`Halaman ${page} PDF sumber`}
        title={`PDF sumber · halaman ${page}`} onClose={() => setExpanded(false)} /> : null}
    </div>
  );
}

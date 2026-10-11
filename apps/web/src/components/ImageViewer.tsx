"use client";

import { useEffect, useRef, useState } from "react";

export function ImageZoomControls({
  zoom,
  onZoom,
  name,
  disabled = false,
}: {
  zoom: number;
  onZoom: (value: number) => void;
  name: string;
  disabled?: boolean;
}) {
  return (
    <div className="reading-controls grid grid-cols-[3rem_minmax(0,1fr)_3rem] gap-2">
      <button type="button" className="btn-secondary px-0 text-xl"
        aria-label={`Perkecil ${name}`} disabled={disabled || zoom <= 100}
        onClick={() => onZoom(zoom - 50)}>−</button>
      <button type="button" className="btn-secondary px-2"
        aria-label={`Zoom ${zoom}%. Sesuaikan ${name} ke layar`}
        title="Sesuaikan ke lebar layar" disabled={disabled}
        onClick={() => onZoom(100)}>
        {zoom === 100 ? "Pas lebar" : `${zoom}%`}
      </button>
      <button type="button" className="btn-secondary px-0 text-xl"
        aria-label={`Perbesar ${name}`} disabled={disabled || zoom >= 300}
        onClick={() => onZoom(zoom + 50)}>+</button>
    </div>
  );
}

export function ImageViewer({ src, alt, title, onClose, initialZoom = 100, rtl = false }: {
  src: string;
  alt: string;
  title: string;
  onClose: () => void;
  initialZoom?: number;
  rtl?: boolean;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(initialZoom);
  useEffect(() => {
    const dialog = dialogRef.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas) canvas.scrollLeft = 0;
  }, [zoom, rtl]);

  function close() {
    dialogRef.current?.close();
    onClose();
  }

  return (
    <dialog ref={dialogRef} aria-label={title} onCancel={(event) => { event.preventDefault(); close(); }}
      className="image-viewer fixed inset-0 m-auto h-[100dvh] max-h-[100dvh] w-full max-w-none border-0 bg-white p-0 font-sans text-charcoal sm:h-[90dvh] sm:max-w-5xl sm:rounded-card">
      <div className="flex h-full min-h-0 flex-col">
        <header className="shrink-0 border-b border-black/10 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="min-w-0 text-base font-semibold">{title}</h2>
            <button type="button" className="btn-secondary min-h-12 shrink-0 text-base"
              onClick={close} autoFocus>Tutup ×</button>
          </div>
          <ImageZoomControls zoom={zoom} onZoom={setZoom} name="gambar" />
        </header>
        <div ref={canvasRef} role="region" tabIndex={0} dir={rtl ? "rtl" : "ltr"} aria-label="Gambar ukuran penuh; geser untuk melihat seluruh bagian"
          className="min-h-0 flex-1 overflow-auto overscroll-contain bg-paper-warmth p-2">
          <div style={{ width: `${zoom}%` }}>
            <img src={src} alt={alt} className="block h-auto w-full" />
          </div>
        </div>
        <p className="shrink-0 border-t border-black/10 px-4 py-3 text-sm text-stone">
          Perbesar dengan +, lalu geser untuk membaca. Pas lebar menampilkan gambar utuh.
        </p>
      </div>
    </dialog>
  );
}

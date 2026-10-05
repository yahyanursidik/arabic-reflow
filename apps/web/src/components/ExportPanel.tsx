"use client";

import { UiReport } from "@/lib/contract";

export function ExportPanel({ report }: { report: UiReport | null }) {
  const blocking = (report?.warnings ?? []).filter((w) => w.severity === "error");

  async function download() {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/documents/${
        window.location.pathname.split("/")[2]
      }/export/epub`,
      { method: "POST" },
    );
    if (!response.ok) {
      alert(`Ekspor gagal (${response.status}).`);
      return;
    }
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") ?? "";
    const match = /filename="?([^";]+)"?/.exec(disposition);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = match?.[1] ?? "document.epub";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  return (
    <section className="rounded-card border border-black/8 bg-pure-white p-6 text-sm">
      <h2 className="text-caption font-semibold uppercase tracking-wide text-stone">
        Ekspor
      </h2>
      <p className="mt-2 text-graphite">
        EPUB 3 divalidasi sebelum diunduh. Suntingan Anda pada blok ikut
        dalam paket.
      </p>
      {blocking.length > 0 ? (
        <p className="mt-2 rounded-small border-l-2 border-coral bg-paper-warmth px-3 py-2 text-vermillion">
          {blocking.length} peringatan berat — periksa sebelum mengekspor.
        </p>
      ) : null}
      <button
        className="mt-4 rounded-button bg-notion-blue px-4 py-2 text-sm font-medium text-pure-white hover:opacity-90"
        onClick={() => void download()}
        type="button"
      >
        Unduh EPUB
      </button>
    </section>
  );
}

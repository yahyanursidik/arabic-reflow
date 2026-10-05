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
    <section className="border border-neutral-200 p-4 text-sm">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Ekspor
      </h2>
      <p className="mt-2 text-neutral-700">
        EPUB 3 divalidasi sebelum diunduh. Suntingan Anda pada blok ikut
        dalam paket.
      </p>
      {blocking.length > 0 ? (
        <p className="mt-2 border-l-2 border-red-600 pl-3 text-red-700">
          {blocking.length} peringatan berat — periksa sebelum mengekspor.
        </p>
      ) : null}
      <button
        className="mt-3 border border-neutral-900 bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white"
        onClick={() => void download()}
        type="button"
      >
        Unduh EPUB
      </button>
    </section>
  );
}

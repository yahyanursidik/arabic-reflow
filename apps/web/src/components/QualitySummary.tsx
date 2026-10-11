"use client";

import { UiReflow, UiReport } from "@/lib/contract";
import { flattenBlocks } from "@/lib/review";

const issueLabels: Record<string, string> = {
  EMPTY_DOCUMENT: "Belum ada isi buku; periksa kebutuhan OCR.",
  DUPLICATE_BLOCK_IDS:
    "ID blok berulang; hasil perlu diperbaiki sebelum ekspor.",
  DUPLICATE_RESOURCE_IDS: "ID gambar/resource berulang.",
  MISSING_RESOURCE: "Gambar atau resource yang dirujuk belum tersedia.",
  INVALID_RESOURCE: "Resource gambar tidak memiliki data yang dapat digunakan.",
  MISSING_COVER_RESOURCE: "Resource sampul belum tersedia; pilih ulang sampul.",
  INVALID_COVER_RESOURCE:
    "Sampul tidak memiliki data gambar yang valid; pilih ulang sampul.",
  XML_INVALID_CHARACTERS:
    "Ada karakter kontrol yang tidak didukung XML EPUB. Karakter tersebut tidak disertakan dalam EPUB; PDF dan ReflowDoc asli tetap utuh. Periksa blok yang ditandai.",
};

export function QualitySummary({
  report,
  reflow,
  onSelect,
  onPage,
  disabled,
}: {
  report: UiReport | null;
  reflow: UiReflow;
  onSelect: (id: string) => void;
  onPage: (page: number) => void;
  disabled: boolean;
}) {
  const quality = report?.quality;
  const headings = flattenBlocks(reflow.blocks).filter(
    (block) => block.type === "heading",
  );
  return (
    <details className="panel mt-5" open>
      <summary className="cursor-pointer font-semibold">
        Kualitas & struktur buku
      </summary>
      {quality ? (
        <p className="mt-3 text-sm text-graphite">
          {quality.blockCount} blok · {quality.editedBlockCount} disunting ·{" "}
          {quality.reviewBlockIds.length} perlu ditinjau{" "}
          <span className="text-xs text-stone">
            (termasuk isi daftar dan catatan kaki)
          </span>
        </p>
      ) : null}
      <div className="mt-4 grid gap-5 md:grid-cols-2">
        <section className="min-w-0">
          <h3 className="text-sm font-semibold text-stone">
            Daftar judul
          </h3>
          {headings.length ? (
            <ul className="mt-2 max-h-44 overflow-y-auto">
              {headings.map((block) => (
                <li key={block.id}>
                  <button
                    type="button"
                    className="flex min-h-12 w-full items-center gap-3 rounded-button px-2 py-3 text-left text-sm hover:bg-paper-warmth disabled:opacity-50"
                    style={{
                      paddingInlineStart: `${Math.min((block.level ?? 1) - 1, 4) * 12 + 8}px`,
                    }}
                    disabled={disabled}
                    onClick={() => onSelect(block.id)}
                  >
                    <span className="shrink-0 text-xs text-stone">
                      H{block.level ?? 1}
                    </span>
                    <span className="min-w-0 flex-1 line-clamp-2 break-words leading-relaxed" dir="auto">
                      {block.text}
                    </span>
                    <span className="ml-auto shrink-0 text-xs text-stone">
                      {block.page ? `Hlm ${block.page}` : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-graphite">
              Belum ada judul. Pilih paragraf dan ubah “Jenis blok” menjadi
              judul untuk memperbaiki struktur.
            </p>
          )}
        </section>
        <section className="min-w-0">
          <h3 className="text-sm font-semibold text-stone">
            Halaman yang perlu ditinjau
          </h3>
          <div className="mt-2 flex max-h-44 flex-wrap gap-2 overflow-y-auto">
            {quality?.pages
              .filter((page) => page.reviewBlockIds.length)
              .map((page) => (
                <button
                  key={page.page}
                  type="button"
                  className="btn-secondary text-xs"
                  disabled={disabled}
                  onClick={() => {
                    onPage(page.page);
                    const first = page.reviewBlockIds[0];
                    if (first) onSelect(first);
                  }}
                >
                  Halaman {page.page} · {page.reviewBlockIds.length} blok
                </button>
              ))}
          </div>
          {!quality?.reviewBlockIds.length ? (
            <p className="mt-2 text-sm text-graphite">
              Tidak ada blok yang ditandai dalam pemeriksaan struktur. Tetap
              bandingkan hasil dengan sumber.
            </p>
          ) : null}
        </section>
      </div>
      {quality?.issues.length ? (
        <ul className="mt-4 space-y-2 border-t border-black/10 pt-3 text-sm">
          {quality.issues.map((issue, index) => (
            <li
              key={`${issue.code}:${index}`}
              className={
                issue.severity === "error" ? "text-[#a82a17]" : "text-graphite"
              }
            >
              {issueLabels[issue.code] ?? issue.message}
            </li>
          ))}
        </ul>
      ) : null}
    </details>
  );
}

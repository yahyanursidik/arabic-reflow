"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import { UiBlock, UiNode, UiReflow } from "@/lib/contract";
import { isolatedText } from "@/lib/review";
import { collapseWarnings } from "@/lib/warnings";
import { ImageViewer } from "./ImageViewer";

function InlineText({ nodes, reflow }: { nodes: UiNode[]; reflow: UiReflow }) {
  return (
    <>
      {nodes.map((node, index) => {
        if (node.kind === "image") {
          return <img key={index} src={reflow.resources[node.resourceId]?.dataUrl}
            alt={node.text} className="inline-source-image" />;
        }
        if (node.kind !== "span") return <span key={index}>{node.text}</span>;
        const parts = isolatedText(node.text);
        return (
          <Fragment key={index}>
            {parts.before}
            <bdi dir={node.dir ?? "auto"} lang={node.lang}>
              {parts.content}
            </bdi>
            {parts.after}
          </Fragment>
        );
      })}
    </>
  );
}

function SourceFigure({ src, alt, page, arabic = false, rtl = false }: { src: string; alt: string; page?: number; arabic?: boolean; rtl?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <figure>
      <img alt={alt} className={`mx-auto h-auto w-auto max-w-full ${arabic ? "source-arabic-image" : ""}`} src={src} />
      <figcaption className="mt-3 flex flex-wrap items-center justify-between gap-2 font-sans text-sm text-stone">
        <span>Gambar{page ? ` · halaman ${page}` : ""}</span>
        <button type="button" data-preview-action className="btn-secondary min-h-12 text-base"
          aria-haspopup="dialog" aria-expanded={expanded}
          onClick={(event) => { event.stopPropagation(); setExpanded(true); }}>
          Perbesar gambar
        </button>
      </figcaption>
      {expanded ? <ImageViewer src={src} alt={alt} title={`Gambar sumber${page ? ` · halaman ${page}` : ""}`}
        initialZoom={arabic ? 200 : 100} rtl={rtl} onClose={() => setExpanded(false)} /> : null}
    </figure>
  );
}

function BlockContent({
  block,
  reflow,
  selectedId,
}: {
  block: UiBlock;
  reflow: UiReflow;
  selectedId?: string | null;
}) {
  const common = { dir: block.dir, lang: block.lang };
  switch (block.type) {
    case "heading": {
      const Tag = `h${Math.min(Math.max(block.level ?? 1, 1), 6)}` as "h1";
      return (
        <Tag {...common}>
          <bdi>{block.text}</bdi>
        </Tag>
      );
    }
    case "paragraph":
      return (
        <p {...common}>
          <InlineText nodes={block.nodes} reflow={reflow} />
        </p>
      );
    case "quote":
      return (
        <blockquote {...common}>
          <bdi>{block.text}</bdi>
        </blockquote>
      );
    case "footnote":
      return (
        <aside
          {...common}
          className="reading-footnote"
          aria-label={`Catatan kaki ${block.marker}`}
        >
          <p className="footnote-label" dir="ltr">
            Catatan kaki {block.marker}
          </p>
          {block.blocks?.map((inner) => (
            <div
              key={inner.id}
              data-block-id={inner.id}
              className={
                selectedId === inner.id
                  ? "rounded-small bg-sky-tint outline outline-notion-blue"
                  : ""
              }
            >
              <BlockContent
                block={inner}
                reflow={reflow}
                selectedId={selectedId}
              />
            </div>
          ))}
        </aside>
      );
    case "image": {
      const resource = block.resourceId
        ? reflow.resources[block.resourceId]
        : undefined;
      return resource?.dataUrl ? (
        <SourceFigure src={resource.dataUrl} alt={block.alt ?? "Gambar dari dokumen sumber"} page={block.page}
          arabic={block.warnings.includes("ARABIC_RENDERED_AS_IMAGE")} rtl={block.dir === "rtl" || block.lang === "ar"} />
      ) : <p className="text-sm text-stone">Gambar tanpa pratinjau</p>;
    }
    case "list": {
      const Tag = block.ordered ? "ol" : "ul";
      return (
        <Tag
          {...common}
          className={`my-3 ms-6 ${block.ordered ? "list-decimal" : "list-disc"}`}
        >
          {block.items?.map((items, index) => (
            <li key={index}>
              {items.map((inner) => (
                <div
                  key={inner.id}
                  data-block-id={inner.id}
                  className={
                    selectedId === inner.id
                      ? "rounded-small bg-sky-tint outline outline-notion-blue"
                      : ""
                  }
                >
                  <BlockContent
                    block={inner}
                    reflow={reflow}
                    selectedId={selectedId}
                  />
                </div>
              ))}
            </li>
          ))}
        </Tag>
      );
    }
    case "table":
      if (!block.rows?.length) {
        const fallback = block.fallbackResourceId
          ? reflow.resources[block.fallbackResourceId]
          : undefined;
        return fallback?.dataUrl ? (
          <SourceFigure src={fallback.dataUrl} page={block.page}
            alt="Tabel dari halaman sumber; ekstraksi teks tabel belum dapat dipastikan" />
        ) : (
          <p className="font-sans text-sm text-stone">
            Tabel belum memiliki isi yang dapat ditampilkan. Bandingkan dengan
            PDF sumber.
          </p>
        );
      }
      return (
        <div className="my-3 overflow-x-auto">
          <table {...common}>
            <caption className="sr-only">
              Tabel dokumen{block.page ? ` halaman ${block.page}` : ""}
            </caption>
            <tbody>
              {block.rows?.map((row, index) => (
                <tr key={index}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} dir={cell.dir} lang={cell.lang}>
                      <bdi>{cell.text}</bdi>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case "page_break":
      return <hr className="my-4 border-black/10" />;
  }
}

export function ReflowPreview({
  reflow,
  selectedId,
  onSelect,
  pageOnly,
  onPageOnlyChange,
  viewKey,
  emptyMessage = "Belum ada teks hasil ekstraksi. Jika PDF berisi halaman pindai, aktifkan OCR lalu konversi ulang.",
}: {
  reflow: UiReflow;
  selectedId: string | null;
  onSelect: (id: string) => void;
  pageOnly: boolean;
  onPageOnlyChange: (value: boolean) => void;
  viewKey: string;
  emptyMessage?: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [fontSize, setFontSize] = useState(20);
  const [showStatus, setShowStatus] = useState(false);
  useEffect(() => {
    container.current?.scrollTo({ top: 0, behavior: "instant" });
  }, [viewKey]);
  useEffect(() => {
    if (!selectedId) return;
    const node = container.current?.querySelector<HTMLElement>(
      `[data-block-id="${CSS.escape(selectedId)}"]`,
    );
    const pane = container.current;
    if (node && pane) {
      const delta =
        node.getBoundingClientRect().top - pane.getBoundingClientRect().top;
      if (delta < 0 || delta + node.offsetHeight > pane.clientHeight)
        pane.scrollTo({
          top: pane.scrollTop + delta - 16,
          behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "auto"
            : "smooth",
        });
    }
  }, [selectedId]);
  return (
    <div className="overflow-hidden rounded-card border border-black/10 bg-white">
      <div className="reading-controls space-y-4 border-b border-black/10 p-4">
        <div>
          <label className="mb-2 block text-sm font-medium" htmlFor="preview-scope">Tampilkan pratinjau</label>
          <select id="preview-scope" className="field" value={pageOnly ? "page" : "all"}
            onChange={(event) => onPageOnlyChange(event.target.value === "page")}>
            <option value="page">Halaman PDF ini</option>
            <option value="all">Seluruh buku</option>
          </select>
        </div>
        <div className="grid grid-cols-[3rem_minmax(0,1fr)_3rem] items-center gap-2">
          <button type="button" className="btn-secondary px-0" aria-label="Perkecil teks pratinjau"
            disabled={fontSize <= 18} onClick={() => setFontSize(fontSize - 2)}>A−</button>
          <p className="text-center text-sm text-stone" aria-live="polite">Ukuran teks {fontSize} px</p>
          <button type="button" className="btn-secondary px-0" aria-label="Perbesar teks pratinjau"
            disabled={fontSize >= 26} onClick={() => setFontSize(fontSize + 2)}>A+</button>
        </div>
        <label className="flex min-h-12 cursor-pointer items-center gap-3 text-sm text-graphite">
          <input type="checkbox" className="h-5 w-5 shrink-0 accent-notion-blue" checked={showStatus}
            onChange={(event) => setShowStatus(event.target.checked)} />
          Tampilkan status pemeriksaan
        </label>
      </div>
      <div
      ref={container}
      role="region"
      tabIndex={0}
      aria-label="Teks pratinjau EPUB"
      style={{ fontSize }}
      className="reflow-preview min-h-60 p-3 sm:p-5 xl:max-h-[65vh] xl:overflow-y-auto"
    >
      {!reflow.blocks.length ? (
        <p className="font-sans text-sm leading-relaxed text-graphite">
          {emptyMessage}
        </p>
      ) : null}
      {reflow.blocks.map((block) => {
        const warnings = collapseWarnings(block.warnings);
        return (
          <div
            key={block.id}
            data-block-id={block.id}
            role="button"
            tabIndex={0}
            aria-pressed={selectedId === block.id}
            aria-label={`Pilih ${block.type === "paragraph" ? "paragraf" : "blok"}${block.page ? `, halaman ${block.page}` : ""}: ${block.text.slice(0, 80)}`}
            onClick={(event) =>
              !(event.target as Element).closest("[data-preview-action], dialog") && onSelect(
                (event.target as Element).closest<HTMLElement>(
                  "[data-block-id]",
                )?.dataset.blockId ?? block.id,
              )
            }
            onKeyDown={(event) => {
              if ((event.target as Element).closest("[data-preview-action], dialog")) return;
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelect(block.id);
              }
            }}
            className={`preview-block cursor-pointer rounded-small hover:bg-paper-warmth ${selectedId === block.id ? "bg-sky-tint/60 outline outline-notion-blue" : ""}`}
          >
            <BlockContent
              block={block}
              reflow={reflow}
              selectedId={selectedId}
            />
            {showStatus && warnings.length ? (
              <p className="preview-status font-sans text-sm leading-relaxed text-graphite">
                {warnings.map((warning) => warning.label).join(" · ")}
              </p>
            ) : null}
          </div>
        );
      })}
      </div>
    </div>
  );
}

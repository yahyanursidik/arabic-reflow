"use client";

import { useEffect, useRef } from "react";

import { UiBlock, UiReflow } from "@/lib/contract";
import { collapseWarnings } from "@/lib/warnings";

function nodesToJsx(block: UiBlock) {
  return block.nodes.map((node, index) => {
    if (node.kind === "span") {
      return (
        <bdi dir={node.dir ?? "auto"} key={index} lang={node.lang}>
          {node.text}
        </bdi>
      );
    }
    return <span key={index}>{node.text}</span>;
  });
}

function integrityNote(block: UiBlock): string | null {
  const parts = collapseWarnings(block.warnings)
    .map((warning) =>
      warning.count > 1 ? `${warning.label} ×${warning.count}` : warning.label,
    );
  if (
    block.integrityScore !== undefined &&
    block.integrityScore < 0.85 &&
    block.type === "paragraph"
  ) {
    parts.push(`skor integritas Arab ${Math.round(block.integrityScore * 100)}%`);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

function BlockView({
  block,
  reflow,
  onSelect,
  selected,
}: {
  block: UiBlock;
  reflow: UiReflow;
  onSelect: (id: string) => void;
  selected: boolean;
}) {
  const selectedClass = selected
    ? "rounded-small outline outline-1 outline-notion-blue bg-sky-tint/50"
    : "";
  const note = integrityNote(block);
  const common =
    "block cursor-pointer rounded-small px-2 py-1 transition-colors hover:bg-paper-warmth " +
    selectedClass;

  let body: React.ReactNode = null;
  switch (block.type) {
    case "heading": {
      const level = Math.min(Math.max(block.level ?? 1, 1), 6);
      const Tag = `h${level}` as "h1";
      body = (
        <Tag
          className={
            "font-notioninter font-semibold tracking-[-0.242px] " + common
          }
          dir={block.dir}
          lang={block.lang}
          onClick={() => onSelect(block.id)}
        >
          {block.text}
        </Tag>
      );
      break;
    }
    case "paragraph":
      body = (
        <p className={common} dir={block.dir} lang={block.lang} onClick={() => onSelect(block.id)}>
          {nodesToJsx(block)}
        </p>
      );
      break;
    case "quote":
      body = (
        <blockquote
          className={(block.dir === "rtl" ? "arabic " : "") + common}
          dir={block.dir}
          lang={block.lang}
          onClick={() => onSelect(block.id)}
        >
          {block.text}
        </blockquote>
      );
      break;
    case "footnote":
      body = (
        <aside
          className={
            "rounded-small border-l-2 border-mocha bg-paper-warmth px-3 py-2 " +
            common
          }
          onClick={() => onSelect(block.id)}
        >
          <p className="font-notioninter text-caption uppercase tracking-wide text-stone">
            Catatan kaki {block.marker}
          </p>
          {(block.blocks ?? []).map((inner) => (
            <p dir={inner.dir} key={inner.id} lang={inner.lang}>
              {inner.nodes.map((n) => n.text).join("")}
            </p>
          ))}
        </aside>
      );
      break;
    case "image": {
      const resource = block.resourceId ? reflow.resources[block.resourceId] : undefined;
      body = (
        <figure
          className={
            "space-y-1 " +
            (resource?.dataUrl ? common : "cursor-pointer rounded-small border border-dashed border-black/15 bg-paper-warmth px-3 py-2 text-center hover:bg-sky-tint/40 ")
          }
          onClick={() => onSelect(block.id)}
        >
          {resource?.dataUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              alt=""
              className="mx-auto max-h-80 w-auto max-w-full rounded-small object-contain"
              src={resource.dataUrl}
            />
          ) : (
            <p className="font-notioninter text-xs text-stone">
              Gambar (tanpa pratinjau)
            </p>
          )}
          <figcaption className="font-notioninter text-[11px] text-stone">
            Gambar{block.page ? ` · hlm ${block.page}` : ""}
            {block.modifiedByUser ? " · dari blok ini" : ""}
          </figcaption>
        </figure>
      );
      break;
    }
    case "table":
      body = (
        <p
          className={
            "font-notioninter rounded-small border border-dashed border-black/15 bg-paper-warmth px-3 py-1.5 text-center text-xs text-stone hover:bg-sky-tint/40 " +
            (selected ? "outline outline-1 outline-notion-blue" : "")
          }
          onClick={() => onSelect(block.id)}
        >
          Tabel terdeteksi{block.page ? ` · hlm ${block.page}` : ""} — diekspor
          sebagai tabel HTML
        </p>
      );
      break;
    case "list":
      body = (
        <div
          className={"font-notioninter rounded-small border border-dashed border-black/15 bg-paper-warmth px-3 py-1.5 text-xs text-stone hover:bg-sky-tint/40 " + (selected ? "outline outline-1 outline-notion-blue" : "")}
          onClick={() => onSelect(block.id)}
        >
          Daftar terdeteksi{block.page ? ` · hlm ${block.page}` : ""} — diekspor
          sebagai &lt;ol&gt;/&lt;ul&gt;
        </div>
      );
      break;
    default:
      body = null;
  }

  return (
    <div className="relative" data-block-id={block.id}>
      {body}
      {note ? (
        <p className="font-notioninter mb-1 px-2 text-[11px] text-vermillion">
          {note}
        </p>
      ) : null}
    </div>
  );
}

export function ReflowPreview({
  reflow,
  selectedId,
  onSelect,
}: {
  reflow: UiReflow;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Keep the selected block visible no matter where the selection came from
  // (preview click, inspector list, filter).
  useEffect(() => {
    if (!selectedId || !containerRef.current) return;
    const node = containerRef.current.querySelector(`[data-block-id="${CSS.escape(selectedId)}"]`);
    node?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedId]);

  return (
    <div
      className="reflow-preview max-h-[70vh] overflow-x-hidden overflow-y-auto rounded-card border border-black/8 bg-pure-white p-6 text-body leading-relaxed text-charcoal"
      ref={containerRef}
    >
      {reflow.blocks.map((block) => (
        <BlockView
          block={block}
          key={block.id}
          onSelect={onSelect}
          reflow={reflow}
          selected={selectedId === block.id}
        />
      ))}
    </div>
  );
}

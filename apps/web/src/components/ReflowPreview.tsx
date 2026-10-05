"use client";

import { UiBlock, UiReflow } from "@/lib/contract";

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
  const notes: string[] = [];
  if (block.warnings.length > 0) {
    notes.push(block.warnings.join(", "));
  }
  if (
    block.integrityScore !== undefined &&
    block.integrityScore < 0.85 &&
    block.type === "paragraph"
  ) {
    notes.push(`integritas Arab ${Math.round(block.integrityScore * 100)}%`);
  }
  return notes.length > 0 ? notes.join(" · ") : null;
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
  const selectedClass = selected ? "outline outline-1 outline-neutral-900" : "";
  const note = integrityNote(block);
  const common =
    "block cursor-pointer px-2 py-1 hover:bg-neutral-50 " + selectedClass;

  let body: React.ReactNode = null;
  switch (block.type) {
    case "heading": {
      const level = Math.min(Math.max(block.level ?? 1, 1), 6);
      const Tag = `h${level}` as "h1";
      body = (
        <Tag className={common} dir={block.dir} lang={block.lang} onClick={() => onSelect(block.id)}>
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
        <aside className={common} onClick={() => onSelect(block.id)}>
          <p className="text-xs uppercase tracking-wide text-neutral-500">
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
        <figure className={common} onClick={() => onSelect(block.id)}>
          {resource?.dataUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img alt="" src={resource.dataUrl} />
          ) : (
            <p className="text-xs text-neutral-500">[gambar {block.resourceId}]</p>
          )}
          {block.captionBlockId ? null : null}
        </figure>
      );
      break;
    }
    case "table":
      body = <p className={common} onClick={() => onSelect(block.id)}>[tabel]</p>;
      break;
    case "list":
      body = <p className={common} onClick={() => onSelect(block.id)}>[daftar]</p>;
      break;
    default:
      body = null;
  }

  return (
    <div className="relative">
      {body}
      {note ? (
        <p className="mb-1 px-2 text-[11px] text-amber-700">{note}</p>
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
  return (
    <div className="reflow-preview max-h-[70vh] overflow-y-auto border border-neutral-200 p-6 text-[15px] leading-relaxed">
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

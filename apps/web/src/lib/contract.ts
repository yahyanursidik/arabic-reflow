/**
 * Runtime contract validation for API responses.
 *
 * Server output is treated as untrusted (VIBE-CODING-INSTRUCTIONS.md):
 * every payload is parsed into a normalized UI model or a ContractError is
 * thrown. Shapes mirror packages/schemas/reflowdoc.schema.json; the compile
 * time types come from src/lib/reflowdoc.d.ts (generated from that schema).
 */

export class ContractError extends Error {
  constructor(path: string, detail: string) {
    super(`contract violation at ${path}: ${detail}`);
    this.name = "ContractError";
  }
}

export interface TextRepairResult {
  changedBlockIds: string[];
  unchangedBlockIds: string[];
  skippedBlockIds: string[];
  reviewBlockIds: string[];
}

export function parseTextRepairResult(value: unknown): TextRepairResult {
  if (!isRecord(value)) throw new ContractError("repair", "expected object");
  const ids = (key: string): string[] => {
    const items = value[key];
    if (!Array.isArray(items) || items.some((item) => typeof item !== "string")) {
      throw new ContractError("repair", `${key} must be a string array`);
    }
    return items as string[];
  };
  return {
    changedBlockIds: ids("changed_block_ids"),
    unchangedBlockIds: ids("unchanged_block_ids"),
    skippedBlockIds: ids("skipped_block_ids"),
    reviewBlockIds: ids("review_block_ids"),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function reqString(
  parent: Record<string, unknown>,
  path: string,
  key: string,
): string {
  const value = parent[key];
  if (typeof value !== "string" || value.length === 0) {
    throw new ContractError(path, `${key} must be a non-empty string`);
  }
  return value;
}

function optString(
  parent: Record<string, unknown>,
  key: string,
): string | undefined {
  const value = parent[key];
  return typeof value === "string" ? value : undefined;
}

function optNumber(
  parent: Record<string, unknown>,
  key: string,
): number | undefined {
  const value = parent[key];
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : undefined;
}

function optBool(
  parent: Record<string, unknown>,
  key: string,
): boolean | undefined {
  const value = parent[key];
  return typeof value === "boolean" ? value : undefined;
}

function array(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

// --- Normalized UI models (UI state stays separate from the canonical doc) ----

export interface DocumentMeta {
  id: string;
  filename: string;
  size: number;
  createdAt?: string;
}

export interface ProfilePage {
  page: number;
  textChars: number;
  arabicChars: number;
  textCoverage: number;
  imageCoverage: number;
  scannedLike: boolean;
  likelyMulticolumn: boolean;
}

export interface Profile {
  pageCount: number;
  classification: string;
  classificationConfidence: number;
  textLayer: boolean;
  imageDominant: boolean;
  arabicDetected: boolean;
  scannedPages: number[];
  likelyMulticolumnPages: number[];
  pages: ProfilePage[];
}

export interface Job {
  id: string;
  documentId: string;
  status: "queued" | "processing" | "completed" | "failed";
  stage: string;
  progress: number;
  warnings: { code: string; message: string }[];
  error?: string;
}

export type UiNode =
  | { kind: "text"; text: string }
  | { kind: "image"; text: string; resourceId: string }
  | {
      kind: "span";
      text: string;
      lang?: string;
      dir?: string;
    };

export type UiBlockType =
  | "heading"
  | "paragraph"
  | "quote"
  | "list"
  | "image"
  | "table"
  | "footnote"
  | "page_break";

export interface UiBlock {
  id: string;
  type: UiBlockType;
  page?: number;
  lang?: string;
  dir?: string;
  level?: number;
  marker?: string;
  text: string;
  nodes: UiNode[];
  confidence?: number;
  warnings: string[];
  integrityScore?: number;
  modifiedByUser: boolean;
  resourceId?: string;
  captionBlockId?: string;
  fallbackResourceId?: string;
  blocks?: UiBlock[]; // footnote inner blocks
  ordered?: boolean;
  items?: UiBlock[][];
  rows?: { text: string; lang?: string; dir?: string }[][];
  alt?: string;
  parentId?: string;
  canMoveUp?: boolean;
  canMoveDown?: boolean;
}

export interface UiResource {
  id: string;
  mediaType?: string;
  dataUrl?: string;
}

export interface UiWarning {
  code: string;
  severity: string;
  message: string;
  page?: number;
}

export interface UiReflow {
  documentId: string;
  languages: string[];
  title: string;
  author: string[];
  coverResourceId?: string;
  blocks: UiBlock[];
  resources: Record<string, UiResource>;
  warnings: UiWarning[];
}

export interface UiReport {
  restorableBlockIds: string[];
  integrity?: {
    score?: number;
    level?: string;
    blockCount: number;
    pageScores: Record<string, number>;
    lowConfidenceBlockIds: string[];
    issues: string[];
  };
  warnings: UiWarning[];
  quality?: {
    blockCount: number;
    editedBlockCount: number;
    reviewBlockIds: string[];
    canExport: boolean;
    pages: { page: number; blockCount: number; reviewBlockIds: string[] }[];
    issues: UiWarning[];
  };
}

export interface Capabilities {
  epubcheckAvailable: boolean;
  ocr: {
    engines: {
      name: "paddle" | "tesseract";
      available: boolean;
      languages: string[];
      message: string;
    }[];
  };
}

export interface ConversionOptions {
  mode: "native" | "auto" | "force";
  engine?: "paddle" | "tesseract";
  languages: ("ar" | "id" | "en")[];
}

export interface BlockUpdate {
  text?: string;
  lang?: string;
  dir?: string;
  type?: "paragraph" | "heading" | "quote";
  level?: number;
  alt?: string;
}

export function parseCapabilities(value: unknown): Capabilities {
  if (!isRecord(value) || !isRecord(value.ocr))
    throw new ContractError("capabilities", "missing OCR information");
  return {
    epubcheckAvailable:
      isRecord(value.validation) &&
      optBool(value.validation, "epubcheck") === true,
    ocr: {
      engines: array(value.ocr.engines).map((item) => {
        if (
          !isRecord(item) ||
          !["paddle", "tesseract"].includes(String(item.name))
        )
          throw new ContractError("capabilities.ocr.engines", "unknown engine");
        return {
          name: item.name as "paddle" | "tesseract",
          available: optBool(item, "available") ?? false,
          languages: array(item.languages).filter(
            (entry): entry is string => typeof entry === "string",
          ),
          message: optString(item, "message") ?? "",
        };
      }),
    },
  };
}

// --- Parsers -----------------------------------------------------------------

export function parseDocumentMeta(value: unknown): DocumentMeta {
  if (!isRecord(value)) throw new ContractError("meta", "not an object");
  const id = reqString(value, "meta", "id");
  const filename = reqString(value, "meta", "filename");
  const size = typeof value.size === "number" ? value.size : 0;
  return { id, filename, size, createdAt: optString(value, "created_at") };
}

export function parseProfile(value: unknown): Profile {
  if (!isRecord(value)) throw new ContractError("profile", "not an object");
  const pages: ProfilePage[] = array(value.pages).map((raw, index) => {
    if (!isRecord(raw))
      throw new ContractError(`profile.pages[${index}]`, "not an object");
    return {
      page: optNumber(raw, "page") ?? index + 1,
      textChars: optNumber(raw, "text_chars") ?? 0,
      arabicChars: optNumber(raw, "arabic_chars") ?? 0,
      textCoverage: optNumber(raw, "text_coverage") ?? 0,
      imageCoverage: optNumber(raw, "image_coverage") ?? 0,
      scannedLike: optBool(raw, "scanned_like") ?? false,
      likelyMulticolumn: optBool(raw, "likely_multicolumn") ?? false,
    };
  });
  return {
    pageCount: optNumber(value, "page_count") ?? pages.length,
    classification: optString(value, "classification") ?? "unknown",
    classificationConfidence:
      optNumber(value, "classification_confidence") ?? 0,
    textLayer: optBool(value, "text_layer") ?? false,
    imageDominant: optBool(value, "image_dominant") ?? false,
    arabicDetected: optBool(value, "arabic_detected") ?? false,
    scannedPages: pages.filter((p) => p.scannedLike).map((p) => p.page),
    likelyMulticolumnPages: pages
      .filter((p) => p.likelyMulticolumn)
      .map((p) => p.page),
    pages,
  };
}

export function parseJob(value: unknown): Job {
  if (!isRecord(value)) throw new ContractError("job", "not an object");
  const status = optString(value, "status") ?? "queued";
  if (!["queued", "processing", "completed", "failed"].includes(status)) {
    throw new ContractError("job.status", `unknown status ${status}`);
  }
  return {
    id: reqString(value, "job", "id"),
    documentId: reqString(value, "job", "document_id"),
    status: status as Job["status"],
    stage: optString(value, "stage") ?? "uploaded",
    progress: optNumber(value, "progress") ?? 0,
    warnings: array(value.warnings).map((w) => {
      if (!isRecord(w))
        throw new ContractError("job.warnings[]", "not an object");
      return {
        code: optString(w, "code") ?? "UNKNOWN",
        message: optString(w, "message") ?? "",
      };
    }),
    error: optString(value, "error"),
  };
}

function parseIntegrity(parent: Record<string, unknown>): number | undefined {
  const integrity = parent.arabic_integrity;
  if (!isRecord(integrity)) return undefined;
  return optNumber(integrity, "score");
}

function parseNodes(parent: Record<string, unknown>, path: string): UiNode[] {
  const content = array(parent.content);
  return content.map((node, index) => {
    if (!isRecord(node))
      throw new ContractError(`${path}.content[${index}]`, "not an object");
    const text = typeof node.text === "string" ? node.text : "";
    if (node.type === "inline_image") {
      return { kind: "image", text: optString(node, "alt") ?? "",
        resourceId: reqString(node, `${path}.content[${index}]`, "resource_id") };
    }
    if (node.type === "span") {
      return {
        kind: "span",
        text,
        lang: optString(node, "lang"),
        dir: optString(node, "dir"),
      };
    }
    return { kind: "text", text };
  });
}

function parseBlock(raw: unknown, path: string): UiBlock {
  if (!isRecord(raw)) throw new ContractError(path, "not an object");
  const type = optString(raw, "type");
  const known: UiBlockType[] = [
    "heading",
    "paragraph",
    "quote",
    "list",
    "image",
    "table",
    "footnote",
    "page_break",
  ];
  if (!type || !known.includes(type as UiBlockType)) {
    throw new ContractError(
      `${path}.type`,
      `unknown block type ${String(type)}`,
    );
  }

  let text = "";
  if (typeof raw.text === "string") {
    text = raw.text;
  } else if (type === "paragraph") {
    text = parseNodes(raw, path)
      .map((n) => n.text)
      .join("");
  }

  const blocks = array(raw.blocks).map((inner, index) =>
    parseBlock(inner, `${path}.blocks[${index}]`),
  );
  const items = array(raw.items).map((item, index) => {
    if (!isRecord(item))
      throw new ContractError(`${path}.items[${index}]`, "not an object");
    return array(item.blocks).map((inner, innerIndex) =>
      parseBlock(inner, `${path}.items[${index}].blocks[${innerIndex}]`),
    );
  });
  const rows = array(raw.rows).map((row, index) =>
    array(row).map((cell, cellIndex) => {
      if (!isRecord(cell))
        throw new ContractError(
          `${path}.rows[${index}][${cellIndex}]`,
          "not an object",
        );
      return {
        text: optString(cell, "text") ?? "",
        lang: optString(cell, "lang"),
        dir: optString(cell, "dir"),
      };
    }),
  );
  if (type === "list")
    text = items
      .flat()
      .map((block) => block.text)
      .join("\n");
  if (type === "table")
    text = rows
      .map((row) => row.map((cell) => cell.text).join(" | "))
      .join("\n");
  if (type === "footnote") text = blocks.map((block) => block.text).join("\n");

  return {
    id: reqString(raw, path, "id"),
    type: type as UiBlockType,
    page: optNumber((raw.source as Record<string, unknown>) ?? {}, "page"),
    lang: optString(raw, "lang"),
    dir: optString(raw, "dir"),
    level: optNumber(raw, "level"),
    marker: optString(raw, "marker"),
    text,
    nodes: type === "paragraph" ? parseNodes(raw, path) : [],
    confidence: optNumber(raw, "confidence"),
    warnings: array(raw.warnings).filter(
      (w): w is string => typeof w === "string",
    ),
    integrityScore: parseIntegrity(raw),
    modifiedByUser: optBool(raw, "modified_by_user") ?? false,
    resourceId: optString(raw, "resource_id"),
    captionBlockId: optString(raw, "caption_block_id"),
    fallbackResourceId: optString(raw, "fallback_resource_id"),
    blocks: type === "footnote" ? blocks : undefined,
    ordered: optBool(raw, "ordered"),
    items: type === "list" ? items : undefined,
    rows: type === "table" ? rows : undefined,
    alt: optString(raw, "alt"),
  };
}

export function parseReflow(value: unknown): UiReflow {
  if (!isRecord(value)) throw new ContractError("reflow", "not an object");
  const blocks: UiBlock[] = [];
  for (const [chapterIndex, chapter] of array(value.chapters).entries()) {
    if (!isRecord(chapter))
      throw new ContractError(`chapters[${chapterIndex}]`, "not an object");
    for (const [blockIndex, block] of array(chapter.blocks).entries()) {
      blocks.push(
        parseBlock(block, `chapters[${chapterIndex}].blocks[${blockIndex}]`),
      );
    }
  }

  const resources: Record<string, UiResource> = {};
  for (const raw of array(value.resources)) {
    if (!isRecord(raw)) continue;
    const id = typeof raw.id === "string" ? raw.id : undefined;
    if (!id) continue;
    const mediaType =
      optString(raw, "media_type") ?? "application/octet-stream";
    const content = typeof raw.content === "string" ? raw.content : undefined;
    resources[id] = {
      id,
      mediaType,
      dataUrl: content ? `data:${mediaType};base64,${content}` : undefined,
    };
  }

  const warnings: UiWarning[] = array(value.warnings).map((w, index) => {
    if (!isRecord(w))
      throw new ContractError(`warnings[${index}]`, "not an object");
    return {
      code: optString(w, "code") ?? "UNKNOWN",
      severity: optString(w, "severity") ?? "info",
      message: optString(w, "message") ?? "",
      page: optNumber(w, "source_page"),
    };
  });

  const metadata = isRecord(value.metadata) ? value.metadata : {};
  return {
    documentId: optString(value, "document_id") ?? "",
    languages: array(metadata.languages).filter(
      (l): l is string => typeof l === "string",
    ),
    title: optString(metadata, "title") ?? "",
    author: array(metadata.author).filter(
      (a): a is string => typeof a === "string",
    ),
    coverResourceId: optString(metadata, "cover_resource_id"),
    blocks,
    resources,
    warnings,
  };
}

export function parseReport(value: unknown): UiReport {
  if (!isRecord(value)) throw new ContractError("report", "not an object");
  const integrity = isRecord(value.integrity) ? value.integrity : undefined;
  const quality = isRecord(value.quality) ? value.quality : undefined;
  const pageScores: Record<string, number> = {};
  if (integrity && isRecord(integrity.page_scores)) {
    for (const [key, score] of Object.entries(integrity.page_scores)) {
      if (typeof score === "number") pageScores[key] = score;
    }
  }
  return {
    quality: quality
      ? {
          blockCount: optNumber(quality, "block_count") ?? 0,
          editedBlockCount: optNumber(quality, "edited_block_count") ?? 0,
          reviewBlockIds: array(quality.review_block_ids).filter(
            (id): id is string => typeof id === "string",
          ),
          canExport: optBool(quality, "can_export") ?? false,
          pages: array(quality.pages).map((page) => {
            if (!isRecord(page))
              throw new ContractError("quality.pages", "not an object");
            return {
              page: optNumber(page, "page") ?? 1,
              blockCount: optNumber(page, "block_count") ?? 0,
              reviewBlockIds: array(page.review_block_ids).filter(
                (id): id is string => typeof id === "string",
              ),
            };
          }),
          issues: array(quality.issues).map((issue) => {
            if (!isRecord(issue))
              throw new ContractError("quality.issues", "not an object");
            return {
              code: optString(issue, "code") ?? "UNKNOWN",
              severity: optString(issue, "severity") ?? "warning",
              message: optString(issue, "message") ?? "",
            };
          }),
        }
      : undefined,
    restorableBlockIds: isRecord(value.review)
      ? array(value.review.restorable_block_ids).filter(
          (id): id is string => typeof id === "string",
        )
      : [],
    integrity: integrity
      ? {
          score: optNumber(integrity, "score"),
          level: optString(integrity, "level"),
          blockCount: optNumber(integrity, "block_count") ?? 0,
          pageScores,
          lowConfidenceBlockIds: array(
            integrity.low_confidence_block_ids,
          ).filter((id): id is string => typeof id === "string"),
          issues: array(integrity.issues).filter(
            (i): i is string => typeof i === "string",
          ),
        }
      : undefined,
    warnings: array(value.warnings).map((w, index) => {
      if (!isRecord(w))
        throw new ContractError(`report.warnings[${index}]`, "not an object");
      return {
        code: optString(w, "code") ?? "UNKNOWN",
        severity: optString(w, "severity") ?? "info",
        message: optString(w, "message") ?? "",
        page: optNumber(w, "source_page"),
      };
    }),
  };
}

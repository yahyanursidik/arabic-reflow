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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function reqString(parent: Record<string, unknown>, path: string, key: string): string {
  const value = parent[key];
  if (typeof value !== "string" || value.length === 0) {
    throw new ContractError(path, `${key} must be a non-empty string`);
  }
  return value;
}

function optString(parent: Record<string, unknown>, key: string): string | undefined {
  const value = parent[key];
  return typeof value === "string" ? value : undefined;
}

function optNumber(parent: Record<string, unknown>, key: string): number | undefined {
  const value = parent[key];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function optBool(parent: Record<string, unknown>, key: string): boolean | undefined {
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

export type UiNode = { kind: "text"; text: string } | {
  kind: "span";
  text: string;
  lang?: string;
  dir?: string;
};

export type UiBlockType =
  | "heading" | "paragraph" | "quote" | "list" | "image" | "table"
  | "footnote" | "page_break";

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
  blocks?: UiBlock[]; // footnote inner blocks
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
  integrity?: {
    score?: number;
    level?: string;
    blockCount: number;
    pageScores: Record<string, number>;
    lowConfidenceBlockIds: string[];
    issues: string[];
  };
  warnings: UiWarning[];
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
    if (!isRecord(raw)) throw new ContractError(`profile.pages[${index}]`, "not an object");
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
    classificationConfidence: optNumber(value, "classification_confidence") ?? 0,
    textLayer: optBool(value, "text_layer") ?? false,
    imageDominant: optBool(value, "image_dominant") ?? false,
    arabicDetected: optBool(value, "arabic_detected") ?? false,
    scannedPages: pages.filter((p) => p.scannedLike).map((p) => p.page),
    likelyMulticolumnPages: pages.filter((p) => p.likelyMulticolumn).map((p) => p.page),
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
      if (!isRecord(w)) throw new ContractError("job.warnings[]", "not an object");
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
    if (!isRecord(node)) throw new ContractError(`${path}.content[${index}]`, "not an object");
    const text = typeof node.text === "string" ? node.text : "";
    if (node.type === "span") {
      return { kind: "span", text, lang: optString(node, "lang"), dir: optString(node, "dir") };
    }
    return { kind: "text", text };
  });
}

function parseBlock(raw: unknown, path: string): UiBlock {
  if (!isRecord(raw)) throw new ContractError(path, "not an object");
  const type = optString(raw, "type");
  const known: UiBlockType[] = [
    "heading", "paragraph", "quote", "list", "image", "table", "footnote", "page_break",
  ];
  if (!type || !known.includes(type as UiBlockType)) {
    throw new ContractError(`${path}.type`, `unknown block type ${String(type)}`);
  }

  let text = "";
  if (typeof raw.text === "string") {
    text = raw.text;
  } else if (type === "paragraph") {
    text = parseNodes(raw, path).map((n) => n.text).join("");
  }

  const blocks = array(raw.blocks).map((inner, index) =>
    parseBlock(inner, `${path}.blocks[${index}]`),
  );

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
    warnings: array(raw.warnings).filter((w): w is string => typeof w === "string"),
    integrityScore: parseIntegrity(raw),
    modifiedByUser: optBool(raw, "modified_by_user") ?? false,
    resourceId: optString(raw, "resource_id"),
    captionBlockId: optString(raw, "caption_block_id"),
    blocks: type === "footnote" ? blocks : undefined,
  };
}

export function parseReflow(value: unknown): UiReflow {
  if (!isRecord(value)) throw new ContractError("reflow", "not an object");
  const blocks: UiBlock[] = [];
  for (const [chapterIndex, chapter] of array(value.chapters).entries()) {
    if (!isRecord(chapter)) throw new ContractError(`chapters[${chapterIndex}]`, "not an object");
    for (const [blockIndex, block] of array(chapter.blocks).entries()) {
      blocks.push(parseBlock(block, `chapters[${chapterIndex}].blocks[${blockIndex}]`));
    }
  }

  const resources: Record<string, UiResource> = {};
  for (const raw of array(value.resources)) {
    if (!isRecord(raw)) continue;
    const id = typeof raw.id === "string" ? raw.id : undefined;
    if (!id) continue;
    const mediaType = optString(raw, "media_type") ?? "application/octet-stream";
    const content = typeof raw.content === "string" ? raw.content : undefined;
    resources[id] = {
      id,
      mediaType,
      dataUrl: content ? `data:${mediaType};base64,${content}` : undefined,
    };
  }

  const warnings: UiWarning[] = array(value.warnings).map((w, index) => {
    if (!isRecord(w)) throw new ContractError(`warnings[${index}]`, "not an object");
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
    languages: array(metadata.languages).filter((l): l is string => typeof l === "string"),
    title: optString(metadata, "title") ?? "",
    author: array(metadata.author).filter((a): a is string => typeof a === "string"),
    coverResourceId: optString(metadata, "cover_resource_id"),
    blocks,
    resources,
    warnings,
  };
}

export function parseReport(value: unknown): UiReport {
  if (!isRecord(value)) throw new ContractError("report", "not an object");
  const integrity = isRecord(value.integrity) ? value.integrity : undefined;
  const pageScores: Record<string, number> = {};
  if (integrity && isRecord(integrity.page_scores)) {
    for (const [key, score] of Object.entries(integrity.page_scores)) {
      if (typeof score === "number") pageScores[key] = score;
    }
  }
  return {
    integrity: integrity
      ? {
          score: optNumber(integrity, "score"),
          level: optString(integrity, "level"),
          blockCount: optNumber(integrity, "block_count") ?? 0,
          pageScores,
          lowConfidenceBlockIds: array(integrity.low_confidence_block_ids).filter(
            (id): id is string => typeof id === "string",
          ),
          issues: array(integrity.issues).filter((i): i is string => typeof i === "string"),
        }
      : undefined,
    warnings: array(value.warnings).map((w, index) => {
      if (!isRecord(w)) throw new ContractError(`report.warnings[${index}]`, "not an object");
      return {
        code: optString(w, "code") ?? "UNKNOWN",
        severity: optString(w, "severity") ?? "info",
        message: optString(w, "message") ?? "",
        page: optNumber(w, "source_page"),
      };
    }),
  };
}

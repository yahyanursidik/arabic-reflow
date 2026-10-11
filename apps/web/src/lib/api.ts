/**
 * Typed API client for the Reflow backend.
 * Base URL: NEXT_PUBLIC_API_URL (docker-compose sets it), default
 * http://127.0.0.1:8000 — explicit IPv4, because `localhost` resolves to ::1
 * on some browsers and the API binds IPv4 only.
 */

import {
  ContractError,
  DocumentMeta,
  Job,
  Profile,
  UiBlock,
  UiReflow,
  UiReport,
  parseDocumentMeta,
  parseJob,
  parseProfile,
  parseReflow,
  parseReport,
  parseCapabilities,
  Capabilities,
  ConversionOptions,
  BlockUpdate,
  TextRepairResult,
  parseTextRepairResult,
} from "./contract";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function apiErrorMessage(status: number, detail?: unknown): string {
  if (status === 413) return "Ukuran PDF melebihi batas 100 MB.";
  if (status === 415)
    return "Berkas bukan PDF yang dapat dibaca. Coba buka PDF di perangkat Anda terlebih dahulu.";
  if (status === 409)
    return "Konversi masih berjalan. Tunggu hingga selesai sebelum mengubah atau mengekspor dokumen.";
  if (typeof detail === "string") {
    if (detail.toLowerCase().includes("encrypted"))
      return "PDF dilindungi kata sandi. Unggah salinan PDF tanpa kata sandi.";
    return detail;
  }
  if (status === 422)
    return "Data belum valid. Periksa teks, judul, kode bahasa (contoh: id, ar), dan arah baca.";
  return `Permintaan gagal (${status}). Silakan coba lagi.`;
}

async function fetchResponse(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      cache: "no-store",
      signal: init?.signal ?? AbortSignal.timeout(120_000),
    });
  } catch (cause) {
    throw new ApiError(
      0,
      `Tidak dapat menghubungi server Reflow (${API_BASE}). Pastikan API berjalan, lalu coba lagi.`,
    );
  }
  if (!response.ok) {
    let detail: unknown;
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = body.detail;
    } catch {
      // keep status-only message
    }
    throw new ApiError(
      response.status,
      apiErrorMessage(response.status, detail),
    );
  }
  return response;
}

async function request<T>(
  path: string,
  parse: (body: unknown) => T,
  init?: RequestInit,
): Promise<T> {
  const response = await fetchResponse(path, init);
  const body: unknown = await response.json();
  return parse(body);
}

export const api = {
  baseUrl: API_BASE,

  async getCapabilities(): Promise<Capabilities> {
    return request("/api/v1/capabilities", parseCapabilities);
  },

  async upload(file: File): Promise<DocumentMeta> {
    const form = new FormData();
    form.append("file", file, file.name);
    return request("/api/v1/documents", parseDocumentMeta, {
      method: "POST",
      body: form,
    });
  },

  async getDocument(id: string): Promise<DocumentMeta> {
    return request(`/api/v1/documents/${id}`, parseDocumentMeta);
  },

  async analyze(id: string): Promise<Profile> {
    return request(`/api/v1/documents/${id}/analyze`, parseProfile, {
      method: "POST",
    });
  },

  async getProfile(id: string): Promise<Profile | null> {
    try {
      return await request(`/api/v1/documents/${id}/profile`, parseProfile);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },

  async convert(
    id: string,
    options: boolean | ConversionOptions,
  ): Promise<{ jobId: string }> {
    const body = await request<{ job_id?: string }>(
      `/api/v1/documents/${id}/convert`,
      (value) => value as { job_id?: string },
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          typeof options === "boolean" ? { ocr: options } : options,
        ),
      },
    );
    if (typeof body.job_id !== "string") {
      throw new ContractError("convert", "missing job_id");
    }
    return { jobId: body.job_id };
  },

  async getJob(jobId: string): Promise<Job> {
    return request(`/api/v1/jobs/${jobId}`, parseJob);
  },

  async getDocumentJob(id: string): Promise<Job | null> {
    try {
      return await request(`/api/v1/documents/${id}/job`, parseJob);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },

  async getReflow(id: string): Promise<UiReflow> {
    return request(`/api/v1/documents/${id}/reflow`, parseReflow);
  },

  async getReport(id: string): Promise<UiReport> {
    return request(`/api/v1/documents/${id}/report`, parseReport);
  },

  async downloadEpub(
    id: string,
    w3c = false,
  ): Promise<{ blob: Blob; filename: string }> {
    const response = await fetchResponse(
      `/api/v1/documents/${id}/export/epub${w3c ? "?validation=w3c" : ""}`,
      { method: "POST" },
    );
    const disposition = response.headers.get("content-disposition") ?? "";
    const encoded = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
    const plain = /filename="?([^";]+)"?/i.exec(disposition);
    let filename = plain?.[1] ?? "document.epub";
    if (encoded?.[1]) {
      try {
        filename = decodeURIComponent(encoded[1]);
      } catch {
        /* fall back to plain name */
      }
    }
    return { blob: await response.blob(), filename };
  },

  async downloadJson(id: string, kind: "reflow" | "report"): Promise<Blob> {
    const response = await fetchResponse(`/api/v1/documents/${id}/${kind}`);
    return new Blob([JSON.stringify(await response.json(), null, 2)], {
      type: "application/json",
    });
  },

  async updateBlock(
    id: string,
    blockId: string,
    update: BlockUpdate,
  ): Promise<UiBlock> {
    return request(
      `/api/v1/documents/${id}/blocks/${blockId}`,
      (value) => {
        const block = parseReflow({
          schema_version: "0.1",
          document_id: id,
          chapters: [{ id: "chapter-001", blocks: [value] }],
        }).blocks[0];
        if (!block) throw new ContractError("block", "empty response");
        return block;
      },
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(update),
      },
    );
  },

  async moveBlock(
    id: string,
    blockId: string,
    direction: "up" | "down",
  ): Promise<void> {
    await request(
      `/api/v1/documents/${id}/blocks/${blockId}/move`,
      () => undefined,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ direction }),
      },
    );
  },

  async renderBlockAsImage(id: string, blockId: string): Promise<UiBlock> {
    return request(
      `/api/v1/documents/${id}/blocks/${blockId}/render-image`,
      (value) => {
        const block = parseReflow({
          schema_version: "0.1",
          document_id: id,
          chapters: [{ id: "chapter-001", blocks: [value] }],
        }).blocks[0];
        if (!block) throw new ContractError("block", "empty response");
        return block;
      },
      { method: "POST" },
    );
  },

  async restoreBlockText(id: string, blockId: string): Promise<UiBlock> {
    return request(
      `/api/v1/documents/${id}/blocks/${blockId}/restore-text`,
      (value) => {
        const block = parseReflow({
          schema_version: "0.1",
          document_id: id,
          chapters: [{ id: "chapter-001", blocks: [value] }],
        }).blocks[0];
        if (!block) throw new ContractError("block", "empty response");
        return block;
      },
      { method: "POST" },
    );
  },

  async normalizeBlockArabic(id: string, blockId: string): Promise<UiBlock> {
    return request(
      `/api/v1/documents/${id}/blocks/${blockId}/normalize-arabic`,
      (value) => {
        const block = parseReflow({
          schema_version: "0.1",
          document_id: id,
          chapters: [{ id: "chapter-001", blocks: [value] }],
        }).blocks[0];
        if (!block) throw new ContractError("block", "empty response");
        return block;
      },
      { method: "POST" },
    );
  },

  async repairText(id: string, blockId: string): Promise<TextRepairResult> {
    return request(`/api/v1/documents/${id}/blocks/${blockId}/repair-text`, parseTextRepairResult, { method: "POST" });
  },

  async repairProblemBlocks(id: string, blockIds: string[]): Promise<TextRepairResult> {
    return request(`/api/v1/documents/${id}/repair-text`, parseTextRepairResult, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ block_ids: blockIds }),
    });
  },

  exportEpubUrl(id: string): string {
    return `${API_BASE}/api/v1/documents/${id}/export/epub`;
  },

  sourcePageUrl(id: string, page: number): string {
    return `${API_BASE}/api/v1/documents/${id}/source/pages/${page}.png`;
  },
};

export interface BookMetadata {
  title?: string;
  author?: string[];
}

export interface CoverResult {
  cover_resource_id: string | null;
  source_page?: number;
}

export interface MetadataResult extends CoverResult {
  title: string;
  author: string[];
}

export const bookApi = {
  async updateMetadata(
    id: string,
    update: BookMetadata,
  ): Promise<MetadataResult> {
    return request(
      `/api/v1/documents/${id}/metadata`,
      (value) => value as MetadataResult,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(update),
      },
    );
  },

  async setCover(id: string, page: number): Promise<CoverResult> {
    return request(
      `/api/v1/documents/${id}/cover?page=${encodeURIComponent(String(page))}`,
      (value) => value as CoverResult,
      { method: "POST" },
    );
  },

  async clearCover(id: string): Promise<CoverResult> {
    return request(
      `/api/v1/documents/${id}/cover`,
      (value) => value as CoverResult,
      {
        method: "DELETE",
      },
    );
  },
};

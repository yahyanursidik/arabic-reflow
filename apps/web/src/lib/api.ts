/**
 * Typed API client for the Reflow backend.
 * Base URL: NEXT_PUBLIC_API_URL (docker-compose sets it), default localhost:8000.
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
} from "./contract";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, parse: (body: unknown) => T, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (cause) {
    throw new ApiError(0, `tidak dapat menghubungi API di ${API_BASE}`);
  }
  if (!response.ok) {
    let detail = `${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep status-only message
    }
    throw new ApiError(response.status, detail);
  }
  const body: unknown = await response.json();
  return parse(body);
}

export const api = {
  baseUrl: API_BASE,

  async upload(file: File): Promise<DocumentMeta> {
    const form = new FormData();
    form.append("file", file, file.name);
    return request("/api/v1/documents", parseDocumentMeta, { method: "POST", body: form });
  },

  async getDocument(id: string): Promise<DocumentMeta> {
    return request(`/api/v1/documents/${id}`, parseDocumentMeta);
  },

  async analyze(id: string): Promise<Profile> {
    return request(`/api/v1/documents/${id}/analyze`, parseProfile, { method: "POST" });
  },

  async getProfile(id: string): Promise<Profile | null> {
    try {
      return await request(`/api/v1/documents/${id}/profile`, parseProfile);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },

  async convert(id: string, ocr: boolean): Promise<{ jobId: string }> {
    const body = await request<{ job_id?: string }>(
      `/api/v1/documents/${id}/convert`,
      (value) => value as { job_id?: string },
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ocr }) },
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

  async updateBlock(
    id: string,
    blockId: string,
    update: { text?: string; lang?: string; dir?: string },
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

export const bookApi = {
  async updateMetadata(id: string, update: BookMetadata): Promise<CoverResult> {
    return request(`/api/v1/documents/${id}/metadata`, (value) => value as CoverResult, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(update),
    });
  },

  async setCover(id: string, page: number): Promise<CoverResult> {
    return request(
      `/api/v1/documents/${id}/cover?page=${encodeURIComponent(String(page))}`,
      (value) => value as CoverResult,
      { method: "POST" },
    );
  },

  async clearCover(id: string): Promise<CoverResult> {
    return request(`/api/v1/documents/${id}/cover`, (value) => value as CoverResult, {
      method: "DELETE",
    });
  },
};

import { DocumentMeta, parseDocumentMeta } from "./contract";

const KEY = "reflow.recent-documents";

export function recentDocuments(): DocumentMeta[] {
  try {
    return (JSON.parse(localStorage.getItem(KEY) ?? "[]") as unknown[])
      .map(parseDocumentMeta)
      .slice(0, 8);
  } catch {
    return [];
  }
}

export function rememberDocument(meta: DocumentMeta) {
  try {
    const records = [
      meta,
      ...recentDocuments().filter((item) => item.id !== meta.id),
    ].slice(0, 8);
    localStorage.setItem(
      KEY,
      JSON.stringify(
        records.map((item) => ({
          id: item.id,
          filename: item.filename,
          size: item.size,
          created_at: item.createdAt,
        })),
      ),
    );
  } catch {
    /* Private browsing/storage limits must not block conversion. */
  }
}

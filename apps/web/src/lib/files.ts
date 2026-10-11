export const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;

export function validatePdf(file: {
  name: string;
  size: number;
}): string | null {
  if (!file.name.toLowerCase().endsWith(".pdf"))
    return "Pilih berkas PDF (.pdf), bukan format lain.";
  if (file.size === 0) return "Berkas ini kosong. Pilih PDF yang dapat dibuka.";
  if (file.size > MAX_UPLOAD_BYTES)
    return "Ukuran PDF melebihi 100 MB. Pilih berkas yang lebih kecil.";
  return null;
}

export function formatBytes(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

"use client";

import { useEffect, useState } from "react";
import { BlockUpdate, UiBlock } from "@/lib/contract";
import { ErrorNotice } from "./Feedback";

export function ImageAltEditor({
  block,
  disabled,
  onSave,
  onDirtyChange,
}: {
  block: UiBlock;
  disabled: boolean;
  onSave: (id: string, update: BlockUpdate) => Promise<void>;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [alt, setAlt] = useState(block.alt ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = alt !== (block.alt ?? "");
  useEffect(() => {
    onDirtyChange(dirty);
    return () => onDirtyChange(false);
  }, [dirty, onDirtyChange]);
  return (
    <form
      className="mt-4 space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (!dirty || busy || disabled) return;
        setBusy(true);
        setError(null);
        void onSave(block.id, { alt })
          .catch((cause) =>
            setError(
              cause instanceof Error
                ? cause.message
                : "Deskripsi gagal disimpan.",
            ),
          )
          .finally(() => setBusy(false));
      }}
    >
      <label htmlFor="image-alt" className="block text-xs font-medium">
        Deskripsi alternatif gambar
      </label>
      <textarea
        id="image-alt"
        className="field min-h-24"
        rows={3}
        maxLength={2000}
        value={alt}
        disabled={disabled || busy}
        onChange={(event) => setAlt(event.target.value)}
      />
      <p className="text-xs leading-relaxed text-stone">
        Deskripsikan gambar untuk pembaca layar. Jangan mengarang teks sumber
        yang tidak terbaca. Deskripsi ikut dalam EPUB.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          type="submit"
          className="btn-primary"
          disabled={!dirty || disabled || busy}
        >
          {busy ? "Menyimpan…" : "Simpan deskripsi"}
        </button>
        <button
          type="button"
          className="btn-secondary"
          disabled={!dirty || disabled || busy}
          onClick={() => setAlt(block.alt ?? "")}
        >
          Batalkan
        </button>
      </div>
      {error ? <ErrorNotice message={error} /> : null}
    </form>
  );
}

/** The supplied artwork stays intact; only its book symbol is framed in the UI. */
export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`brand ${compact ? "brand-compact" : ""}`}>
      <span className="brand-symbol" aria-hidden="true">
        <img src="/brand/arabic-reflow-logo.png" alt="" width={1254} height={1254} />
      </span>
      <span className="brand-name">Arabic<span>Reflow</span></span>
    </span>
  );
}

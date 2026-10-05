export default function Home() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-24">
      <h1 className="text-2xl font-semibold tracking-tight">Reflow</h1>
      <p className="mt-3 leading-relaxed text-neutral-700">
        Convert mixed Arabic&#8211;Latin PDFs into clean, semantic, reflowable
        EPUB 3 books.
      </p>
      <p className="mt-2 leading-relaxed text-neutral-700">
        Preserve first. Reconstruct second. Never invent.
      </p>

      <section className="mt-10 border-t border-neutral-200 pt-6">
        <h2 className="text-sm font-medium text-neutral-900">Status</h2>
        <p className="mt-2 leading-relaxed text-neutral-700">
          The conversion engine and review interface are under development.
          Upload arrives with the API milestone; the engine pipeline currently
          covers analysis, extraction, and script detection.
        </p>
      </section>
    </main>
  );
}

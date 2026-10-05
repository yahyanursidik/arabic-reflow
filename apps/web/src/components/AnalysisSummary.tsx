"use client";

import { Profile } from "@/lib/contract";

function yesNo(value: boolean): string {
  return value ? "ya" : "tidak";
}

export function AnalysisSummary({ profile }: { profile: Profile }) {
  return (
    <section className="rounded-card border border-black/8 bg-pure-white p-6 text-sm">
      <h2 className="text-caption font-semibold uppercase tracking-wide text-stone">
        Ringkasan analisis
      </h2>
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 md:grid-cols-4">
        <div>
          <dt className="text-stone">Halaman</dt>
          <dd className="font-medium text-ink-black">{profile.pageCount}</dd>
        </div>
        <div>
          <dt className="text-stone">Klasifikasi</dt>
          <dd className="font-medium text-ink-black">
            {profile.classification}
            <span className="ml-1 font-normal text-stone">
              ({Math.round(profile.classificationConfidence * 100)}%)
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-stone">Lapisan teks</dt>
          <dd className="font-medium text-ink-black">{yesNo(profile.textLayer)}</dd>
        </div>
        <div>
          <dt className="text-stone">Terdeteksi Arab</dt>
          <dd className="font-medium text-ink-black">{yesNo(profile.arabicDetected)}</dd>
        </div>
      </dl>
      <ul className="mt-4 space-y-1 text-xs text-graphite">
        {profile.scannedPages.length > 0 ? (
          <li>
            Halaman seperti hasil pindai: {profile.scannedPages.join(", ")} —
            butuh OCR untuk menghasilkan teks.
          </li>
        ) : null}
        {profile.likelyMulticolumnPages.length > 0 ? (
          <li>
            Kemungkinan multi-kolom: {profile.likelyMulticolumnPages.join(", ")} —
            urutan baca periksa saat review.
          </li>
        ) : null}
        {!profile.textLayer && profile.scannedPages.length === 0 ? (
          <li>Dokumen ini tidak punya lapisan teks.</li>
        ) : null}
      </ul>
    </section>
  );
}

"use client";

import { Profile } from "@/lib/contract";

function yesNo(value: boolean): string {
  return value ? "ya" : "tidak";
}

export function AnalysisSummary({ profile }: { profile: Profile }) {
  return (
    <section className="border border-neutral-200 p-4 text-sm">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Ringkasan analisis
      </h2>
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 md:grid-cols-4">
        <div>
          <dt className="text-neutral-500">Halaman</dt>
          <dd className="font-medium">{profile.pageCount}</dd>
        </div>
        <div>
          <dt className="text-neutral-500">Klasifikasi</dt>
          <dd className="font-medium">
            {profile.classification}
            <span className="ml-1 font-normal text-neutral-500">
              ({Math.round(profile.classificationConfidence * 100)}%)
            </span>
          </dd>
        </div>
        <div>
          <dt className="text-neutral-500">Lapisan teks</dt>
          <dd className="font-medium">{yesNo(profile.textLayer)}</dd>
        </div>
        <div>
          <dt className="text-neutral-500">Terdeteksi Arab</dt>
          <dd className="font-medium">{yesNo(profile.arabicDetected)}</dd>
        </div>
      </dl>
      <ul className="mt-3 space-y-0.5 text-xs text-neutral-600">
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

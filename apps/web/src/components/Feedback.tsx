import Link from "next/link";

export function ErrorNotice({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-button border border-coral/25 bg-[#fff4f1] p-4 text-sm text-[#a82a17]"
    >
      <p>{message}</p>
      {onRetry ? (
        <button
          type="button"
          className="mt-2 font-semibold underline underline-offset-4"
          onClick={onRetry}
        >
          Coba lagi
        </button>
      ) : null}
    </div>
  );
}

export function WorkflowSteps({ step }: { step: 1 | 2 | 3 | 4 }) {
  return (
    <nav aria-label="Tahapan konversi" className="mb-8">
      <ol className="grid grid-cols-4 gap-2 text-xs sm:text-sm">
        {["Unggah PDF", "Konversi", "Tinjau hasil", "Unduh EPUB"].map(
          (label, index) => (
            <li
              key={label}
              aria-current={index + 1 === step ? "step" : undefined}
              className={`border-t-2 pt-3 ${index + 1 <= step ? "border-notion-blue text-notion-blue" : "border-black/10 text-stone"}`}
            >
              <span className="mb-1 block font-semibold">0{index + 1}</span>
              {label}
            </li>
          ),
        )}
      </ol>
    </nav>
  );
}

export function EmptyDocument({ message }: { message: string }) {
  return (
    <div className="panel mx-auto max-w-2xl py-12 text-center">
      <h1 className="text-heading-sm font-semibold">
        Dokumen belum bisa dibuka
      </h1>
      <div className="mt-4">
        <ErrorNotice message={message} />
      </div>
      <Link className="btn-secondary mt-5" href="/">
        Kembali ke unggahan
      </Link>
    </div>
  );
}

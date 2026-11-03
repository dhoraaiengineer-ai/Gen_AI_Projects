interface AuthCardProps {
  children: React.ReactNode;
}

export function AuthCard({ children }: AuthCardProps) {
  return (
    <div className="w-full max-w-md animate-fade-in">
      {/* Brand + platform description */}
      <div className="mb-8 text-center space-y-3">
        {/* Icon badge */}
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-brand/10 ring-1 ring-brand/30">
          <svg
            className="h-6 w-6 text-brand"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </div>

        {/* Wordmark */}
        <div>
          <p className="text-xl font-bold tracking-tight">
            <span className="text-brand">AutoRAG</span>
            <span className="text-foreground"> Architect</span>
          </p>
          <p className="mt-0.5 text-xs font-medium uppercase tracking-widest text-text-3">
            Enterprise RAG Platform
          </p>
        </div>

        {/* Platform summary — one sentence, helps orient first-time users */}
        <p className="text-xs text-text-3 leading-relaxed max-w-xs mx-auto">
          Autonomous 9-agent loop that builds, evaluates, and self-improves RAG pipelines with zero manual tuning.
        </p>
      </div>

      {/* Card */}
      <div className="rounded-2xl border border-line bg-bg-card p-8 shadow-xl shadow-black/40">
        {children}
      </div>
    </div>
  );
}

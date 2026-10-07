"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

/** Route-level error boundary. Shows a professional message and digest — never a stack trace. */
export default function ErrorBoundary({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.warn("Route error boundary caught an error", { digest: error.digest });
  }, [error]);

  return (
    <div role="alert" className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-critical/10 text-critical">
        <AlertTriangle className="size-6" aria-hidden />
      </span>
      <div>
        <h1 className="text-lg font-semibold">Something went wrong</h1>
        <p className="mt-1 text-sm text-muted-foreground">This page couldn&apos;t be displayed. Your data is safe.</p>
        {error.digest && <p className="mt-2 font-mono text-xs text-muted-foreground">Reference: {error.digest}</p>}
      </div>
      <Button variant="outline" onClick={reset}>
        <RefreshCw /> Try again
      </Button>
    </div>
  );
}

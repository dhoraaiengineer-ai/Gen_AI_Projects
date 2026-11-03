import Link from "next/link";
import { ArrowLeft } from "lucide-react";

interface BackButtonProps {
  href: string;
  label: string;
  className?: string;
}

/** Standard "back to parent list" link, used on detail/sub-pages
 * (e.g. /dashboard/[id], /pipelines/[id]/history, /agents/[agent]). */
export function BackButton({ href, label, className }: BackButtonProps) {
  return (
    <Link
      href={href}
      className={`inline-flex items-center gap-1.5 text-xs font-semibold text-text-3 transition-colors motion-safe:duration-150 hover:text-accent ${className ?? ""}`}
    >
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </Link>
  );
}

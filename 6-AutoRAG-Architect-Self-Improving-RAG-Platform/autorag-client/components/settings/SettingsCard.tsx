import { cn } from "@/lib/utils";

interface SettingsCardProps {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

/** Shared card shell for each settings section. */
export function SettingsCard({ title, description, children, className }: SettingsCardProps) {
  return (
    <div className={cn("rounded-xl border bg-card p-6 shadow-sm", className)}>
      <div className="mb-4">
        <h3 className="text-base font-semibold leading-none tracking-tight">{title}</h3>
        {description && (
          <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {children}
    </div>
  );
}

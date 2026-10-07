import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset [&_svg]:size-3",
  {
    variants: {
      variant: {
        default: "bg-primary/5 text-primary ring-primary/15 dark:bg-primary/10",
        secondary: "bg-muted text-muted-foreground ring-border",
        outline: "text-foreground ring-border",
        success: "bg-success/10 text-success ring-success/20",
        warning: "bg-warning/10 text-warning-foreground ring-warning/25",
        critical: "bg-critical/10 text-critical ring-critical/20",
        ai: "bg-ai-soft text-ai ring-ai/20",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

function Badge({ className, variant, ...props }: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };

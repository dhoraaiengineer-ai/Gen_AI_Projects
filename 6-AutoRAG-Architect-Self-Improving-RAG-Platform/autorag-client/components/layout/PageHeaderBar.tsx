"use client";

import { usePathname } from "next/navigation";

import { NAV_SECTIONS, isActive } from "@/lib/nav";
import { PageHero } from "@/components/layout/PageHero";

function getCrumb(pathname: string): { label: string; category?: string } {
  for (const section of NAV_SECTIONS) {
    const item = section.items.find((i) => isActive(pathname, i));
    if (item) return { label: item.label, category: section.label };
  }
  return { label: "Home" };
}

interface PageHeaderBarProps {
  title?: string;
  description?: string;
}

/**
 * Page-header layer (26-Jul-2026, site_design reference rollout: swapped
 * the plain light title bar for the shared dark-gradient PageHero, matching
 * DarkGradientTitleCard.tsx / EnterprisePlatformLayout.tsx across every
 * page). Still the second of three distinct layers: DashboardTopbar
 * (global, page-agnostic, stays light) -> PageHeaderBar (this) -> page
 * content. Falls back to the nav-derived label/category when a page
 * doesn't pass its own title.
 */
export function PageHeaderBar({ title, description }: PageHeaderBarProps) {
  const pathname = usePathname();
  const crumb = getCrumb(pathname);
  const resolvedTitle = title ?? crumb.label;

  return (
    <div className="bg-ws-1 px-8 pb-2 pt-6">
      <PageHero title={resolvedTitle} description={description} category={crumb.category} />
    </div>
  );
}

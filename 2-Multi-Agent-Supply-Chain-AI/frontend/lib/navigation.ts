import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Boxes,
  Bot,
  FileText,
  LayoutDashboard,
  LineChart,
  Settings,
  Sparkles,
  Truck,
  Factory,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

export interface NavSection {
  title?: string;
  items: NavItem[];
}

export const NAVIGATION: NavSection[] = [
  {
    items: [
      { href: "/", label: "Overview", icon: LayoutDashboard, description: "Supply-chain health at a glance" },
      { href: "/copilot", label: "AI Copilot", icon: Sparkles, description: "Ask the multi-agent copilot" },
    ],
  },
  {
    title: "Operations",
    items: [
      { href: "/inventory", label: "Inventory", icon: Boxes, description: "Stock positions and stockout risk" },
      { href: "/demand", label: "Demand Forecast", icon: LineChart, description: "Forecasts, trend and seasonality" },
      { href: "/suppliers", label: "Suppliers", icon: Factory, description: "Supplier comparison and scoring" },
      { href: "/logistics", label: "Logistics", icon: Truck, description: "Shipments and carrier performance" },
    ],
  },
  {
    title: "Intelligence",
    items: [
      { href: "/agents", label: "Agent Center", icon: Bot, description: "Agent status and performance" },
      { href: "/documents", label: "Documents", icon: FileText, description: "Knowledge base and document search" },
      { href: "/analytics", label: "Analytics", icon: BarChart3, description: "Executive business impact" },
    ],
  },
  {
    title: "System",
    items: [
      { href: "/activity", label: "Activity", icon: Activity, description: "Real-time agent activity" },
      { href: "/settings", label: "Settings", icon: Settings, description: "Preferences and integrations" },
    ],
  },
];

export const ALL_NAV_ITEMS = NAVIGATION.flatMap((s) => s.items);

export function navItemFor(pathname: string): NavItem | undefined {
  if (pathname === "/") return ALL_NAV_ITEMS[0];
  return ALL_NAV_ITEMS.filter((i) => i.href !== "/").find((i) => pathname.startsWith(i.href));
}

export function sectionFor(pathname: string): string | undefined {
  return NAVIGATION.find((s) => s.items.some((i) => i.href !== "/" && pathname.startsWith(i.href)))?.title;
}

import type { LucideIcon } from "lucide-react";
import {
  Boxes,
  Factory,
  FileSearch,
  Globe,
  LineChart,
  Network,
  PenLine,
  ScanSearch,
  Shield,
  ShieldCheck,
  Truck,
  UserCheck,
} from "lucide-react";
import type { PipelineStep } from "@/types";

/** Display metadata for every node in the agent graph. */
export const STEP_META: Record<PipelineStep, { label: string; short: string; icon: LucideIcon; kind: "control" | "agent" | "human" }> = {
  guard: { label: "Input Guardrails", short: "Guardrails", icon: Shield, kind: "control" },
  classifier: { label: "Intent Classifier", short: "Classifier", icon: ScanSearch, kind: "control" },
  supervisor: { label: "Supervisor", short: "Supervisor", icon: Network, kind: "control" },
  demand: { label: "Demand Agent", short: "Demand", icon: LineChart, kind: "agent" },
  inventory: { label: "Inventory Agent", short: "Inventory", icon: Boxes, kind: "agent" },
  supplier: { label: "Supplier Agent", short: "Supplier", icon: Factory, kind: "agent" },
  logistics: { label: "Logistics Agent", short: "Logistics", icon: Truck, kind: "agent" },
  rag: { label: "Knowledge Agent", short: "Knowledge", icon: FileSearch, kind: "agent" },
  research: { label: "Research Agent", short: "Research", icon: Globe, kind: "agent" },
  approval: { label: "Human Approval", short: "Approval", icon: UserCheck, kind: "human" },
  synthesizer: { label: "Synthesizer", short: "Synthesizer", icon: PenLine, kind: "control" },
  validator: { label: "Output Validator", short: "Validator", icon: ShieldCheck, kind: "control" },
};

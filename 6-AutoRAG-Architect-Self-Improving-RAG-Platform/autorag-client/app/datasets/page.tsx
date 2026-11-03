import { AppShell } from "@/components/layout/AppShell";
import { DatasetsPageClient } from "@/components/datasets/DatasetsPageClient";

// 24-Jul-2026: real, DB-backed golden dataset manager (Evaluation Center
// Phase 2) -- replaces the previous AdvancedFeaturePlaceholder now that
// app/routes/evaluation_datasets.py is real and live.
export default function DatasetsPage() {
  return (
    <AppShell
      title="Evaluation Datasets"
      description="Curated, versioned golden-question benchmarks — run the same questions against every pipeline version for an objective comparison."
    >
      <DatasetsPageClient />
    </AppShell>
  );
}

"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { CopilotPanel } from "@/components/copilot/copilot-panel";

function CopilotWithQuery() {
  const params = useSearchParams();
  return <CopilotPanel initialQuestion={params.get("q") ?? undefined} />;
}

export default function CopilotPage() {
  return (
    <Suspense>
      <CopilotWithQuery />
    </Suspense>
  );
}

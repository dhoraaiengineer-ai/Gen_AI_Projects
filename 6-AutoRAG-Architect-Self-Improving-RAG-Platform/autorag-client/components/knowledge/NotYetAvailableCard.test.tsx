import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Layers } from "lucide-react";

import { NotYetAvailableCard } from "@/components/knowledge/NotYetAvailableCard";

describe("NotYetAvailableCard", () => {
  it("renders the title and honest 'not yet available' reason, never a fabricated metric", () => {
    render(
      <NotYetAvailableCard
        title="Chunking"
        icon={Layers}
        reason="chunk-strategy distribution isn't captured at ingestion time yet"
      />,
    );
    expect(screen.getByText("Chunking")).toBeInTheDocument();
    expect(screen.getByText(/Not yet available/)).toBeInTheDocument();
    expect(screen.getByText(/chunk-strategy distribution isn't captured/)).toBeInTheDocument();
  });
});

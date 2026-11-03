import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { AlertCenter } from "@/components/observer/AlertCenter";
import type { ObserverAlert } from "@/lib/observer";

describe("AlertCenter", () => {
  it("shows a positive confirmation when there are no alerts", () => {
    render(<AlertCenter alerts={[]} />);
    expect(screen.getByText(/within thresholds/i)).toBeInTheDocument();
  });

  it("renders each alert with its category and pipeline", () => {
    const alerts: ObserverAlert[] = [
      {
        id: "p1-faith",
        pipelineLabel: "Support · v1.0",
        severity: "critical",
        category: "Hallucination",
        message: "Faithfulness 0.40 below 0.5 hard-block gate.",
      },
    ];
    render(<AlertCenter alerts={alerts} />);
    expect(screen.getByText("Hallucination")).toBeInTheDocument();
    expect(screen.getByText(/Support · v1.0/)).toBeInTheDocument();
  });
});

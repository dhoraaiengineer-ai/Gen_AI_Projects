import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { HealthSummaryCards } from "@/components/health/HealthSummaryCards";

describe("HealthSummaryCards", () => {
  it("renders overall status, uptime, latency, and alerts", () => {
    render(<HealthSummaryCards status="healthy" uptimeRatio={0.998} latencyMs={42} alerts={0} />);
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("99.8%")).toBeInTheDocument();
    expect(screen.getByText("42 ms")).toBeInTheDocument();
  });

  it("emphasizes a critical status and a non-zero alert count", () => {
    // 19-Jul-2026 rebuild on the shared StatCard: the value text itself is
    // always plain white (font-mono text-3xl ... text-foreground) -- color
    // differentiation happens on the icon via the `iconColor` prop (inline
    // style), not a text class. Assert the real mechanism, not text color.
    const { container } = render(
      <HealthSummaryCards status="critical" uptimeRatio={0.5} latencyMs={null} alerts={1} />,
    );
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument(); // failed-probe latency
    expect(screen.getByText("1")).toBeInTheDocument();

    const icons = container.querySelectorAll("svg");
    expect(icons[0]).toHaveStyle({ color: "rgb(244, 63, 94)" }); // Overall Health icon tinted critical red
    expect(icons[3]).toHaveStyle({ color: "rgb(244, 63, 94)" }); // Active Alerts icon tinted red when alerts > 0
  });
});

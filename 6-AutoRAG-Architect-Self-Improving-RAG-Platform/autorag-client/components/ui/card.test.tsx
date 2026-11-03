import { render, screen } from "@testing-library/react";
import { Card, CardHeader, CardTitle, CardContent } from "./card";

describe("Card", () => {
  it("renders without crashing", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Test Card</CardTitle>
        </CardHeader>
        <CardContent>
          <p>This is a test card.</p>
        </CardContent>
      </Card>
    );
    expect(screen.getByText("Test Card")).toBeInTheDocument();
    expect(screen.getByText("This is a test card.")).toBeInTheDocument();
  });
});
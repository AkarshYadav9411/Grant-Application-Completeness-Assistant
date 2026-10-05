import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("renders readable status text", () => {
    render(<StatusBadge status="PARTIALLY_SUPPORTED" />);
    expect(screen.getByText("Partially Supported")).toBeInTheDocument();
  });

  it("renders compact label", () => {
    render(<StatusBadge status="PARTIALLY_SUPPORTED" compact />);
    expect(screen.getByText("Partial")).toBeInTheDocument();
  });
});

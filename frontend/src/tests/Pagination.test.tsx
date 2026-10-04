import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import Pagination from "@/components/Pagination";

describe("Pagination", () => {
  it("hides when a single page", () => {
    const { container } = render(
      <Pagination page={1} totalPages={1} totalItems={5} pageSize={20} onChange={() => {}} label="Test pagination" />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows range and navigates", () => {
    const onChange = vi.fn();
    render(
      <Pagination page={1} totalPages={3} totalItems={45} pageSize={20} onChange={onChange} label="Test pagination" />
    );
    expect(screen.getByText(/Showing/)).toHaveTextContent("1–20 of 45");
    expect(screen.getByRole("button", { name: "Page 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(onChange).toHaveBeenCalledWith(2);
  });

  it("marks current page", () => {
    render(
      <Pagination page={2} totalPages={3} totalItems={45} pageSize={20} onChange={() => {}} label="Test pagination" />
    );
    expect(screen.getByRole("button", { name: "Page 2" })).toHaveAttribute("aria-current", "page");
  });
});

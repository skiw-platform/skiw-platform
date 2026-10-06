import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { content } from "./content";

describe("App shell", () => {
  afterEach(cleanup);

  it("has exactly one main landmark and one level-1 heading", () => {
    render(<App />);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("names the navigation and gives every link a real href", () => {
    render(<App />);
    const nav = screen.getByRole("navigation", { name: content.navLabel });
    const links = nav.querySelectorAll("a");
    expect(links.length).toBeGreaterThan(0);
    links.forEach((link) => {
      expect(link.getAttribute("href")).toMatch(/^\//);
    });
  });

  it("offers a skip link that targets the main landmark", () => {
    render(<App />);
    const skip = screen.getByRole("link", { name: content.skipLink });
    expect(skip.getAttribute("href")).toBe("#main");
    expect(screen.getByRole("main").getAttribute("id")).toBe("main");
  });
});

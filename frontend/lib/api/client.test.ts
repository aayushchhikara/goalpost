import { describe, expect, it } from "vitest";

import { api } from "./client";

describe("api client", () => {
  it("exposes typed request helpers", () => {
    expect(typeof api.GET).toBe("function");
  });
});

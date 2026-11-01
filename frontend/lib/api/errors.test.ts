import { describe, expect, it } from "vitest";

import { ApiError, unwrap } from "./errors";

const reply = (status: number, body?: unknown) => {
  const response = new Response(body === undefined ? null : JSON.stringify(body), { status });
  return Promise.resolve(
    response.ok ? { data: body as never, response } : { error: body, response },
  );
};

describe("unwrap", () => {
  it("returns data", async () => {
    await expect(unwrap(reply(200, { ok: true }))).resolves.toEqual({ ok: true });
  });

  it("treats 204 No Content as success", async () => {
    await expect(unwrap(reply(204))).resolves.toBeUndefined();
  });

  it("throws the backend's error message", async () => {
    const error = await unwrap(
      reply(409, { code: "already_done", message: "Occurrence is already done", details: [] }),
    ).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("already_done");
    expect((error as ApiError).message).toBe("Occurrence is already done");
  });

  it("prefers the first field detail", async () => {
    const error = await unwrap(
      reply(422, {
        code: "validation_error",
        message: "Request is invalid",
        details: [{ field: "filters.0", message: "'author' isn't a rule field" }],
      }),
    ).catch((e: unknown) => e);
    expect((error as ApiError).message).toBe("'author' isn't a rule field");
  });
});

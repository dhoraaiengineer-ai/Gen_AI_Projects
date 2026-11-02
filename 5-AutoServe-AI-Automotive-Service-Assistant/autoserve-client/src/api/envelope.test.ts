import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, HealthSchema, apiGet } from "./envelope";

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ status, json: async () => body }));
}

afterEach(() => vi.unstubAllGlobals());

describe("apiGet", () => {
  it("returns validated data on ok", async () => {
    mockFetch(200, { status: "ok", data: { status: "ok" }, error: null, request_id: "r1" });
    await expect(apiGet("/health", HealthSchema)).resolves.toEqual({ status: "ok" });
  });

  it("throws ApiError with the envelope code on error", async () => {
    mockFetch(404, { status: "error", data: null, error: { code: "NOT_FOUND", message: "Not found." }, request_id: "r2" });
    await expect(apiGet("/x", HealthSchema)).rejects.toMatchObject({ code: "NOT_FOUND", requestId: "r2", httpStatus: 404 });
  });

  it("rejects a response that does not match the schema", async () => {
    mockFetch(200, { status: "ok", data: { status: "weird" }, error: null, request_id: "r3" });
    await expect(apiGet("/health", HealthSchema)).rejects.not.toBeInstanceOf(ApiError);
  });
});

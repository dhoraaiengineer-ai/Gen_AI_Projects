import { z } from "zod";

/** API envelope {status, data, error, request_id} — every response is parsed with Zod before use (rules/20). */
export const ErrorBodySchema = z.object({
  code: z.string(),
  message: z.string(),
  details: z.record(z.unknown()).nullish(),
});

export const envelopeSchema = <T extends z.ZodTypeAny>(data: T) =>
  z.object({
    status: z.enum(["ok", "error"]),
    data: data.nullable(),
    error: ErrorBodySchema.nullable(),
    request_id: z.string(),
  });

export const HealthSchema = z.object({ status: z.literal("ok") });

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly requestId: string,
    public readonly httpStatus: number,
  ) {
    super(message);
  }
}

export async function apiGet<T extends z.ZodTypeAny>(path: string, schema: T, init?: RequestInit): Promise<z.infer<T>> {
  const resp = await fetch(path, { ...init, headers: { Accept: "application/json", ...init?.headers } });
  const env = envelopeSchema(schema).parse(await resp.json());
  if (env.status === "error" || env.data === null) {
    throw new ApiError(env.error?.code ?? "INTERNAL_ERROR", env.error?.message ?? "Request failed", env.request_id, resp.status);
  }
  return env.data;
}

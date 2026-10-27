import type { ApiErrorBody } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Return the response data, or throw an ApiError carrying the backend's error shape. */
export async function unwrap<T>(request: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await request;
  if (error !== undefined || data === undefined) {
    const body = (error ?? {}) as Partial<ApiErrorBody>;
    const detail = body.details?.[0]?.message;
    throw new ApiError(
      detail ?? body.message ?? `Request failed (${response.status})`,
      body.code ?? "error",
      response.status,
    );
  }
  return data;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) return "Can't reach the backend. Is it running? (make dev)";
  return "Something went wrong.";
}

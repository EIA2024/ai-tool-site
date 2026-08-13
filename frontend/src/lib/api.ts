import type { ApiResponse } from "../types";

const BASE = import.meta.env.VITE_API_BASE || "/api";
const DEFAULT_TIMEOUT_MS = 30_000;

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

interface RequestOptions {
  timeoutMs?: number;
}

async function request<T>(
  path: string,
  init: RequestInit,
  opts: RequestOptions = {}
): Promise<ApiResponse<T>> {
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, signal: controller.signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("TIMEOUT", `Request timed out after ${timeoutMs}ms`, 408);
    }
    throw new ApiError("NETWORK_ERROR", `Network error: ${String(err)}`, 0);
  } finally {
    clearTimeout(timer);
  }

  let body: ApiResponse<T>;
  try {
    body = (await res.json()) as ApiResponse<T>;
  } catch {
    throw new ApiError(
      "INVALID_RESPONSE",
      `Server returned non-JSON (HTTP ${res.status})`,
      res.status
    );
  }

  if (!res.ok) {
    throw new ApiError(
      body.error?.code ?? "HTTP_ERROR",
      body.error?.message ?? `HTTP ${res.status}`,
      res.status
    );
  }
  return body;
}

export function get<T = unknown>(
  path: string,
  opts?: RequestOptions
): Promise<ApiResponse<T>> {
  return request<T>(path, { method: "GET" }, opts);
}

export function post<T = unknown>(
  path: string,
  body: unknown,
  opts?: RequestOptions
): Promise<ApiResponse<T>> {
  return request<T>(
    path,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    opts
  );
}

export function del<T = unknown>(
  path: string,
  opts?: RequestOptions
): Promise<ApiResponse<T>> {
  return request<T>(path, { method: "DELETE" }, opts);
}

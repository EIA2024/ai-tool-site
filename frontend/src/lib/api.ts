import type { ApiResponse, RequestOptions } from "../types";

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

async function request<T>(
  path: string,
  init: RequestInit,
  opts: RequestOptions = {}
): Promise<ApiResponse<T>> {
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  let timedOut = false;
  let callerAborted = opts.signal?.aborted ?? false;
  let rejectCancellation: (reason: DOMException) => void = () => {};
  const cancellation = new Promise<never>((_, reject) => {
    rejectCancellation = reject;
  });
  const onInternalAbort = () => {
    rejectCancellation(new DOMException("Aborted", "AbortError"));
  };
  const onCallerAbort = () => {
    callerAborted = true;
    controller.abort();
  };
  const timer = setTimeout(() => {
    if (!controller.signal.aborted) {
      timedOut = true;
      controller.abort();
    }
  }, timeoutMs);

  controller.signal.addEventListener("abort", onInternalAbort, { once: true });
  if (callerAborted) {
    controller.abort();
  } else {
    opts.signal?.addEventListener("abort", onCallerAbort, { once: true });
  }

  try {
    const res = await Promise.race([
      fetch(`${BASE}${path}`, { ...init, signal: controller.signal }),
      cancellation,
    ]);

    let body: ApiResponse<T>;
    try {
      body = (await Promise.race([res.json(), cancellation])) as ApiResponse<T>;
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        throw err;
      }
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
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      if (timedOut) {
        throw new ApiError("TIMEOUT", `Request timed out after ${timeoutMs}ms`, 408);
      }
      if (callerAborted) {
        throw new ApiError("ABORTED", "Request was aborted", 0);
      }
    }
    if (err instanceof ApiError) throw err;
    throw new ApiError("NETWORK_ERROR", `Network error: ${String(err)}`, 0);
  } finally {
    clearTimeout(timer);
    opts.signal?.removeEventListener("abort", onCallerAbort);
    controller.signal.removeEventListener("abort", onInternalAbort);
  }
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

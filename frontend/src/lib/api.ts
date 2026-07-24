import type { ApiResponse } from "../types";

const BASE = "/api";

export async function get<T = unknown>(path: string): Promise<ApiResponse<T>> {
  const res = await fetch(`${BASE}${path}`);
  return res.json();
}

export async function post<T = unknown>(
  path: string,
  body: unknown
): Promise<ApiResponse<T>> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

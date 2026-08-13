import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, get } from "../src/lib/api";

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("API request cancellation", () => {
  it("times out while reading the response body", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => new Promise(() => {}),
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = get("/slow", { timeoutMs: 50 });
    const assertion = expect(request).rejects.toMatchObject<ApiError>({
      code: "TIMEOUT",
      status: 408,
    });
    await vi.advanceTimersByTimeAsync(50);

    await assertion;
  });

  it("distinguishes caller cancellation from timeout", async () => {
    const controller = new AbortController();
    const fetchMock = vi.fn().mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        })
    );
    vi.stubGlobal("fetch", fetchMock);

    const request = get("/cancelled", {
      timeoutMs: 10_000,
      signal: controller.signal,
    });
    controller.abort();

    await expect(request).rejects.toMatchObject<ApiError>({
      code: "ABORTED",
      status: 0,
    });
  });

  it("removes the caller abort listener after completion", async () => {
    const controller = new AbortController();
    const addSpy = vi.spyOn(controller.signal, "addEventListener");
    const removeSpy = vi.spyOn(controller.signal, "removeEventListener");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ success: true, data: "ok" }),
      })
    );

    await get("/done", { signal: controller.signal });

    expect(addSpy).toHaveBeenCalledOnce();
    expect(removeSpy).toHaveBeenCalledWith("abort", addSpy.mock.calls[0][1]);
  });
});

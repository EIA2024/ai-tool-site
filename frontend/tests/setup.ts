import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// vitest runs without `globals`, so testing-library can't auto-register its
// cleanup hook. Do it here so each test starts from a clean DOM.
afterEach(() => {
  cleanup();
});

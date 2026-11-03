import "@testing-library/jest-dom/vitest";

import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// React Testing Library does not auto-clean without globals; register it here.
afterEach(() => {
  cleanup();
});

// jsdom does not implement ResizeObserver; recharts' ResponsiveContainer
// requires it to mount. Stub it so chart components can render in tests.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

// jsdom does not implement the Pointer Capture API; Radix UI (Select, etc.)
// calls these on pointer interactions and throws "not a function" otherwise.
Element.prototype.hasPointerCapture ??= () => false;
Element.prototype.setPointerCapture ??= () => {};
Element.prototype.releasePointerCapture ??= () => {};

// jsdom does not implement scrollIntoView either; Radix Select calls it when
// scrolling the highlighted option into view on open.
Element.prototype.scrollIntoView ??= () => {};

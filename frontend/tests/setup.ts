import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// jsdom has no ResizeObserver; React Flow (frontend/src/canvas/) observes its
// pane and node elements unconditionally, so tests need a stub. jsdom also
// has no real layout, so this can't report genuine sizes — tests that care
// about React Flow's measured output (e.g. rendered edge paths) should
// assert against the pure builders in canvas/toFlowGraph.ts instead.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??=
  ResizeObserverStub as unknown as typeof ResizeObserver;

// jsdom also has no DOMMatrixReadOnly, which React Flow uses to read the
// viewport's zoom out of its CSS transform.
class DOMMatrixReadOnlyStub {
  m22: number;

  constructor(transform: string) {
    const scale = transform?.match(/scale\(([\d.]+)\)/)?.[1];
    this.m22 = scale ? Number(scale) : 1;
  }
}
// @ts-expect-error jsdom stub, not a full DOMMatrixReadOnly implementation
globalThis.DOMMatrixReadOnly ??= DOMMatrixReadOnlyStub;

afterEach(() => {
  cleanup();
});

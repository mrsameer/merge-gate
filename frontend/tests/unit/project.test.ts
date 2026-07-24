// Project-init test for T003 — the frontend must be an initialized Vite +
// React 18 + TypeScript project declaring its canvas/state stack.
//
// plan.md names the frontend's primary dependencies (React 18, @xyflow/react,
// Vite, Zustand) and its TypeScript version floor. This test encodes that
// promise against frontend/package.json so the dependency set stays
// reviewable in one place and can't silently drift.

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

// <root>/frontend/tests/unit/project.test.ts
const FRONTEND_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
);
const PACKAGE_JSON_PATH = path.join(FRONTEND_ROOT, "package.json");

const EXPECTED_DEPENDENCIES: Record<string, string | null> = {
  react: "18",
  "react-dom": "18",
  "@xyflow/react": null,
  zustand: null,
};

const EXPECTED_DEV_DEPENDENCIES: Record<string, string | null> = {
  typescript: "5",
  vite: null,
};

function loadPackageJson(): {
  dependencies?: Record<string, string>;
  devDependencies?: Record<string, string>;
} {
  return JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf8"));
}

function assertDeclaresRange(
  deps: Record<string, string>,
  name: string,
  majorPrefix: string | null,
) {
  const range = deps[name];
  expect(range, `missing dependency: ${name}`).toBeTruthy();
  if (majorPrefix) {
    const version = range.replace(/^[\^~]/, "");
    expect(
      version.startsWith(majorPrefix),
      `expected ${name}@${majorPrefix}.x, got ${range}`,
    ).toBe(true);
  }
}

describe("frontend project scaffold", () => {
  it("frontend/package.json exists", () => {
    expect(existsSync(PACKAGE_JSON_PATH)).toBe(true);
  });

  it("package.json declares the React Flow canvas + state dependencies", () => {
    const { dependencies = {} } = loadPackageJson();
    for (const [name, majorPrefix] of Object.entries(EXPECTED_DEPENDENCIES)) {
      assertDeclaresRange(dependencies, name, majorPrefix);
    }
  });

  it("package.json declares Vite + TypeScript 5.x as dev dependencies", () => {
    const { devDependencies = {} } = loadPackageJson();
    for (const [name, majorPrefix] of Object.entries(
      EXPECTED_DEV_DEPENDENCIES,
    )) {
      assertDeclaresRange(devDependencies, name, majorPrefix);
    }
  });
});

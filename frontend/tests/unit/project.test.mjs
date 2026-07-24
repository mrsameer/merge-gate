// Project-init test for T003 — the frontend must be an initialized Vite +
// React 18 + TypeScript project declaring its canvas/state stack.
//
// plan.md names the frontend's primary dependencies (React 18, @xyflow/react,
// Vite, Zustand) and its TypeScript version floor. This test encodes that
// promise against frontend/package.json so the dependency set stays
// reviewable in one place and can't silently drift. It uses only Node's
// built-in test runner and fs/JSON — no installed dependencies required —
// so it can run (and fail for the right reason) before `npm install` exists.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

// <root>/frontend/tests/unit/project.test.mjs
const FRONTEND_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
);
const PACKAGE_JSON_PATH = path.join(FRONTEND_ROOT, "package.json");

const EXPECTED_DEPENDENCIES = {
  react: "18",
  "react-dom": "18",
  "@xyflow/react": null,
  zustand: null,
};

const EXPECTED_DEV_DEPENDENCIES = {
  typescript: "5",
  vite: null,
};

function loadPackageJson() {
  return JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf8"));
}

function assertDeclaresRange(deps, name, majorPrefix) {
  const range = deps[name];
  assert.ok(range, `missing dependency: ${name}`);
  if (majorPrefix) {
    const version = range.replace(/^[\^~]/, "");
    assert.ok(
      version.startsWith(majorPrefix),
      `expected ${name}@${majorPrefix}.x, got ${range}`,
    );
  }
}

test("frontend/package.json exists", () => {
  assert.ok(existsSync(PACKAGE_JSON_PATH), "frontend/package.json is missing");
});

test("package.json declares the React Flow canvas + state dependencies", () => {
  const { dependencies = {} } = loadPackageJson();
  for (const [name, majorPrefix] of Object.entries(EXPECTED_DEPENDENCIES)) {
    assertDeclaresRange(dependencies, name, majorPrefix);
  }
});

test("package.json declares Vite + TypeScript 5.x as dev dependencies", () => {
  const { devDependencies = {} } = loadPackageJson();
  for (const [name, majorPrefix] of Object.entries(EXPECTED_DEV_DEPENDENCIES)) {
    assertDeclaresRange(devDependencies, name, majorPrefix);
  }
});

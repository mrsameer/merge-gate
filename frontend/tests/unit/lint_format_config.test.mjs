// Config test for T004 — the frontend must have eslint + prettier configured.
//
// tasks.md T004 requires eslint (lint) and prettier (format) to be set up for
// the frontend. This test encodes that promise against frontend/package.json
// and the presence of config files, so the tooling can't silently disappear.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

// <root>/frontend/tests/unit/lint_format_config.test.mjs
const FRONTEND_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
);
const PACKAGE_JSON_PATH = path.join(FRONTEND_ROOT, "package.json");

function loadPackageJson() {
  return JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf8"));
}

test("package.json declares eslint and prettier as dev dependencies", () => {
  const { devDependencies = {} } = loadPackageJson();
  for (const name of ["eslint", "prettier"]) {
    assert.ok(devDependencies[name], `missing dev dependency: ${name}`);
  }
});

test("package.json declares lint and format scripts", () => {
  const { scripts = {} } = loadPackageJson();
  assert.ok(scripts.lint, "missing npm script: lint");
  assert.ok(scripts.format, "missing npm script: format");
});

test("eslint flat config file exists", () => {
  assert.ok(
    existsSync(path.join(FRONTEND_ROOT, "eslint.config.js")),
    "frontend/eslint.config.js is missing",
  );
});

test("prettier config file exists", () => {
  const candidates = [".prettierrc", ".prettierrc.json", "prettier.config.js"];
  const found = candidates.some((name) =>
    existsSync(path.join(FRONTEND_ROOT, name)),
  );
  assert.ok(found, "no prettier config file found in frontend/");
});

// Config test for T004 — the frontend must have eslint + prettier configured.
//
// tasks.md T004 requires eslint (lint) and prettier (format) to be set up for
// the frontend. This test encodes that promise against frontend/package.json
// and the presence of config files, so the tooling can't silently disappear.

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

// <root>/frontend/tests/unit/lint_format_config.test.ts
const FRONTEND_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
);
const PACKAGE_JSON_PATH = path.join(FRONTEND_ROOT, "package.json");

function loadPackageJson(): {
  devDependencies?: Record<string, string>;
  scripts?: Record<string, string>;
} {
  return JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf8"));
}

describe("frontend lint + format tooling", () => {
  it("package.json declares eslint and prettier as dev dependencies", () => {
    const { devDependencies = {} } = loadPackageJson();
    for (const name of ["eslint", "prettier"]) {
      expect(
        devDependencies[name],
        `missing dev dependency: ${name}`,
      ).toBeTruthy();
    }
  });

  it("package.json declares lint and format scripts", () => {
    const { scripts = {} } = loadPackageJson();
    expect(scripts.lint, "missing npm script: lint").toBeTruthy();
    expect(scripts.format, "missing npm script: format").toBeTruthy();
  });

  it("eslint flat config file exists", () => {
    expect(
      existsSync(path.join(FRONTEND_ROOT, "eslint.config.js")),
      "frontend/eslint.config.js is missing",
    ).toBe(true);
  });

  it("prettier config file exists", () => {
    const candidates = [
      ".prettierrc",
      ".prettierrc.json",
      "prettier.config.js",
    ];
    const found = candidates.some((name) =>
      existsSync(path.join(FRONTEND_ROOT, name)),
    );
    expect(found, "no prettier config file found in frontend/").toBe(true);
  });
});

#!/usr/bin/env node
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = join(dirname(fileURLToPath(import.meta.url)), "..");
const dest = join(rootDir, "desktop", "src-tauri", "resources", "stack");

const copyItems = [
  { src: "docker-compose.yml", dest: "docker-compose.yml", type: "file" },
  { src: ".env.example", dest: ".env.example", type: "file" },
  { src: "scripts", dest: "scripts", type: "dir" },
  { src: "backend", dest: "backend", type: "dir" },
  { src: "frontend", dest: "frontend", type: "dir" },
];

const excludeDirNames = new Set([
  ".venv",
  "__pycache__",
  ".pytest_cache",
  "node_modules",
  "dist",
  ".ruff_cache",
]);

function shouldSkip(name) {
  return excludeDirNames.has(name);
}

function copyFiltered(src, target) {
  mkdirSync(target, { recursive: true });
  for (const name of readdirSync(src)) {
    if (shouldSkip(name)) {
      continue;
    }
    const from = join(src, name);
    const to = join(target, name);
    if (statSync(from).isDirectory()) {
      copyFiltered(from, to);
    } else {
      cpSync(from, to);
    }
  }
}

function main() {
  console.log(`[prepare-stack] Preparing desktop stack bundle at ${dest}`);
  rmSync(dest, { recursive: true, force: true });
  mkdirSync(dest, { recursive: true });

  for (const item of copyItems) {
    const srcPath = join(rootDir, item.src);
    const destPath = join(dest, item.dest);
    if (!existsSync(srcPath)) {
      throw new Error(`Missing source path: ${srcPath}`);
    }
    if (item.type === "file") {
      cpSync(srcPath, destPath);
      continue;
    }
    copyFiltered(srcPath, destPath);
  }

  console.log("[prepare-stack] Stack bundle ready");
}

main();

import { cp, mkdir, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const standaloneDir = path.join(root, ".next", "standalone");
const staticSource = path.join(root, ".next", "static");
const staticTarget = path.join(standaloneDir, ".next", "static");
const publicSource = path.join(root, "public");
const publicTarget = path.join(standaloneDir, "public");

if (!existsSync(standaloneDir) || !existsSync(staticSource)) {
  throw new Error("Standalone build output is missing. Run `npm run build` before `npm run test:e2e`.");
}

await mkdir(path.dirname(staticTarget), { recursive: true });
await rm(staticTarget, { recursive: true, force: true });
await cp(staticSource, staticTarget, { recursive: true });

if (existsSync(publicSource)) {
  await rm(publicTarget, { recursive: true, force: true });
  await cp(publicSource, publicTarget, { recursive: true });
}

console.log("Prepared standalone assets for Playwright.");

// @vitest-environment node
import { cp, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";

import { build } from "vite";
import { expect, it } from "vitest";

async function iconUrl(svg: string): Promise<string> {
  // Inside web/ so the scratch copy resolves the same node_modules.
  const root = await mkdtemp(join(process.cwd(), ".icon-hash-"));
  try {
    await cp("index.html", join(root, "index.html"));
    await cp("src", join(root, "src"), { recursive: true });
    await mkdir(join(root, "dist"));
    await writeFile(join(root, "src", "icon.svg"), svg);
    await build({ root, logLevel: "silent", configFile: join(process.cwd(), "vite.config.ts") });
    const html = await readFile(join(root, "dist", "index.html"), "utf8");
    return /rel="icon" href="([^"]+)"/.exec(html)?.[1] ?? "";
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

it("gives the icon a content-hashed URL that changes with its content", async () => {
  const a = await iconUrl('<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>');
  const b = await iconUrl('<svg xmlns="http://www.w3.org/2000/svg"><rect width="2" height="2"/></svg>');
  expect(a).toMatch(/^\/assets\/icon-[\w-]{8}\.svg$/);
  expect(b).toMatch(/^\/assets\/icon-[\w-]{8}\.svg$/);
  expect(a).not.toEqual(b);
}, 60_000);

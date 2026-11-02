import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

/** Creates the synthetic ROs for both journeys (scripts/e2e_setup.py) and stores their ids for the tests. */
export default function globalSetup() {
  const db = process.env.API_DATABASE_URL ?? "postgresql+asyncpg://autoserve:autoserve@localhost:5433/autoserve";
  const out = execFileSync("uv", ["run", "python", "-m", "scripts.e2e_setup"], {
    cwd: join(HERE, "..", "..", "autoserve-server"),
    env: { ...process.env, DATABASE_URL: db, DATABASE_POOLER_MODE: "direct", PYTHONIOENCODING: "utf-8" },
    encoding: "utf-8",
    timeout: 300_000,
  });
  const start = out.search(/^\{\r?$/m); // the pretty-printed JSON block (log lines may precede it)
  const json = out.slice(start).replace(/\r\n/g, "\n");
  JSON.parse(json); // fail fast on unexpected output
  writeFileSync(join(HERE, ".data.json"), json, "utf-8");
}

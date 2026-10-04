import { readFileSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";

/** Stop the simulator spawned by globalSetup. */
export default async function globalTeardown() {
  const e2eDir = resolve(__dirname, "..", "..", "..", ".e2e");
  try {
    const pid = Number(readFileSync(join(e2eDir, "sim.pid"), "utf-8"));
    if (pid) process.kill(pid);
  } catch {
    // Already gone; continue.
  }
  void rmSync;
}

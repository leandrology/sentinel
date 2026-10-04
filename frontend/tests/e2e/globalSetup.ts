import { spawnSync, spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

/** Generate the synthetic video and start the event simulator for E2E. */
export default async function globalSetup() {
  const root = resolve(__dirname, "..", "..", "..");
  const e2eDir = join(root, ".e2e");
  mkdirSync(e2eDir, { recursive: true });
  const python = join(root, "backend", ".venv", "Scripts", "python.exe");

  const gen = spawnSync(python, [join(root, "scripts", "generate_test_video.py"), join(e2eDir, "motion.mp4")], {
    cwd: root,
    encoding: "utf-8",
  });
  if (gen.status !== 0) throw new Error(`video fixture failed: ${gen.stderr}`);

  try {
    const fs = await import("node:fs");
    fs.rmSync(join(e2eDir, "e2e.db"), { force: true });
  } catch {
    // No stale DB; continue.
  }

  const log = join(e2eDir, "simulator.log");
  const sim = spawn(python, [join(root, "scripts", "run_simulator.py")], {
    cwd: root,
    detached: true,
    stdio: ["ignore", "ignore", "ignore"],
  });
  sim.unref();
  if (!sim.pid) throw new Error("simulator did not start");
  writeFileSync(join(e2eDir, "sim.pid"), String(sim.pid));
  // Give the simulator a moment to bind before the backend connects.
  await new Promise((r) => setTimeout(r, 2500));
  void log;
}

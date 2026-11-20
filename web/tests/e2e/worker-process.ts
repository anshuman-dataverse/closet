import { type ChildProcess, spawn } from "node:child_process";
import path from "node:path";
import { OWNER, SERVICE_KEY, SUPABASE_URL, WORKER_ID } from "./env";

const WORKER_DIR = path.resolve(__dirname, "../../../worker");

/** Starts the real worker in --fake mode against the local stack. */
export function startFakeWorker(): ChildProcess {
  const child = spawn("uv", ["run", "--project", WORKER_DIR, "closet-worker", "--fake"], {
    cwd: WORKER_DIR,
    env: {
      ...process.env,
      SUPABASE_URL,
      SUPABASE_SERVICE_ROLE_KEY: SERVICE_KEY,
      OWNER_USER_ID: OWNER.id,
      WORKER_ID,
      DATABASE_URL: "",
      OPENAI_API_KEY: "",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.stderr?.on("data", (d: Buffer) => {
    if (process.env.E2E_DEBUG) process.stderr.write(`[worker] ${d}`);
  });
  return child;
}

export async function stopWorker(child: ChildProcess | undefined) {
  if (!child || child.exitCode !== null) return;
  const exited = new Promise((r) => child.once("exit", r));
  child.kill("SIGTERM");
  await Promise.race([exited, new Promise((r) => setTimeout(r, 5000))]);
  if (child.exitCode === null) child.kill("SIGKILL");
}

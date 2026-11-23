"""Job loop: heartbeat every 30s, claim every 3s, dispatch with per-kind timeouts.

Nothing here listens on a port. All traffic is outbound to Supabase.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime
from typing import Any

from . import __version__, capabilities, fakes
from .config import Settings, load_settings
from .jobs import NotImplementedYet, TransientError, implemented, spec_for
from .jobs.context import JobContext
from .queue import Job, Queue, SupabaseQueue
from .scheduler import STATE_PATH, Scheduler
from .store import SupabaseItemStore

log = logging.getLogger("closet_worker")

HEARTBEAT_S = 30.0
CLAIM_S = 3.0
MAX_TRIES = 3
BACKOFF_S = (1.0, 2.0, 4.0)


def execute(
    job: Job, *, fake: bool, ctx: JobContext | None = None, sleep: Any = time.sleep
) -> dict[str, Any]:
    """Run one job's handler with its timeout and transient retries. Raises on failure."""
    spec = spec_for(job.kind)
    if fake:
        return fakes.run(job.kind, job.payload, ctx)
    if spec.handler is None:
        raise NotImplementedYet(f"'{job.kind}' isn't built yet")
    handler = spec.handler
    for attempt in range(MAX_TRIES):
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            return pool.submit(handler, job.payload, ctx).result(timeout=spec.timeout_s)
        except FutureTimeout as e:
            raise TimeoutError(f"Timed out after {spec.timeout_s:.0f}s") from e
        except TransientError:
            if attempt == MAX_TRIES - 1:
                raise
            sleep(BACKOFF_S[attempt])
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    raise AssertionError("unreachable")


def process(queue: Queue, job: Job, *, fake: bool, ctx: JobContext | None = None) -> None:
    log.info("job %s %s (attempt %s)", job.id, job.kind, job.attempts)
    try:
        result = execute(job, fake=fake, ctx=ctx)
    except Exception as e:  # report every failure to the app instead of crashing
        msg = str(e) or e.__class__.__name__
        log.warning("job %s failed: %s", job.id, msg)
        queue.fail(job, msg)
        return
    queue.complete(job, result)


LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class FakeModeRefused(SystemExit):
    pass


def require_local(supabase_url: str) -> None:
    """Fake mode (sample results for automated tests) may only run against the local test
    database, so it can never write sample data into a real closet."""
    from urllib.parse import urlsplit

    host = urlsplit(supabase_url).hostname or ""
    if host not in LOCAL_HOSTS:
        raise FakeModeRefused(
            f"Fake mode only runs against local Supabase (127.0.0.1), not {host}. "
            "It's for automated tests. Start the worker without --fake."
        )


class Worker:
    def __init__(
        self,
        settings: Settings,
        queue: Queue,
        *,
        fake: bool,
        scheduler: Scheduler | None = None,
        ctx: JobContext | None = None,
    ) -> None:
        if fake:
            require_local(settings.supabase_url)
        self.s = settings
        self.queue = queue
        self.fake = fake
        self.ctx = ctx or JobContext(settings=settings)
        self.stop = threading.Event()
        # Fake mode (e2e) runs no nightly tasks (they'd race the tests) and keeps its own state
        # file, so a test run can never mark the real worker's nightly backup as done.
        self.scheduler = scheduler or (
            Scheduler(STATE_PATH.with_name("scheduler-fake.json"), daily=())
            if fake
            else Scheduler(STATE_PATH)
        )

    def beat(self) -> None:
        caps = (
            {
                "searxng": True,
                "ollama": False,
                "openai": False,
                "compat": {"installed": False, "on": False, "n": 0, "need": 30},
            }
            if self.fake
            else capabilities.detect(self.s)
        )
        self.queue.heartbeat(__version__, caps)

    def _heartbeat_loop(self) -> None:
        while not self.stop.is_set():
            try:
                self.beat()
            except Exception as e:
                log.warning("heartbeat failed: %s", e)
            self.stop.wait(HEARTBEAT_S)

    def tick(self) -> bool:
        """One pass: scheduled tasks, then claim and run at most one job. True if a job ran."""
        now = datetime.now()
        if self.scheduler.requeue_due(now):
            n = self.queue.requeue_stale()
            if n:
                log.info("requeued %s stale jobs", n)
        for kind in self.scheduler.due_kinds(now, implemented()):
            self.queue.enqueue(kind)
        job = self.queue.claim()
        if job is None:
            return False
        process(self.queue, job, fake=self.fake, ctx=self.ctx)
        return True

    def run(self, *, once: bool = False) -> None:
        self.beat()
        if once:
            while self.tick():
                pass
            return
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        while not self.stop.is_set():
            try:
                busy = self.tick()
            except Exception as e:  # e.g. Supabase unreachable: keep going
                log.warning("loop error: %s", e)
                busy = False
            if not busy:
                self.stop.wait(CLAIM_S)


def cli() -> None:
    p = argparse.ArgumentParser(prog="closet-worker")
    p.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "export-eval", "compat-eval", "import", "backup", "restore"],
    )
    p.add_argument("--fake", action="store_true", help="return fixtures instead of running models")
    p.add_argument("--once", action="store_true", help="drain the queue once, then exit")
    p.add_argument("--out", default="~/ClosetPhotos/eval", help="export-eval: output folder")
    p.add_argument(
        "zip", nargs="?", help="import: a results zip; restore: a BACKUP_DIR/db/<stamp> folder"
    )
    p.add_argument("--yes", action="store_true", help="restore: confirm writing to the target")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    if not args.verbose:  # the claim loop polls every 3 s; keep routine HTTP lines out of the log
        for name in ("httpx", "httpcore", "hpack"):
            logging.getLogger(name).setLevel(logging.WARNING)
    settings = load_settings()
    if args.command == "import":
        _import(settings, args.zip)
        return
    if args.command == "restore":
        _restore(settings, args.zip, args.yes)
        return
    queue = SupabaseQueue(settings)
    items = SupabaseItemStore(queue.db, settings.owner)

    if args.command == "export-eval":
        from .export_eval import export_eval

        zip_path = export_eval(items, args.out)
        print(f"Wrote {zip_path}. Check labels.csv, then upload the zip to Colab.")
        return

    if args.command == "backup":
        from .jobs import backup

        r = backup.run({}, JobContext(settings=settings, items=items))
        print(json.dumps(r, indent=2))
        return
    if args.command == "compat-eval":
        _compat_eval(settings, items)
        return

    worker = Worker(settings, queue, fake=args.fake, ctx=JobContext(settings=settings, items=items))

    def _stop(*_: object) -> None:
        log.info("stopping")
        worker.stop.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info(
        "closet-worker %s as %s%s", __version__, settings.worker_id, " (fake)" if args.fake else ""
    )
    worker.run(once=args.once)


def _compat_eval(settings: Settings, items: SupabaseItemStore) -> None:
    from .jobs.suggest_outfits import scorer_for
    from .recsys.compat_eval import evaluate, summary, write_gate
    from .recsys.model import Piece

    scorer = scorer_for(JobContext(settings=settings, items=items), require_gate=False)
    if scorer is None:
        print(
            f"No outfit model in {settings.compat_model_dir}. Copy compat_head.safetensors and "
            "compat_config.json there from the Colab run (colab/README.md)."
        )
        return
    r = evaluate(
        [Piece.from_row(x) for x in items.list_items()],
        items.list_suggestion_events(),
        items.list_wear_logs(),
        (items.get_profile() or {}).get("analysis"),
        scorer,
    )
    print(summary(r, write_gate(settings.compat_model_dir, r)))


def _restore(settings: Settings, folder: str | None, yes: bool) -> None:
    """Target comes only from CLOSET_RESTORE_* variables, never from worker/.env, so a restore
    can't overwrite production by accident."""
    import os
    from pathlib import Path

    from supabase import create_client

    from .restore import RestoreError, run_restore

    need = ["CLOSET_RESTORE_DB_URL", "CLOSET_RESTORE_SUPABASE_URL", "CLOSET_RESTORE_SERVICE_KEY"]
    missing = [n for n in need if not os.environ.get(n)]
    if not folder or missing:
        raise SystemExit(
            "Usage: set CLOSET_RESTORE_DB_URL, CLOSET_RESTORE_SUPABASE_URL and "
            "CLOSET_RESTORE_SERVICE_KEY, then run "
            "closet-worker restore ~/ClosetBackups/db/<stamp> --yes  (see README)"
            + (f"\nMissing: {', '.join(missing)}" if missing else "")
        )
    target = os.environ["CLOSET_RESTORE_SUPABASE_URL"]
    if not yes:
        raise SystemExit(f"This writes to {target}. Add --yes to go ahead.")
    db = create_client(target, os.environ["CLOSET_RESTORE_SERVICE_KEY"])
    try:
        r = run_restore(
            Path(folder).expanduser(),
            settings.backup_dir / "files",
            os.environ["CLOSET_RESTORE_DB_URL"],
            db,
        )
    except RestoreError as e:
        raise SystemExit(f"Not restored: {e}") from e
    print(json.dumps(r, indent=2))
    if r["mismatch"]:
        raise SystemExit("Restored, but some row counts differ from the backup (listed above).")


def _import(settings: Settings, zip_path: str | None) -> None:
    from pathlib import Path

    from .bundle import BundleError, install, read_bundle

    if not zip_path:
        raise SystemExit("Give the zip: closet-worker import colab/outputs/<file>.zip")
    try:
        b = read_bundle(Path(zip_path).expanduser())
    except BundleError as e:
        raise SystemExit(f"Not imported: {e}") from e
    for p in install(b, settings.compat_model_dir, settings.fit_gate_path, settings.heads_dir):
        print("installed", p)
    if b.kind == "compat":
        print("The outfit model stays off until it’s measured: run closet-worker compat-eval.")
    elif b.kind == "heads":
        from .vision.heads import load

        h = load(settings.heads_dir)
        on = [] if h is None else [k for k, g in h.gate.items() if g.get("use")]
        print("Heads on (they beat today’s guesses on your photos):", ", ".join(on) or "none")
    else:
        from .vision.fit import read_gate

        on = sorted(read_gate(settings.fit_gate_path))
        print("Fit suggestions on for:", ", ".join(on) if on else "none yet (none passed)")
    print("The worker reads these files on its next job: no restart needed.")


if __name__ == "__main__":
    cli()

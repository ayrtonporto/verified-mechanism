"""Local REPL smoke: proves Lean feedback path works (agent-facing API)."""
from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path

from re_harness.config import HarnessSettings
from re_harness.events import EventLogger
from re_harness.lean import LeanClient


async def main() -> int:
    settings = HarnessSettings.from_env(n_workers=1)
    root = Path("sample-problems/p01_linear")
    challenge = (root / "challenge.lean").read_text(encoding="utf-8")
    solution = challenge.replace("  sorry", "  linarith")
    events = EventLogger(Path("/tmp/repl_smoke_events.jsonl"), problem_id="p01_linear")
    client = LeanClient(
        image=settings.lean_image,
        events=events,
        session_id=uuid.uuid4().hex,
        timeout_s=600,
    )
    t0 = time.monotonic()
    print(f"image={settings.lean_image}", flush=True)
    print("check_file begin", flush=True)
    try:
        result = await client.check_file(solution, timeout_s=600)
    finally:
        client.close()
    dt = time.monotonic() - t0
    print(f"elapsed_s={dt:.1f}", flush=True)
    print(
        f"accepted={result.accepted} timed_out={result.timed_out} has_sorry={result.has_sorry}",
        flush=True,
    )
    print(f"message_count={len(result.messages)}", flush=True)
    for m in result.messages[:8]:
        print(m, flush=True)
    return 0 if result.accepted and not result.timed_out else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

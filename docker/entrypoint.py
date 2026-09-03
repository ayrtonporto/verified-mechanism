#!/usr/bin/env python3
"""Fixed entrypoints for the networkless Lean runtime image."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import threading
from pathlib import Path

MAX_INPUT_BYTES = 2_500_000
MAX_LOG_CHARS = 100_000


def _run_with_capped_logs(argv: list[str], *, cwd: Path, env: dict[str, str]):
    """Drain child pipes continuously while retaining only their bounded tails."""

    process = subprocess.Popen(
        argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    tails = {"stdout": bytearray(), "stderr": bytearray()}

    def drain(name: str, pipe) -> None:
        while chunk := pipe.read(65_536):
            tail = tails[name]
            tail.extend(chunk)
            if len(tail) > MAX_LOG_CHARS:
                del tail[:-MAX_LOG_CHARS]

    threads = [
        threading.Thread(target=drain, args=("stdout", process.stdout)),
        threading.Thread(target=drain, args=("stderr", process.stderr)),
    ]
    for thread in threads:
        thread.start()
    return_code = process.wait()
    for thread in threads:
        thread.join()
    return return_code, {
        name: bytes(value).decode("utf-8", errors="replace") for name, value in tails.items()
    }


def _runtime_env() -> dict[str, str]:
    env = dict(os.environ)
    for line in Path("/opt/lean.env").read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key in {"LEAN_PATH", "LEAN_SRC_PATH", "LEAN_SYSROOT", "PATH"}:
            env[key] = value
    env["HOME"] = "/tmp"
    return env


def _read_request() -> dict:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError(f"request exceeds {MAX_INPUT_BYTES} bytes")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("request must be a JSON object")
    return value


def health() -> int:
    proc = subprocess.run(
        ["lean", "--version"], capture_output=True, text=True, env=_runtime_env(), timeout=15
    )
    print(json.dumps({
        "ok": proc.returncode == 0,
        "lean": proc.stdout.strip(),
        "lean_version": os.environ.get("LEAN_VERSION"),
        "mathlib_commit": os.environ.get("MATHLIB_COMMIT"),
        "repl_commit": os.environ.get("REPL_COMMIT"),
        "comparator_commit": os.environ.get("COMPARATOR_COMMIT"),
        "uid": os.getuid(),
    }))
    return 0 if proc.returncode == 0 else 1


def repl() -> int:
    os.chdir("/opt/mathlib")
    os.execve(
        "/opt/repl/.lake/build/bin/repl",
        ["/opt/repl/.lake/build/bin/repl"],
        _runtime_env(),
    )


def compare() -> int:
    request = _read_request()
    required = {"challenge", "solution", "theorem_names", "definition_names", "permitted_axioms"}
    missing = required - request.keys()
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    if not all(isinstance(request[key], list) for key in (
        "theorem_names", "definition_names", "permitted_axioms"
    )):
        raise ValueError("name and axiom fields must be lists")
    if not all(isinstance(item, str) and item for key in (
        "theorem_names", "definition_names", "permitted_axioms"
    ) for item in request[key]):
        raise ValueError("names and axioms must be non-empty strings")
    if not isinstance(request["challenge"], str) or not isinstance(request["solution"], str):
        raise ValueError("challenge and solution must be strings")

    project = Path("/work/project")
    if project.exists():
        shutil.rmtree(project)
    shutil.copytree("/opt/project-template", project, symlinks=True)
    # The immutable template is intentionally mode 0555 in /opt. Its tmpfs
    # copy must be writable for Lake build artifacts, without ever following
    # the absolute package symlink back into the read-only image.
    for root, directories, files in os.walk(project, followlinks=False):
        os.chmod(root, os.stat(root, follow_symlinks=False).st_mode | stat.S_IWUSR)
        for name in directories + files:
            path = Path(root) / name
            if not path.is_symlink():
                os.chmod(path, path.stat().st_mode | stat.S_IWUSR)
    (project / "Challenge.lean").write_text(request["challenge"], encoding="utf-8")
    (project / "Solution.lean").write_text(request["solution"], encoding="utf-8")
    config = {
        "challenge_module": "Challenge",
        "solution_module": "Solution",
        "theorem_names": request["theorem_names"],
        "definition_names": request["definition_names"],
        "permitted_axioms": request["permitted_axioms"],
        "enable_nanoda": False,
    }
    config_path = project / "comparator.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    env = _runtime_env()
    env.update({
        "COMPARATOR_LANDRUN": "/opt/comparator/scripts/fake-landrun.sh",
        "COMPARATOR_LEAN4EXPORT": "/opt/comparator/.lake/packages/lean4export/.lake/build/bin/lean4export",
    })
    return_code, logs = _run_with_capped_logs(
        ["lake", "env", "/opt/comparator/.lake/build/bin/comparator", str(config_path)],
        cwd=project,
        env=env,
    )
    output = {
        "passed": return_code == 0,
        "exit_code": return_code,
        **logs,
    }
    print(json.dumps(output))
    return 0 if return_code == 0 else 1


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "health"
    try:
        if command == "health":
            return health()
        if command == "repl":
            return repl()
        if command == "compare":
            return compare()
        raise ValueError(f"unknown entrypoint {command!r}")
    except BaseException as exc:
        print(json.dumps({"passed": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

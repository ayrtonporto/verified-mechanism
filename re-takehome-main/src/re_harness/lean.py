"""Docker-only warm Lean REPL and fresh Comparator clients."""

from __future__ import annotations

import hashlib
import json
import os
import re
import select
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from .events import EventLogger
from .manifest import ProblemSpec

MAX_LEAN_SOURCE_BYTES = 1_000_000
MAX_REPL_RESPONSE_BYTES = 2_000_000
CONTAINER_LABEL_KEY = "ai.verifiedmechanisms.re_takehome.session"


class LeanRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class LeanCheck:
    accepted: bool
    messages: list[dict[str, Any]]
    has_sorry: bool
    timed_out: bool
    duration_ms: int
    container_restarted: bool = False


def docker_available() -> bool:
    try:
        proc = subprocess.run(
            ["docker", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def cleanup_session_containers(session_id: str) -> None:
    """Remove only containers bearing this run's unguessable exact label."""

    if not re.fullmatch(r"[a-f0-9]{32}", session_id):
        return
    try:
        listed = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"label={CONTAINER_LABEL_KEY}={session_id}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        ids = [line for line in listed.stdout.splitlines() if re.fullmatch(r"[a-f0-9]{12,64}", line)]
        if ids:
            subprocess.run(
                ["docker", "rm", "-f", *ids],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _hardened_docker_args(*, session_id: str, name: str, image: str) -> list[str]:
    return [
        "docker", "run", "--rm", "-i", "--pull=never",
        "--name", name,
        "--label", f"{CONTAINER_LABEL_KEY}={session_id}",
        "--network=none",
        "--read-only",
        "--user", "65532:65532",
        "--cap-drop=ALL",
        "--security-opt", "no-new-privileges=true",
        "--memory", "5g", "--memory-swap", "5g",
        "--cpus", "2",
        "--pids-limit", "512",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m,mode=1777",
        "--tmpfs", "/work:rw,nosuid,nodev,size=512m,mode=1777",
        "-e", "HOME=/tmp",
        "-w", "/work",
        image,
    ]


class LeanClient:
    def __init__(
        self,
        *,
        image: str,
        events: EventLogger,
        session_id: str | None = None,
        timeout_s: int = 120,
    ):
        self.image = image
        self.events = events
        self.session_id = session_id or uuid.uuid4().hex
        self.timeout_s = timeout_s
        self._proc: subprocess.Popen[bytes] | None = None
        self._container_name: str | None = None
        self._base_env: int | None = None
        self._lock = threading.RLock()
        self._ever_started = False

    async def check_file(self, source: str, *, timeout_s: int | None = None) -> LeanCheck:
        import asyncio

        try:
            return await asyncio.to_thread(self._check_file_sync, source, timeout_s)
        except asyncio.CancelledError:
            # Cancelling to_thread does not stop its OS thread. Tear down the
            # whole disposable container so the blocked reader returns before
            # final verification can begin.
            await asyncio.shield(asyncio.to_thread(self._force_remove))
            raise

    def _check_file_sync(self, source: str, timeout_s: int | None) -> LeanCheck:
        encoded = source.encode("utf-8")
        if len(encoded) > MAX_LEAN_SOURCE_BYTES:
            raise LeanRuntimeError(f"Lean source exceeds {MAX_LEAN_SOURCE_BYTES} bytes")
        body = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith("import ")
        )
        started = time.monotonic()
        with self._lock:
            restarted = self._ensure_alive()
            _env, messages, timed_out = self._send(body, self._base_env, timeout_s or self.timeout_s)
        has_sorry = any("sorry" in str(message.get("data", "")).lower() for message in messages)
        accepted = not timed_out and not has_sorry and not any(
            message.get("severity") == "error" for message in messages
        )
        result = LeanCheck(
            accepted=accepted,
            messages=messages,
            has_sorry=has_sorry,
            timed_out=timed_out,
            duration_ms=round((time.monotonic() - started) * 1000),
            container_restarted=restarted,
        )
        self.events.emit(
            "lean_check",
            source_sha256=hashlib.sha256(encoded).hexdigest(),
            source_bytes=len(encoded),
            result=asdict(result),
        )
        return result

    def _ensure_alive(self) -> bool:
        if self._proc is not None and self._proc.poll() is None:
            return False
        restarted = self._ever_started
        self.start()
        return restarted

    def start(self) -> None:
        if not docker_available():
            raise LeanRuntimeError("Docker is unavailable; there is no host Lean fallback")
        cleanup_session_containers(self.session_id)
        self._container_name = f"re-takehome-repl-{self.session_id[:12]}"
        argv = _hardened_docker_args(
            session_id=self.session_id, name=self._container_name, image=self.image
        ) + ["repl"]
        self._proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self._ever_started = True
        env_id, messages, timed_out = self._send("import Mathlib", None, max(180, self.timeout_s))
        if timed_out or env_id is None or any(m.get("severity") == "error" for m in messages):
            self.close()
            detail = "; ".join(str(m.get("data", "")) for m in messages[:3])
            raise LeanRuntimeError(f"REPL failed to import Mathlib: {detail or 'no response'}")
        self._base_env = env_id
        self.events.emit("lean_container_started", session_id=self.session_id, image=self.image)

    def _send(
        self, command: str, env: int | None, timeout_s: int
    ) -> tuple[int | None, list[dict[str, Any]], bool]:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.stdout is None:
            return None, [{"severity": "error", "data": "REPL is not running"}], False
        payload: dict[str, Any] = {"cmd": command}
        if env is not None:
            payload["env"] = env
        try:
            proc.stdin.write((json.dumps(payload) + "\n\n").encode("utf-8"))
            proc.stdin.flush()
        except (BrokenPipeError, OSError):
            self._proc = None
            return None, [{"severity": "error", "data": "REPL process died"}], False

        deadline = time.monotonic() + timeout_s
        raw = bytearray()
        delimiter_at: int | None = None
        stdout_fd = proc.stdout.fileno()
        while delimiter_at is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([stdout_fd], [], [], max(0.0, remaining))[0]:
                self._force_remove()
                self._proc = None
                return None, [{"severity": "error", "data": f"TIMEOUT after {timeout_s}s"}], True
            try:
                # os.read is bounded, unlike BufferedReader.readline() on an
                # attacker-controlled line. Never allocate beyond the cap.
                chunk = os.read(stdout_fd, min(65_536, MAX_REPL_RESPONSE_BYTES + 1 - len(raw)))
            except OSError:
                chunk = b""
            if not chunk:
                self._proc = None
                return None, [{"severity": "error", "data": "REPL process died"}], False
            raw.extend(chunk)
            lf_at = raw.find(b"\n\n")
            crlf_at = raw.find(b"\r\n\r\n")
            candidates = [position for position in (lf_at, crlf_at) if position >= 0]
            delimiter_at = min(candidates) if candidates else None
            if delimiter_at is None and len(raw) > MAX_REPL_RESPONSE_BYTES:
                self._force_remove()
                self._proc = None
                return None, [{"severity": "error", "data": "REPL response exceeded size limit"}], False

        raw = raw[:delimiter_at]
        try:
            response = json.loads(raw)
            if not isinstance(response, dict):
                raise TypeError("response must be an object")
        except (json.JSONDecodeError, TypeError) as exc:
            self._force_remove()
            self._proc = None
            return None, [{"severity": "error", "data": f"REPL protocol error: {exc}"}], False
        messages = response.get("messages", [])
        if not isinstance(messages, list):
            self._force_remove()
            self._proc = None
            messages = [{"severity": "error", "data": "REPL returned invalid messages"}]
            return None, messages, False
        env_id = response.get("env")
        if isinstance(env_id, bool) or (env_id is not None and not isinstance(env_id, int)):
            self._force_remove()
            self._proc = None
            return None, [{"severity": "error", "data": "REPL returned invalid environment"}], False
        return env_id, messages, False

    def _force_remove(self) -> None:
        if self._container_name:
            try:
                subprocess.run(
                    ["docker", "rm", "-f", self._container_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        if self._proc is not None:
            try:
                self._proc.kill()
            except OSError:
                pass

    def close(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
            if proc is not None:
                try:
                    if proc.stdin:
                        proc.stdin.close()
                    proc.wait(timeout=3)
                except Exception:
                    self._proc = proc
                    self._force_remove()
                    self._proc = None
            cleanup_session_containers(self.session_id)
            self._container_name = None
            self._base_env = None


@dataclass(frozen=True)
class ComparatorResult:
    passed: bool
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    output: dict[str, Any]


def compare_solution(
    *,
    image: str,
    session_id: str,
    challenge: str,
    solution: str,
    spec: ProblemSpec,
    timeout_s: int,
) -> ComparatorResult:
    for label, source in (("challenge", challenge), ("solution", solution)):
        if len(source.encode("utf-8")) > MAX_LEAN_SOURCE_BYTES:
            raise LeanRuntimeError(f"{label} exceeds {MAX_LEAN_SOURCE_BYTES} bytes")
    name = f"re-takehome-compare-{session_id[:12]}"
    argv = _hardened_docker_args(session_id=session_id, name=name, image=image) + ["compare"]
    payload = json.dumps({
        "challenge": challenge,
        "solution": solution,
        "theorem_names": list(spec.theorem_names),
        "definition_names": list(spec.definition_names),
        "permitted_axioms": ["propext", "Classical.choice", "Quot.sound"],
    }).encode("utf-8")
    started = time.monotonic()
    try:
        proc = subprocess.run(argv, input=payload, capture_output=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        cleanup_session_containers(session_id)
        return ComparatorResult(False, None, True, round((time.monotonic() - started) * 1000), {
            "error": f"Comparator timed out after {timeout_s}s"
        })
    finally:
        cleanup_session_containers(session_id)
    stdout = proc.stdout.decode("utf-8", errors="replace")[-MAX_REPL_RESPONSE_BYTES:]
    stderr = proc.stderr.decode("utf-8", errors="replace")[-20_000:]
    try:
        output = json.loads(stdout)
    except json.JSONDecodeError:
        output = {"stdout": stdout, "stderr": stderr}
    return ComparatorResult(
        passed=proc.returncode == 0 and bool(output.get("passed", True)),
        exit_code=proc.returncode,
        timed_out=False,
        duration_ms=round((time.monotonic() - started) * 1000),
        output=output,
    )


def numeric_answers_are_literals(solution: str, names: tuple[str, ...]) -> tuple[bool, list[str]]:
    """Require each declared Nat answer body to be an ASCII decimal literal."""

    def mask_comments(text: str) -> str:
        chars = list(text)
        i = 0
        depth = 0
        line_comment = False
        in_string = False
        while i < len(text):
            pair = text[i:i + 2]
            char = text[i]
            if line_comment:
                if char == "\n":
                    line_comment = False
                else:
                    chars[i] = " "
                i += 1
            elif depth:
                if pair == "/-":
                    chars[i:i + 2] = [" ", " "]
                    depth += 1
                    i += 2
                elif pair == "-/":
                    chars[i:i + 2] = [" ", " "]
                    depth -= 1
                    i += 2
                else:
                    if char != "\n":
                        chars[i] = " "
                    i += 1
            elif in_string:
                if char == "\\" and i + 1 < len(text):
                    chars[i:i + 2] = [" ", " "]
                    i += 2
                else:
                    if char == '"':
                        in_string = False
                    chars[i] = " "
                    i += 1
            elif pair == "--":
                chars[i:i + 2] = [" ", " "]
                line_comment = True
                i += 2
            elif pair == "/-":
                chars[i:i + 2] = [" ", " "]
                depth = 1
                i += 2
            elif char == '"':
                chars[i] = " "
                in_string = True
                i += 1
            else:
                i += 1
        return "".join(chars)

    code = mask_comments(solution)
    errors: list[str] = []
    for name in names:
        declaration = re.compile(rf"\babbrev\s+{re.escape(name)}\s*:\s*ℕ\s*:=")
        matches = list(declaration.finditer(code))
        if len(matches) != 1:
            errors.append(f"{name} must be defined exactly once as a decimal Nat literal")
            continue
        body_start = matches[0].end()
        next_decl = re.search(
            r"^\s*(?:theorem|lemma|abbrev|def|opaque|instance|example)\b",
            code[body_start:],
            flags=re.MULTILINE,
        )
        body_end = body_start + next_decl.start() if next_decl else len(code)
        if re.fullmatch(r"\s*[0-9]+\s*", code[body_start:body_end]) is None:
            errors.append(f"{name} must be defined exactly once as a decimal Nat literal")
    return not errors, errors

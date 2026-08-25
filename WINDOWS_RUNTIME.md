# Windows native runtime

**Status (2026-08-25):** **partial** — Windows Python + D: toolchains work; **Lean/Docker long jobs not green yet** via Windows `docker.exe`.  
**Hard rule:** install toolchains on **D:** only (user constraint).

---

## What is on D: now

| Component | Path | Status |
|-----------|------|--------|
| Repo / kit | `D:\Mis documentos\Documentos\Verified Mechanism\` | SoT |
| Python 3.11 (uv) | `D:\Python\uv-python\`, cache `D:\Python\uv-cache\` | OK |
| Kit venv | `re-takehome-main\.venv\` (on D:) | OK; `pip install -e ".[dev]"` done |
| `.env` | `re-takehome-main\.env` (gitignored) | OK (copied from WSL) |
| Docker CLI | `D:\Docker\bin\docker.exe` | OK |
| Docker engine | **WSL** Ubuntu-22.04 (distro/data on **D:\WSL**) | OK; image Lean present |
| Docker Desktop | **not installed** | blocked — see below |
| TCP bridge | WSL `socat :2375` → `/var/run/docker.sock` | fragile for long REPL |

---

## Docker Desktop blocker (C: space, not “refused D:”)

Installer log:

```text
not enough disk space to install: need 3459 MiB, only ~3230 MiB available
```

That check is against **C:** free space even when `--installation-dir=D:\Docker\DockerDesktop`.  
**D:** has ~95 GB free.** C:** is the bottleneck (~3.2 GB free).

No Docker Desktop bits were left installed on C: (empty dirs only).  
Installer binary kept on `D:\Docker\DockerDesktopInstaller.exe`.

**To finish Desktop later:** free ≥4 GB on **C:** (or move user TEMP to D: *and* satisfy installer checks), then:

```powershell
# still prefer D: install dir
D:\Docker\DockerDesktopInstaller.exe install --quiet --accept-license `
  --installation-dir="D:\Docker\DockerDesktop" `
  --wsl-default-data-root="D:\Docker\data"
```

Until then: **do not** force Desktop onto C:.

---

## Working stack today (hybrid, D:-centric)

```text
Windows Python 3.11 (D:\…\re-takehome-main\.venv)
  → docker.exe (D:\Docker\bin)
  → DOCKER_HOST=tcp://<WSL_IP>:2375
  → socat in WSL
  → dockerd in WSL (data under D:\WSL)
```

### Start TCP proxy (WSL, keep alive)

```bash
wsl.exe -d Ubuntu-22.04 -- bash -c \
  'pgrep -f "socat TCP-LISTEN:2375" || socat TCP-LISTEN:2375,bind=0.0.0.0,reuseaddr,fork UNIX-CONNECT:/var/run/docker.sock &'
```

### Env for Windows Python

```powershell
$env:PATH = "D:\Docker\bin;" + $env:PATH
$env:DOCKER_HOST = "tcp://$((wsl -d Ubuntu-22.04 -- hostname -I).Trim().Split()[0]):2375"
$env:LEAN_CONTAINER_MEMORY = "8g"
$env:COMPARATOR_TIMEOUT_S = "900"
$env:PYTHONPATH = "D:\Mis documentos\Documentos\Verified Mechanism\re-takehome-main"
cd "D:\Mis documentos\Documentos\Verified Mechanism\re-takehome-main"
.\.venv\Scripts\python.exe run.py ...
```

Helper: `run_p01_sg_win_smoke.sh` (git-bash; uses Windows paths for Win32 python).

---

## Smoke result (2026-08-25)

| Step | Result |
|------|--------|
| Windows venv + imports + key | OK |
| `docker.exe version` via TCP | OK |
| S-G LLM call | OK (~$0.00009) |
| Lean REPL `check_file` via docker attach | **FAIL** `WinError 10038` (not a socket) |
| Comparator container wait | **FAIL** TCP timeout / exit 125 |
| Output | `outputs/s_g/20260825T051130Z/` status `harness_error` |

**Conclusion:** hybrid Windows-python + TCP-docker is **not** reliable for the kit’s interactive Lean REPL / long `docker run -i`.  
**Proven path remains full WSL process tree** (`wsl.exe -d Ubuntu-22.04 -- bash …/run_p01_sg_calib.sh`) with session kept alive.

---

## Kit patches for Windows (local)

| File | Change |
|------|--------|
| `src/re_harness/runner.py` | Register only existing signals (no bare `SIGHUP` on Windows) |
| `src/re_harness/artifacts.py` | `os.fchmod` → fallback `os.chmod` on Windows |

Defaults for judging unchanged. Revisit before submit if upstream differs.

---

## Recommended next moves

1. **Science runs:** keep using **WSL attached** (already green Qwen/GPT-OSS p01).  
2. **True native Windows Lean:** free C: ≥4 GB → install Docker Desktop to **D:\Docker\…** → re-smoke without TCP socat.  
3. Optional: investigate npipe/SSH docker context instead of raw TCP (still needs a Windows engine or Desktop).

---

## Non-goals

- Does not change S/R/H science.  
- Does not install anything on C: beyond unavoidable installer temp attempts (cleaned).  
- Does not claim Windows Lean path green.

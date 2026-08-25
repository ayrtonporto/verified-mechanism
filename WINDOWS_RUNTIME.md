# Windows native runtime (target)

**Status:** decided 2026-08-25 — **smoke not yet proven** on this box.  
**Why:** WSL paid runs work, but Hermes/tool-launched WSL sessions often **kill mid-Lean** (exit 127 / incomplete `result.json`). That cost hours; it was **not** host OOM on the failed S-G attempts (free RAM was high). Native Windows + Docker Desktop should keep one long-lived process tree.

WSL remains a **fallback** with a known-good recipe.

---

## Goal

Run the same harness on Windows:

```text
OpenRouter + Docker Lean image + run.py + experiments_agents
```

without going through `wsl.exe` for the long job.

---

## Prerequisites

1. **Docker Desktop** running (Linux containers), enough RAM; close Chrome for Mathlib.
2. **Python 3.11** on Windows (`py -3.11` or `python`).
3. Repo SoT: `D:\Mis documentos\Documentos\Verified Mechanism\re-takehome-main`
4. **`.env`** in kit root (gitignored) with `OPENROUTER_API_KEY=...`  
   - Copy from WSL if needed:  
     `wsl.exe -d Ubuntu-22.04 -- cat ~/verified-mechanism/re-takehome-main/.env`  
     → paste into Windows kit `.env` (do not commit, do not chat the key).
5. Image already used in WSL (same digest):  
   `ghcr.io/verifiedmechanisms/re-takehome-lean@sha256:ee48287cd31c0a7df572093a879ed7289c2f01fec6c7af8716c605fc8c670c39`

---

## One-time setup (PowerShell)

```powershell
cd "D:\Mis documentos\Documentos\Verified Mechanism\re-takehome-main"

# venv
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"

# .env (create manually; never commit)
# OPENROUTER_API_KEY=sk-or-...

# optional: pull image if missing
docker pull ghcr.io/verifiedmechanisms/re-takehome-lean@sha256:ee48287cd31c0a7df572093a879ed7289c2f01fec6c7af8716c605fc8c670c39
```

If `scripts/setup.sh` is bash-only, either run the equivalent steps above or:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash -lc 'cd /mnt/d/Mis\ documentos/Documentos/Verified\ Mechanism/re-takehome-main && bash scripts/setup.sh'
```

…but prefer a **Windows venv** for native `run.py`.

---

## Every paid / Lean run (PowerShell)

```powershell
cd "D:\Mis documentos\Documentos\Verified Mechanism\re-takehome-main"
$env:LEAN_CONTAINER_MEMORY = "8g"
$env:COMPARATOR_TIMEOUT_S = "900"
$env:LEAN_CHECK_TIMEOUT_S = "300"
$env:PYTHONPATH = (Get-Location).Path
# optional pilot:
# $env:BASELINE_MAX_TURNS = "3"

.\.venv\Scripts\python.exe run.py `
  --problems <set_with_manifest> `
  --out outputs `
  --agent experiments_agents.s_g:create_agent
```

**Must:** `--problems` is a **set** directory with `manifest.json`.

### Temp 1-problem set (p01)

```powershell
$tmp = "D:\Mis documentos\Documentos\Verified Mechanism\tmp-p01-set"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path "$tmp\p01_linear" | Out-Null
Copy-Item sample-problems\p01_linear\problem.md, sample-problems\p01_linear\challenge.lean "$tmp\p01_linear\"
@'
{
  "schema_version": 1,
  "set": "tmp_p01_only",
  "problems": [
    {
      "id": "p01_linear",
      "theorem_names": ["p01_linear"],
      "definition_names": [],
      "numeric_answer_names": []
    }
  ]
}
'@ | Set-Content -Encoding utf8 "$tmp\manifest.json"
```

Then run with `--problems $tmp`.

---

## Smoke checklist (prove native path)

| Step | Pass criteria |
|------|----------------|
| `docker version` | engine running |
| `python -c "from re_harness.config import HarnessSettings; ..."` | key loaded, budget 1.0 |
| `LEAN_CONTAINER_MEMORY` seen as `8g` | same hook as WSL |
| One S-G or kit baseline × p01 | `summary.json` passed 1/1, `actual_cost_usd` present |
| Wall | expect ~3 min cold (like WSL calib) |

Record row in `experiments/REGISTRY.md` as `CAL-*-p01-win` when green.

---

## WSL fallback (known good)

```bash
wsl.exe -d Ubuntu-22.04 -- bash /home/ayrton/verified-mechanism/run_p01_sg_calib.sh
```

Keep the WSL session attached for the full job. Do not rely on detached `nohup` from a dying client.

---

## Git / trees

| Role | Path |
|------|------|
| SoT + preferred runtime | Windows repo above |
| WSL clone | `~/verified-mechanism` — sync when dual-editing; not required once Windows native is green |

---

## Non-goals of this doc

- Does not change science arms or COORDINATION_PLAN.
- Does not replace comparator or kit defaults for judging (local 8g stays env override).

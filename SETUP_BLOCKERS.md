# Setup blockers — qué arreglar para empezar

Estado al **2026-08-25**. Objetivo: entorno rápido y estable para el agente y
experimentos. El kit `re-takehome-main/` se toca solo con overrides locales documentados.

**WSL desbloqueado y calibrado (Qwen + GPT-OSS p01).**  
**Runtime pivot:** prefer **Windows nativo** when Docker Desktop can live on **D:**.  
Today: Desktop **blocked by low C: free space** (~3.2 GB; installer wants ~3.5 GB even with install-dir on D:).  
Hybrid Windows-Python + WSL-docker TCP **not green** for Lean REPL. **WSL attached = production path.**

---

## Resuelto — WSL setup + calibs

| Check | Resultado |
|---|---|
| `docker pull` imagen pinned | OK |
| `health` | OK — Lean **v4.32.0**, Mathlib `81a5d257`, comparator `07bc4ea4` |
| `smoke_test.sh` | **passed** ~1 m 48 s |
| REPL agent path | **accepted** warm ~9 s |
| Paid Qwen × p01 | **passed** ~$0.00018 / ~192 s (`20260824T040147Z`) |
| Paid S-G GPT-OSS × p01 | **passed** ~$0.000075 / ~193 s (`outputs/s_g/20260825T041102Z`) |
| Phase 0–1 arms + registry | **done** (`experiments/`, `experiments_agents/`) |

Imagen:

```text
ghcr.io/verifiedmechanisms/re-takehome-lean@sha256:ee48287cd31c0a7df572093a879ed7289c2f01fec6c7af8716c605fc8c670c39
```

---

## Hallazgo crítico — el tope de 5 GB del container no alcanza en esta laptop

El harness fija `--memory 5g` en cada container Lean/Comparator
(`src/re_harness/lean.py::_hardened_docker_args`).

Medido:

| Container memory | `import Mathlib` / smoke |
|---|---|
| **5g** (default kit) | thrashing (~150–160 GB block I/O), timeout |
| **8g** (override local) | `import Mathlib` **~44 s**; smoke **~1 m 48 s**; REPL warm **~9 s** |

Override local (no cambia el default de judging):

```bash
export LEAN_CONTAINER_MEMORY=8g
# PowerShell: $env:LEAN_CONTAINER_MEMORY="8g"
```

Parche mínimo en el kit: lee `LEAN_CONTAINER_MEMORY` con default `5g`.

También hace falta **RAM de host libre** (cerrar Chrome) para Mathlib ~6.5 GB.

---

## Hallazgo 2026-08-25 — WSL session kills no es OOM

Intentos fallidos de S-G: LLM OK, luego proceso muerto (exit 127) con **~7–8 GB free**.
Causa: ciclo de vida de sesión WSL / quoting desde el launcher, no thrash Mathlib.
Mitigación operativa WSL: `wsl.exe -d Ubuntu-22.04 -- bash /ruta/script.sh` foreground largo.
Mitigación estratégica: **Windows native runtime** (`WINDOWS_RUNTIME.md`).

---

## Cómo arrancar un run

### Preferido — Windows (cuando smoke esté verde)

Ver **`WINDOWS_RUNTIME.md`**.

### Fallback — WSL

```bash
# 1) Windows: cerrar Chrome
wsl -d Ubuntu-22.04
export PATH="$HOME/.pyshim:$HOME/.local/bin:$PATH"
export LEAN_CONTAINER_MEMORY=8g
export COMPARATOR_TIMEOUT_S=900
export PYTHONPATH="$HOME/verified-mechanism/re-takehome-main${PYTHONPATH:+:$PYTHONPATH}"
cd ~/verified-mechanism/re-takehome-main
# mantener sesión attached todo el wall time
```

Helpers: `run_p01_e2e_clean.sh`, `run_p01_sg_calib.sh`, etc.

---

## Operativos

### Mantener viva la VM (WSL)

Trabajos largos: cliente `wsl.exe` **attached**. Detached/`nohup` mueren cuando el cliente sale.

### Dos copias del repo

| Copia | Path | Uso |
|---|---|---|
| Windows (git SoT + target runtime) | `D:\Mis documentos\Documentos\Verified Mechanism` | commits, prefer runs nativos |
| WSL nativo (fallback runtime) | `~/verified-mechanism` | docker/Lean si Windows no está listo |

Sync: `git pull` en WSL tras push, o copiar paths puntuales.

### `.env` / OpenRouter key

Key en **gitignored** `.env` junto al kit. Históricamente WSL.
Para Windows: copiar a `re-takehome-main/.env` sin commitear ni pegar en chat.

### sshrun

Fallback lento (~14 min/op). No usar para Part Two (sesga timeouts).

---

## Pendiente

- [ ] Liberar **≥4 GB en C:** (o TEMP en D: + checks del installer) e instalar Docker Desktop en **`D:\Docker\...`** — hoy C: ~3.2 GB free bloquea.
- [ ] Re-smoke Windows Lean **sin** TCP socat (Desktop engine).
- [ ] Freeze `S_dev` / `S_eval`.
- [ ] Mientras tanto: corridas científicas en **WSL attached** (ya verde).

---

## Ya resueltos (históricos)

- Docker en WSL, imagen Lean, smoke, REPL
- Root-cause crashes pull = host RAM (histórico); session-kill = otro bug (2026-08-25)
- OpenRouter key + calibs Qwen/GPT-OSS p01
- Science arms S/R/H + experiment registry

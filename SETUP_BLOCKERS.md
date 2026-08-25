# Setup blockers — qué arreglar para empezar

> ⚠️ **SUPERSEDED (2026-08-25):** the production runtime moved from WSL to **`sshrun` via SSH + tmux**
> because WSL is unreliable for agent-driven runs (**session-kill**, not OOM). See `PROJECT_STATE.md`
> §17 and `HANDOFF.md`. The WSL memory recipe below is still valid *if* WSL is ever used, but paid runs
> now go on `sshrun`. p01 validated there: pass, $0.00017, ~4.7 min.

Estado al **2026-08-25**. Objetivo: entorno rápido y estable para el agente y
experimentos. El kit `re-takehome-main/` se toca solo con overrides locales documentados.

**Production path (historical, WSL): WSL Ubuntu dockerd** (not Docker Desktop for Lean).  
Memory recipe: `WSL_LEAN_MEMORY.md` + `wsl_lean_env.sh`.  
`.wslconfig`: 10 GB WSL, **no** `autoMemoryReclaim` during Lean runs.

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

## Por qué pide tanta RAM (vs tu Lean “normal”)

Este kit **no** es un `lake build` nativo caliente. Hace:

1. Container Docker **fresco** con **Mathlib completo** (`import Mathlib` cold).  
2. Luego otro container **Comparator** que vuelve a buildear Challenge + Solution.

Por eso 5g thrashs y 8g funciona aquí. Detalle: **`WSL_LEAN_MEMORY.md`**.

| Knob | Valor |
|------|--------|
| WSL `.wslconfig` memory | **10GB** |
| `autoMemoryReclaim` | **OFF** en runs (antes gradual podía achicar mid-job) |
| `LEAN_CONTAINER_MEMORY` | **8g** (default kit 5g = malo aquí) |
| Workers Lean | **1** |
| Host | Cerrar Chrome pesado + Docker Desktop durante runs |

---

## Hallazgo — session kill ≠ OOM

Intentos fallidos con mucha RAM libre y exit 127: el cliente WSL se cortó, no Mathlib.  
Mitigación: `wsl.exe -d Ubuntu-22.04 -- bash /ruta/script.sh` **attached** todo el wall time.

---

## Cómo arrancar un run (WSL — producción)

```bash
# Windows: Chrome liviano/cerrado; Docker Desktop cerrado
# Si tocaste .wslconfig: ya se aplicó con wsl --shutdown

wsl.exe -d Ubuntu-22.04 -- bash -lc '
  source ~/verified-mechanism/wsl_lean_env.sh
  cd ~/verified-mechanism/re-takehome-main
'

# Calib GPT-OSS p01:
wsl.exe -d Ubuntu-22.04 -- bash /home/ayrton/verified-mechanism/run_p01_sg_calib.sh
```

Helpers: `run_p01_e2e_clean.sh`, `run_p01_sg_calib.sh`, `wsl_lean_env.sh`.

### Docker Desktop (opcional, no Lean)

Puede estar en `D:\Docker\DockerDesktop`. **No** usarlo para la imagen Lean en esta laptop. Ver `WINDOWS_RUNTIME.md`.

---

## Operativos

### Mantener viva la VM (WSL)

Trabajos largos: cliente `wsl.exe` **attached**. Detached/`nohup` mueren cuando el cliente sale.

### Dos copias del repo

| Copia | Path | Uso |
|---|---|---|
| Windows (git SoT) | `D:\Mis documentos\Documentos\Verified Mechanism` | commits |
| WSL (runtime Lean) | `~/verified-mechanism` | docker/Lean runs |

Sync: `git pull` en WSL tras push, o copiar paths.

### `.env`

Solo en kit gitignored (WSL y/o Windows). Nunca commit / chat.

### sshrun

Lento; no Part Two.

---

## Pendiente

- [ ] Freeze `S_dev` / `S_eval`
- [ ] Batches S-Q / S-G en S_dev (WSL, un arm a la vez)
- [ ] Windows Lean nativo: aparcado (Desktop inestable con Mathlib aquí)

---

## Ya resueltos (históricos)

- Docker WSL + imagen Lean + smoke + REPL  
- 5g thrash → 8g override  
- Session-kill vs OOM diferenciados  
- Calibs Qwen/GPT-OSS p01  
- Science arms S/R/H + registry  
- `.wslconfig` sin reclaim agresivo  

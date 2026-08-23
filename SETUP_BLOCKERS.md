# Setup blockers — qué arreglar para empezar

Estado al **2026-08-23 (tarde)**. Objetivo: entorno rápido y estable para el agente y
experimentos. El kit `re-takehome-main/` se toca solo con overrides locales documentados.

**WSL desbloqueado.** Imagen Lean pull + health + smoke + REPL path verificados.

---

## ✅ Resuelto hoy — WSL setup completo

| Check | Resultado |
|---|---|
| `docker pull` imagen pinned | OK (~4–5 min con Chrome cerrado) |
| `health` | OK — Lean **v4.32.0**, Mathlib `81a5d257`, comparator `07bc4ea4` |
| `smoke_test.sh` (comparator `p01_linear` + `linarith`) | **passed** en **~1 m 48 s** |
| REPL agent path (`services.lean.check_file`) | **accepted=True** en **~9 s** (warm) |

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
| **5g** (default kit) | thrashing (~150–160 GB block I/O), timeout a 180s y a 900s |
| **8g** (override local) | `import Mathlib` **~44 s**; smoke completo **~1 m 48 s**; REPL warm **~9 s** |

Override local (no cambia el default de judging):

```bash
export LEAN_CONTAINER_MEMORY=8g
```

Parche mínimo en el kit (Windows + copia WSL): lee `LEAN_CONTAINER_MEMORY` con default `5g`.
Judging sin esa variable sigue en 5g.

También hace falta **RAM de host libre**:

- Cerrar **Chrome** (~3 GB) antes de runs.
- WSL `.wslconfig`: `memory=10GB` (subido desde 8GB tras el pull exitoso).
- Host total 15 GB: viable con Chrome cerrado; frágil con Chrome + Mathlib a la vez.

---

## Cómo arrancar un run (checklist)

```bash
# 1) Windows: cerrar Chrome (y ChatGPT si está)
# 2) Host free RAM >= ~10 GB recomendado antes de cold Mathlib

wsl -d Ubuntu-22.04
export PATH="$HOME/.pyshim:$HOME/.local/bin:$PATH"
export LEAN_CONTAINER_MEMORY=8g
export COMPARATOR_TIMEOUT_S=900   # cold comparator; warm puede bajar
cd ~/verified-mechanism/re-takehome-main

# sin key:
bash scripts/smoke_test.sh

# con key:
# cp .env.example .env   # pegar OPENROUTER_API_KEY
# .venv/bin/python run.py --problems sample-problems --out outputs \
#   --agent baselines.simple_agent:create_agent
```

Scripts helper en `~/verified-mechanism/` (solo WSL, no son el kit):

- `do_setup.sh` — pull + health + pip
- `do_smoke.sh` — smoke con overrides locales
- `diag_mathlib_import.sh` — diagnóstico de memoria del container
- `repl_smoke.py` — path REPL del agente

---

## 🟡 Operativos (no bloquean el arranque del kit)

### Mantener viva la VM

Trabajos largos: cliente `wsl.exe` **attached**. Detached/`nohup` mueren cuando el cliente sale.

### Dos copias del repo

| Copia | Path | Uso |
|---|---|---|
| Windows (source of truth para git en esta sesión) | `D:\Mis documentos\Documentos\Verified Mechanism` | commits desde Windows/Hermes |
| WSL nativo (runtime) | `~/verified-mechanism` | docker/Lean runs |

**Sincronizar a mano** tras editar código en Windows:

```bash
# ejemplo: copiar lean.py parcheado
cp "/mnt/d/Mis documentos/Documentos/Verified Mechanism/re-takehome-main/src/re_harness/lean.py" \
   ~/verified-mechanism/re-takehome-main/src/re_harness/lean.py
```

O `git pull` en WSL cuando el cambio esté commiteado/pusheado.

La copia WSL estaba en `86e5ebd` cuando Windows ya tenía commits más nuevos + el parche local.

### `.env` / OpenRouter key

Aún **no** hay `.env` en WSL ni en Windows. Siguiente paso humano: pegar la key del mail.

### sshrun

Fallback lento (~14 min/op). No usar para Part Two (sesga timeouts). Imagen Lean puede faltar allí; no prioritario.

---

## ⚪ Decisión pendiente

- **VM cloud 16–32 GB** para matrices largas desatendidas de Part Two.
  Dev/testing en Ryzen+WSL con Chrome cerrado ya funciona.

---

## Ya resueltos (históricos)

- ✅ Docker en WSL (v29.1.3), datos en **D:**
- ✅ Python 3.11.16 vía `uv` + `~/.pyshim/python3`
- ✅ Repo clonado en WSL nativo y en sshrun
- ✅ `avid-server` detenido / sin auto-restart en el flujo de setup
- ✅ Root-cause de crashes WSL = host RAM (no guest, no CPU)
- ✅ **Imagen Lean pull + health + smoke + REPL** (2026-08-23)

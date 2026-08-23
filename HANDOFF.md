# HANDOFF

## Read first

1. `PROJECT_STATE.md`
2. `SETUP_BLOCKERS.md` (WSL ya desbloqueado; overrides locales)
3. `docs/AGENT_API.md` y `RULES.md` (en `re-takehome-main/`)
4. Baseline: `baselines/simple_agent.py`
5. No inventar constraints de ejecución

---

## Current phase

**Phase 0 casi cerrada → entrar a Phase 1 (instrumentación) / calibración económica.**

Entorno WSL operativo. `submission/agent.py` sigue siendo stub.

---

## What was done this session (2026-08-23)

### WSL unlock

1. Cerré Chrome en el host (~3 GB) → free RAM host ~11 GB.
2. Pull de la imagen pinned Lean/Mathlib en WSL nativo (`~/verified-mechanism`).
3. Health OK: Lean **v4.32.0**, Mathlib `81a5d257`, comparator `07bc4ea4`.
4. Descubrimiento: el tope **`--memory 5g`** del harness hace thrashing de Mathlib en esta laptop
   (~150 GB block I/O, timeouts). Con **8g**, `import Mathlib` ~**44 s**.
5. Parche local mínimo: `LEAN_CONTAINER_MEMORY` env override en
   `re-takehome-main/src/re_harness/lean.py` (default sigue `5g` para judging).
6. WSL `.wslconfig`: `memory=10GB` (antes 8GB).
7. **Smoke OK** (~1 m 48 s): comparator acepta `p01_linear` con `linarith`.
8. **REPL path OK** (~9 s warm): `accepted=True` vía `LeanClient.check_file`.

### Commands that worked

```bash
# setup (WSL)
bash ~/verified-mechanism/do_setup.sh

# smoke con overrides locales
export LEAN_CONTAINER_MEMORY=8g COMPARATOR_TIMEOUT_S=900
bash ~/verified-mechanism/do_smoke.sh

# REPL agent path
export LEAN_CONTAINER_MEMORY=8g
cd ~/verified-mechanism/re-takehome-main
.venv/bin/python ~/verified-mechanism/repl_smoke.py
```

### Commands / attempts that failed

- Pull con Chrome abierto / host free <~3 GB → VM WSL killed.
- `smoke_test.sh` con default `5g` + `COMPARATOR_TIMEOUT_S=180` → timeout.
- Mismo smoke con `900s` pero `5g` → sigue timeout (no es solo time; es RAM del container).
- Copia WSL del repo desactualizada vs Windows (clon separado en `86e5ebd`).

### Files changed

- `re-takehome-main/src/re_harness/lean.py` — `LEAN_CONTAINER_MEMORY` override (Windows tree; copiado a WSL).
- `SETUP_BLOCKERS.md`, este `HANDOFF.md`, `PROJECT_STATE.md`.
- Helpers locales (no kit): `do_setup.sh`, `do_smoke.sh`, `diag_mathlib_import.sh`, `repl_smoke.py`.

---

## Current project thesis

Coordinación Qwen + GPT-OSS para maximizar pruebas Lean aceptadas, y caracterizar cuándo
la colaboración aporta respecto de cada modelo solo. Lean feedback = señal de coordinación.

Arquitectura prioritaria aún: **Candidate A** (propose → Lean → diagnose/repair).
Blackboard = hipótesis, no implementar todavía.

---

## Immediate next actions (in order)

1. **Pegar OpenRouter key** en WSL:  
   `cp ~/verified-mechanism/re-takehome-main/.env.example ~/verified-mechanism/re-takehome-main/.env`
2. **Sincronizar** copia WSL con Windows (commit en Windows + pull en WSL, o copiar archivos).
3. Calibración económica: 1–2 problemas × cada modelo con baseline (`BASELINE_MODEL=...`).
4. `judge_check.sh` cuando haya un agent mínimo (aunque sea el baseline vía `--agent`).
5. Phase 1: instrumentación de experimentos si el harness no alcanza para Part Two.
6. Solos propios (no confiar ciegamente en `outputs/baseline/*` del kit: corridos con ~1080s cap).

---

## Do not do yet

- Multi-agent framework complejo / blackboard
- Optimizar prompts sin mediciones
- Cambiar interfaces evaluator-facing sin necesidad
- Matrices grandes sin key + logging fiable
- Asumir roles fijos Qwen vs GPT-OSS

---

## Runtime contract (short)

- Implement `submission/agent.py`: `async solve(problem, services) -> AgentResult`
- `services.llm.complete(model in {qwen/qwen3.5-flash-02-23, openai/gpt-oss-120b}, ...)`
- `services.lean.check_file(full_source)` — feedback; grading final = comparator fresco
- `services.checkpoint(source, meta)`
- Caps: `$1` / problem, `28800s` wall (defaults). Local: `LEAN_CONTAINER_MEMORY=8g`.

---

## Next action

**Obtener la OpenRouter key en `.env` (WSL) y correr calibración económica de 1 problema por modelo con el baseline.**

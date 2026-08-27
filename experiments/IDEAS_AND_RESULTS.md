# Ideas & results ledger — everything we attacked, and how it scored

**Purpose.** One ordered place that records *every* idea/mechanism tried on the Lean
theorem-proving task, what it is, and its result — so we never re-propose or
re-build something already done. Update this whenever a new arm runs.

**Scoreboard (unchanged across every mechanism so far):**
- **Solvable frontier = 6/9** on `S_dev`: `{p01, p03, p05, p06, p10, putnam_2018_a1}`.
- **Best single arm = 5/9** (R-G, SK-G, BON-G, ST-G).
- **Never solved by anything:** `p09_imo1964`, `rmo_2000_2`, `rmo_2000_3`.
- Models are fixed: **Q = qwen/qwen3.5-flash-02-23**, **G = openai/gpt-oss-120b**.
  Universal mechanisms only; Lean/Mathlib is the sole verifier; no fine-tuning;
  ≤ $1 and ≤ 8 h per problem (cost is a non-issue; wall time is the real limit).

---

## 1. Ideas ledger (idea-centric)

| # | Idea (plain) | Arm(s) | What it does | Best S_dev | Moved 6/9 frontier? | Status |
|---|---|---|---|:--:|:--:|---|
| 1 | Ask one model, multi-turn Lean loop | S-Q, S-G | Kit baseline: whole-file, retry with Lean feedback | 4/9 (S-G) | — (baseline) | done |
| 2 | Propose → repair from Lean errors (same model) | R-Q, R-G | Structured targeted repair with diagnostics | **5/9 (R-G)** | no (adds only `p10`) | done |
| 3 | Cross-model repair (handoff) | H-QG, H-GQ | The *other* model repairs the proposer's file | 4/9 | no (H-GQ *lost* `p05`) | done |
| 4 | Deterministic Mathlib tactic sweep | AT-G | Zero-model battery (`simp_all,omega,nlinarith,decide,aesop…`) + tactic menu | 4/9 | no (but free wins on `p01`,`p05`) | done — **kept as stage 0** |
| 5 | Skeleton / sorry-first | SK-G | Propose `have … := by sorry` skeleton, then fill holes | 5/9 | no | done |
| 6 | Many independent attempts (best-of-N) | BON-G | 8 diverse whole-file samples, higher temp, first Lean-accepted wins | 5/9 | no | done (N-cap now raised 24→512) |
| 7 | Think in NL → translate to Lean | PF-GQ | G writes a math plan, Q formalizes, then repair | 4/9 | no | done |
| 8 | Verified proof-**state** tree search (COPRA-style) | ST-G, ST-GQ | Nodes = Lean-verified tactic prefixes + exact goal; harvest `apply?`/`exact?` premises; Lean checks every child; best-first + backtrack; per-node retry + action repair + stratified frontier (v2/P0) | 5/9 | no — **0 native closes** | done |
| 9 | Split independent theorems, solve each alone | MT-G | Multi-theorem wrapper: `p09_a`/`p09_b` each become their own single-theorem problem, then reassemble | p09 = 0/1 | no (p09 still fails) | **done 2026-08-27** — infra kept |
| 10 | Verified `have`-decomposition, holes filled independently | SF-G, MT-SF-G | Model writes a `have`-skeleton; **compose-check** it really closes; fill each hole in place (sweep + goal-state-targeted model tactics + 1 repair), freeze solved holes; composes with #9 | *running* | *TBD* | **in flight 2026-08-27** |
| 11 | Scaled sampling (best-of-100+) | (BON-G, high N) | Honest capability-ceiling test using the unused time budget | not yet | *TBD* | reserved (run if #9/#10 don't move it) |

Ideas explicitly considered and **dropped** (not pillars):
- **Fixed-strong-tactic + model-generated hints** (e.g. `nlinarith [hint,…]`): too
  narrow — only helps polynomial/inequality goals; folded into the tactic menu, not
  a pillar.

---

## 2. Per-problem grid (all arms, S_dev, comparator pass = 1)

`1*` = solved by the deterministic tactic sweep (no model call, variance-proof).
`—` = not run for that arm.

| Problem | Diff | S-Q | S-G | R-Q | R-G | H-QG | H-GQ | AT-G | SK-G | BON-G | PF-GQ | ST-G | ST-GQ | MT-G |
|---------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| p01_linear | E | 1 | 1 | 1 | 1 | 1 | 1 | 1* | 1* | 1* | 1* | 1* | 1* | — |
| p03_sq_ge_two_ab | E | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 0 | 1 | 1 | — |
| p05_gcd_mersenne | M | 0 | 1 | 0 | 1 | 0 | 0 | 1* | 1* | 1* | 1* | 1* | 1* | — |
| p06_pow_mod | M | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | — |
| p09_imo1964 | H | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| p10_factorial_pow | H | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 1 | — |
| rmo_2000_2 | H | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — |
| rmo_2000_3 | H | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — |
| putnam_2018_a1 | H | 0 | 1 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 0 | — |
| **TOTAL** | | **3** | **4** | **4** | **5** | **4** | **3** | **4** | **5** | **5** | **4** | **5** | **4** | — |

MT-G was run only on a `p09`-only set (the targeted fix); on single-theorem
problems it delegates to AT-G behaviour, so those cells are not separately run.

---

## 3. Two robust facts + the caveat

1. **Deterministic sweep floor (variance-proof):** `p01` (`nlinarith`) and `p05`
   (`simp_all`) are solved for free, no model call, every run. Keep as stage 0.
2. **Model complementarity:** `p06` is Qwen-only, `p05`/`putnam_2018_a1` favour G →
   Union(S) = 5 > any single S arm. Argues for adaptive model choice/union.
3. **High run-to-run variance (caveat):** the same R-G config scored 5/9 then 2/9.
   Single-run ±1 is inside the noise; nothing has been repeated ×3 yet.

---

## 4. The diagnosis on record (why 6/9 holds)

Even a properly-built verified search (StateTree v2: retry rounds, action-level
repair from exact Lean errors, stratified frontier, real Mathlib premises) closes
**zero** hard problems natively and stalls at **max depth ≤ 2** with a very high
invalid-action rate. The evidenced bottleneck is the **action policy**: Q and G are
general chat models, not trained tactic/value policies, so against a raw goal state
they emit a low-hit-rate stream of tactic proposals and cannot chain a verified
trajectory deep enough. Search, verification, premises and budget are all available
and cheap — the models' per-step proposals are the limit.

The two open bets against this (both 2026-08-27):
- **#10 sketch-and-fill** plays to the models' *strength* (structured NL/Lean
  argument) and factorises depth into independent shallow holes — the untried
  structural lever. Compose-check filters bad decompositions cheaply.
- **#11 scaled sampling** is the honest ceiling test: if hundreds of diverse
  whole-file/skeleton samples on `p09`/`rmo_2000_2` still yield zero compiling
  proofs, the ceiling is real and clinched.

---

## 5. Status of in-flight work (2026-08-27)

| Arm | Where | State | Result |
|---|---|---|---|
| MT-G (#9) | tmux `mtp09` (finished) | done | `p09` still 0/1 — split alone insufficient; G can't prove `p09_a` even isolated via repair |
| MT-SF-G (#10) | tmux `mtsf` (finished) | done | **p09 ❌, rmo_2000_2 ❌, rmo_2000_3 ❌ — frontier still 6/9.** Failure mode diagnosed below (2.6). |
| BON high-N (#11) | reserved → **killed** | not launching | 512×70s ≈ 10 h > 8 h wall; needs a time/cost budget guard, not a nominal N. |

### 2.6 Why sketch-and-fill (#10) did not move the frontier — validated critique
An external review (`RESPUESTA_IDEAS_INNOVADORAS_POST_LEDGER_ES.md`) pinned two real
defects, both confirmed:
- **compose-check verifies *sufficiency*, not *non-triviality*.** A skeleton `have h :
  <original goal> := by sorry; exact h` composes but its only hole IS the original
  problem — no difficulty reduction. Need to also reject holes α-equivalent to / as
  hard as the parent goal, and score *fillability* (does automation find progress).
- **the hole-filler reuses the weak free-Lean-text policy** (5 free strings + 1
  repair) — the exact thing diagnosed as the ceiling — with **no `grind`**, no
  `exact?/apply?/simp?/aesop?` suggestions, no menu-selection, no prefix recycling.

### 2.7 Verified capability facts (for the next levers)
- Image is **Lean v4.32.0** → **`grind`** (kernel-verified automation) is available and
  is **missing from `CLOSING_TACTICS`** — a concrete gap.
- Harness `llm.complete` supports **`tools`/`tool_choice`** and **`seed`** → tool-calling
  MenuTree and seeded sampling are buildable with no harness change.

### 2.8 Next-lever backlog (from the validated review, cheap→dear)
| id | lever | model cost | why | first test / kill |
|---|---|---|---|---|
| E0 | add `grind` + modern automation to battery & hole-filler | ~0 | verified gap; may close subgoals nothing else did | probe grind on 3 hard + subgoals; kill if unavailable / closes nothing new |
| E1 | **MaxPrefix** — rescue max Lean-verified prefix of failed whole-file proofs (truncate-and-resume) | 0 (offline replay) | tells us if models make deep partial progress we discard | replay stored failed candidates; kill if ~none have a novel valid prefix >2 |
| E2 | **MenuTree** — Lean pre-builds valid actions; model only selects IDs via tool-calling | med | separates "can't write Lean" from "can't rank"; makes the bottleneck observable | ranking arms det/rand/Q/G vs free; kill if menus infertile or ranking ≤ random |
| E3 | **PortfolioCut** — fix #10: many cheap cuts, score fillability, fill via grind/menu cascade | med | corrects the two defects in 2.6 | vs current SF on 3 hard; kill if <~5% cuts non-trivial+advanceable |
| E4 | BridgeSearch (bidirectional) | high | only if E3 yields valid-but-unclosed cuts | kill if frontiers don't connect |
| E5 | adaptive BON with time/cost guard (not nominal N) | high | honest ceiling test within 8 h | last resort |

### 2.9 E0/E1 results (2026-08-27)
- **E0 `grind`**: works on the image (v4.32.0); does NOT close any of the 3 hard
  problems whole, nor the p09 periodicity subgoal `2^n%7=2^(n%3)%7` (grind splits
  the iff then stalls; omega fails it). Added to `CLOSING_TACTICS` as a strict floor
  improvement; **not a frontier-mover.**
- **E1 MaxPrefix (offline, 56 stored candidates)**: models DO produce deep verified
  prefixes — `p09_b` up to **8/11** steps, `rmo_2000_3` up to **4/5** — that we
  discarded. BUT the **resume probe** shows those deep prefixes are mostly *easy
  scaffolding*: after the verified prefix the remaining goal is still the crux
  (`rmo_2000_2` → `⊢ x=9∧y=11` intact after a case split; `rmo_2000_3` → the full
  `∑≤3` after only deriving monotonicity). The battery (incl. grind) finishes **none**
  of the near-misses. `p09_b` is genuinely close (remaining = `⊢ False` in fixed
  residues) but `p09_a` stays walled at 2 steps and blocks p09.
- **Refined ceiling statement:** Q+G build the easy structure (case splits, helper
  facts) and stall precisely at the ONE hard mathematical step (periodicity
  contradiction / Diophantine bound / Abel summation). Depth ≠ progress on the crux.
  This makes generic truncate-and-resume low-value here; the crux is what's missing.

### 2.10 Infrastructure: parallel dev driver (`fastdrive.py`)
The memory limit is the Lean check (one 8 GB container), not model calls (HTTP,
parallel, and the real wall-time hog). `fastdrive.py` runs every problem/repeat
agent concurrently on one event loop sharing ONE `LeanClient` (its internal lock
serializes checks through a warm container) + one `LLMClient`; model calls overlap,
Lean checks queue, authoritative comparator runs sequentially at the end. Cuts dev
wall time from ~sum toward ~max of per-problem times; `--repeat N` gives ×N variance
cheaply. Dev fast-path only; the graded S_eval run uses the kit runner.

Code substrate: `experiments_agents/{multitheorem,sketchfill}.py` + factories
`mt_g.py`, `sf_g.py`, `mt_sf_g.py`. Run scripts on sshrun: `run_mt_p09.sh`,
`run_mt_sf_hard.sh`. Dev driver: `fastdrive.py`. Probes: `probe_grind.py`,
`maxprefix_offline.py`, `resume_probe.py`.

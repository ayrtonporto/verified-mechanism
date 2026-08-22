# Setup and troubleshooting

## Requirements

- Docker Engine or Docker Desktop
- Python 3.11 or newer
- Approximately 20 GB free disk
- At least 8 GB RAM for one worker; allow about 5 GB more for each additional
  concurrent worker

Nothing else is required. In particular, do not install `elan`, Lean, Lake, or
Mathlib on the host.

## Setup

```bash
bash scripts/setup.sh
cp .env.example .env
```

Put the emailed key after `OPENROUTER_API_KEY=`. `.env` is ignored by Git.
An exported environment variable takes precedence over `.env`, which is how
the judging command supplies a fresh key.

`setup.sh` creates `.venv`, installs the small Python harness, pulls the pinned
multi-platform runtime image, and runs its health check. Docker automatically
selects AMD64 or ARM64 for the machine.

## Checks

```bash
bash scripts/smoke_test.sh     # image + Comparator; no API key
bash scripts/judge_check.sh    # your agent + exact output contract; uses key
```

Normal runs write to a timestamped directory under the output root, for example
`outputs/submission/20260819T120000Z/`. Use `--resume latest` or
`--resume <timestamp>` to continue an interrupted run for the selected agent.
If you rename or group run directories, `--resume` may also be a safe path
relative to the agent directory.

## Common failures

- **Docker daemon unavailable:** start Docker Desktop or the system Docker
  service, then rerun setup.
- **Image pull denied:** the GHCR package must be public. Confirm the image
  reference printed by setup and contact the hiring team if access changed.
- **Killed/OOM:** reduce `--n-workers`. Each active worker has an independent
  warm Mathlib process and a 5 GB container limit.
- **Missing key:** copy `.env.example` to `.env`; do not add quotes or `export`.
- **REPL timeout:** the client kills and recreates that problem's container.
  Other workers continue.
- **Apple Silicon is unexpectedly emulating AMD64:** inspect the image manifest;
  the release must contain both `linux/amd64` and `linux/arm64`.

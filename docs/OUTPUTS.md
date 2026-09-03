# Output contract

`--out` names an output root, not a single run directory. Given:

```bash
python run.py --problems sample-problems --out outputs
```

the default submission agent writes:

```text
outputs/
└── submission/
    └── <timestamp>/
        ├── run.json
        ├── summary.json
        └── <problem-id>/
            ├── solution.lean
            ├── result.json
            ├── transcript.json
            ├── events.jsonl
            ├── checkpoint.json
            └── worker-config.json
```

The reference baseline similarly writes to `outputs/baseline/<timestamp>/`.
Timestamps use UTC form such as `20260819T120000Z`.

Use `--resume <timestamp>` to continue a specific run for the selected agent,
or `--resume latest` to continue the newest run under that agent. If you rename
or nest a run directory, pass the path relative to the agent directory, for
example `--resume qwen/qwen3.5-flash-02-23`. Resume skips problems that already
have a valid `result.json` and reruns missing or incomplete problems.

All JSON formats have `schema_version: 1`.

- `run.json`: run ID, problem set, agent factory, limits, image reference,
  worker count, platform, and timestamps. It contains no key.
- `result.json`: final status, point, Comparator verdict, answer-shape check,
  actual budget state, deadline state, models used, and agent error/metadata.
- `transcript.json`: ordered full model requests and responses, token details,
  actual costs, errors, and latency. Secrets are redacted.
- `events.jsonl`: append-only lifecycle source of truth. Each line is flushed
  and fsynced before the operation proceeds, allowing transcript recovery
  after a hard kill.
- `summary.json`: deterministic problem rows, points, failure reasons, model
  participation, aggregate actual spend, and timing.

Statuses include `passed`, `failed`, `agent_timeout`, `timed_out`,
`over_budget`, `cost_unknown`, `harness_error`, and `missing`.

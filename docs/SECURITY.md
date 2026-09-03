# Security boundary

## Trust model

Applicant Python is trusted and reviewed. Generated Lean is hostile: Lean
elaboration can execute metaprograms, perform IO, spawn processes, and consume
unbounded resources. It therefore never runs on the host.

The OpenRouter key remains in the agent process. It is not written to worker
configuration, command-line arguments, Docker environment variables, or logs.
The logger also replaces the exact key if it appears accidentally in content.

## Container controls

Every problem receives a new warm-REPL container. Every final score receives a
second fresh Comparator container. Both use:

- `--network=none`
- no host bind mounts
- an unprivileged UID
- a read-only root filesystem
- bounded tmpfs for `/tmp` and `/work`
- all Linux capabilities dropped
- `no-new-privileges`
- Docker's default seccomp policy
- CPU, memory, PID, input, output, and wall-clock limits

The image contains no application secrets. A timeout force-removes the entire
container namespace, and cleanup filters by an unguessable per-problem label.
There is no host Lean fallback.

The warm REPL is only feedback. A malicious attempt could affect later REPL
checks inside the same disposable problem container, but it cannot affect
another problem or the final verdict. Comparator runs from pristine challenge
and solution inputs in a fresh container and permits only `propext`,
`Classical.choice`, and `Quot.sound`.

Comparator's internal development landrun shim is safe here only because the
outer hardened Docker container is the compilation sandbox. Never invoke the
image's Comparator entrypoint outside that outer isolation.

## Operational controls

The image build pins Lean, Mathlib, REPL, Comparator, and elan source commits.
The release workflow builds native AMD64/ARM64 images, emits SBOM/provenance,
signs the manifest digest, and returns the immutable digest that must replace
the release tag in the harness before distribution.


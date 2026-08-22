---
description: Compile the take-home PDF (pdf/build/build.sh)
allowed-tools: Bash(bash pdf/build/build.sh), Bash(cd pdf/build && bash build.sh)
---

Compile the take-home PDF by running the build script from the repo root:

```
bash pdf/build/build.sh
```

The script regenerates `pdf/build/logo-light.pdf` if `logo-light.svg` is newer, runs pdflatex twice on `pdf/build/take-home.tex`, and publishes the result to `pdf/take-home.pdf`.

Report the script's output (the "Published:" line with the page count). If pdflatex fails, rerun it without `> /dev/null` to surface the LaTeX error, and report the first error with its line number in take-home.tex.

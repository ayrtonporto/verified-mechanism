"""Versioned problem-set manifest loading and validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$")


class ManifestError(ValueError):
    pass


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


@dataclass(frozen=True)
class ProblemSpec:
    id: str
    theorem_names: tuple[str, ...]
    definition_names: tuple[str, ...]
    numeric_answer_names: tuple[str, ...]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ProblemSet:
    root: Path
    name: str
    problems: tuple[ProblemSpec, ...]

    def paths(self, spec: ProblemSpec) -> tuple[Path, Path]:
        problem_dir = (self.root / spec.id).resolve()
        try:
            problem_dir.relative_to(self.root)
        except ValueError as exc:
            raise ManifestError(f"problem {spec.id!r} escapes the problem root") from exc
        description = problem_dir / "problem.md"
        challenge = problem_dir / "challenge.lean"
        for path in (description, challenge):
            if not path.is_file() or path.is_symlink():
                raise ManifestError(f"required regular file missing: {path}")
        return description, challenge


def _names(value: Any, field: str, *, may_be_empty: bool) -> tuple[str, ...]:
    if not isinstance(value, list) or (not may_be_empty and not value):
        requirement = "a list" if may_be_empty else "a non-empty list"
        raise ManifestError(f"{field} must be {requirement}")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ManifestError(f"{field} entries must be non-empty strings")
    if len(set(value)) != len(value):
        raise ManifestError(f"{field} contains duplicates")
    return tuple(value)


def load_problem_set(root: Path) -> ProblemSet:
    root = root.resolve()
    manifest_path = root / "manifest.json"
    try:
        raw = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            parse_constant=_reject_nonfinite,
        )
    except FileNotFoundError as exc:
        raise ManifestError(f"missing {manifest_path}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise ManifestError(f"invalid {manifest_path}: {exc}") from exc
    if raw.get("schema_version") != 1:
        raise ManifestError("manifest schema_version must be 1")
    entries = raw.get("problems")
    if not isinstance(entries, list) or not entries:
        raise ManifestError("manifest problems must be a non-empty list")

    seen: set[str] = set()
    specs: list[ProblemSpec] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ManifestError(f"problems[{index}] must be an object")
        problem_id = entry.get("id")
        if not isinstance(problem_id, str) or not _ID_RE.fullmatch(problem_id):
            raise ManifestError(f"invalid problem id at problems[{index}]: {problem_id!r}")
        if problem_id in seen:
            raise ManifestError(f"duplicate problem id: {problem_id}")
        seen.add(problem_id)
        theorems = _names(entry.get("theorem_names"), "theorem_names", may_be_empty=False)
        definitions = _names(entry.get("definition_names", []), "definition_names", may_be_empty=True)
        numeric = _names(entry.get("numeric_answer_names", []), "numeric_answer_names", may_be_empty=True)
        if not set(numeric) <= set(definitions):
            raise ManifestError(f"{problem_id}: numeric answers must also be definition names")
        metadata = entry.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ManifestError(f"{problem_id}: metadata must be an object")
        allowed_fields = {
            "id", "theorem_names", "definition_names", "numeric_answer_names", "metadata"
        }
        unknown = set(entry) - allowed_fields
        if unknown:
            raise ManifestError(f"{problem_id}: unknown manifest fields: {sorted(unknown)}")
        spec = ProblemSpec(problem_id, theorems, definitions, numeric, metadata)
        # Validate files eagerly so workers never discover a partial set midway.
        ProblemSet(root, "", (spec,)).paths(spec)
        specs.append(spec)
    name = raw.get("set", root.name)
    if not isinstance(name, str):
        raise ManifestError("manifest set must be a string")
    return ProblemSet(root=root, name=name, problems=tuple(specs))

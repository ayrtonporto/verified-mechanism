"""In-run DAG of Lean-verified intermediate advances.

Unlike the older sibling lemma bank, nodes are inserted as soon as their exact proof
certificate passes Lean.  A failed route therefore preserves every accepted prefix.
Certificates are executable tactic code, not prompt prose; callers must replay them in a
new context before injection.  The graph itself records provenance, dependencies, route
state, and actual/decisive reuse counts.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable


_FORBIDDEN = re.compile(r"\b(?:sorry|admit|axiom|native_decide)\b", re.IGNORECASE)


def normalize_statement(statement: str) -> str:
    return re.sub(r"\s+", "", statement or "").lower()


def _hash(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:20]


def _imports(context: str) -> tuple[str, ...]:
    return tuple(re.findall(r"^\s*import\s+([^\s]+)", context or "", re.MULTILINE))


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_.']*|[0-9]+", text or "")
        if token.lower() not in {"theorem", "lemma", "have", "by", "exact", "true"}
    }


class RouteState(str, Enum):
    INVALID = "invalid_route"
    SUFFICIENT_INCOMPLETE = "sufficient_incomplete"
    COMPLETE = "complete"


@dataclass
class VerifiedLemmaNode:
    node_id: str
    statement_key: str
    statement: str
    proof: str
    certificate: str
    context: str
    context_hash: str
    imports: tuple[str, ...]
    dependencies: tuple[str, ...]
    provenance: dict[str, Any]
    reuse_count: int = 0
    decisive_reuse_count: int = 0
    discoveries: int = 1

    @property
    def alias(self) -> str:
        return f"vp_{self.node_id[:12]}"


@dataclass
class RouteRecord:
    route_id: str
    state: RouteState
    goal: str
    bridge_verified: bool
    proved_nodes: tuple[str, ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)


class VerifiedProgressGraph:
    """Acyclic store of accepted lemma certificates for one isolated problem run."""

    def __init__(self, *, max_nodes: int = 64):
        self.max_nodes = max_nodes
        self.nodes: dict[str, VerifiedLemmaNode] = {}
        self.by_statement: dict[str, list[str]] = {}
        self.routes: list[RouteRecord] = []
        self.rejected_cycles = 0
        self.rejected_restatements = 0
        self.rejected_unverified = 0
        self.rejected_incompatible = 0

    def add_verified(
        self,
        *,
        statement: str,
        proof: str,
        certificate: str,
        context: str,
        dependencies: Iterable[str] = (),
        provenance: dict[str, Any] | None = None,
        original_goal: str = "",
        lean_accepted: bool,
        node_id: str | None = None,
    ) -> VerifiedLemmaNode | None:
        if not lean_accepted or _FORBIDDEN.search(proof) or _FORBIDDEN.search(certificate):
            self.rejected_unverified += 1
            return None
        statement_key = normalize_statement(statement)
        if not statement_key or statement_key in {"true", "false", normalize_statement(original_goal)}:
            self.rejected_restatements += 1
            return None
        deps = tuple(dict.fromkeys(str(dep) for dep in dependencies))
        if any(dep not in self.nodes for dep in deps):
            self.rejected_cycles += 1
            return None
        context_hash = _hash(context)
        resolved_id = node_id or _hash(statement_key, context_hash)
        if resolved_id in deps or any(self._reachable(dep, resolved_id) for dep in deps):
            self.rejected_cycles += 1
            return None

        existing = self.nodes.get(resolved_id)
        if existing is not None:
            existing.discoveries += 1
            if len(certificate) < len(existing.certificate):
                existing.proof = proof
                existing.certificate = certificate
                existing.dependencies = deps
                existing.provenance = dict(provenance or {})
            return existing
        if len(self.nodes) >= self.max_nodes:
            return None
        node = VerifiedLemmaNode(
            node_id=resolved_id,
            statement_key=statement_key,
            statement=statement.strip(),
            proof=proof.strip(),
            certificate=certificate.strip(),
            context=context,
            context_hash=context_hash,
            imports=_imports(context),
            dependencies=deps,
            provenance=dict(provenance or {}),
        )
        self.nodes[resolved_id] = node
        self.by_statement.setdefault(statement_key, []).append(resolved_id)
        return node

    def add_dependency(self, node_id: str, dependency_id: str) -> bool:
        """Add one edge, rejecting missing nodes, self edges, and transitive cycles."""

        node = self.nodes.get(node_id)
        if node is None or dependency_id not in self.nodes:
            return False
        if dependency_id == node_id or self._reachable(dependency_id, node_id):
            self.rejected_cycles += 1
            return False
        node.dependencies = tuple(dict.fromkeys([*node.dependencies, dependency_id]))
        return True

    def _reachable(self, start: str, target: str) -> bool:
        todo = [start]
        seen: set[str] = set()
        while todo:
            current = todo.pop()
            if current == target:
                return True
            if current in seen:
                continue
            seen.add(current)
            node = self.nodes.get(current)
            if node is not None:
                todo.extend(node.dependencies)
        return False

    def candidates(self, *, goal: str, context: str, limit: int = 8) -> list[VerifiedLemmaNode]:
        """Return potentially useful nodes; Lean must still revalidate compatibility."""

        target_imports = set(_imports(context))
        target_has_mathlib = "Mathlib" in target_imports
        goal_tokens = _tokens(goal)
        ranked: list[tuple[float, VerifiedLemmaNode]] = []
        for node in self.nodes.values():
            if node.imports and not target_has_mathlib and not set(node.imports) <= target_imports:
                self.rejected_incompatible += 1
                continue
            node_tokens = _tokens(node.statement)
            overlap = len(goal_tokens & node_tokens)
            score = overlap / max(1, len(node_tokens))
            # Keep zero-overlap nodes behind relevant ones: Lean is the final utility
            # filter and some algebraic bridge facts share few surface tokens.
            ranked.append((score, node))
        ranked.sort(key=lambda item: (-item[0], item[1].reuse_count, len(item[1].statement)))
        return [node for _score, node in ranked[:limit]]

    def reject_incompatible(self) -> None:
        self.rejected_incompatible += 1

    def mark_reused(self, node_ids: Iterable[str], *, decisive: bool = False) -> None:
        for node_id in set(node_ids):
            node = self.nodes.get(node_id)
            if node is None:
                continue
            node.reuse_count += 1
            if decisive:
                node.decisive_reuse_count += 1

    def record_route(
        self,
        *,
        route_id: str,
        state: RouteState,
        goal: str,
        bridge_verified: bool,
        proved_nodes: Iterable[str] = (),
        provenance: dict[str, Any] | None = None,
    ) -> None:
        self.routes.append(RouteRecord(
            route_id=route_id,
            state=state,
            goal=goal,
            bridge_verified=bridge_verified,
            proved_nodes=tuple(proved_nodes),
            provenance=dict(provenance or {}),
        ))

    def metadata(self) -> dict[str, Any]:
        return {
            "nodes_saved": len(self.nodes),
            "nodes_reused": sum(1 for node in self.nodes.values() if node.reuse_count),
            "reuse_events": sum(node.reuse_count for node in self.nodes.values()),
            "decisive_reuses": sum(node.decisive_reuse_count for node in self.nodes.values()),
            "rejected_cycles": self.rejected_cycles,
            "rejected_restatements": self.rejected_restatements,
            "rejected_unverified": self.rejected_unverified,
            "rejected_incompatible": self.rejected_incompatible,
            "nodes": [
                {
                    "node_id": node.node_id,
                    "statement": node.statement,
                    "proof": node.proof,
                    "context_hash": node.context_hash,
                    "dependencies": list(node.dependencies),
                    "provenance": node.provenance,
                    "reuse_count": node.reuse_count,
                    "decisive_reuse_count": node.decisive_reuse_count,
                    "discoveries": node.discoveries,
                }
                for node in self.nodes.values()
            ],
            "routes": [
                {**asdict(route), "state": route.state.value}
                for route in self.routes[-48:]
            ],
        }


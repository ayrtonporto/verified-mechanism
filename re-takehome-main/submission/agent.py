"""Implement your agent here. Infrastructure code should not need changes."""

from re_harness import AgentResult, Problem, Services


class SubmissionAgent:
    async def solve(self, problem: Problem, services: Services) -> AgentResult:
        raise NotImplementedError(
            "Implement SubmissionAgent.solve; see docs/AGENT_API.md"
        )


def create_agent() -> SubmissionAgent:
    return SubmissionAgent()


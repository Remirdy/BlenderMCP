"""Base classes and shared utilities for the Multi-Agent Scene Orchestration system."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from ..utils.logging_utils import get_logger

log = get_logger("remirdy.agents")


AgentName = Literal["geometry", "materials", "lighting", "composition", "critique"]


@dataclass
class AgentResult:
    """Standard result envelope returned by every specialist agent."""
    agent: str
    success: bool
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    suggestions: list[str] = field(default_factory=list)


@dataclass
class OrchestrationState:
    """Shared state passed between agents in a run."""
    prompt: str
    focus_areas: list[AgentName]
    iteration: int = 0
    max_iterations: int = 3
    history: list[dict[str, Any]] = field(default_factory=list)
    quality_score: float = 0.0
    last_vision: dict[str, Any] | None = None
    created_objects: list[str] = field(default_factory=list)


class BaseAgent:
    """Abstract base for all specialist agents."""

    name: AgentName

    def __init__(self, name: AgentName):
        self.name = name
        self.log = get_logger(f"remirdy.agents.{name}")

    def run(self, state: OrchestrationState, **kwargs: Any) -> AgentResult:
        """Execute one specialist pass. Must be overridden."""
        raise NotImplementedError

    def _record(self, state: OrchestrationState, result: AgentResult) -> None:
        """Helper to log agent activity into the shared state."""
        entry = {
            "iteration": state.iteration,
            "agent": self.name,
            "success": result.success,
            "summary": result.summary,
            "duration_ms": round(result.duration_ms, 1),
            "suggestions": result.suggestions[:5],
        }
        state.history.append(entry)
        self.log.info("%s pass → %s (%.0fms)", self.name, result.summary, result.duration_ms)


def timed(fn: Callable) -> Callable:
    """Decorator that measures execution time and attaches it to AgentResult."""
    def wrapper(self, *args, **kwargs):
        start = time.perf_counter()
        result: AgentResult = fn(self, *args, **kwargs)
        result.duration_ms = (time.perf_counter() - start) * 1000
        return result
    return wrapper

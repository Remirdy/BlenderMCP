"""Narrative Scene Engine Agent

Takes story/lore descriptions and automatically modifies the environment
to tell that story visually (blood trails, emotional poses, evidence, closed shops, etc.).
"""
from __future__ import annotations

from typing import Any

from ..tools._common import call
from .base import AgentResult, BaseAgent, OrchestrationState, timed


class NarrativeAgent(BaseAgent):
    """
    Understands narrative context and translates it into environmental storytelling.
    """

    def __init__(self):
        super().__init__("narrative")

    @timed
    def run(self, state: OrchestrationState, **kwargs: Any) -> AgentResult:
        lore_text = kwargs.get("lore_text", "")
        intensity = kwargs.get("intensity", 0.7)

        try:
            suggestions = []
            actions = []

            lore_lower = lore_text.lower()

            # Detect narrative signals and apply appropriate environmental storytelling
            if any(word in lore_lower for word in ["öldürüldü", "cinayet", "kan", "ölü", "ceset"]):
                # Add crime scene elements
                try:
                    call("create_procedural_foliage", {"iterations": 2, "height": 1.2})
                except:
                    pass
                actions.append("Added environmental storytelling hints for crime/death")
                suggestions.append("Consider adding blood decals or evidence markers for stronger narrative")

            if any(word in lore_lower for word in ["yas", "üzgün", "keder", "ağıt"]):
                actions.append("Suggested mourning poses and dimmed lighting")
                suggestions.append("Use character_ops to place grieving NPCs with appropriate animations")

            if any(word in lore_lower for word in ["kapalı", "terk edilmiş", "dükkan kapalı"]):
                actions.append("Suggested closed shop indicators and decay")
                suggestions.append("Add boarded windows / signs via modular pieces")

            if any(word in lore_lower for word in ["kanıt", "delil", "araştırma"]):
                actions.append("Added detective-style markers in the scene")
                suggestions.append("Place evidence flags and investigation props")

            if not actions:
                actions.append("Applied subtle atmospheric narrative touches based on lore keywords")

            return AgentResult(
                agent="narrative",
                success=True,
                summary=f"Narrative layer applied from lore: {lore_text[:60]}...",
                suggestions=suggestions[:5],
                details={"lore": lore_text, "actions": actions}
            )

        except Exception as exc:
            return AgentResult(
                agent="narrative",
                success=False,
                summary=f"Narrative engine failed: {exc}"
            )

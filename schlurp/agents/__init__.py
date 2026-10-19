"""Agents: anything that chooses a move in a position. No Pygame here."""

from schlurp.agents.base import Agent, Thoughts
from schlurp.agents.random_agent import RandomAgent

# Every AI agent, by its name in the start menu, Watch and Tournament.
AGENTS: dict[str, type[Agent]] = {
    "Random": RandomAgent,
}


def make_agent(name: str, seed: int | None = None) -> Agent:
    """Build an agent from its name, a key of AGENTS like "Random". Raises ValueError for a name it does not know.

    Later agents will take options after a colon, like a search depth.
    """
    base, *options = name.split(":")
    if base not in AGENTS:
        raise ValueError(f"No agent called {base!r}. The agents are: {', '.join(AGENTS)}")
    if options:
        raise ValueError(f"{base} has nothing to set after a colon")
    agent = AGENTS[base](seed=seed)
    agent.name = name
    return agent


__all__ = ["AGENTS", "Agent", "RandomAgent", "Thoughts", "make_agent"]

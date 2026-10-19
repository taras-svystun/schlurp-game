"""Agents: anything that chooses a move in a position. No Pygame here."""

from schlurp.agents.alphabeta_agent import AlphaBetaAgent
from schlurp.agents.base import Agent, Thoughts
from schlurp.agents.greedy_agent import GreedyAgent
from schlurp.agents.heuristics import HEURISTICS
from schlurp.agents.random_agent import RandomAgent

# Every AI agent, by its name in the start menu, Watch and Tournament.
AGENTS: dict[str, type[Agent]] = {
    "Random": RandomAgent,
    "Greedy": GreedyAgent,
    "AlphaBeta": AlphaBetaAgent,
}
# What each agent can set after colons in its name, in any order: "AlphaBeta:2", "AlphaBeta:3:pawns".
# A whole number is the depth; a name is a heuristic. Random and Greedy have nothing to set.
OPTIONS: dict[str, tuple[str, ...]] = {
    "AlphaBeta": ("depth", "heuristic"),
}
OPTION_TEXT = {
    "depth": "a depth (a whole number from 1 up)",
    "heuristic": f"a heuristic ({', '.join(HEURISTICS)})",
}


def make_agent(name: str, seed: int | None = None) -> Agent:
    """Build an agent from its name: a key of AGENTS, like "Greedy",
    maybe with options after colons (see OPTIONS), like "AlphaBeta:2" or "AlphaBeta:3:pawns".
    Raises ValueError for a name it does not know.
    """
    base, *options = name.split(":")
    if base not in AGENTS:
        raise ValueError(f"No agent called {base!r}. The agents are: {', '.join(AGENTS)}")
    allowed = OPTIONS.get(base, ())
    if options and not allowed:
        raise ValueError(f"{base} has nothing to set after a colon. Only these do: {', '.join(OPTIONS)}")
    settings = {}
    for option in options:
        if option.isdigit() and int(option) >= 1:
            key, value = "depth", int(option)
        elif option in HEURISTICS:
            key, value = "heuristic", HEURISTICS[option]
        else:
            key = None
        if key not in allowed:
            raise ValueError(f"{option!r} in {name!r} is not {' nor '.join(OPTION_TEXT[key] for key in allowed)}")
        if key in settings:
            raise ValueError(f"{name!r} sets the {key} twice")
        settings[key] = value
    agent = AGENTS[base](seed=seed, **settings)
    # Shown in the window and written in game records, so "AlphaBeta:2" is not mistaken for the default depth.
    agent.name = name
    return agent


__all__ = ["AGENTS", "HEURISTICS", "OPTIONS", "Agent", "AlphaBetaAgent", "GreedyAgent", "RandomAgent", "Thoughts", "make_agent"]

"""Agents: anything that chooses a move in a position. No Pygame here."""

import math

from schlurp.agents.alphabeta_agent import AlphaBetaAgent
from schlurp.agents.base import Agent, Thoughts
from schlurp.agents.deepening_agent import DeepeningAgent
from schlurp.agents.greedy_agent import GreedyAgent
from schlurp.agents.heuristics import FEATURES, HEURISTICS, weighted
from schlurp.agents.random_agent import RandomAgent

# Every AI agent, by its name in the start menu, Watch and Tournament.
AGENTS: dict[str, type[Agent]] = {
    "Random": RandomAgent,
    "Greedy": GreedyAgent,
    "AlphaBeta": AlphaBetaAgent,
    "Deepening": DeepeningAgent,
}
# What each agent can set after colons in its name, in any order: "AlphaBeta:2", "AlphaBeta:3:pawns", "Deepening:1s:mix".
# A whole number is the depth; a name is a heuristic; a number with an "s" is a time limit per move, in seconds. A feature with a weight, like "mobility=0.1",
# builds a heuristic on the spot: `pawns` plus each feature times its weight ("AlphaBeta:2:mobility=0.1:holes=-1").
# Random and Greedy have nothing to set.
OPTIONS: dict[str, tuple[str, ...]] = {
    "AlphaBeta": ("depth", "heuristic"),
    "Deepening": ("depth", "heuristic", "time_limit"),
}
OPTION_TEXT = {
    "depth": "a depth (a whole number from 1 up)",
    "time_limit": "a time limit (like 0.5s)",
    "heuristic": f"a heuristic ({', '.join(HEURISTICS)}) or features with weights ({', '.join(f'{n}=0.5' for n in FEATURES)})",
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
    settings, weights = {}, {}
    for option in options:
        if feature_weight(option):
            feature, weight = feature_weight(option)
            if feature in weights:
                raise ValueError(f"{name!r} gives {option.partition('=')[0]} two weights")
            weights[feature] = weight
            continue
        if option.isdigit() and int(option) >= 1:
            key, value = "depth", int(option)
        elif option in HEURISTICS:
            key, value = "heuristic", HEURISTICS[option]
        elif seconds(option):
            key, value = "time_limit", seconds(option)
        else:
            key = None
        if key not in allowed:
            raise ValueError(f"{option!r} in {name!r} is not {' nor '.join(OPTION_TEXT[key] for key in allowed)}")
        if key in settings:
            raise ValueError(f"{name!r} sets the {key.replace('_', ' ')} twice")
        settings[key] = value
    if weights:
        if "heuristic" not in allowed:
            raise ValueError(f"{base} has no heuristic to give weights to")
        if "heuristic" in settings:
            raise ValueError(f"{name!r} names a heuristic and also gives weights: use one or the other")
        settings["heuristic"] = weighted(weights)
    agent = AGENTS[base](seed=seed, **settings)
    # Shown in the window and written in game records, so "AlphaBeta:2" is not mistaken for the default depth.
    agent.name = name
    return agent


def seconds(option: str) -> float | None:
    """The time in an option like "0.5s" or "2s", or None if the option is not a time above 0."""
    if not option.endswith("s"):
        return None
    try:
        value = float(option[:-1])
    except ValueError:
        return None
    return value if 0 < value < math.inf else None


def feature_weight(option: str):
    """The feature and weight in an option like "mobility=0.1", or None if the option is not one."""
    feature, equals, weight = option.partition("=")
    if not equals or feature not in FEATURES:
        return None
    try:
        value = float(weight)
    except ValueError:
        return None
    return (FEATURES[feature], value) if math.isfinite(value) else None


__all__ = [
    "AGENTS",
    "HEURISTICS",
    "OPTIONS",
    "Agent",
    "AlphaBetaAgent",
    "DeepeningAgent",
    "GreedyAgent",
    "RandomAgent",
    "Thoughts",
    "make_agent",
]

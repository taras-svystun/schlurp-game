"""Run an AI agent in a background thread, so the window keeps drawing while it thinks.

An agent object never thinks in two threads at once, and a move that is no longer wanted can be
cancelled. See docs/adr/0004 for why it works this way.
"""

import threading
import time
import weakref

from schlurp.agents import Agent, Thoughts
from schlurp.engine import Game

# One lock for each agent object. A weak dictionary, so an agent that is no longer used is not kept alive.
_locks: weakref.WeakKeyDictionary[Agent, threading.Lock] = weakref.WeakKeyDictionary()
_locks_guard = threading.Lock()  # so two threads never make two different locks for one agent


def _lock_for(agent: Agent) -> threading.Lock:
    with _locks_guard:
        if agent not in _locks:
            _locks[agent] = threading.Lock()
        return _locks[agent]


class AgentThread:
    """One agent choosing one move.

    Python cannot kill a thread, so `cancel()` asks the agent to stop (see `Agent.should_stop`),
    and the window forgets this object, so its move is never played.
    """

    def __init__(self, agent: Agent, game: Game):
        # A copy, because the window may undo or play moves in its game while the agent thinks.
        self._game = game.copy()
        self.position = game.position
        self.started = time.monotonic()
        self.thoughts: Thoughts | None = None
        self.seconds = 0.0  # how long the agent thought
        self.finished = 0.0  # time.monotonic() when it was done; only valid once `is_done`
        self.error: Exception | None = None
        self._agent = agent
        self._cancelled = threading.Event()  # this thread's own, so cancelling it never stops another thread
        # daemon=True: closing the window does not wait for an agent that is still thinking.
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        # If the same agent is still thinking in an older thread, wait here, in the background, until it is done.
        with _lock_for(self._agent):
            if self._cancelled.is_set():
                return  # cancelled while waiting: nobody wants this move, so do not even start
            self._agent.stop = self._cancelled
            started = time.perf_counter()
            try:
                self.thoughts = self._agent.think_in_game(self._game)
            except Exception as error:
                # Keep it for the window to show, instead of leaving it waiting for a move forever.
                self.error = error
            finally:
                self._agent.stop = None
            self.seconds = time.perf_counter() - started
            self.finished = time.monotonic()

    def cancel(self) -> None:
        """The move is no longer wanted. Returns at once; the thread ends as soon as the agent notices."""
        self._cancelled.set()

    @property
    def is_done(self) -> bool:
        return not self._thread.is_alive()

    def wait(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

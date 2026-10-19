# One agent thinks in one thread at a time, and can be asked to stop

In the window an agent thinks in a background thread (`schlurp/ui/agent_thread.py`). Python cannot kill a thread, so when the person pressed Undo, New or Menu, the window just forgot the thread and went on. The next AI turn then started a second thread **with the same agent object**, while the first one could still be thinking.

With Random this did no harm, because it answers in microseconds. Search agents keep data on the agent while they think: the time a search must stop, a table of positions already judged, an MCTS tree, the random generator. Two threads changing that data at the same time give wrong moves that we could never repeat. Awalé's Deepening agent, which this project copies, keeps its `deadline` on the agent, so it would have the bug. The forgotten search also keeps one CPU core busy until it ends, and slows the new one.

## The decision

Two small parts, both in `schlurp/ui/agent_thread.py`, plus one method on `Agent`:

1. **A lock for each agent object.** `AgentThread` takes the agent's lock *inside the background thread*, before it calls the agent, and gives it back when the agent returns, even after an error. So an agent never runs in two threads at once. A new thread for a busy agent waits in the background; the window never waits.
2. **A stop flag.** `AgentThread.cancel()` sets a `threading.Event` that belongs to that one thread. While the thread runs the agent, `agent.should_stop()` reads that event. A long search (AlphaBeta, Deepening, MCTS) checks it now and then and returns at once. A thread that was cancelled before it got the lock never calls the agent at all. The window calls `cancel()` on Undo, New and Menu, wherever it used to forget a thread.

Random and Greedy finish in under a millisecond, so they never check `should_stop()`; they do not need to.

## Why this is safe

- **The window never blocks.** Only background threads take an agent's lock. The main loop only sets events and reads `is_done`, which never wait.
- **No deadlock.** A thread holds one lock, never takes a second one, and gives it back in a `finally`. The agent never takes our lock. So no two threads can each wait for the other.
- **One cancel cannot stop the wrong search.** Each thread has its own event, and the agent sees the event of the thread that holds the lock. Cancelling an old thread never stops the new one.
- **Old answers are never played.** As before, the window drops the cancelled `AgentThread` object, so its move is never read.
- **Tournaments do not change.** They call agents directly, in one thread per process. There `stop` is never set and `should_stop()` is always False.
- **Agents do not change.** The interface (`choose_move`, `think`, `think_in_game`) is the same. `should_stop()` is an extra a search may use.
- **The one cost:** if an agent ignores `should_stop()` and thinks for long, a new thread for it waits until it ends. That only delays the AI's next move, and it is correct (nothing runs twice). Every search agent we write checks the flag, and a test will check it.

## Considered options

- **A fresh copy of the agent for every move.** No sharing at all, but the copy's random generator would start from the same state every move, so Random would play the same choices again and again. It also throws away what a search learned on earlier moves, and the forgotten search still burns the CPU.
- **Wait for the old thread in the main loop.** Simple, but the window would freeze until the old search ends.
- **Run agents in processes, which can be killed.** Stops a search at once, but every move would send the game and the agent between processes, and an agent could no longer keep anything between moves. Kept in mind if a heavy agent makes the window stutter (the GIL).
- **Only the stop flag, no lock.** A search checks the flag only now and then, so for a moment two threads would still share the agent.

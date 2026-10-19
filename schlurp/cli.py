"""The `schlurp` command. Each way to use the game is a subcommand."""

import argparse
import sys

from schlurp.agents import AGENTS, make_agent
from schlurp.tournament import OPENING_MOVES, OPENINGS, default_workers, run_tournament


def agent_name(name: str) -> str:
    """Check an agent name on the command line, so a typo is reported before anything starts."""
    try:
        make_agent(name)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None
    return name


def main() -> None:
    parser = argparse.ArgumentParser(prog="schlurp", description="Schlurp: play people or AI, and compare AI agents.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("play", help="Open a window to play: two people on one computer, or a person against an AI.")

    tournament = commands.add_parser(
        "tournament",
        help="Play many games between two AI agents, with no window, and compare them.",
        description="Each random opening is played twice, with the agents swapping players.",
    )
    tournament.add_argument("a", type=agent_name, help=f"agent A: one of {', '.join(AGENTS)}")
    tournament.add_argument("b", type=agent_name, help="agent B")
    tournament.add_argument("--openings", type=int, default=OPENINGS, help=f"how many random openings (default {OPENINGS}); there are two games per opening")
    tournament.add_argument("--opening-moves", type=int, default=OPENING_MOVES, help=f"random moves in each opening (default {OPENING_MOVES})")
    tournament.add_argument("--seed", type=int, help="the same seed plays exactly the same games again (default: a random one, shown in the report)")
    tournament.add_argument("--workers", type=int, help=f"how many processes (default {default_workers()}, half the CPU cores)")
    tournament.add_argument("--save", action="store_true", help="save every game in a CSV file in records/tournaments")
    args = parser.parse_args()

    if args.command == "play":
        from schlurp.ui.app import run  # imported here so other commands never load Pygame

        run()
    elif args.command == "tournament":
        run_tournament_command(args)


def run_tournament_command(args: argparse.Namespace) -> None:
    def show_progress(done: int, total: int) -> None:
        if done % max(1, total // 100) and done != total:
            return  # only every 1%, so the screen is not flooded
        # "\r" goes back to the start of the line, so the count updates in place.
        print(f"\rPlayed {done} of {total} games", end="", file=sys.stderr, flush=True)

    tournament = run_tournament(
        args.a, args.b, args.openings, args.opening_moves, args.seed, args.workers, on_progress=show_progress
    )
    print(file=sys.stderr)
    print()
    print(tournament.report())
    if args.save:
        print(f"\nSaved to {tournament.save()}")

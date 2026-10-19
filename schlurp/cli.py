"""The `schlurp` command. Each way to use the game is a subcommand."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="schlurp", description="Schlurp: play people or AI, and compare AI agents.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("play", help="Open a window where two people play on one computer.")
    args = parser.parse_args()

    if args.command == "play":
        from schlurp.ui.app import run  # imported here so other commands never load Pygame

        run()

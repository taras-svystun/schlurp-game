// Plays messages through our web game inside Pyodide, in Node, for tests/test_web.py.
// Usage: node tests/pyodide_game.mjs <path to schlurp.zip>  (messages as a JSON list on stdin)
// Prints the answers as a JSON list: one list of answers for each list of messages.
import { readFileSync } from "node:fs";
import { loadPyodide } from "pyodide";

const [zipPath] = process.argv.slice(2);
const games = JSON.parse(readFileSync(0, "utf8"));
const pyodide = await loadPyodide();
pyodide.unpackArchive(new Uint8Array(readFileSync(zipPath)), "zip"); // a plain array: Pyodide does not take a Node Buffer
const { WebGame } = pyodide.pyimport("schlurp.web_game");
const answers = games.map((messages) => {
  const game = WebGame();
  return messages.map((message) => JSON.parse(game.handle_json(JSON.stringify(message))));
});
process.stdout.write(JSON.stringify(answers));

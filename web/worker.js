// Runs our Python game in Pyodide, away from the page, so the page never freezes (see docs/adr/0005).
// The page posts a message like {type: "play", move: "a1c3"}; the worker answers with the new state.
// The messages are explained in schlurp/web_game.py.

// The Pyodide version must be the same as in package.json, which the tests use. A test checks it.
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

async function startGame() {
  const [pyodide, zip] = await Promise.all([
    loadPyodide(),
    // "no-cache": ask the server every time, so a rebuilt zip is never stale. The zip is small.
    fetch("build/schlurp.zip", { cache: "no-cache" }).then((response) => {
      if (!response.ok) throw new Error(`build/schlurp.zip: ${response.status} ${response.statusText}`);
      return response.arrayBuffer();
    }),
  ]);
  pyodide.unpackArchive(zip, "zip");
  return pyodide.pyimport("schlurp.web_game").WebGame();
}

// Started at once; messages that come before it is ready wait for it, in order.
const game = startGame();

self.onmessage = async (event) => {
  let answer;
  try {
    answer = JSON.parse((await game).handle_json(JSON.stringify(event.data)));
  } catch (problem) {
    answer = { type: "error", message: `The game could not start: ${problem.message}` };
  }
  self.postMessage(answer);
};

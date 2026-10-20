// The page: draws the board, turns clicks into moves, and sends them to the game in worker.js.
// It knows nothing about the rules: every state it draws comes from the worker (see schlurp/web_game.py).

const SVG = "http://www.w3.org/2000/svg";
const COLUMNS = "abcdefg";
const NAMES = { blue: "Blue", green: "Green" };

const worker = new Worker("worker.js", { type: "module" });
const started = performance.now();

let state = null; // the last state from the worker
let selected = null; // the name of the picked pawn, like "a7", or null
let waiting = true; // a message is on its way to the worker; clicks wait for its answer
let problem = ""; // the last error from the worker, shown until the next good answer

// The engine's cells go a1, b1, ..., g1, a2, ..., g7. On screen row 7 is at the top.
function cellName(index) {
  return COLUMNS[index % 7] + (Math.floor(index / 7) + 1);
}

function cellXY(name) {
  return [COLUMNS.indexOf(name[0]), 7 - Number(name[1])];
}

function send(message) {
  waiting = true;
  worker.postMessage(message);
}

worker.onmessage = (event) => {
  const answer = event.data;
  waiting = false;
  if (answer.type === "error") {
    problem = answer.message;
  } else {
    if (!state) {
      const seconds = ((performance.now() - started) / 1000).toFixed(1);
      document.getElementById("loaded").textContent = `Loaded in ${seconds} s.`;
      console.log(`Schlurp loaded in ${seconds} s`);
    }
    state = answer;
    problem = "";
    selected = null;
  }
  draw();
};

worker.onerror = (event) => {
  problem = `The game could not start: ${event.message || "the worker failed to load"}`;
  draw();
};

function mover() {
  return state.to_move === "blue" ? "B" : "G";
}

// The move a click on an empty cell makes at once: a clone there, from whichever pawn.
function cloneOnto(name) {
  for (const targets of Object.values(state.reachable)) {
    if (targets[name] === name) return name;
  }
  return null;
}

function click(name, letter) {
  if (!state || waiting || state.result) return;
  if (letter === mover()) {
    // One of your own pawns: pick it, or drop it if it was already picked.
    if (name === selected) selected = null;
    else if (name in state.reachable) selected = name;
  } else if (letter === "." && selected && state.reachable[selected][name]) {
    send({ type: "play", move: state.reachable[selected][name] });
  } else if (letter === "." && cloneOnto(name)) {
    send({ type: "play", move: name });
  } else {
    selected = null;
  }
  draw();
}

function svg(tag, attributes, parent) {
  const element = document.createElementNS(SVG, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  parent.appendChild(element);
  return element;
}

function ring(name, kind, board) {
  const [x, y] = cellXY(name);
  svg("circle", { cx: x + 0.5, cy: y + 0.5, r: 0.42, class: `ring ${kind}` }, board);
}

function drawBoard() {
  const board = document.getElementById("board");
  board.replaceChildren();
  const targets = selected ? state.reachable[selected] : {};
  for (let index = 0; index < 49; index++) {
    const name = cellName(index);
    const letter = state.cells[index];
    const [x, y] = cellXY(name);
    const clickable =
      !state.result && ((letter === mover() && name in state.reachable) || (letter === "." && (targets[name] || cloneOnto(name))));
    const cell = svg("rect", { x, y, width: 1, height: 1, class: clickable ? "cell clickable" : "cell" }, board);
    cell.addEventListener("click", () => click(name, letter));
    if (letter !== ".") {
      const dimmed = letter === mover() && !(name in state.reachable) && !state.result;
      const pawn = svg("circle", { cx: x + 0.5, cy: y + 0.5, r: 0.34, class: `pawn ${letter === "B" ? "blue" : "green"}${dimmed ? " dimmed" : ""}` }, board);
      if (clickable) pawn.classList.add("clickable");
      pawn.addEventListener("click", () => click(name, letter));
    }
  }
  const last = state.moves.at(-1);
  if (last) {
    ring(last.slice(-2), "last", board);
    if (last.length === 4) {
      const [x, y] = cellXY(last.slice(0, 2));
      svg("circle", { cx: x + 0.5, cy: y + 0.5, r: 0.08, class: "left" }, board);
    }
  }
  if (selected) {
    ring(selected, "selected", board);
    for (const [name, move] of Object.entries(targets)) ring(name, move.length === 4 ? "jump" : "clone", board);
  }
}

function statusText() {
  if (problem) return problem;
  const result = state.result;
  if (result) {
    const [blue, green] = result.score;
    const winner = result.winner ? `${NAMES[result.winner]} wins` : "A draw";
    return `${winner}, ${blue} to ${green} (${result.ended_by}).`;
  }
  const turn = `${NAMES[state.to_move]} to move.`;
  if (state.passed) {
    const other = state.to_move === "blue" ? "Green" : "Blue";
    return `${other} cannot move and passes. ${turn}`;
  }
  return turn;
}

function draw() {
  document.getElementById("status").textContent = state || problem ? statusText() : "Loading the game…";
  if (!state) return;
  drawBoard();
  document.getElementById("pawns").textContent = `Blue ${state.pawns.blue} · Green ${state.pawns.green}`;
  const moves = document.getElementById("moves");
  moves.replaceChildren(...state.moves.map((move) => Object.assign(document.createElement("li"), { textContent: move })));
  document.getElementById("undo").disabled = waiting || state.moves.length === 0;
  document.getElementById("new").disabled = waiting;
}

document.getElementById("undo").addEventListener("click", () => send({ type: "undo" }));
document.getElementById("new").addEventListener("click", () => send({ type: "new", first: document.getElementById("first").value }));

send({ type: "new", first: "blue" });

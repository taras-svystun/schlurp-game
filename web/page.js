// The page: draws the board, turns clicks into moves, and sends them to the game in worker.js.
// It knows nothing about the rules: every state it draws comes from the worker (see schlurp/web_game.py).
//
// Two ways to play:
// - on this computer: two people take turns at the same mouse;
// - online: the address is ?game=<id>&seat=<secret>. Moves go through the game server (api.php), which
//   only passes them on; the worker checks every move that comes from the other player.

import { ANIMATION_SECONDS, drawBoard, moveAnimation } from "./board.js";

const NAMES = { blue: "Blue", green: "Green" };
const POLL_SECONDS = 1; // how often an online game asks the server for the other player's move

const worker = new Worker("worker.js", { type: "module" });
const started = performance.now();

let state = null; // the last state from the worker
let selected = null; // the name of the picked pawn, like "a7", or null
let busy = true; // waiting for the worker or the server; clicks wait too
let problem = ""; // the last error, shown until the next good answer
let animation = null; // the last move, while it is being animated

// The online game, or null when two people share this computer.
const address = new URLSearchParams(location.search);
const online = address.has("game")
  ? {
      game: address.get("game"),
      secret: address.get("seat"),
      you: null, // "blue" or "green", once the server says which player the secret belongs to
      known: 0, // how many of the game's moves the worker has played
      stopped: "", // why the game cannot go on, like an illegal move from the other player
      queue: Promise.resolve(), // online steps run one after another, never two at once
    }
  : null;

// --- Talking to the worker -------------------------------------------------------------------------------

// The worker answers messages in the order it gets them, so each answer goes to the oldest waiting question.
const waiting = [];
worker.onmessage = (event) => waiting.shift()(event.data);
worker.onerror = (event) => {
  problem = `The game could not start: ${event.message || "the worker failed to load"}`;
  draw();
};

function ask(message) {
  return new Promise((resolve) => {
    waiting.push(resolve);
    worker.postMessage(message);
  });
}

// Show a new state from the worker, or its error.
function show(answer) {
  if (answer.type === "error") {
    problem = answer.message;
    return false;
  }
  if (!state) {
    const seconds = ((performance.now() - started) / 1000).toFixed(1);
    document.getElementById("loaded").textContent = `Loaded in ${seconds} s.`;
    console.log(`Schlurp loaded in ${seconds} s`);
  }
  animation = moveAnimation(state, answer);
  if (animation) setTimeout(draw, ANIMATION_SECONDS * 1000 + 20); // then draw the board standing still
  state = answer;
  problem = "";
  selected = null;
  return true;
}

// Two people on this computer: send a message to the worker and show the answer.
async function act(message) {
  busy = true;
  draw();
  show(await ask(message));
  busy = false;
  draw();
}

// --- Talking to the game server --------------------------------------------------------------------------

async function server(action, { body, query = {} } = {}) {
  const url = `api.php?${new URLSearchParams({ action, ...query })}`;
  const options = body ? { method: "POST", body: JSON.stringify(body) } : {};
  const response = await fetch(url, options);
  const answer = await response.json();
  return { status: response.status, ...answer };
}

async function createOnlineGame() {
  busy = true;
  draw();
  const you = document.getElementById("you").value;
  const other = you === "blue" ? "green" : "blue";
  try {
    const created = await server("create", { body: { first: document.getElementById("first").value } });
    if (created.error) throw new Error(created.error);
    const link = (secret) => `${location.origin}${location.pathname}?game=${created.game}&seat=${secret}`;
    // The other player's link goes after "#" in ours: browsers never send that part to a server,
    // and it stays there when the page is reloaded, so we can show it again.
    location.href = `${link(created.secrets[you])}#invite=${created.secrets[other]}`;
  } catch (error) {
    problem = `Could not start an online game: ${error.message}`;
    busy = false;
    draw();
  }
}

// A step that returns false changed nothing, so the board is not drawn again.
function onlineStep(step) {
  online.queue = online.queue
    .then(step)
    .catch((error) => {
      problem = `Cannot reach the server (${error.message}). Trying again…`;
    })
    .then((changed) => {
      if (changed !== false) draw();
    });
  return online.queue;
}

// Open the online game: ask the server for every move so far, and let the worker replay them.
async function openOnlineGame() {
  const game = await server("game", { query: { game: online.game, secret: online.secret ?? "" } });
  if (game.error) {
    online.stopped = game.status === 404 ? "There is no such game. Games are deleted after 30 days with no move." : game.error;
    return;
  }
  if (!game.you) {
    online.stopped = "This link does not belong to a player of this game.";
    return;
  }
  online.you = game.you;
  const answer = await ask({ type: "new", first: game.first, moves: game.moves.map(({ move, player }) => ({ move, player })) });
  if (!show(answer)) {
    online.stopped = `This game has a move that breaks the rules. ${answer.message}`;
    return;
  }
  online.known = game.moves.length;
  busy = false;
  setTimeout(poll, POLL_SECONDS * 1000);
}

// Ask the server for new moves, play them, and ask again a second later, until the game ends.
function poll() {
  if (online.stopped || state.result) return;
  onlineStep(async () => {
    const game = await server("game", { query: { game: online.game, after: online.known } });
    if (game.error) throw new Error(game.error);
    const fresh = game.moves.filter(({ number }) => number >= online.known);
    if (!fresh.length && !problem.startsWith("Cannot reach")) return false; // nothing new: most seconds
    for (const { number, player, move } of game.moves) {
      if (number !== online.known) continue; // already played, like our own move coming back
      if (!show(await ask({ type: "play", move, player }))) {
        online.stopped = `${NAMES[player]} sent a move that breaks the rules (${move}): ${problem}. The game stops.`;
        return;
      }
      online.known += 1;
    }
    if (problem.startsWith("Cannot reach")) problem = "";
  }).then(() => setTimeout(poll, POLL_SECONDS * 1000));
}

// Our own move in an online game: the server stores it first, then the worker plays it.
function playOnline(move) {
  busy = true;
  draw();
  onlineStep(async () => {
    const sent = await server("move", { body: { game: online.game, secret: online.secret, number: online.known, move } });
    if (sent.status === 409) {
      problem = "The game moved on in the meantime. Here it is now.";
    } else if (sent.error) {
      problem = sent.error;
    } else {
      show(await ask({ type: "play", move, player: online.you }));
      online.known += 1;
    }
  }).then(() => {
    busy = false;
    draw();
  });
}

// --- Clicks ----------------------------------------------------------------------------------------------

function mover() {
  return state.to_move === "blue" ? "B" : "G";
}

// Can the person at this page move now?
function canMove() {
  if (!state || busy || state.result) return false;
  return !online || (!online.stopped && state.to_move === online.you);
}

// The move a click on an empty cell makes at once: a clone there, from whichever pawn.
function cloneOnto(name) {
  for (const targets of Object.values(state.reachable)) {
    if (targets[name] === name) return name;
  }
  return null;
}

function play(move) {
  if (online) playOnline(move);
  else act({ type: "play", move });
}

function click(name, letter) {
  if (!canMove()) return;
  if (letter === mover()) {
    // One of your own pawns: pick it, or drop it if it was already picked.
    if (name === selected) selected = null;
    else if (name in state.reachable) selected = name;
  } else if (letter === "." && selected && state.reachable[selected][name]) {
    play(state.reachable[selected][name]);
  } else if (letter === "." && cloneOnto(name)) {
    play(name);
  } else {
    selected = null;
  }
  draw();
}

// --- Drawing ---------------------------------------------------------------------------------------------

function statusText() {
  if (online?.stopped) return online.stopped;
  if (problem) return problem;
  if (!state) return "Loading the game…";
  const result = state.result;
  if (result) {
    const [blue, green] = result.score;
    const winner = result.winner ? `${NAMES[result.winner]} wins` : "A draw";
    return `${winner}, ${blue} to ${green} (${result.ended_by}).`;
  }
  let turn = `${NAMES[state.to_move]} to move.`;
  if (online) turn = state.to_move === online.you ? `Your move (${NAMES[online.you]}).` : `Waiting for ${NAMES[state.to_move]}'s move…`;
  if (state.passed) {
    const other = state.to_move === "blue" ? "Green" : "Blue";
    return `${other} cannot move and passes. ${turn}`;
  }
  return turn;
}

function draw() {
  document.getElementById("status").textContent = statusText();
  if (!state) return;
  drawBoard(document.getElementById("board"), {
    cells: state.cells,
    moves: state.moves,
    reachable: state.reachable,
    mover: mover(),
    selected,
    active: canMove(),
    animation,
    onClick: click,
  });
  document.getElementById("pawns").textContent = `Blue ${state.pawns.blue} · Green ${state.pawns.green}`;
  const moves = document.getElementById("moves");
  moves.replaceChildren(...state.moves.map((move) => Object.assign(document.createElement("li"), { textContent: move })));
  if (!online) {
    document.getElementById("undo").disabled = busy || state.moves.length === 0;
    document.getElementById("new").disabled = busy;
    document.getElementById("create").disabled = busy;
  }
}

window.addEventListener("resize", draw); // the board zooms in on narrow screens (see board.js)

// --- Start -----------------------------------------------------------------------------------------------

// The link for the other player, if we made this game (see createOnlineGame).
function inviteLink() {
  const secret = new URLSearchParams(location.hash.slice(1)).get("invite");
  return secret ? `${location.origin}${location.pathname}?game=${online.game}&seat=${secret}` : "";
}

async function copyInvite() {
  const input = document.getElementById("invite-link");
  const button = document.getElementById("copy");
  try {
    await navigator.clipboard.writeText(input.value); // only on HTTPS or localhost
  } catch {
    input.select(); // elsewhere the old way, which still works in every browser
    document.execCommand("copy");
  }
  button.textContent = "Copied";
  setTimeout(() => (button.textContent = "Copy"), 1500);
}

if (online) {
  document.getElementById("local").hidden = true;
  document.getElementById("online").hidden = false;
  const invite = inviteLink();
  if (invite) {
    document.getElementById("invite").hidden = false;
    document.getElementById("invite-link").value = invite;
    document.getElementById("copy").addEventListener("click", copyInvite);
  }
  const open = () =>
    onlineStep(openOnlineGame).then(() => {
      if (online.you) document.getElementById("you-are").textContent = `Online game. You play ${NAMES[online.you]}.`;
      else if (!online.stopped) setTimeout(open, 2000); // the server could not be reached: try again
    });
  open();
} else {
  document.getElementById("undo").addEventListener("click", () => act({ type: "undo" }));
  document.getElementById("new").addEventListener("click", () => act({ type: "new", first: document.getElementById("first").value }));
  document.getElementById("create").addEventListener("click", createOnlineGame);
  act({ type: "new", first: "blue" });
}

// Draws the board under the microscope, in SVG: the round lens, the grid and the microbes,
// and the short animation of the last move. The look follows the Pygame window (schlurp/ui/board_view.py).
//
// Nothing moves between moves, so the page costs no CPU while the players think. A move animates for
// ANIMATION_SECONDS: the pawn lands (a clone grows, a jump flies from its cell), then the infected
// neighbours change colour. The browser runs these as CSS animations; browsers that ask for less motion get none.

const SVG = "http://www.w3.org/2000/svg";
const COLUMNS = "abcdefg";
const PAWN_RADIUS = 0.38; // in cells
const LENS_RADIUS = 5.25; // the board's corners are 4.95 cells from its middle, so the whole board is inside

// What the SVG shows: the whole microscope, or on a narrow screen (a phone) only the board and the labels,
// so a cell is big enough for a finger, about 44 px.
const WHOLE = "-2.3 -2.3 11.6 11.6";
const ZOOMED = "-0.6 -0.25 7.85 7.85";
const ZOOM_BELOW_PX = 520;

export const ANIMATION_SECONDS = 0.45;
const LANDING_SECONDS = 0.2; // the pawn lands first; the infections follow

export function cellName(index) {
  return COLUMNS[index % 7] + (Math.floor(index / 7) + 1);
}

// The top-left corner of a cell. The engine's row 1 is at the bottom.
function cellXY(name) {
  return [COLUMNS.indexOf(name[0]), 7 - Number(name[1])];
}

function svg(tag, attributes, parent) {
  const element = document.createElementNS(SVG, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  parent.appendChild(element);
  return element;
}

// The outline of a microbe: a circle with soft bumps. Each cell gets its own bumps, which never change.
function blob(radius, seed) {
  const phase = seed * 1.7;
  const points = [];
  for (let i = 0; i < 24; i++) {
    const angle = (2 * Math.PI * i) / 24;
    const r = radius * (1 + 0.06 * Math.sin(3 * angle + phase) + 0.04 * Math.sin(5 * angle - 1.3 * phase));
    points.push(`${(r * Math.cos(angle)).toFixed(3)},${(r * Math.sin(angle)).toFixed(3)}`);
  }
  return `M${points.join("L")}Z`;
}

// One microbe, centred on (0, 0) inside a group placed on its cell. `colour` is "blue" or "green".
function microbe(colour, seed, parent) {
  const group = svg("g", { class: `microbe ${colour}` }, parent);
  svg("path", { d: blob(PAWN_RADIUS, seed), class: "membrane" }, group);
  svg("path", { d: blob(PAWN_RADIUS * 0.82, seed), class: "body" }, group);
  svg("circle", { cx: -PAWN_RADIUS * 0.22, cy: -PAWN_RADIUS * 0.18, r: PAWN_RADIUS * 0.32, class: "nucleus" }, group);
  return group;
}

// What changed with the last move, to animate it; null when the new state is not one move after the old one
// (a new game, an Undo, an online game opened).
export function moveAnimation(before, after) {
  if (!before || after.moves.length !== before.moves.length + 1) return null;
  if (before.moves.some((move, i) => after.moves[i] !== move)) return null;
  const move = after.moves.at(-1);
  const target = move.slice(-2);
  const source = move.length === 4 ? move.slice(0, 2) : null;
  const infected = [];
  for (let index = 0; index < 49; index++) {
    const name = cellName(index);
    if (name !== target && before.cells[index] !== "." && after.cells[index] !== "." && before.cells[index] !== after.cells[index]) {
      infected.push(name);
    }
  }
  return { target, source, infected, started: performance.now() };
}

// Start a CSS animation part of the way through, so a redraw in the middle of a move does not restart it.
function animate(element, name, delay, seconds, elapsed) {
  element.style.animation = `${name} ${seconds}s ${delay - elapsed}s both`;
}

function drawLens(board) {
  const defs = svg("defs", {}, board);
  const light = svg("radialGradient", { id: "lens-light" }, defs);
  svg("stop", { offset: "0%", "stop-color": "var(--lens-middle)" }, light);
  svg("stop", { offset: "100%", "stop-color": "var(--lens-edge)" }, light);
  // The metal ring around the lens, from outside in.
  [0.55, 0.42, 0.32, 0.12].forEach((width, i) => svg("circle", { cx: 3.5, cy: 3.5, r: LENS_RADIUS + width, class: `metal metal-${i}` }, board));
  svg("circle", { cx: 3.5, cy: 3.5, r: LENS_RADIUS, fill: "url(#lens-light)" }, board);
  for (let i = 0; i <= 7; i++) {
    svg("line", { x1: i, y1: 0, x2: i, y2: 7, class: "grid" }, board);
    svg("line", { x1: 0, y1: i, x2: 7, y2: i, class: "grid" }, board);
  }
  svg("rect", { x: 0, y: 0, width: 7, height: 7, class: "grid edge" }, board);
  for (let i = 0; i < 7; i++) {
    svg("text", { x: i + 0.5, y: 7.42, class: "label" }, board).textContent = COLUMNS[i];
    svg("text", { x: -0.32, y: 6.5 - i + 0.1, class: "label" }, board).textContent = String(i + 1);
  }
}

// Draw everything. `view` holds:
//   cells, moves, reachable, mover ("B" or "G")  from the worker's state
//   selected   the picked pawn, like "a7", or null
//   active     can the person at this page move now? (only then are pawns dimmed and cells clickable)
//   animation  from moveAnimation, or null
//   onClick    called with a cell name and its letter (".", "B" or "G")
export function drawBoard(board, view) {
  const { cells, moves, reachable, mover, selected, active, animation, onClick } = view;
  board.replaceChildren();
  board.setAttribute("viewBox", board.clientWidth < ZOOM_BELOW_PX ? ZOOMED : WHOLE);
  drawLens(board);
  const elapsed = animation ? (performance.now() - animation.started) / 1000 : Infinity;
  const moving = elapsed < ANIMATION_SECONDS ? animation : null;
  const targets = selected ? reachable[selected] : {};
  const cloneTargets = new Set(Object.values(reachable).flatMap((places) => Object.entries(places).filter(([, move]) => move.length === 2).map(([cell]) => cell)));

  const last = moves.at(-1);
  if (last && !moving) {
    const [x, y] = cellXY(last.slice(-2));
    svg("circle", { cx: x + 0.5, cy: y + 0.5, r: PAWN_RADIUS + 0.08, class: "ring last" }, board);
    if (last.length === 4) {
      const [sx, sy] = cellXY(last.slice(0, 2));
      svg("circle", { cx: sx + 0.5, cy: sy + 0.5, r: 0.08, class: "left" }, board);
    }
  }

  for (let index = 0; index < 49; index++) {
    const name = cellName(index);
    const letter = cells[index];
    const [x, y] = cellXY(name);
    const clickable = active && ((letter === mover && name in reachable) || (letter === "." && (targets[name] || cloneTargets.has(name))));
    const cell = svg("rect", { x, y, width: 1, height: 1, class: clickable ? "cell clickable" : "cell" }, board);
    cell.addEventListener("click", () => onClick(name, letter));
    if (letter === ".") continue;
    const place = svg("g", { transform: `translate(${x + 0.5} ${y + 0.5})`, class: clickable ? "clickable" : "" }, board);
    place.addEventListener("click", () => onClick(name, letter));
    // CSS animations set `transform`, which would replace the place's own: they go on the groups inside.
    const body = svg("g", {}, place);
    const colour = letter === "B" ? "blue" : "green";
    const pawn = microbe(colour, index, body);
    if (moving && name === moving.target) {
      if (moving.source) {
        const [sx, sy] = cellXY(moving.source);
        pawn.style.setProperty("--from-x", `${sx - x}px`);
        pawn.style.setProperty("--from-y", `${sy - y}px`);
        animate(pawn, "fly", 0, LANDING_SECONDS, elapsed);
      } else {
        animate(pawn, "grow", 0, LANDING_SECONDS, elapsed);
      }
    } else if (moving && moving.infected.includes(name)) {
      // The old colour on top fades away, showing the new one, while the microbe swells a little.
      const old = microbe(colour === "blue" ? "green" : "blue", index, body);
      old.classList.add("old");
      animate(old, "fade", LANDING_SECONDS, ANIMATION_SECONDS - LANDING_SECONDS, elapsed);
      animate(body, "swell", LANDING_SECONDS, ANIMATION_SECONDS - LANDING_SECONDS, elapsed);
    }
    if (active && letter === mover && !(name in reachable)) {
      svg("circle", { cx: 0, cy: 0, r: PAWN_RADIUS + 0.05, class: "dim" }, place);
    }
  }

  if (selected) {
    const [x, y] = cellXY(selected);
    svg("circle", { cx: x + 0.5, cy: y + 0.5, r: PAWN_RADIUS + 0.08, class: "ring selected" }, board);
    for (const [name, move] of Object.entries(targets)) {
      const [tx, ty] = cellXY(name);
      svg("circle", { cx: tx + 0.5, cy: ty + 0.5, r: PAWN_RADIUS - 0.07, class: `ring target ${mover === "B" ? "blue" : "green"} ${move.length === 4 ? "jump" : "clone"}` }, board);
    }
  }
}

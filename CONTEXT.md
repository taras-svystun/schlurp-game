# Schlurp

Schlurp is the Microscope puzzle from the computer game "The 7th Guest" (1993): two players grow colonies of microbes on a square board and infect each other's. Outside the 7th Guest the same game is called Ataxx. This project lets people play it on one computer, against each other or against AI, and lets us build and compare AI players.

## Language

### The board

**Board**:
A square grid of 7 by 7 cells, with no blocked cells. The game starts with Blue's pawns on the top-left and bottom-right corners and Green's on the other two.
_Avoid_: Grid, plate, damier, field

**Cell**:
One square of the board. A cell is empty or holds one pawn. Cells are named like on a chess board: columns a–g from left to right, rows 1–7 from bottom to top, so `a1` is the bottom-left corner.
_Avoid_: Square, case, tile, hole

**Neighbour**:
A cell touching another cell by a side or a corner. A cell has at most 8 neighbours.
_Avoid_: Adjacent cell

**Blue / Green**:
The two players. Blue moves first unless the start menu says otherwise.
_Avoid_: Player 1 / Player 2, x / o, black / white, red

**Pawn**:
One microbe on the board, belonging to Blue or Green. All pawns of a player are the same.
_Avoid_: Piece, stone, microbe, counter

**Position**:
A moment in a game: which cells hold whose pawns, whose turn it is, and how many jumps in a row were just made. It knows nothing else about earlier moves.
_Avoid_: State, board state, snapshot

**Game**:
All positions from the start of one game up to now, with the moves between them and how it ended.
_Avoid_: Match, round, session

### Moves

**Move**:
A clone or a jump by the player to move.
_Avoid_: Turn, play

**Clone**:
A move that puts a new pawn on an empty neighbour of one of your pawns. The old pawn stays. Clones onto the same cell from different pawns are the same move, written as that cell: `c3`.
_Avoid_: Duplicate, copy, single, grow

**Jump**:
A move that takes one of your pawns to an empty cell exactly 2 cells away, over a row, a column or a corner. The cell it left becomes empty. Written as both cells: `a1c3`.
_Avoid_: Double, leap, hop

**Infect**:
After a clone or a jump, every enemy pawn on a neighbour of the cell the pawn landed on turns to the mover's colour.
_Avoid_: Capture, convert, flip, contaminate, phagocyte

**Pass**:
When the player to move has no move, the turn goes back to the other player at once. A pass is not a move.
_Avoid_: Skip, null move

### End of the game

**Win**:
The game ends when the board is full, when a player has no pawns left, or when neither player can move. The player with more pawns wins; equal counts are a draw.

**Fifty-move rule**:
When 100 moves in a row (50 by each player) are all jumps, the game ends in a draw, whoever has more pawns.
_Avoid_: Move limit, jump limit, halfmove clock

### Who plays

**Player**:
Blue or Green in a specific game. An agent plays for a player.
_Avoid_: Side, user, colour

**Agent**:
Anything that chooses a move in a position: a person clicking cells, a random chooser, or an AI like "alpha-beta, depth 3, heuristic mix".
_Avoid_: Bot, AI player, engine, strategy

**Heuristic**:
A function that looks at a position and gives it a number: how good it is for one player. It does not choose moves by itself.
_Avoid_: Evaluation, strategy, score function

**Search**:
A method that looks ahead through possible moves to pick one, such as alpha-beta or MCTS. Search usually uses a heuristic to judge the positions it reaches.
_Avoid_: Strategy, algorithm

**Playout**:
A game played from a position to the end with random moves. MCTS judges a position by the share of its playouts each player wins.
_Avoid_: Rollout, simulation, random game

**Depth**:
How many moves ahead a search looks, counting the moves of both players. Depth 4 is my move, the answer, my next move, and the next answer.
_Avoid_: Ply, level, horizon

**Time limit**:
How long an agent may think about one move. An agent with a time limit looks 1 move ahead, then 2, then 3, and so on, and when the time is up it plays the best move of the deepest search it finished.
_Avoid_: Clock, budget, timeout

**Thoughts**:
What an agent shows about how it chose its move: the score of each possible move, the line of play it expects, and how much work it did.
_Avoid_: Brains, debug info, logs

### Ways to use the game

**Play**:
One game in a window where at least one agent is a person. Two people can share the computer, or a person plays against an AI.
_Avoid_: Match, session

**Watch**:
One game between two AI agents, shown in a window move by move, with their thoughts next to the board.
_Avoid_: Spectate, replay

**Tournament**:
Many games between AI agents, run without a window, to compare them with numbers instead of by eye.
_Avoid_: Arena, benchmark, simulation

**Points**:
In a tournament, a win gives an agent 1 point, a draw 1/2 and a loss 0. An agent's points are shown as a share of the games played: 50% means the two agents are even.
_Avoid_: Score (the score is the pawns each player ends a game with), rating

**Hint**:
In Play, the move an AI agent would choose for the person whose turn it is, shown only when the person asks.
_Avoid_: Tip, suggestion, assist

**Game record**:
A saved game: who played Blue and Green, the list of moves in cell names, and the result.
_Avoid_: Log, replay, history, save file

**Random opening**:
The first few moves of a tournament game, chosen at random so that games between the same agents are not all identical. Each random opening is played twice, with the agents swapping players.
_Avoid_: Warm-up, seed moves

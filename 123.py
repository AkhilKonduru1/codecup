"""Zero Point One bot for CodeCup 26.

This implementation keeps the single-file requirement while providing a
self-contained engine with:

* compact leaper move generation that understands both regular moves and
  redeployments ("drops") of captured pieces;
* reversible move application so the search can explore game trees safely;
* iterative-deepening negamax with alpha-beta pruning, capture-only
  quiescence, move ordering (MVV/LVA + history heuristic) and a light-weight
  time manager; and
* a basic positional evaluator that rewards central control, mobility and the
  material value of captured pieces still in hand.

The file is intentionally free of external dependencies – it only relies on the
standard library – so that it can be compiled and executed directly by the
CodeCup judges.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

# Board helpers -----------------------------------------------------------------

FILES = "abcdefgh"
RANKS = "12345678"

MOVE_BOARD = 0
MOVE_DROP = 1
PIECE_ORDER = ["W", "N", "F", "D", "A"]
PIECE_INDEX = {p: i for i, p in enumerate(PIECE_ORDER)}

PIECE_VALUES = {
    "W": 20000,
    "N": 700,
    "F": 550,
    "D": 450,
    "A": 320,
}

# Raw leaper offsets expressed as (d_row, d_col) on the 8x8 board where rows are
# labelled a-h (0-7) and columns 1-8 (0-7).
LEAPER_OFFSETS = {
    "W": ((1, 0), (-1, 0), (0, 1), (0, -1)),
    "N": (
        (1, 2),
        (1, -2),
        (-1, 2),
        (-1, -2),
        (2, 1),
        (2, -1),
        (-2, 1),
        (-2, -1),
    ),
    "F": ((1, 1), (1, -1), (-1, 1), (-1, -1)),
    "D": ((0, 2), (0, -2), (2, 0), (-2, 0)),
    "A": ((2, 2), (2, -2), (-2, 2), (-2, -2)),
}

# Pre-compute a simple centrality/initiative table used by the evaluation and
# move ordering. Squares closer to the centre and further from the owner’s home
# rows are preferred.
SQUARE_ACTIVITY: List[int] = []
for row in range(8):
    for col in range(8):
        centre = 14 - int(abs(row - 3.5) * 3 + abs(col - 3.5) * 3)
        advance_red = row * 2  # reward reaching deeper ranks for red
        retreat_blue = (7 - row) * 2  # analogous for blue pieces (mirrored)
        SQUARE_ACTIVITY.append(centre + advance_red + retreat_blue)


# Utility functions --------------------------------------------------------------

def square_to_index(coord: str) -> int:
    """Convert a board coordinate like "b5" into a 0..63 index."""
    if len(coord) != 2:
        raise ValueError(f"Invalid square '{coord}'")
    row = FILES.index(coord[0])
    col = RANKS.index(coord[1])
    return row * 8 + col


def index_to_square(index: int) -> str:
    row, col = divmod(index, 8)
    return f"{FILES[row]}{RANKS[col]}"


def mirror_index(index: int) -> int:
    row, col = divmod(index, 8)
    return (7 - row) * 8 + col


@dataclass
class Move:
    kind: int
    src: Optional[int]
    dst: int
    piece: str
    captured: str

    @staticmethod
    def board(src: int, dst: int, piece: str, target: str) -> "Move":
        return Move(MOVE_BOARD, src, dst, piece, target)

    @staticmethod
    def drop(dst: int, piece: str) -> "Move":
        return Move(MOVE_DROP, None, dst, piece, ".")


class ZeroPointOneBot:
    """Single-file Zero Point One engine with search and evaluation."""

    def __init__(self) -> None:
        self.board: List[str] = ["."] * 64
        self.captured_red: List[int] = [0] * 5
        self.captured_blue: List[int] = [0] * 5
        self.turn_red: bool = True
        self.our_color_red: bool = True
        self.awaiting_opponent_start: bool = False

        self.history: Dict[Tuple[str, int], int] = {}

        self.time_limit: float = 2.8  # seconds per search burst
        self.search_start: float = 0.0
        self.time_exceeded: bool = False

        self.max_depth: int = 6
        self.quiescence_depth: int = 6

    # ------------------------------------------------------------------ Game IO
    def reset_game(self, we_are_red: bool) -> None:
        self.board = ["."] * 64
        self.captured_red = [0] * 5
        self.captured_blue = [0] * 5
        self.turn_red = True
        self.our_color_red = we_are_red
        self.awaiting_opponent_start = we_are_red
        self.history.clear()

    def choose_start_sequence(self, for_red: bool) -> str:
        if for_red:
            # Compact central structure guarding the wazir while letting knights
            # and ferzes develop quickly.
            return "WNFDDFAAADAFNAAA"
        return "wnfddfa aad afnaaa".replace(" ", "")

    def apply_start_sequence(self, sequence: str, for_red: bool) -> None:
        rows = (0, 1) if for_red else (6, 7)
        idx = 0
        for row in rows:
            for col in range(8):
                piece = sequence[idx]
                idx += 1
                if piece == ".":
                    self.board[row * 8 + col] = "."
                else:
                    self.board[row * 8 + col] = piece.upper() if for_red else piece.lower()

    def parse_move(self, token: str, is_red_move: bool) -> Move:
        if len(token) == 4:
            src = square_to_index(token[:2])
            dst = square_to_index(token[2:])
            piece = self.board[src]
            target = self.board[dst]
            return Move.board(src, dst, piece, target)
        if len(token) == 3:
            piece = token[0]
            dst = square_to_index(token[1:])
            return Move.drop(dst, piece)
        raise ValueError(f"Invalid move token '{token}'")

    def format_move(self, move: Move) -> str:
        if move.kind == MOVE_DROP:
            return f"{move.piece}{index_to_square(move.dst)}"
        assert move.src is not None
        return f"{index_to_square(move.src)}{index_to_square(move.dst)}"

    def play_move_from_string(self, token: str, is_red_move: bool) -> None:
        move = self.parse_move(token, is_red_move)
        self.play_move(move, is_red_move)

    def play_move(self, move: Move, is_red_move: bool) -> None:
        captured = self.make_move(move, is_red_move)
        # No undo – this updates the permanent game state.
        if captured is not None and captured.upper() == "W":
            # Game would end; nothing special to do for bookkeeping because the
            # arbiter will send Quit immediately afterwards.
            pass

    # --------------------------------------------------------------- Move utils
    def make_move(self, move: Move, is_red_move: bool) -> Optional[str]:
        if move.kind == MOVE_BOARD:
            assert move.src is not None
            piece = move.piece
            target = move.captured
            assert self.board[move.src] == piece
            assert self.board[move.dst] == target
            self.board[move.src] = "."
            self.board[move.dst] = piece
            if target != ".":
                pool = self.captured_red if is_red_move else self.captured_blue
                pool[PIECE_INDEX[target.upper()]] += 1
            return target
        # Drop
        pool = self.captured_red if is_red_move else self.captured_blue
        pool[PIECE_INDEX[move.piece.upper()]] -= 1
        self.board[move.dst] = move.piece
        return None

    def undo_move(self, move: Move, is_red_move: bool, captured: Optional[str]) -> None:
        if move.kind == MOVE_BOARD:
            assert move.src is not None
            self.board[move.src] = move.piece
            self.board[move.dst] = captured if captured is not None else "."
            if captured and captured != ".":
                pool = self.captured_red if is_red_move else self.captured_blue
                pool[PIECE_INDEX[captured.upper()]] -= 1
        else:
            self.board[move.dst] = "."
            pool = self.captured_red if is_red_move else self.captured_blue
            pool[PIECE_INDEX[move.piece.upper()]] += 1

    # --------------------------------------------------------------- Move gen
    def generate_moves(self, is_red_turn: bool) -> List[Move]:
        moves: List[Move] = []
        board = self.board
        for idx, piece in enumerate(board):
            if piece == ".":
                continue
            if piece.isupper() != is_red_turn:
                continue
            p_type = piece.upper()
            for dr, dc in LEAPER_OFFSETS[p_type]:
                row, col = divmod(idx, 8)
                nr, nc = row + dr, col + dc
                if not (0 <= nr < 8 and 0 <= nc < 8):
                    continue
                dst = nr * 8 + nc
                target = board[dst]
                if target == "." or target.isupper() != is_red_turn:
                    moves.append(Move.board(idx, dst, piece, target))
        pool = self.captured_red if is_red_turn else self.captured_blue
        if any(pool):
            for p_idx, count in enumerate(pool):
                if count <= 0:
                    continue
                piece = PIECE_ORDER[p_idx] if is_red_turn else PIECE_ORDER[p_idx].lower()
                for sq, occupant in enumerate(board):
                    if occupant == ".":
                        moves.append(Move.drop(sq, piece))
        return moves

    def generate_captures(self, is_red_turn: bool) -> List[Move]:
        return [
            move
            for move in self.generate_moves(is_red_turn)
            if move.kind == MOVE_BOARD and move.captured != "."
        ]

    def order_moves(self, moves: Iterable[Move]) -> List[Move]:
        ordered: List[Tuple[int, Move]] = []
        for move in moves:
            if move.kind == MOVE_BOARD:
                target_value = PIECE_VALUES.get(move.captured.upper(), 0) if move.captured != "." else 0
                mover_value = PIECE_VALUES[move.piece.upper()]
                capture_bonus = 0
                if move.captured != ".":
                    if move.captured.upper() == "W":
                        capture_bonus = 100_000
                    else:
                        capture_bonus = 5_000 + target_value - mover_value // 2
                history_bonus = self.history.get((move.piece, move.dst), 0)
                activity_bonus = SQUARE_ACTIVITY[move.dst]
                score = capture_bonus + history_bonus + activity_bonus
            else:
                drop_value = PIECE_VALUES[move.piece.upper()]
                history_bonus = self.history.get((move.piece, move.dst), 0) // 4
                score = 1_000 + drop_value + SQUARE_ACTIVITY[move.dst] + history_bonus
            ordered.append((score, move))
        ordered.sort(key=lambda item: item[0], reverse=True)
        return [move for _, move in ordered]

    # --------------------------------------------------------------- Evaluation
    def evaluate(self) -> int:
        score = 0
        for idx, piece in enumerate(self.board):
            if piece == ".":
                continue
            value = PIECE_VALUES[piece.upper()]
            activity = SQUARE_ACTIVITY[idx] if piece.isupper() else SQUARE_ACTIVITY[mirror_index(idx)]
            mobility = len(self._mobility_cache(idx, piece))
            total = value + activity + mobility * 5
            if piece.isupper():
                score += total
            else:
                score -= total
        for i, count in enumerate(self.captured_red):
            score += count * PIECE_VALUES[PIECE_ORDER[i]]
        for i, count in enumerate(self.captured_blue):
            score -= count * PIECE_VALUES[PIECE_ORDER[i]]
        return score

    def _mobility_cache(self, idx: int, piece: str) -> List[int]:
        row, col = divmod(idx, 8)
        offsets = LEAPER_OFFSETS[piece.upper()]
        moves: List[int] = []
        for dr, dc in offsets:
            nr, nc = row + dr, col + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                moves.append(nr * 8 + nc)
        return moves

    def evaluate_for(self, is_red_turn: bool) -> int:
        base = self.evaluate()
        return base if is_red_turn else -base

    # --------------------------------------------------------------- Search
    def search(self, is_red_turn: bool) -> Move:
        moves = self.generate_moves(is_red_turn)
        if not moves:
            return Move.drop(0, PIECE_ORDER[0])  # fallback, should never happen

        ordered_moves = self.order_moves(moves)
        best_move = ordered_moves[0]
        best_score = -float("inf")

        self.search_start = time.time()
        self.time_exceeded = False

        depth = 1
        while depth <= self.max_depth:
            alpha = -100_000_000
            beta = 100_000_000
            score, move = self.negamax(depth, alpha, beta, is_red_turn)
            if self.time_exceeded:
                break
            if move is not None:
                best_move = move
                best_score = score
            depth += 1
        if best_score == -float("inf"):
            best_move = ordered_moves[0]
        return best_move

    def negamax(self, depth: int, alpha: int, beta: int, is_red_turn: bool) -> Tuple[int, Optional[Move]]:
        if self.check_time():
            return 0, None
        if depth == 0:
            return self.quiescence(alpha, beta, is_red_turn), None

        best_move: Optional[Move] = None
        local_alpha = alpha
        moves = self.order_moves(self.generate_moves(is_red_turn))
        if not moves:
            return self.evaluate_for(is_red_turn), None

        for move in moves:
            captured = self.make_move(move, is_red_turn)
            if captured is not None and captured.upper() == "W":
                score = 100_000_000 - (self.max_depth - depth) * 100
            else:
                score, _ = self.negamax(depth - 1, -beta, -local_alpha, not is_red_turn)
                score = -score
            self.undo_move(move, is_red_turn, captured)
            if self.time_exceeded:
                return 0, None
            if score > local_alpha:
                local_alpha = score
                best_move = move
                if local_alpha >= beta:
                    self.record_history(move, depth)
                    break
        if best_move is None:
            best_move = moves[0]
        return local_alpha, best_move

    def quiescence(self, alpha: int, beta: int, is_red_turn: bool, depth: int = 0) -> int:
        if self.check_time():
            return 0
        stand_pat = self.evaluate_for(is_red_turn)
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat
        if depth >= self.quiescence_depth:
            return alpha
        captures = self.order_moves(self.generate_captures(is_red_turn))
        for move in captures:
            captured = self.make_move(move, is_red_turn)
            if captured is not None and captured.upper() == "W":
                score = 100_000_000 - depth * 10
            else:
                score = -self.quiescence(-beta, -alpha, not is_red_turn, depth + 1)
            self.undo_move(move, is_red_turn, captured)
            if self.time_exceeded:
                return alpha
            if score >= beta:
                self.record_history(move, depth + 1)
                return beta
            if score > alpha:
                alpha = score
        return alpha

    def record_history(self, move: Move, depth: int) -> None:
        key = (move.piece, move.dst)
        self.history[key] = self.history.get(key, 0) + (1 << depth)

    def check_time(self) -> bool:
        if self.time_exceeded:
            return True
        if time.time() - self.search_start >= self.time_limit:
            self.time_exceeded = True
        return self.time_exceeded


# --------------------------------------------------------------------------- CLI

def main() -> None:
    bot = ZeroPointOneBot()
    color_known = False

    for raw in sys.stdin:
        token = raw.strip()
        if not token:
            continue

        if token == "Quit":
            break

        if token == "Start":
            bot.reset_game(we_are_red=True)
            start = bot.choose_start_sequence(for_red=True)
            bot.apply_start_sequence(start, for_red=True)
            print(start)
            sys.stdout.flush()
            color_known = True
            continue

        if not color_known:
            bot.reset_game(we_are_red=False)
            bot.apply_start_sequence(token, for_red=True)
            reply = bot.choose_start_sequence(for_red=False)
            bot.apply_start_sequence(reply, for_red=False)
            print(reply)
            sys.stdout.flush()
            color_known = True
            bot.turn_red = True
            continue

        if bot.awaiting_opponent_start:
            bot.apply_start_sequence(token, for_red=False)
            bot.awaiting_opponent_start = False
            bot.turn_red = True
            move = bot.search(is_red_turn=True)
            bot.play_move(move, True)
            bot.turn_red = False
            print(bot.format_move(move))
            sys.stdout.flush()
            continue

        is_red_move = bot.turn_red
        bot.play_move_from_string(token, is_red_move)
        bot.turn_red = not bot.turn_red

        our_turn = (bot.turn_red and bot.our_color_red) or (not bot.turn_red and not bot.our_color_red)
        if our_turn:
            move = bot.search(bot.turn_red)
            bot.play_move(move, bot.turn_red)
            bot.turn_red = not bot.turn_red
            print(bot.format_move(move))
            sys.stdout.flush()


if __name__ == "__main__":
    main()

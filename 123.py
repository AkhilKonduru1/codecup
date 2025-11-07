import sys
import time
import random
import math
from sys import stdin, stdout

drW = [1, -1, 0, 0]
dcW = [0, 0, 1, -1]
drF = [1, 1, -1, -1]
dcF = [1, -1, 1, -1]
drN = [1, 1, -1, -1, 2, 2, -2, -2]
dcN = [2, -2, 2, -2, 1, -1, 1, -1]
drD = [0, 0, 2, -2]
dcD = [2, -2, 0, 0]
drA = [2, 2, -2, -2]
dcA = [2, -2, 2, -2]

PIECE_VALUES = {'W': 10000, 'N': 500, 'F': 400, 'D': 300, 'A': 200}

CENTER_BONUS = 30
DEVELOPMENT_BONUS = 15
KING_SAFETY_BONUS = 100
MOBILITY_BONUS = 5
THREAT_BONUS = 20
DEFENSE_BONUS = 10

OPENING_BOOK = {
    "red": [
        "WNFFDDDDAAAAAAAA",
        "WNFDADAAADDFDAAAA",
        "WNFDADAAADDFDAAAA"
    ],
    "blue": [
        "wnffddddaaaaaaaa",
        "wnfddddaaaaaaaa",
        "wnfddddaaaaaaaa"
    ]
}

ENDGAME_PATTERNS = {
    'king_attack': 500,
    'king_defense': 300,
    'piece_activity': 50,
    'pawn_promotion': 200
}

class ZeroPointOneAI:
    def __init__(self):
        self.board = [['.' for _ in range(8)] for __ in range(8)]
        self.capRed = [0] * 5
        self.capBlue = [0] * 5
        self.isRed = False
        self.ourTurn = False
        self.start_time = time.time()
        self.time_limit = 25.0
        
    def is_upper(self, c):
        return 'A' <= c <= 'Z'
    
    def is_lower(self, c):
        return 'a' <= c <= 'z'
    
    def index_of(self, c):
        u = c.upper()
        if u == 'W': return 0
        if u == 'N': return 1
        if u == 'F': return 2
        if u == 'D': return 3
        if u == 'A': return 4
        return -1
    
    def get_piece_value(self, piece):
        if piece == '.':
            return 0
        return PIECE_VALUES.get(piece.upper(), 0)
    
    def get_positional_bonus(self, r, c, piece):
        bonus = 0
        
        center_distance = abs(r - 3.5) + abs(c - 3.5)
        bonus += max(0, CENTER_BONUS - center_distance * 3)
        
        if self.isRed:
            if r <= 1:
                bonus += DEVELOPMENT_BONUS
        else:
            if r >= 6:
                bonus += DEVELOPMENT_BONUS
        
        if piece.upper() == 'W':
            friendly_count = 0
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 8 and 0 <= nc < 8:
                        if self.board[nr][nc] != '.':
                            if (self.isRed and self.is_upper(self.board[nr][nc])) or \
                               (not self.isRed and self.is_lower(self.board[nr][nc])):
                                friendly_count += 1
            bonus += friendly_count * KING_SAFETY_BONUS
            
            if self.isRed and r > 2:
                bonus += 50
            elif not self.isRed and r < 5:
                bonus += 50
        
        mobility = self.count_mobility(r, c, piece)
        bonus += mobility * MOBILITY_BONUS
        
        threat_bonus = self.calculate_threats(r, c, piece)
        bonus += threat_bonus * THREAT_BONUS
        
        defense_bonus = self.calculate_defense(r, c, piece)
        bonus += defense_bonus * DEFENSE_BONUS
        
        return bonus
    
    def count_mobility(self, r, c, piece):
        moves = self.get_piece_moves(r, c, piece)
        return len(moves)
    
    def calculate_threats(self, r, c, piece):
        threats = 0
        moves = self.get_piece_moves(r, c, piece)
        for move in moves:
            if len(move) == 5 and move[4] is not None:
                target = move[4]
                if target != '.':
                    if (self.isRed and self.is_lower(target)) or (not self.isRed and self.is_upper(target)):
                        threats += 1
        return threats
    
    def calculate_defense(self, r, c, piece):
        defense = 0
        moves = self.get_piece_moves(r, c, piece)
        for move in moves:
            if len(move) == 5 and move[4] is not None:
                target = move[4]
                if target != '.':
                    if (self.isRed and self.is_upper(target)) or (not self.isRed and self.is_lower(target)):
                        defense += 1
        return defense
    
    def evaluate_board(self):
        score = 0
        
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece == '.':
                    continue
                
                piece_value = self.get_piece_value(piece)
                positional_bonus = self.get_positional_bonus(r, c, piece)
                
                if (self.isRed and self.is_upper(piece)) or (not self.isRed and self.is_lower(piece)):
                    score += piece_value + positional_bonus
                else:
                    score -= piece_value + positional_bonus
        
        for i in range(5):
            piece_value = PIECE_VALUES[['W', 'N', 'F', 'D', 'A'][i]]
            if self.isRed:
                score += self.capRed[i] * piece_value
                score -= self.capBlue[i] * piece_value
            else:
                score += self.capBlue[i] * piece_value
                score -= self.capRed[i] * piece_value
        
        score += self.evaluate_endgame()
        
        score += self.evaluate_tactical_patterns()
        
        return score
    
    def evaluate_endgame(self):
        score = 0
        
        red_pieces = sum(1 for r in range(8) for c in range(8) 
                        if self.board[r][c] != '.' and self.is_upper(self.board[r][c]))
        blue_pieces = sum(1 for r in range(8) for c in range(8) 
                         if self.board[r][c] != '.' and self.is_lower(self.board[r][c]))
        
        total_pieces = red_pieces + blue_pieces
        
        if total_pieces <= 8:
            for r in range(8):
                for c in range(8):
                    piece = self.board[r][c]
                    if piece.upper() == 'W':
                        if (self.isRed and self.is_upper(piece)) or (not self.isRed and self.is_lower(piece)):
                            center_distance = abs(r - 3.5) + abs(c - 3.5)
                            score += max(0, 100 - center_distance * 20)
        
        return score
    
    def evaluate_tactical_patterns(self):
        score = 0
        
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece == '.':
                    continue
                
                if self.is_double_attack(r, c, piece):
                    piece_value = self.get_piece_value(piece)
                    if (self.isRed and self.is_upper(piece)) or (not self.isRed and self.is_lower(piece)):
                        score += piece_value * 0.5
                    else:
                        score -= piece_value * 0.5
        
        return score
    
    def is_double_attack(self, r, c, piece):
        moves = self.get_piece_moves(r, c, piece)
        enemy_targets = 0
        
        for move in moves:
            if len(move) == 5 and move[4] is not None:
                target = move[4]
                if target != '.':
                    if (self.isRed and self.is_lower(target)) or (not self.isRed and self.is_upper(target)):
                        enemy_targets += 1
        
        return enemy_targets >= 2
    
    def get_all_moves(self, is_red_turn):
        moves = []
        
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece == '.':
                    continue
                if is_red_turn and not self.is_upper(piece):
                    continue
                if not is_red_turn and not self.is_lower(piece):
                    continue
                
                piece_moves = self.get_piece_moves(r, c, piece)
                for move in piece_moves:
                    if self.is_valid_move(move, is_red_turn):
                        moves.append(move)
        
        captured = self.capRed if is_red_turn else self.capBlue
        for i in range(5):
            if captured[i] > 0:
                piece = (['W', 'N', 'F', 'D', 'A'][i] if is_red_turn else 
                        ['w', 'n', 'f', 'd', 'a'][i])
                for rr in range(8):
                    for cc in range(8):
                        if self.board[rr][cc] == '.':
                            move = (piece, rr, cc, None, None)
                            if self.is_valid_move(move, is_red_turn):
                                moves.append(move)
        
        return moves
    
    def get_piece_moves(self, r, c, piece):
        moves = []
        t = piece.upper()
        
        if t == 'W':
            for i in range(4):
                nr, nc = r + drW[i], c + dcW[i]
                if 0 <= nr < 8 and 0 <= nc < 8:
                    moves.append((r, c, nr, nc, self.board[nr][nc]))
        elif t == 'N':
            for i in range(8):
                nr, nc = r + drN[i], c + dcN[i]
                if 0 <= nr < 8 and 0 <= nc < 8:
                    moves.append((r, c, nr, nc, self.board[nr][nc]))
        elif t == 'F':
            for i in range(4):
                nr, nc = r + drF[i], c + dcF[i]
                if 0 <= nr < 8 and 0 <= nc < 8:
                    moves.append((r, c, nr, nc, self.board[nr][nc]))
        elif t == 'D':
            for i in range(4):
                nr, nc = r + drD[i], c + dcD[i]
                if 0 <= nr < 8 and 0 <= nc < 8:
                    moves.append((r, c, nr, nc, self.board[nr][nc]))
        elif t == 'A':
            for i in range(4):
                nr, nc = r + drA[i], c + dcA[i]
                if 0 <= nr < 8 and 0 <= nc < 8:
                    moves.append((r, c, nr, nc, self.board[nr][nc]))
        
        return moves
    
    def is_valid_move(self, move, is_red_turn):
        if len(move) == 5 and move[4] is not None:
            r1, c1, r2, c2, target = move
            piece = self.board[r1][c1]
            if piece == '.':
                return False
            if is_red_turn and not self.is_upper(piece):
                return False
            if not is_red_turn and not self.is_lower(piece):
                return False
            
            if target != '.':
                if (is_red_turn and self.is_upper(target)) or (not is_red_turn and self.is_lower(target)):
                    return False
            
            return True
        elif len(move) == 5 and move[4] is None:
            piece, r, c, _, _ = move
            if self.board[r][c] != '.':
                return False
            
            idx = self.index_of(piece)
            if idx == -1:
                return False
            
            captured = self.capRed if is_red_turn else self.capBlue
            if captured[idx] <= 0:
                return False
            
            return True
        
        return False
    
    def make_move(self, move):
        if len(move) == 5 and move[4] is not None:
            r1, c1, r2, c2, target = move
            piece = self.board[r1][c1]
            
            self.board[r2][c2] = piece
            self.board[r1][c1] = '.'
            
            if target != '.':
                idx = self.index_of(target)
                if self.isRed:
                    self.capRed[idx] += 1
                else:
                    self.capBlue[idx] += 1
                
                return target.upper() == 'W'
        elif len(move) == 5 and move[4] is None:
            piece, r, c, _, _ = move
            self.board[r][c] = piece
            idx = self.index_of(piece)
            if (self.isRed and self.is_upper(piece)) or (not self.isRed and self.is_lower(piece)):
                if self.isRed:
                    self.capRed[idx] -= 1
                else:
                    self.capBlue[idx] -= 1
        
        return False
    
    def unmake_move(self, move, captured_piece=None):
        if len(move) == 5 and move[4] is not None:
            r1, c1, r2, c2, target = move
            piece = self.board[r2][c2]
            
            self.board[r1][c1] = piece
            self.board[r2][c2] = target
            
            if target and target != '.':
                idx = self.index_of(target)
                if self.isRed:
                    self.capRed[idx] -= 1
                else:
                    self.capBlue[idx] -= 1
        elif len(move) == 5 and move[4] is None:
            piece, r, c, _, _ = move
            self.board[r][c] = '.'
            idx = self.index_of(piece)
            if (self.isRed and self.is_upper(piece)) or (not self.isRed and self.is_lower(piece)):
                if self.isRed:
                    self.capRed[idx] += 1
                else:
                    self.capBlue[idx] += 1
    
    def order_moves(self, moves, is_red_turn):
        def move_priority(move):
            if len(move) == 5 and move[4] is not None:
                r1, c1, r2, c2, target = move
                piece = self.board[r1][c1]

                # Base: captures prioritized by target value (and king highest)
                capture_score = 0
                if target != '.':
                    target_value = self.get_piece_value(target)
                    piece_value = self.get_piece_value(piece)
                    if target.upper() == 'W':
                        capture_score = 10000
                    else:
                        # MVV-LVA style
                        capture_score = 1000 + target_value - piece_value

                # Advancement and centralization
                if is_red_turn:
                    advance_bonus = r2 * 10
                else:
                    advance_bonus = (7 - r2) * 10
                center_distance = abs(r2 - 3.5) + abs(c2 - 3.5)
                center_bonus = 50 - center_distance * 10

                # Defense improvement: simulate move and score added defense for the moved piece
                defense_improvement = 0
                moved_piece_defense_after = 0
                # Simulate quickly
                saved_target = self.board[r2][c2]
                self.board[r2][c2] = piece
                self.board[r1][c1] = '.'
                try:
                    moved_piece_defense_after = self.calculate_defense(r2, c2, piece)
                finally:
                    # revert
                    self.board[r1][c1] = piece
                    self.board[r2][c2] = saved_target
                defense_improvement = moved_piece_defense_after * 20

                return capture_score + advance_bonus + center_bonus + defense_improvement
            else:
                return 0

        return sorted(moves, key=move_priority, reverse=True)

    def quiescence(self, alpha, beta, is_red_turn):
        # Stand-pat evaluation
        stand_pat = self.evaluate_board()
        if stand_pat >= beta:
            return stand_pat
        if stand_pat > alpha:
            alpha = stand_pat

        # Generate capture moves only for side to move
        capture_moves = []
        all_moves = self.get_all_moves(is_red_turn)
        for mv in all_moves:
            if len(mv) == 5 and mv[4] is not None and mv[4] != '.':
                capture_moves.append(mv)

        # Simple ordering: most valuable victim - least valuable attacker
        def cap_key(mv):
            r1, c1, r2, c2, target = mv
            return self.get_piece_value(target) - self.get_piece_value(self.board[r1][c1])
        capture_moves.sort(key=cap_key, reverse=True)

        start_check = time.time()
        for mv in capture_moves:
            # Time guard inside quiescence as well
            if time.time() - self.start_time > self.time_limit * 0.98:
                break
            won = self.make_move(mv)
            score = self.quiescence(-beta, -alpha, not is_red_turn)
            self.unmake_move(mv)
            score = -score
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
        return alpha
    
    def minimax(self, depth, alpha, beta, maximizing_player, is_red_turn):
        if depth <= 0:
            return self.quiescence(alpha, beta, is_red_turn)
        
        if time.time() - self.start_time > self.time_limit * 0.98:
            return self.evaluate_board()
        
        moves = self.get_all_moves(is_red_turn)
        if not moves:
            return self.evaluate_board()
        
        moves = self.order_moves(moves, is_red_turn)
        # Consider more moves now; ordering will prune via alpha-beta
        moves = moves[:20]
        
        if maximizing_player:
            max_eval = float('-inf')
            for i, move in enumerate(moves):
                if not self.is_valid_move(move, is_red_turn):
                    continue
                
                if i > 5 and time.time() - self.start_time > self.time_limit * 0.8:
                    break
                
                won = self.make_move(move)
                if won:
                    self.unmake_move(move)
                    return 10000 if is_red_turn == self.isRed else -10000
                
                eval_score = self.minimax(depth - 1, alpha, beta, False, not is_red_turn)
                self.unmake_move(move)
                
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            
            return max_eval
        else:
            min_eval = float('inf')
            for i, move in enumerate(moves):
                if not self.is_valid_move(move, is_red_turn):
                    continue
                
                if i > 5 and time.time() - self.start_time > self.time_limit * 0.8:
                    break
                
                won = self.make_move(move)
                if won:
                    self.unmake_move(move)
                    return 10000 if is_red_turn == self.isRed else -10000
                
                eval_score = self.minimax(depth - 1, alpha, beta, True, not is_red_turn)
                self.unmake_move(move)
                
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            
            return min_eval
    
    def has_tactical_moves(self, moves):
        for move in moves:
            if len(move) == 5 and move[4] is not None and move[4] != '.':
                return True
        return False
    
    def get_best_move(self):
        moves = self.get_all_moves(self.isRed)
        if not moves:
            return None
        
        for move in moves:
            won = self.make_move(move)
            if won:
                self.unmake_move(move)
                return move
            self.unmake_move(move)
        
        best_move = None
        best_score = float('-inf') if self.isRed else float('inf')
        
        moves = self.order_moves(moves, self.isRed)
        
        # Iterative deepening until time budget nearly exhausted
        depth = 1
        while True:
            if time.time() - self.start_time > self.time_limit * 0.95:
                break
            
            depth_best_move = None
            depth_best_score = float('-inf') if self.isRed else float('inf')
            
            # Expand moves researched with depth
            moves_to_search = moves[:min(12, len(moves))]
            for move in moves_to_search:
                
                if time.time() - self.start_time > self.time_limit * 0.98:
                    break
                
                won = self.make_move(move)
                if won:
                    self.unmake_move(move)
                    return move
                
                score = self.minimax(depth - 1, float('-inf'), float('inf'), False, not self.isRed)
                self.unmake_move(move)
                
                if self.isRed:
                    if score > depth_best_score:
                        depth_best_score = score
                        depth_best_move = move
                else:
                    if score < depth_best_score:
                        depth_best_score = score
                        depth_best_move = move
            
            if depth_best_move is not None:
                best_move = depth_best_move
                best_score = depth_best_score
            depth += 1
        
        if best_move is None:
            for move in moves:
                if len(move) == 5 and move[4] is not None and move[4] != '.':
                    return move
            for move in moves:
                if len(move) == 5 and move[4] is not None:
                    r1, c1, r2, c2, target = move
                    if self.isRed and r2 > r1:
                        return move
                    elif not self.isRed and r2 < r1:
                        return move
            return moves[0] if moves else None
        
        return best_move
    
    def get_opening_sequence(self, color):
        if color == "red":
            return OPENING_BOOK["red"][0]
        else:
            return OPENING_BOOK["blue"][0]
    
    def format_move(self, move):
        if len(move) == 5 and move[4] is not None:
            r1, c1, r2, c2, target = move
            return chr(ord('a') + r1) + str(c1 + 1) + chr(ord('a') + r2) + str(c2 + 1)
        elif len(move) == 5 and move[4] is None:
            piece, r, c, _, _ = move
            if 0 <= r < 8 and 0 <= c < 8:
                return piece + chr(ord('a') + r) + str(c + 1)
        return ""
    
    def play_game(self):
        line = stdin.readline().strip()
        if not line:
            sys.exit(0)
        
        if line == "Start":
            self.isRed = True
            seq = self.get_opening_sequence("red")
            stdout.write(seq + "\n")
            stdout.flush()
            oppseq = stdin.readline().strip()
            
            for i in range(8):
                self.board[0][i] = seq[i] if i < len(seq) else '.'
            for i in range(8):
                self.board[1][i] = seq[8 + i] if 8 + i < len(seq) else '.'
            for i in range(8):
                self.board[6][i] = oppseq[i] if i < len(oppseq) else '.'
            for i in range(8):
                self.board[7][i] = oppseq[8 + i] if 8 + i < len(oppseq) else '.'
            self.ourTurn = True
        else:
            self.isRed = False
            redseq = line
            seq = self.get_opening_sequence("blue")
            stdout.write(seq + "\n")
            stdout.flush()
            
            for i in range(8):
                self.board[0][i] = redseq[i] if i < len(redseq) else '.'
            for i in range(8):
                self.board[1][i] = redseq[8 + i] if 8 + i < len(redseq) else '.'
            for i in range(8):
                self.board[6][i] = seq[i] if i < len(seq) else '.'
            for i in range(8):
                self.board[7][i] = seq[8 + i] if 8 + i < len(seq) else '.'
            self.ourTurn = False
        
        while True:
            if self.ourTurn:
                self.start_time = time.time()
                
                try:
                    best_move = self.get_best_move()
                except Exception as e:
                    moves = self.get_all_moves(self.isRed)
                    if moves:
                        best_move = moves[0]
                    else:
                        best_move = None
                
                if best_move is None:
                    stdout.write("Quit\n")
                    stdout.flush()
                    break
                
                move_str = self.format_move(best_move)
                
                if len(move_str) != 4:
                    moves = self.get_all_moves(self.isRed)
                    if moves:
                        for move in moves:
                            if len(move) == 5 and move[4] is not None:
                                move_str = self.format_move(move)
                                if move_str and len(move_str) == 4:
                                    break
                
                # Allow 4-char regular moves and 3-char revival moves
                if move_str and (len(move_str) == 4 or len(move_str) == 3):
                    stdout.write(move_str + "\n")
                    stdout.flush()
                else:
                    stdout.write("Quit\n")
                    stdout.flush()
                    break
                
                won = self.make_move(best_move)
                if won:
                    break
                
                self.ourTurn = False
            else:
                line = stdin.readline()
                if not line:
                    break
                line = line.strip()
                if line == "Quit":
                    break
                
                if len(line) == 4:
                    r1 = ord(line[0]) - ord('a')
                    c1 = int(line[1]) - 1
                    r2 = ord(line[2]) - ord('a')
                    c2 = int(line[3]) - 1
                    moving = self.board[r1][c1]
                    dest = self.board[r2][c2]
                    self.board[r2][c2] = moving
                    self.board[r1][c1] = '.'
                    if dest != '.':
                        idx = self.index_of(dest)
                        if self.isRed:
                            self.capRed[idx] += 1
                        else:
                            self.capBlue[idx] += 1
                        if (self.isRed and dest == 'W') or (not self.isRed and dest == 'w'):
                            break
                elif len(line) == 3:
                    piece = line[0]
                    r = ord(line[1]) - ord('a')
                    c = int(line[2]) - 1
                    self.board[r][c] = piece
                    idx = self.index_of(piece)
                    if (self.isRed and self.is_lower(piece)) or (not self.isRed and self.is_upper(piece)):
                        if self.isRed:
                            self.capRed[idx] -= 1
                        else:
                            self.capBlue[idx] -= 1
                    else:
                        if self.isRed:
                            self.capBlue[idx] -= 1
                        else:
                            self.capRed[idx] -= 1
                
                self.ourTurn = True

if __name__ == "__main__":
    ai = ZeroPointOneAI()
    ai.play_game()

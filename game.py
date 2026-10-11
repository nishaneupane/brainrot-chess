"""Chess plumbing on top of python-chess (pip install chess):
the NPC baseline bot, game playing with a move cap, and brainrot commentary."""
import random

import chess

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
PIECE_SLANG = {chess.PAWN: "pawn", chess.KNIGHT: "horsey", chess.BISHOP: "pointy hat guy",
               chess.ROOK: "castle", chess.QUEEN: "queen", chess.KING: "king"}
MAX_PLIES = 160  # 80 moves each, then the judges count material


def material(board, color):
    return sum(VALUES[p.piece_type] * (1 if p.color == color else -1) for p in board.piece_map().values())


class NPCBot:
    """The baseline. Takes a free mate or the juiciest capture, otherwise random.
    Basically a chess.com 250 who just learned how the horsey moves."""

    id = "npc"
    name = "NPC Bot"

    def choose(self, board, rng=random):
        moves = list(board.legal_moves)
        for m in moves:
            board.push(m)
            mate = board.is_checkmate()
            board.pop()
            if mate:
                return m
        caps = [m for m in moves if board.is_capture(m)]
        if caps and rng.random() < 0.7:
            def gain(m):
                p = board.piece_at(m.to_square)
                return VALUES[p.piece_type] if p else 1  # en passant
            return max(caps, key=gain)
        return rng.choice(moves)


def commentary(board, move, mover_name):
    """One brainrot line for a move (call BEFORE board.push)."""
    lines = []
    piece = board.piece_at(move.from_square)
    victim = board.piece_at(move.to_square)
    if board.is_castling(move):
        lines.append(f"{mover_name} castled. King said 'i'm not built for this' and dipped")
    if victim:
        if victim.piece_type == chess.QUEEN:
            lines.append(f"{mover_name} FANUM TAXED THE QUEEN. NOT THE QUEEN")
        elif VALUES[victim.piece_type] >= 3:
            lines.append(f"{mover_name} fanum taxed a {PIECE_SLANG[victim.piece_type]} (+{VALUES[victim.piece_type]} aura)")
    if move.promotion:
        lines.append(f"pawn glow-up arc complete. {PIECE_SLANG[move.promotion]} unlocked")
    board.push(move)
    if board.is_checkmate():
        lines.append(f"CHECKMATE. {mover_name} mogged the king. L + ratio + no rizz")
    elif board.is_check():
        lines.append(f"{mover_name} is mogging the king rn")
    board.pop()
    if piece and piece.piece_type == chess.KING and not board.is_castling(move) and board.fullmove_number < 15:
        lines.append(f"{mover_name} walking the king out early. absolute ohio behavior")
    return " / ".join(lines)


def play(white, black, rng=random, record=False):
    """Returns (result, info). result: 0 white won, 1 black won, None draw.
    Unfinished games past MAX_PLIES go to whoever is up 3+ points of material."""
    board, players = chess.Board(), (white, black)
    sans, fens, comments = [], [board.board_fen()], []
    while not board.is_game_over(claim_draw=True) and len(sans) < MAX_PLIES:
        idx = 0 if board.turn == chess.WHITE else 1
        move = players[idx].choose(board, rng)
        if record:
            comments.append(commentary(board, move, players[idx].name))
            sans.append(board.san(move))
        else:
            sans.append(move.uci())
        board.push(move)
        if record:
            fens.append(board.board_fen())

    how = "checkmate"
    if board.is_checkmate():
        result = 1 if board.turn == chess.WHITE else 0  # side to move got mated
    elif board.is_game_over(claim_draw=True):
        result, how = None, "draw"
    else:
        diff = material(board, chess.WHITE)
        result = 0 if diff >= 3 else 1 if diff <= -3 else None
        how = "judges' decision (material)" if result is not None else "draw (move cap)"
    info = {"moves": sans, "how": how, "plies": len(sans)}
    if record:
        info |= {"fens": fens, "comments": comments}
    return result, info

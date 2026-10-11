"""Evolving chess agents. A strategy is a handful of named genes the LLM can read
and rewrite. Each move is scored locally (1-ply + 'is my piece about to get
fanum taxed' check), so games are fast and only breeding costs LLM calls."""
import random
import uuid

import chess

from game import VALUES

GENES = {
    "greed": "how much it loves material (taking pieces, keeping pieces)",
    "paranoia": "penalty for leaving a piece where the opponent can take it next move",
    "mate_hunter": "bonus for a move that is checkmate",
    "check_spam": "bonus for giving check",
    "center_rizz": "bonus for pieces attacking the 4 center squares",
    "activity": "bonus for how many squares the moved piece now attacks",
    "development": "bonus for moving knights/bishops off the back rank",
    "king_safety": "bonus for castling, penalty for walking the king around",
    "pawn_pushing": "bonus for advancing pawns",
    "chaos": "random noise added to every move score (0 = deterministic)",
}

PERSONALITIES = [
    "sigma grindset, wakes up at 4am to analyze the Sicilian",
    "pure aura farmer, every move is for the edit",
    "certified yapper, explains its moves to nobody",
    "mewing through the whole game, refuses to blink",
    "chronically online, 9000 hours of bullet chess",
    "rizzless but in a lovable way",
    "Ohio final boss energy",
    "delulu, thinks it's a grandmaster",
    "permanently low on time, premoves everything",
    "certified hater, trash talks the board itself",
]

NAMES = [
    "Skibidi Sicilian", "Rizzler Rook", "Ohio Opening", "Sigma Gambit", "Fanum Tax Bishop",
    "Aura Farmer", "Mewing Knight", "Gigachad Pawn", "Bombastic Side Eye", "Delulu Defense",
    "Sus Castle", "Yapper Queen", "No Cap Caro-Kann", "Erm Actually En Passant", "Cooked Kingside",
    "Lowkey Lasker", "Brainrot Bongcloud", "Big Back Blunder", "Npc Slayer", "Glazer Gambit",
]

CENTER = [chess.D4, chess.E4, chess.D5, chess.E5]


def random_genes(rng):
    g = {k: round(rng.uniform(-1, 1), 2) for k in GENES}
    g["chaos"] = round(rng.uniform(0, 1), 2)
    return g


def best_capture_gain(board):
    """Value of the best piece the side to move can capture right now."""
    best = 0
    for m in board.legal_moves:
        if board.is_capture(m):
            p = board.piece_at(m.to_square)
            best = max(best, VALUES[p.piece_type] if p else 1)
    return best


class Agent:
    def __init__(self, genes, name, personality, generation=0, parents=(),
                 playbook="", trash_talk="", agent_id=None):
        self.id = agent_id or uuid.uuid4().hex[:8]
        self.genes, self.name, self.personality = genes, name, personality
        self.generation, self.parents = generation, list(parents)
        self.playbook, self.trash_talk = playbook, trash_talk
        self.wins = self.losses = self.draws = 0

    def score_move(self, board, move, rng):
        g, me = self.genes, board.turn
        piece = board.piece_at(move.from_square)
        victim = board.piece_at(move.to_square)
        s = 0.0
        if victim:
            s += 10 * g["greed"] * VALUES[victim.piece_type]
        if board.is_castling(move):
            s += 15 * g["king_safety"]
        elif piece.piece_type == chess.KING:
            s -= 8 * g["king_safety"]
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP) and chess.square_rank(move.from_square) in (0, 7):
            s += 6 * g["development"]
        if piece.piece_type == chess.PAWN:
            s += 2 * g["pawn_pushing"] * (1 if me == chess.WHITE else -1) * (
                chess.square_rank(move.to_square) - chess.square_rank(move.from_square))

        board.push(move)
        if board.is_checkmate():
            board.pop()
            return 1000 * g["mate_hunter"]
        if board.is_check():
            s += 8 * g["check_spam"]
        s += 3 * g["center_rizz"] * sum(1 for sq in CENTER if board.is_attacked_by(me, sq))
        s += 0.8 * g["activity"] * len(board.attacks(move.to_square))
        s -= 10 * g["paranoia"] * best_capture_gain(board)
        board.pop()
        return s + rng.gauss(0, 10 * max(g["chaos"], 0))

    def choose(self, board, rng=random):
        return max(board.legal_moves, key=lambda m: self.score_move(board, m, rng))

    @property
    def games(self):
        return self.wins + self.losses + self.draws

    @property
    def score(self):
        return (self.wins + 0.5 * self.draws) / self.games if self.games else 0.0

    def reset_record(self):
        self.wins = self.losses = self.draws = 0

    def to_dict(self):
        return {"id": self.id, "name": self.name, "personality": self.personality,
                "generation": self.generation, "parents": self.parents, "genes": self.genes,
                "playbook": self.playbook, "trash_talk": self.trash_talk}


def random_agent(rng, used_names):
    name = rng.choice([n for n in NAMES if n not in used_names] or NAMES)
    used_names.add(name)
    return Agent(random_genes(rng), name, rng.choice(PERSONALITIES),
                 playbook="no thoughts. head empty. vibes only.",
                 trash_talk="just spawned and already know i'm him fr fr")

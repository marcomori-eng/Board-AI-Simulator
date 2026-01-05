"""
Game State Manager
==================
Gestisce lo stato completo della partita, incluse carte, punteggi e cronologia.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import random
from datetime import datetime


class Suit(Enum):
    """Semi delle carte italiane."""
    COPPE = "coppe"
    DENARI = "denari"
    BASTONI = "bastoni"
    SPADE = "spade"


@dataclass
class Card:
    """Rappresenta una carta del mazzo."""
    suit: Suit
    rank: str
    points: int
    strength: int  # 1 = più forte
    
    def __repr__(self):
        return f"{self.rank} di {self.suit.value}"
    
    def __hash__(self):
        return hash((self.suit, self.rank))
    
    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.suit == other.suit and self.rank == other.rank


@dataclass
class HandResult:
    """Risultato di una singola mano."""
    hand_number: int
    cards_played: Dict[str, Card]  # player_id -> carta giocata
    winner: str
    points_won: int
    trump_used: bool
    first_player: str


@dataclass
class GameState:
    """Stato completo della partita."""
    
    # Configurazione
    game_id: str
    trump_suit: Optional[Suit] = None
    trump_card: Optional[Card] = None
    
    # Giocatori
    player1_id: str = "player1"
    player2_id: str = "player2"
    
    # Mani dei giocatori
    player1_hand: List[Card] = field(default_factory=list)
    player2_hand: List[Card] = field(default_factory=list)
    
    # Punteggi
    player1_score: int = 0
    player2_score: int = 0
    
    # Carte vinte
    player1_won_cards: List[Card] = field(default_factory=list)
    player2_won_cards: List[Card] = field(default_factory=list)
    
    # Mazzo
    deck: List[Card] = field(default_factory=list)
    
    # Stato gioco
    current_player: str = "player1"
    hand_number: int = 0
    is_game_over: bool = False
    winner: Optional[str] = None
    
    # Cronologia
    hands_history: List[HandResult] = field(default_factory=list)
    score_history: List[Dict[str, int]] = field(default_factory=list)
    
    # Metadati
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def get_player_hand(self, player_id: str) -> List[Card]:
        """Restituisce la mano del giocatore."""
        if player_id == self.player1_id:
            return self.player1_hand
        return self.player2_hand
    
    def get_player_score(self, player_id: str) -> int:
        """Restituisce il punteggio del giocatore."""
        if player_id == self.player1_id:
            return self.player1_score
        return self.player2_score
    
    def add_score(self, player_id: str, points: int):
        """Aggiunge punti al giocatore."""
        if player_id == self.player1_id:
            self.player1_score += points
        else:
            self.player2_score += points
        
        # Registra nella cronologia
        self.score_history.append({
            "hand": self.hand_number,
            "player1": self.player1_score,
            "player2": self.player2_score
        })
    
    def get_opponent(self, player_id: str) -> str:
        """Restituisce l'ID dell'avversario."""
        return self.player2_id if player_id == self.player1_id else self.player1_id
    
    def cards_remaining_in_deck(self) -> int:
        """Numero di carte rimanenti nel mazzo."""
        return len(self.deck)
    
    def is_endgame(self) -> bool:
        """True se siamo nelle ultime 3 mani (mazzo vuoto)."""
        return len(self.deck) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte lo stato in dizionario per logging/serializzazione."""
        return {
            "game_id": self.game_id,
            "trump_suit": self.trump_suit.value if self.trump_suit else None,
            "player1_score": self.player1_score,
            "player2_score": self.player2_score,
            "hand_number": self.hand_number,
            "is_game_over": self.is_game_over,
            "winner": self.winner,
            "hands_history": [
                {
                    "hand": h.hand_number,
                    "winner": h.winner,
                    "points": h.points_won,
                    "trump_used": h.trump_used
                }
                for h in self.hands_history
            ],
            "score_history": self.score_history
        }


class Deck:
    """Gestisce il mazzo di carte."""
    
    # Definizione carte standard della Briscola
    CARD_VALUES = [
        ("Asso", 11, 1),
        ("Tre", 10, 2),
        ("Re", 4, 3),
        ("Cavallo", 3, 4),
        ("Fante", 2, 5),
        ("7", 0, 6),
        ("6", 0, 7),
        ("5", 0, 8),
        ("4", 0, 9),
        ("2", 0, 10),
    ]
    
    @classmethod
    def create_deck(cls) -> List[Card]:
        """Crea un mazzo completo di 40 carte."""
        deck = []
        for suit in Suit:
            for rank, points, strength in cls.CARD_VALUES:
                deck.append(Card(
                    suit=suit,
                    rank=rank,
                    points=points,
                    strength=strength
                ))
        return deck
    
    @classmethod
    def shuffle(cls, deck: List[Card], seed: Optional[int] = None) -> List[Card]:
        """Mescola il mazzo."""
        if seed is not None:
            random.seed(seed)
        shuffled = deck.copy()
        random.shuffle(shuffled)
        return shuffled
    
    @classmethod
    def calculate_total_points(cls) -> int:
        """Calcola i punti totali nel mazzo."""
        return sum(points for _, points, _ in cls.CARD_VALUES) * 4  # 4 semi


class GameLogger:
    """Logger per la cronologia della partita."""
    
    def __init__(self, game_id: str):
        self.game_id = game_id
        self.events: List[Dict[str, Any]] = []
    
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Registra un evento."""
        self.events.append({
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": data
        })
    
    def log_hand_start(self, hand_number: int, first_player: str):
        self.log_event("hand_start", {
            "hand_number": hand_number,
            "first_player": first_player
        })
    
    def log_card_played(self, player: str, card: Card, is_first: bool):
        self.log_event("card_played", {
            "player": player,
            "card": str(card),
            "suit": card.suit.value,
            "rank": card.rank,
            "points": card.points,
            "is_first": is_first
        })
    
    def log_hand_result(self, result: HandResult):
        self.log_event("hand_result", {
            "hand_number": result.hand_number,
            "winner": result.winner,
            "points_won": result.points_won,
            "trump_used": result.trump_used
        })
    
    def log_game_end(self, state: GameState):
        self.log_event("game_end", {
            "winner": state.winner,
            "player1_score": state.player1_score,
            "player2_score": state.player2_score,
            "total_hands": state.hand_number
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Restituisce un riepilogo della partita."""
        return {
            "game_id": self.game_id,
            "total_events": len(self.events),
            "events": self.events
        }

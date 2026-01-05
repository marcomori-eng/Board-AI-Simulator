"""
Dynamic Game Engine
====================
Motore di gioco dinamico che interpreta le regole da file YAML.
Funziona con qualsiasi gioco definito nel formato standard.
"""

from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
import random
import yaml
import uuid


# ============================================
# COMPONENTI DINAMICI
# ============================================

@dataclass
class DynamicCard:
    """Carta generica definita da YAML."""
    id: str
    suit: str
    rank: str
    points: int
    strength: int
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self):
        return f"{self.rank} di {self.suit}"
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if not isinstance(other, DynamicCard):
            return False
        return self.id == other.id


@dataclass
class DynamicDeck:
    """Mazzo dinamico costruito da definizione YAML."""
    cards: List[DynamicCard] = field(default_factory=list)
    total_points: int = 0
    
    @classmethod
    def from_yaml(cls, deck_config: Dict[str, Any]) -> 'DynamicDeck':
        """Costruisce un mazzo dalla configurazione YAML."""
        cards = []
        total_points = 0
        
        suits = deck_config.get('suits', [])
        card_values = deck_config.get('card_values', [])
        
        for suit in suits:
            suit_id = suit.get('id', suit.get('name', '').lower())
            suit_name = suit.get('name', suit_id)
            
            for cv in card_values:
                card_id = f"{cv['rank']}_{suit_id}"
                card = DynamicCard(
                    id=card_id,
                    suit=suit_name,
                    rank=cv['rank'],
                    points=cv.get('points', 0),
                    strength=cv.get('strength', 0)
                )
                cards.append(card)
                total_points += cv.get('points', 0)
        
        return cls(cards=cards, total_points=total_points)
    
    def shuffle(self, seed: Optional[int] = None) -> List[DynamicCard]:
        """Restituisce una copia mescolata del mazzo."""
        if seed is not None:
            random.seed(seed)
        shuffled = self.cards.copy()
        random.shuffle(shuffled)
        return shuffled


@dataclass
class DynamicGameState:
    """Stato di gioco dinamico."""
    game_id: str
    game_name: str
    
    # Configurazione
    trump_suit: Optional[str] = None
    trump_card: Optional[DynamicCard] = None
    
    # Giocatori
    players: List[str] = field(default_factory=list)
    player_hands: Dict[str, List[DynamicCard]] = field(default_factory=dict)
    player_scores: Dict[str, int] = field(default_factory=dict)
    player_won_cards: Dict[str, List[DynamicCard]] = field(default_factory=dict)
    
    # Mazzo
    deck: List[DynamicCard] = field(default_factory=list)
    discard_pile: List[DynamicCard] = field(default_factory=list)
    
    # Stato
    current_player_idx: int = 0
    hand_number: int = 0
    phase: str = "setup"
    is_game_over: bool = False
    winner: Optional[str] = None
    
    # Cronologia
    action_log: List[Dict[str, Any]] = field(default_factory=list)
    score_history: List[Dict[str, int]] = field(default_factory=list)
    
    # Metadati
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    rules_config: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def current_player(self) -> str:
        return self.players[self.current_player_idx]
    
    def get_opponent(self, player: str) -> str:
        """Per giochi a 2 giocatori."""
        idx = self.players.index(player)
        return self.players[(idx + 1) % len(self.players)]
    
    def next_player(self):
        """Passa al prossimo giocatore."""
        self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
    
    def set_current_player(self, player: str):
        """Imposta il giocatore corrente."""
        self.current_player_idx = self.players.index(player)
    
    def add_score(self, player: str, points: int):
        """Aggiunge punti a un giocatore."""
        self.player_scores[player] = self.player_scores.get(player, 0) + points
        self.score_history.append({
            "hand": self.hand_number,
            **{p: self.player_scores.get(p, 0) for p in self.players}
        })
    
    def log_action(self, action_type: str, data: Dict[str, Any]):
        """Registra un'azione."""
        self.action_log.append({
            "timestamp": datetime.now().isoformat(),
            "hand": self.hand_number,
            "type": action_type,
            "data": data
        })
    
    def is_deck_empty(self) -> bool:
        return len(self.deck) == 0
    
    def cards_in_hand(self, player: str) -> int:
        return len(self.player_hands.get(player, []))


# ============================================
# REGOLE DINAMICHE
# ============================================

class DynamicRules:
    """Interpreta e applica le regole dal file YAML."""
    
    def __init__(self, rules_path: Path):
        with open(rules_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.game_name = self.config.get('game', {}).get('name', 'Unknown Game')
        self.game_type = self.config.get('game', {}).get('type', 'card_game')
        
        # Carica configurazione giocatori
        self.min_players = self.config.get('players', {}).get('min', 2)
        self.max_players = self.config.get('players', {}).get('max', 2)
        
        # Carica componenti
        self.deck_config = self.config.get('components', {}).get('deck', {})
        
        # Carica setup
        self.setup_config = self.config.get('setup', {})
        
        # Carica gameplay
        self.gameplay_config = self.config.get('gameplay', {})
        
        # Carica condizioni vittoria
        self.victory_config = self.config.get('victory_conditions', {})
        
        # Carica glossario per interpretazione
        self.glossary = {
            item['term']: item['definition'] 
            for item in self.config.get('glossary', [])
        }
    
    def get_cards_per_player(self) -> int:
        """Numero di carte iniziali per giocatore."""
        for step in self.setup_config.get('steps', []):
            if step.get('action') == 'deal_cards':
                params = step.get('parameters', {})
                return params.get('cards_per_player', 3)
        return 3
    
    def has_trump(self) -> bool:
        """Verifica se il gioco ha briscola."""
        for step in self.setup_config.get('steps', []):
            if step.get('action') == 'reveal_trump':
                return True
        return False
    
    def get_turn_order(self) -> str:
        """Ordine dei turni."""
        return self.gameplay_config.get('turn_order', 'orario')
    
    def get_victory_threshold(self) -> int:
        """Soglia punti per vincere."""
        single = self.victory_config.get('single_game', {})
        return single.get('threshold', 61)
    
    def get_trick_winner_rules(self) -> List[Dict[str, Any]]:
        """Regole per determinare chi vince la mano."""
        return self.gameplay_config.get('trick_winner_rules', [])
    
    def must_follow_suit(self) -> bool:
        """Se bisogna rispondere al seme."""
        # Cerca nelle regole se c'è obbligo di rispondere al seme
        for phase in self.gameplay_config.get('phases', []):
            for step in phase.get('steps', []):
                rules = step.get('rules', [])
                for rule in rules:
                    if "non c'è obbligo di rispondere" in rule.lower():
                        return False
                    if "obbligo di rispondere" in rule.lower():
                        return True
        return False  # Default: no obbligo
    
    def get_draw_after_trick(self) -> bool:
        """Se si pesca dopo ogni mano."""
        for phase in self.gameplay_config.get('phases', []):
            for step in phase.get('steps', []):
                if step.get('action') == 'draw_cards':
                    return True
        return False
    
    def get_end_game_trigger(self) -> str:
        """Condizione per fine partita."""
        trigger = self.config.get('end_game', {}).get('trigger', {})
        return trigger.get('condition', 'deck_empty')


# ============================================
# ENGINE DINAMICO
# ============================================

class DynamicGameEngine:
    """Motore di gioco che si adatta a qualsiasi gioco definito in YAML."""
    
    def __init__(self, rules_path: Path):
        self.rules = DynamicRules(rules_path)
        self.deck_template = DynamicDeck.from_yaml(self.rules.deck_config)
    
    def create_game(
        self,
        player_ids: List[str],
        seed: Optional[int] = None
    ) -> DynamicGameState:
        """Crea una nuova partita."""
        
        game_id = str(uuid.uuid4())[:8]
        
        # Crea e mescola il mazzo
        deck = self.deck_template.shuffle(seed)
        
        # Inizializza stato
        state = DynamicGameState(
            game_id=game_id,
            game_name=self.rules.game_name,
            players=player_ids,
            deck=deck,
            rules_config=self.rules.config,
            start_time=datetime.now()
        )
        
        # Inizializza punteggi e mani
        for player in player_ids:
            state.player_scores[player] = 0
            state.player_hands[player] = []
            state.player_won_cards[player] = []
        
        # Esegui setup
        self._execute_setup(state)
        
        state.phase = "play"
        return state
    
    def _execute_setup(self, state: DynamicGameState):
        """Esegue i passi di setup definiti nel YAML."""
        
        for step in self.rules.setup_config.get('steps', []):
            action = step.get('action', '')
            
            if action == 'shuffle_deck':
                # Già fatto in create_game
                state.log_action("shuffle_deck", {"message": "Mazzo mescolato"})
            
            elif action == 'deal_cards':
                cards_per_player = step.get('parameters', {}).get('cards_per_player', 3)
                for _ in range(cards_per_player):
                    for player in state.players:
                        if state.deck:
                            card = state.deck.pop()
                            state.player_hands[player].append(card)
                
                state.log_action("deal_cards", {
                    "cards_per_player": cards_per_player,
                    "hands": {p: [str(c) for c in h] for p, h in state.player_hands.items()}
                })
            
            elif action == 'reveal_trump':
                if state.deck:
                    # La briscola è la prima carta del mazzo rimanente
                    state.trump_card = state.deck[0]
                    state.trump_suit = state.trump_card.suit
                    
                    state.log_action("reveal_trump", {
                        "trump_card": str(state.trump_card),
                        "trump_suit": state.trump_suit
                    })
            
            elif action == 'place_deck':
                state.log_action("place_deck", {"cards_remaining": len(state.deck)})
    
    def play_hand(
        self,
        state: DynamicGameState,
        player_cards: Dict[str, DynamicCard]
    ) -> Dict[str, Any]:
        """
        Gioca una mano con le carte scelte dai giocatori.
        
        Args:
            state: Stato attuale del gioco
            player_cards: Dizionario {player_id: carta_giocata}
        
        Returns:
            Risultato della mano
        """
        state.hand_number += 1
        
        # Log inizio mano
        state.log_action("hand_start", {
            "hand_number": state.hand_number,
            "first_player": state.current_player
        })
        
        # Rimuovi carte dalle mani e registra
        cards_played = []
        first_player = state.current_player
        first_card = player_cards[first_player]
        
        for player in state.players:
            card = player_cards[player]
            state.player_hands[player].remove(card)
            cards_played.append((player, card))
            
            state.log_action("card_played", {
                "player": player,
                "card": str(card),
                "suit": card.suit,
                "rank": card.rank,
                "points": card.points,
                "is_first": player == first_player
            })
        
        # Determina vincitore
        winner = self._determine_trick_winner(
            cards_played, first_card.suit, state.trump_suit
        )
        
        # Calcola punti
        points_won = sum(card.points for _, card in cards_played)
        
        # Aggiorna stato
        state.add_score(winner, points_won)
        for _, card in cards_played:
            state.player_won_cards[winner].append(card)
        
        # Registra risultato
        trump_used = any(card.suit == state.trump_suit for _, card in cards_played)
        
        state.log_action("hand_result", {
            "hand_number": state.hand_number,
            "winner": winner,
            "points_won": points_won,
            "trump_used": trump_used
        })
        
        # Il vincitore gioca per primo
        state.set_current_player(winner)
        
        # Pesca carte se necessario
        if self.rules.get_draw_after_trick() and not state.is_deck_empty():
            self._draw_cards(state, winner)
        
        # Controlla fine partita
        self._check_game_end(state)
        
        return {
            "hand_number": state.hand_number,
            "winner": winner,
            "points_won": points_won,
            "trump_used": trump_used,
            "cards_played": {p: str(c) for p, c in cards_played}
        }
    
    def _determine_trick_winner(
        self,
        cards_played: List[tuple],
        lead_suit: str,
        trump_suit: Optional[str]
    ) -> str:
        """Determina il vincitore della mano secondo le regole."""
        
        first_player, first_card = cards_played[0]
        best_player = first_player
        best_card = first_card
        
        for player, card in cards_played[1:]:
            # Regole di confronto
            if trump_suit:
                card_is_trump = card.suit == trump_suit
                best_is_trump = best_card.suit == trump_suit
                
                if card_is_trump and not best_is_trump:
                    # La briscola batte tutto
                    best_player, best_card = player, card
                elif card_is_trump and best_is_trump:
                    # Entrambe briscole: vince la più forte
                    if card.strength < best_card.strength:
                        best_player, best_card = player, card
                elif not card_is_trump and not best_is_trump:
                    # Nessuna briscola
                    if card.suit == lead_suit and best_card.suit == lead_suit:
                        # Stesso seme del primo: vince la più forte
                        if card.strength < best_card.strength:
                            best_player, best_card = player, card
                    elif card.suit == lead_suit:
                        # Solo questa è del seme iniziale
                        best_player, best_card = player, card
            else:
                # Senza briscola: vince il seme iniziale più forte
                if card.suit == lead_suit and best_card.suit == lead_suit:
                    if card.strength < best_card.strength:
                        best_player, best_card = player, card
                elif card.suit == lead_suit:
                    best_player, best_card = player, card
        
        return best_player
    
    def _draw_cards(self, state: DynamicGameState, hand_winner: str):
        """Fa pescare carte ai giocatori."""
        
        # Chi ha vinto pesca per primo
        draw_order = [hand_winner] + [p for p in state.players if p != hand_winner]
        
        for player in draw_order:
            if state.deck:
                card = state.deck.pop()
                state.player_hands[player].append(card)
                
                state.log_action("card_drawn", {
                    "player": player,
                    "card": str(card),
                    "cards_remaining": len(state.deck)
                })
    
    def _check_game_end(self, state: DynamicGameState):
        """Controlla se la partita è finita."""
        
        trigger = self.rules.get_end_game_trigger()
        
        if trigger == 'deck_empty':
            # Partita finisce quando mazzo vuoto E mani vuote
            all_hands_empty = all(
                len(state.player_hands[p]) == 0 
                for p in state.players
            )
            if state.is_deck_empty() and all_hands_empty:
                state.is_game_over = True
        
        if state.is_game_over:
            state.end_time = datetime.now()
            state.winner = self._determine_winner(state)
            
            state.log_action("game_end", {
                "winner": state.winner,
                "scores": state.player_scores.copy(),
                "total_hands": state.hand_number
            })
    
    def _determine_winner(self, state: DynamicGameState) -> Optional[str]:
        """Determina il vincitore secondo le regole."""
        
        threshold = self.rules.get_victory_threshold()
        
        scores = state.player_scores
        max_score = max(scores.values())
        
        # Chi supera la soglia
        winners = [p for p, s in scores.items() if s >= threshold]
        
        if len(winners) == 1:
            return winners[0]
        elif len(winners) > 1:
            # Pareggio possibile
            return None
        else:
            # Nessuno ha superato la soglia - vince chi ha di più
            for player, score in scores.items():
                if score == max_score:
                    # Controlla pareggio
                    if list(scores.values()).count(max_score) > 1:
                        return None
                    return player
        
        return None
    
    def get_valid_actions(self, state: DynamicGameState, player: str) -> List[DynamicCard]:
        """Restituisce le azioni valide per un giocatore."""
        
        hand = state.player_hands.get(player, [])
        
        if not self.rules.must_follow_suit():
            # Può giocare qualsiasi carta
            return hand.copy()
        
        # TODO: Implementare logica per giochi con obbligo di risposta
        return hand.copy()
    
    def get_game_info(self) -> Dict[str, Any]:
        """Restituisce informazioni sul gioco caricato."""
        return {
            "name": self.rules.game_name,
            "type": self.rules.game_type,
            "players": f"{self.rules.min_players}-{self.rules.max_players}",
            "has_trump": self.rules.has_trump(),
            "victory_threshold": self.rules.get_victory_threshold(),
            "total_cards": len(self.deck_template.cards),
            "total_points": self.deck_template.total_points
        }

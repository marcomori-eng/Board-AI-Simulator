"""
Agent System
============
Implementa gli agenti AI che giocano a Briscola con diversi profili comportamentali.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
import random
import yaml
from pathlib import Path

from .game_state import Card, Suit, GameState


@dataclass
class AgentProfile:
    """Profilo comportamentale dell'agente."""
    name: str
    description: str
    
    # Tratti
    risk_tolerance: float = 0.5
    trump_conservation: float = 0.5
    memory_strength: float = 0.5
    bluff_tendency: float = 0.2
    point_greed: float = 0.5
    defensive_play: float = 0.5
    
    # Pesi decisionali
    play_high_card: float = 0.5
    play_trump: float = 0.5
    sacrifice_points: float = 0.5
    wait_for_opportunity: float = 0.5
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentProfile':
        """Crea un profilo da dizionario."""
        traits = data.get('traits', {})
        weights = data.get('decision_weights', {})
        
        return cls(
            name=data.get('name', 'Unknown'),
            description=data.get('description', ''),
            risk_tolerance=traits.get('risk_tolerance', 0.5),
            trump_conservation=traits.get('trump_conservation', 0.5),
            memory_strength=traits.get('memory_strength', 0.5),
            bluff_tendency=traits.get('bluff_tendency', 0.2),
            point_greed=traits.get('point_greed', 0.5),
            defensive_play=traits.get('defensive_play', 0.5),
            play_high_card=weights.get('play_high_card', 0.5),
            play_trump=weights.get('play_trump', 0.5),
            sacrifice_points=weights.get('sacrifice_points', 0.5),
            wait_for_opportunity=weights.get('wait_for_opportunity', 0.5)
        )


class AgentMemory:
    """Memoria dell'agente per le carte giocate."""
    
    def __init__(self, memory_strength: float):
        self.memory_strength = memory_strength
        self.cards_played: List[Card] = []
        self.trumps_played: List[Card] = []
        self.opponent_cards_seen: List[Card] = []
        self.trump_suit: Optional[Suit] = None
    
    def remember_card(self, card: Card, played_by_opponent: bool = False):
        """Memorizza una carta giocata."""
        # Probabilità di ricordare basata sulla forza della memoria
        if random.random() < self.memory_strength:
            self.cards_played.append(card)
            if played_by_opponent:
                self.opponent_cards_seen.append(card)
            if self.trump_suit and card.suit == self.trump_suit:
                self.trumps_played.append(card)
    
    def set_trump_suit(self, suit: Suit):
        """Imposta il seme di briscola."""
        self.trump_suit = suit
    
    def get_remaining_trumps_estimate(self) -> int:
        """Stima quante briscole sono ancora in gioco."""
        total_trumps = 10
        remembered = len([c for c in self.trumps_played])
        # Aggiunge incertezza basata sulla memoria
        uncertainty = int((1 - self.memory_strength) * 3)
        return max(0, total_trumps - remembered + random.randint(-uncertainty, uncertainty))
    
    def has_seen_high_cards(self, suit: Suit) -> bool:
        """Verifica se ha visto carte alte di un seme."""
        high_ranks = ["Asso", "Tre", "Re"]
        return any(
            c.suit == suit and c.rank in high_ranks 
            for c in self.cards_played 
            if random.random() < self.memory_strength
        )
    
    def reset(self):
        """Resetta la memoria per una nuova partita."""
        self.cards_played = []
        self.trumps_played = []
        self.opponent_cards_seen = []


class Agent:
    """Agente AI che gioca a Briscola."""
    
    def __init__(self, player_id: str, profile: AgentProfile):
        self.player_id = player_id
        self.profile = profile
        self.memory = AgentMemory(profile.memory_strength)
        self.random_gen = random.Random()
    
    def set_seed(self, seed: int):
        """Imposta il seed per riproducibilità."""
        self.random_gen.seed(seed)
    
    def reset(self):
        """Resetta l'agente per una nuova partita."""
        self.memory.reset()
    
    def choose_card(
        self, 
        hand: List[Card], 
        game_state: GameState,
        opponent_card: Optional[Card] = None
    ) -> Card:
        """
        Sceglie quale carta giocare.
        
        Args:
            hand: Carte in mano all'agente
            game_state: Stato attuale del gioco
            opponent_card: Carta giocata dall'avversario (se non siamo primi)
        
        Returns:
            La carta scelta da giocare
        """
        if not hand:
            raise ValueError("Mano vuota, impossibile giocare")
        
        if len(hand) == 1:
            return hand[0]
        
        # Profilo random: scelta casuale
        if self.profile.name == "Casuale":
            return self.random_gen.choice(hand)
        
        # Imposta il seme di briscola nella memoria
        self.memory.set_trump_suit(game_state.trump_suit)
        
        # Dividi le carte per categoria
        trumps = [c for c in hand if c.suit == game_state.trump_suit]
        non_trumps = [c for c in hand if c.suit != game_state.trump_suit]
        high_cards = [c for c in hand if c.points >= 10]  # Assi e Tre
        low_cards = [c for c in hand if c.points == 0]
        
        # CASO 1: Siamo il primo giocatore
        if opponent_card is None:
            return self._choose_as_first_player(
                hand, trumps, non_trumps, high_cards, low_cards, game_state
            )
        
        # CASO 2: Rispondiamo all'avversario
        return self._choose_as_second_player(
            hand, trumps, non_trumps, high_cards, low_cards, 
            opponent_card, game_state
        )
    
    def _choose_as_first_player(
        self, 
        hand: List[Card],
        trumps: List[Card],
        non_trumps: List[Card],
        high_cards: List[Card],
        low_cards: List[Card],
        game_state: GameState
    ) -> Card:
        """Logica di scelta quando si è il primo a giocare."""
        
        # Nella fase finale (mazzo vuoto), strategia più aggressiva
        if game_state.is_endgame():
            return self._endgame_first_player(hand, trumps, high_cards, game_state)
        
        # Tendenza a giocare liscio per non sprecare carte
        if low_cards and self.random_gen.random() > self.profile.point_greed:
            # Preferisci carte non briscola basse
            non_trump_low = [c for c in low_cards if c not in trumps]
            if non_trump_low:
                return self.random_gen.choice(non_trump_low)
            return self.random_gen.choice(low_cards)
        
        # Strategia aggressiva: gioca alto
        if self.random_gen.random() < self.profile.risk_tolerance:
            if high_cards:
                non_trump_high = [c for c in high_cards if c not in trumps]
                if non_trump_high:
                    return self.random_gen.choice(non_trump_high)
        
        # Default: carta media
        sorted_hand = sorted(non_trumps or hand, key=lambda c: c.strength)
        mid_index = len(sorted_hand) // 2
        return sorted_hand[mid_index]
    
    def _choose_as_second_player(
        self,
        hand: List[Card],
        trumps: List[Card],
        non_trumps: List[Card],
        high_cards: List[Card],
        low_cards: List[Card],
        opponent_card: Card,
        game_state: GameState
    ) -> Card:
        """Logica di scelta quando si risponde all'avversario."""
        
        points_at_stake = opponent_card.points
        is_opponent_trump = opponent_card.suit == game_state.trump_suit
        
        # Carte dello stesso seme che possono battere l'avversario
        same_suit_beaters = [
            c for c in hand 
            if c.suit == opponent_card.suit and c.strength < opponent_card.strength
        ]
        
        # ===== CASO: Avversario gioca briscola =====
        if is_opponent_trump:
            # Possiamo battere con briscola più alta?
            trump_beaters = [c for c in trumps if c.strength < opponent_card.strength]
            
            if trump_beaters:
                # Ci sono molti punti in gioco?
                if points_at_stake >= 10 or self.random_gen.random() < self.profile.risk_tolerance:
                    # Usa la briscola più bassa che batte
                    return max(trump_beaters, key=lambda c: c.strength)
            
            # Non possiamo battere: gioca il liscio più basso
            if low_cards:
                return min(low_cards, key=lambda c: c.strength)
            return min(hand, key=lambda c: c.points)
        
        # ===== CASO: Avversario NON gioca briscola =====
        
        # Possiamo battere con lo stesso seme?
        if same_suit_beaters:
            if points_at_stake >= 3 or self.random_gen.random() < self.profile.point_greed:
                return max(same_suit_beaters, key=lambda c: c.strength)
        
        # Possiamo usare una briscola?
        if trumps and not same_suit_beaters:
            # Valutazione se vale la pena usare briscola
            should_use_trump = (
                points_at_stake >= 10 or  # Molti punti
                (points_at_stake >= 3 and self.random_gen.random() < self.profile.risk_tolerance) or
                game_state.is_endgame()  # Fase finale
            )
            
            # Ma considera la conservazione delle briscole
            if should_use_trump and self.random_gen.random() > self.profile.trump_conservation:
                # Usa la briscola più debole
                return max(trumps, key=lambda c: c.strength)
        
        # Non possiamo/vogliamo vincere: sacrifica il liscio più basso
        if low_cards:
            non_trump_low = [c for c in low_cards if c not in trumps]
            if non_trump_low:
                return min(non_trump_low, key=lambda c: c.strength)
        
        # Ultima risorsa: carta con meno punti
        return min(hand, key=lambda c: (c.points, -c.strength))
    
    def _endgame_first_player(
        self,
        hand: List[Card],
        trumps: List[Card],
        high_cards: List[Card],
        game_state: GameState
    ) -> Card:
        """Strategia aggressiva per le ultime mani."""
        
        # Calcola se siamo in vantaggio
        my_score = game_state.get_player_score(self.player_id)
        opponent_score = game_state.get_player_score(game_state.get_opponent(self.player_id))
        
        # Se vinciamo, gioca conservativo
        if my_score > 60:
            low_cards = [c for c in hand if c.points == 0]
            if low_cards:
                return self.random_gen.choice(low_cards)
        
        # Se perdiamo, sii aggressivo
        if opponent_score > my_score:
            if trumps:
                return max(trumps, key=lambda c: c.points)
            if high_cards:
                return max(high_cards, key=lambda c: c.points)
        
        # Default
        return max(hand, key=lambda c: c.points)
    
    def observe_card(self, card: Card, played_by_opponent: bool):
        """Osserva una carta giocata e la memorizza."""
        self.memory.remember_card(card, played_by_opponent)


class AgentFactory:
    """Factory per creare agenti con profili specifici."""
    
    def __init__(self, profiles_path: Optional[Path] = None):
        self.profiles: Dict[str, AgentProfile] = {}
        
        if profiles_path and profiles_path.exists():
            self._load_profiles(profiles_path)
        else:
            self._create_default_profiles()
    
    def _load_profiles(self, path: Path):
        """Carica i profili dal file YAML."""
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        for profile_id, profile_data in data.get('profiles', {}).items():
            self.profiles[profile_id] = AgentProfile.from_dict(profile_data)
    
    def _create_default_profiles(self):
        """Crea profili di default se nessun file è fornito."""
        self.profiles = {
            "balanced": AgentProfile(
                name="Bilanciato",
                description="Strategia equilibrata"
            ),
            "aggressive": AgentProfile(
                name="Aggressivo",
                description="Gioca per vincere ogni mano",
                risk_tolerance=0.9,
                trump_conservation=0.2,
                point_greed=0.9
            ),
            "conservative": AgentProfile(
                name="Conservativo",
                description="Risparmia briscole",
                risk_tolerance=0.3,
                trump_conservation=0.9,
                defensive_play=0.8
            ),
            "random": AgentProfile(
                name="Casuale",
                description="Gioca a caso"
            )
        }
    
    def create_agent(self, player_id: str, profile_name: str) -> Agent:
        """Crea un agente con il profilo specificato."""
        if profile_name not in self.profiles:
            raise ValueError(f"Profilo '{profile_name}' non trovato. "
                           f"Disponibili: {list(self.profiles.keys())}")
        
        return Agent(player_id, self.profiles[profile_name])
    
    def list_profiles(self) -> List[str]:
        """Restituisce la lista dei profili disponibili."""
        return list(self.profiles.keys())

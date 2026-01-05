"""
Dynamic Agent
=============
Agente AI dinamico che legge le regole dal YAML e adatta la strategia.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import random
import yaml

from .dynamic_engine import DynamicCard, DynamicGameState, DynamicRules


@dataclass
class DynamicAgentProfile:
    """Profilo comportamentale dell'agente dinamico."""
    name: str
    description: str = ""
    
    # Tratti generici che si adattano a qualsiasi gioco
    risk_tolerance: float = 0.5      # Quanto rischia
    resource_conservation: float = 0.5  # Quanto conserva risorse (briscole, carte forti)
    memory_strength: float = 0.5     # Quanto ricorda le carte giocate
    aggression: float = 0.5          # Quanto è aggressivo
    point_focus: float = 0.5         # Quanto si concentra sui punti
    defensive_play: float = 0.5      # Quanto gioca in difesa
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DynamicAgentProfile':
        traits = data.get('traits', {})
        return cls(
            name=data.get('name', 'Unknown'),
            description=data.get('description', ''),
            risk_tolerance=traits.get('risk_tolerance', 0.5),
            resource_conservation=traits.get('trump_conservation', traits.get('resource_conservation', 0.5)),
            memory_strength=traits.get('memory_strength', 0.5),
            aggression=traits.get('point_greed', traits.get('aggression', 0.5)),
            point_focus=traits.get('point_greed', traits.get('point_focus', 0.5)),
            defensive_play=traits.get('defensive_play', 0.5)
        )


class DynamicAgentMemory:
    """Memoria dell'agente per le carte giocate."""
    
    def __init__(self, memory_strength: float):
        self.memory_strength = memory_strength
        self.cards_seen: List[DynamicCard] = []
        self.trump_cards_seen: List[DynamicCard] = []
        self.opponent_cards: List[DynamicCard] = []
        self.current_trump_suit: Optional[str] = None
    
    def observe_card(self, card: DynamicCard, played_by_opponent: bool = False):
        """Osserva una carta giocata."""
        if random.random() < self.memory_strength:
            self.cards_seen.append(card)
            if played_by_opponent:
                self.opponent_cards.append(card)
            if self.current_trump_suit and card.suit == self.current_trump_suit:
                self.trump_cards_seen.append(card)
    
    def set_trump(self, trump_suit: str):
        self.current_trump_suit = trump_suit
    
    def reset(self):
        self.cards_seen = []
        self.trump_cards_seen = []
        self.opponent_cards = []
        self.current_trump_suit = None


class DynamicAgent:
    """
    Agente AI dinamico che si adatta a qualsiasi gioco.
    Legge le regole dal YAML e decide le azioni di conseguenza.
    """
    
    def __init__(
        self, 
        player_id: str, 
        profile: DynamicAgentProfile,
        rules: Optional[DynamicRules] = None
    ):
        self.player_id = player_id
        self.profile = profile
        self.rules = rules
        self.memory = DynamicAgentMemory(profile.memory_strength)
        self.rng = random.Random()
    
    def set_rules(self, rules: DynamicRules):
        """Imposta le regole del gioco."""
        self.rules = rules
        self._analyze_rules()
    
    def _analyze_rules(self):
        """Analizza le regole per capire le strategie ottimali."""
        if not self.rules:
            return
        
        # Capisce se c'è briscola
        self.has_trump = self.rules.has_trump()
        
        # Capisce se bisogna rispondere al seme
        self.must_follow_suit = self.rules.must_follow_suit()
        
        # Soglia vittoria
        self.victory_threshold = self.rules.get_victory_threshold()
        
        # Legge strategie consigliate dal glossario
        self.strategies = []
        strategy_section = self.rules.config.get('strategy', {})
        for tip in strategy_section.get('tips', []):
            self.strategies.append({
                'category': tip.get('category', ''),
                'description': tip.get('description', '')
            })
    
    def set_seed(self, seed: int):
        self.rng.seed(seed)
    
    def reset(self):
        self.memory.reset()
    
    def choose_card(
        self,
        hand: List[DynamicCard],
        state: DynamicGameState,
        opponent_card: Optional[DynamicCard] = None
    ) -> DynamicCard:
        """
        Sceglie quale carta giocare basandosi sulle regole del gioco.
        """
        if not hand:
            raise ValueError("Mano vuota")
        
        if len(hand) == 1:
            return hand[0]
        
        # Imposta la briscola nella memoria
        if state.trump_suit:
            self.memory.set_trump(state.trump_suit)
        
        # Profilo random: scelta casuale
        if self.profile.name.lower() == "casuale" or self.profile.name.lower() == "random":
            return self.rng.choice(hand)
        
        # Categorizza le carte
        trump_cards = [c for c in hand if state.trump_suit and c.suit == state.trump_suit]
        non_trump = [c for c in hand if not state.trump_suit or c.suit != state.trump_suit]
        high_value = [c for c in hand if c.points >= 10]
        low_value = [c for c in hand if c.points == 0]
        
        # CASO 1: Siamo il primo a giocare
        if opponent_card is None:
            return self._choose_as_leader(
                hand, trump_cards, non_trump, high_value, low_value, state
            )
        
        # CASO 2: Rispondiamo all'avversario
        return self._choose_as_follower(
            hand, trump_cards, non_trump, high_value, low_value,
            opponent_card, state
        )
    
    def _choose_as_leader(
        self,
        hand: List[DynamicCard],
        trump_cards: List[DynamicCard],
        non_trump: List[DynamicCard],
        high_value: List[DynamicCard],
        low_value: List[DynamicCard],
        state: DynamicGameState
    ) -> DynamicCard:
        """Logica quando si gioca per primi."""
        
        # Fine partita: più aggressivi
        if state.is_deck_empty():
            return self._endgame_leader(hand, trump_cards, high_value, state)
        
        # Tendenza a giocare basso per non sprecare
        if low_value and self.rng.random() > self.profile.point_focus:
            # Preferisce non-briscola basse
            low_non_trump = [c for c in low_value if c not in trump_cards]
            if low_non_trump:
                return self.rng.choice(low_non_trump)
            return self.rng.choice(low_value)
        
        # Strategia aggressiva
        if self.rng.random() < self.profile.risk_tolerance:
            if high_value:
                high_non_trump = [c for c in high_value if c not in trump_cards]
                if high_non_trump:
                    return self.rng.choice(high_non_trump)
        
        # Default: carta media non briscola
        sorted_hand = sorted(non_trump or hand, key=lambda c: c.strength)
        mid_idx = len(sorted_hand) // 2
        return sorted_hand[mid_idx]
    
    def _choose_as_follower(
        self,
        hand: List[DynamicCard],
        trump_cards: List[DynamicCard],
        non_trump: List[DynamicCard],
        high_value: List[DynamicCard],
        low_value: List[DynamicCard],
        opponent_card: DynamicCard,
        state: DynamicGameState
    ) -> DynamicCard:
        """Logica quando si risponde all'avversario."""
        
        points_at_stake = opponent_card.points
        is_opponent_trump = state.trump_suit and opponent_card.suit == state.trump_suit
        
        # Carte che possono battere l'avversario nello stesso seme
        same_suit_beaters = [
            c for c in hand
            if c.suit == opponent_card.suit and c.strength < opponent_card.strength
        ]
        
        # CASO: Avversario gioca briscola
        if is_opponent_trump:
            trump_beaters = [c for c in trump_cards if c.strength < opponent_card.strength]
            
            if trump_beaters:
                if points_at_stake >= 10 or self.rng.random() < self.profile.risk_tolerance:
                    return max(trump_beaters, key=lambda c: c.strength)
            
            if low_value:
                return min(low_value, key=lambda c: c.strength)
            return min(hand, key=lambda c: c.points)
        
        # CASO: Avversario NON gioca briscola
        
        # Possiamo battere con stesso seme?
        if same_suit_beaters:
            if points_at_stake >= 3 or self.rng.random() < self.profile.point_focus:
                return max(same_suit_beaters, key=lambda c: c.strength)
        
        # Usiamo briscola?
        if trump_cards and not same_suit_beaters:
            should_use_trump = (
                points_at_stake >= 10 or
                (points_at_stake >= 3 and self.rng.random() < self.profile.risk_tolerance) or
                state.is_deck_empty()
            )
            
            if should_use_trump and self.rng.random() > self.profile.resource_conservation:
                return max(trump_cards, key=lambda c: c.strength)
        
        # Scarta il liscio più basso
        if low_value:
            low_non_trump = [c for c in low_value if c not in trump_cards]
            if low_non_trump:
                return min(low_non_trump, key=lambda c: c.strength)
        
        return min(hand, key=lambda c: (c.points, -c.strength))
    
    def _endgame_leader(
        self,
        hand: List[DynamicCard],
        trump_cards: List[DynamicCard],
        high_value: List[DynamicCard],
        state: DynamicGameState
    ) -> DynamicCard:
        """Strategia fine partita."""
        
        my_score = state.player_scores.get(self.player_id, 0)
        opponent = state.get_opponent(self.player_id)
        opp_score = state.player_scores.get(opponent, 0)
        
        # Se vinciamo, gioca conservativo
        if my_score > self.victory_threshold - 1:
            low = [c for c in hand if c.points == 0]
            if low:
                return self.rng.choice(low)
        
        # Se perdiamo, sii aggressivo
        if opp_score > my_score:
            if trump_cards:
                return max(trump_cards, key=lambda c: c.points)
            if high_value:
                return max(high_value, key=lambda c: c.points)
        
        return max(hand, key=lambda c: c.points)
    
    def observe_card(self, card: DynamicCard, played_by_opponent: bool):
        """Osserva una carta giocata."""
        self.memory.observe_card(card, played_by_opponent)


class DynamicAgentFactory:
    """Factory per creare agenti dinamici."""
    
    def __init__(self, profiles_path: Optional[Path] = None):
        self.profiles: Dict[str, DynamicAgentProfile] = {}
        
        if profiles_path and profiles_path.exists():
            self._load_profiles(profiles_path)
        else:
            self._create_default_profiles()
    
    def _load_profiles(self, path: Path):
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        for profile_id, profile_data in data.get('profiles', {}).items():
            self.profiles[profile_id] = DynamicAgentProfile.from_dict(profile_data)
    
    def _create_default_profiles(self):
        self.profiles = {
            "balanced": DynamicAgentProfile(
                name="Bilanciato",
                description="Strategia equilibrata"
            ),
            "aggressive": DynamicAgentProfile(
                name="Aggressivo",
                description="Gioca per vincere ogni mano",
                risk_tolerance=0.9,
                resource_conservation=0.2,
                aggression=0.9,
                point_focus=0.9
            ),
            "conservative": DynamicAgentProfile(
                name="Conservativo",
                description="Risparmia risorse",
                risk_tolerance=0.3,
                resource_conservation=0.9,
                defensive_play=0.8
            ),
            "random": DynamicAgentProfile(
                name="Casuale",
                description="Gioca a caso"
            ),
            "expert": DynamicAgentProfile(
                name="Esperto",
                description="Memoria perfetta, decisioni ottimali",
                memory_strength=1.0,
                risk_tolerance=0.6,
                resource_conservation=0.7
            )
        }
    
    def create_agent(
        self, 
        player_id: str, 
        profile_name: str,
        rules: Optional[DynamicRules] = None
    ) -> DynamicAgent:
        """Crea un agente con il profilo specificato."""
        if profile_name not in self.profiles:
            raise ValueError(f"Profilo '{profile_name}' non trovato")
        
        agent = DynamicAgent(player_id, self.profiles[profile_name], rules)
        if rules:
            agent._analyze_rules()
        return agent
    
    def list_profiles(self) -> List[str]:
        return list(self.profiles.keys())

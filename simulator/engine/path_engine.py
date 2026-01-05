"""
Path Game Engine
================
Motore per giochi di percorso (es. Gioco dell'Oca) definiti in YAML.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import random
import uuid
import yaml

@dataclass
class PathGameState:
    game_id: str
    players: List[str]
    positions: Dict[str, int]
    hands: Dict[str, List[str]] # Carte
    status: Dict[str, Any] # Es. has_key, skip_turn
    turn_number: int = 0
    current_player_idx: int = 0
    is_game_over: bool = False
    winner: Optional[str] = None
    log: List[str] = field(default_factory=list)
    
    @property
    def current_player(self):
        return self.players[self.current_player_idx]

class PathEngine:
    def __init__(self, rules_path: str):
        with open(rules_path, 'r', encoding='utf-8') as f:
            self.rules = yaml.safe_load(f)
        
        self.board_config = self.rules.get('components', {}).get('board', {})
        self.max_space = self.board_config.get('length', 30)
        self.spaces = {s['id']: s for s in self.board_config.get('spaces', [])}
        
        # Carica carte
        self.deck_definitions = self.rules.get('components', {}).get('deck', {}).get('card_values', [])
        self.deck = []
        for card_def in self.deck_definitions:
            count = card_def.get('count', 1)
            for _ in range(count):
                self.deck.append(card_def)
                
    def create_game(self, players: List[str], seed=None) -> PathGameState:
        if seed: random.seed(seed)
        
        # Shuffle deck
        random.shuffle(self.deck)
        
        state = PathGameState(
            game_id=str(uuid.uuid4())[:8],
            players=players,
            positions={p: 1 for p in players},
            hands={p: [] for p in players},
            status={p: {} for p in players}
        )
        
        # Setup: deal cards
        for _ in range(2):
            for p in players:
                self._draw_card(state, p)
                
        return state

    def play_turn(self, state: PathGameState, actions: Dict=None):
        player = state.current_player
        
        # Check skip turn
        if state.status[player].get('skip_turn', 0) > 0:
            state.log.append(f"{player} salta il turno")
            state.status[player]['skip_turn'] -= 1
            self._next_turn(state)
            return

        # 1. Gioca carta (AI semplice: usa pozioni se averle)
        # TODO: Implementare uso carte intelligente
        
        # 2. Tira dado
        roll = random.randint(1, 6)
        state.log.append(f"{player} tira {roll}")
        
        # 3. Muovi
        start_pos = state.positions[player]
        # Regola esatta: rimbalzo
        target = start_pos + roll
        if target > self.max_space:
            excess = target - self.max_space
            target = self.max_space - excess
        
        state.positions[player] = target
        state.log.append(f"{player} muove a {target}")
        
        # 4. Effetti Casella (ricorsivo semplice)
        self._resolve_space(state, player, target)
        
        # Check vittoria
        if state.positions[player] == self.max_space:
            state.is_game_over = True
            state.winner = player
            return

        self._next_turn(state)

    def _resolve_space(self, state, player, pos_id):
        # Cerca definizione spazio (pos_id as string)
        space_def = self.spaces.get(str(pos_id))
        if not space_def: return
        
        effect = space_def.get('effect')
        if not effect: return
        
        # Interpreta effetti stringa
        state.log.append(f"Effetto casella {pos_id}: {effect}")
        
        if effect.startswith('move_to_'):
            dest = int(effect.split('_')[2])
            state.positions[player] = dest
            # Potenziale chain reaction? Per ora no per safe
        
        elif effect.startswith('back_'):
            bk = int(effect.split('_')[1])
            state.positions[player] = max(1, state.positions[player] - bk)
        
        elif effect == 'draw_card':
            self._draw_card(state, player)
            
        elif effect == 'skip_turn':
            state.status[player]['skip_turn'] = 1
            
        elif effect == 'get_key':
            # Ruba chiave agli altri
            for p in state.players:
                state.status[p]['has_key'] = False
            state.status[player]['has_key'] = True
            state.log.append(f"{player} prende la Chiave d'Oro!")
            
        elif effect == 'check_key_or_6':
            # Logica blocco
            has_key = state.status[player].get('has_key', False)
            # Se non ha chiave e non ha fatto 6 (roll perso qui...), torna indietro?
            # Regola complessa: "ti serve chiave o 6 per passare".
            # Semplificazione: se sei atterrato qui senza chiave, torni indietro di 1
            if not has_key: 
                state.positions[player] -= 1
                state.log.append("Portone chiuso! Indietro.")

    def _draw_card(self, state, player):
        if self.deck:
            card = self.deck.pop(0) # Pesca
            state.hands[player].append(card)
            # Ricicla mazzo se vuoto?
            
    def _next_turn(self, state):
        state.current_player_idx = (state.current_player_idx + 1) % len(state.players)
        state.turn_number += 1

    def get_game_info(self) -> Dict[str, Any]:
        return {
            "name": self.rules['game']['name'],
            "type": "path_game",
            "players": f"{self.rules['players']['min']}-{self.rules['players']['max']}",
            "victory_threshold": "Arrivo",
            "total_cards": len(self.deck_definitions),
            "has_trump": False       
        }

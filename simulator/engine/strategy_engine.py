"""
Dynamic Strategy Engine
=======================
Motore per giochi da tavolo strategici (es. Risiko) definiti in YAML.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import random
import uuid
import yaml

@dataclass
class Territory:
    id: str
    name: str
    owner: Optional[str] = None
    armies: int = 0
    borders: List[str] = field(default_factory=list)

@dataclass
class StrategyState:
    game_id: str
    players: List[str]
    board: Dict[str, Territory]
    player_cards: Dict[str, List[str]] # Carte obiettivo/risorse
    turn_number: int = 0
    current_player_idx: int = 0
    phase: str = "setup" # setup, reinforcements, attack, maneuver
    is_game_over: bool = False
    winner: Optional[str] = None
    
    # Log
    action_log: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def current_player(self) -> str:
        return self.players[self.current_player_idx]

class StrategyEngine:
    def __init__(self, rules_path: str):
        with open(rules_path, 'r', encoding='utf-8') as f:
            self.rules = yaml.safe_load(f)
        
        self.map_config = self.rules.get('components', {}).get('board', {})
        self.dice_config = self.rules.get('components', {}).get('dice', {})
    
    def create_game(self, players: List[str], seed: Optional[int] = None) -> StrategyState:
        if seed:
            random.seed(seed)
            
        # Crea mappa (semplificata per demo se non definita completamente)
        board = {}
        defined_spaces = self.map_config.get('spaces', [])
        
        # Se non ci sono spazi definiti (caso test), generiamo un grafo random
        if not defined_spaces:
            defined_spaces = [
                {"id": f"t{i}", "name": f"Territory {i}", "borders": []} 
                for i in range(20)
            ]
            # Collega random
            for i in range(20):
                target = (i + 1) % 20
                defined_spaces[i]["borders"].append(f"t{target}")
                defined_spaces[target]["borders"].append(f"t{i}")
        
        for space in defined_spaces:
            t = Territory(
                id=space['id'],
                name=space['name'],
                borders=space.get('borders', [])
            )
            board[t.id] = t
            
        state = StrategyState(
            game_id=str(uuid.uuid4())[:8],
            players=players,
            board=board,
            player_cards={p: [] for p in players}
        )
        
        self._setup_board(state)
        return state
    
    def _setup_board(self, state: StrategyState):
        """Distribuisce territori e armate iniziali."""
        territories = list(state.board.values())
        random.shuffle(territories)
        
        # Assegna territori
        for i, t in enumerate(territories):
            owner = state.players[i % len(state.players)]
            t.owner = owner
            t.armies = 3 # Base iniziale
            
        state.phase = "reinforcements"
    
    def play_turn(self, state: StrategyState, agent_actions: Dict[str, Any]) -> Dict[str, Any]:
        """Esegue un turno completo per un giocatore."""
        
        player = state.current_player
        logs = []
        
        # 1. Rinforzi
        # Calcola armate: Territori / 3
        territories_owned = len([t for t in state.board.values() if t.owner == player])
        reinforcements = max(3, territories_owned // 3)
        
        # L'agente decide dove metterle (semplificato: random sui propri)
        my_territories = [t for t in state.board.values() if t.owner == player]
        if my_territories:
            for _ in range(reinforcements):
                target = random.choice(my_territories)
                target.armies += 1
        
        logs.append(f"{player} riceve {reinforcements} armate")
        
        # 2. Attacchi (loop finché l'agente vuole o può)
        # Semplificazione: prova 3 attacchi casuali dove ha vantaggio > 2
        attacks_made = 0
        for _ in range(3):
            candidates = []
            for t in my_territories:
                if t.armies > 1:
                    for border_id in t.borders:
                        target = state.board.get(border_id)
                        if target and target.owner != player:
                            candidates.append((t, target))
            
            if not candidates:
                break
                
            # Scegli attacco migliore (strategia base inclusa nell'engine per demo)
            attacker, defender = max(candidates, key=lambda x: x[0].armies - x[1].armies)
            
            if attacker.armies > defender.armies + 1: # Attacca solo se vantaggio
                res = self._resolve_battle(attacker, defender)
                logs.append(f"Attacco {attacker.name} -> {defender.name}: {res}")
                attacks_made += 1
        
        # 3. Passa turno
        state.current_player_idx = (state.current_player_idx + 1) % len(state.players)
        state.turn_number += 1
        
        # Check vittoria
        if self._check_victory(state):
            state.is_game_over = True
            state.winner = self._check_victory(state)
        
        return {"logs": logs, "turn": state.turn_number}

    def _resolve_battle(self, attacker: Territory, defender: Territory) -> str:
        """Risolve una battaglia (Rossi vs Blu)."""
        # Dadi attacker (max 3)
        n_att = min(3, attacker.armies - 1)
        # Dadi defender (max 3)
        n_def = min(3, defender.armies)
        
        dice_att = sorted([random.randint(1, 6) for _ in range(n_att)], reverse=True)
        dice_def = sorted([random.randint(1, 6) for _ in range(n_def)], reverse=True)
        
        lost_att = 0
        lost_def = 0
        
        for a, d in zip(dice_att, dice_def):
            if d >= a: # Difesa vince pareggi
                lost_att += 1
            else:
                lost_def += 1
        
        attacker.armies -= lost_att
        defender.armies -= lost_def
        
        result = f"Attaccante perde {lost_att}, Difensore perde {lost_def}"
        
        if defender.armies <= 0:
            # Conquista
            defender.owner = attacker.owner
            move_in = n_att # Semplificato
            attacker.armies -= move_in
            defender.armies = move_in
            result += " -> CONQUISTATO!"
            
        return result

    def _check_victory(self, state: StrategyState) -> Optional[str]:
        """Controlla se qualcuno possiede tutto."""
        owners = {t.owner for t in state.board.values()}
        if len(owners) == 1:
            return list(owners)[0]
        
        # Limite turni per evitare loop infiniti
        if state.turn_number >= 100:
            # Vince chi ha più territori
            counts = {}
            for t in state.board.values():
                counts[t.owner] = counts.get(t.owner, 0) + 1
            return max(counts, key=counts.get)
            
        return None

    def get_game_info(self) -> Dict[str, Any]:
        return {
            "name": self.rules['game']['name'],
            "type": self.rules['game']['type'],
            "players": f"{self.rules['players']['min']}-{self.rules['players']['max']}",
            "victory_threshold": "Conquista Globale",
            "total_cards": "N/A",
            "has_trump": False
        }

"""
Simulator - Sistema di simulazione batch e analisi KPI
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import statistics

from .engine import BriscolaEngine, AgentFactory, GameState


@dataclass
class SimulationResult:
    """Risultato di una singola simulazione."""
    game_id: str
    winner: Optional[str]
    player1_profile: str
    player2_profile: str
    player1_score: int
    player2_score: int
    total_hands: int
    score_history: List[Dict[str, int]]
    trump_hands: int
    duration_ms: float


@dataclass 
class BatchResult:
    """Risultato di un batch di simulazioni."""
    total_games: int
    player1_profile: str
    player2_profile: str
    results: List[SimulationResult] = field(default_factory=list)
    
    # KPI calcolati
    kpis: Dict[str, Any] = field(default_factory=dict)


class Simulator:
    """Simula partite in batch e calcola KPI."""
    
    def __init__(self, profiles_path: Optional[Path] = None):
        self.agent_factory = AgentFactory(profiles_path)
        self.engine = BriscolaEngine()
    
    def run_single_game(
        self, 
        profile1: str, 
        profile2: str, 
        seed: Optional[int] = None,
        log_actions: bool = False
    ) -> Tuple[SimulationResult, Optional[List[Dict[str, Any]]]]:
        """Esegue una singola partita."""
        start = datetime.now()
        
        agent1 = self.agent_factory.create_agent("player1", profile1)
        agent2 = self.agent_factory.create_agent("player2", profile2)
        
        state, logger = self.engine.play_game(agent1, agent2, seed, verbose=False, log_actions=log_actions)
        
        duration = (datetime.now() - start).total_seconds() * 1000
        
        trump_hands = sum(1 for h in state.hands_history if h.trump_used)
        
        result = SimulationResult(
            game_id=state.game_id,
            winner=state.winner,
            player1_profile=profile1,
            player2_profile=profile2,
            player1_score=state.player1_score,
            player2_score=state.player2_score,
            total_hands=state.hand_number,
            score_history=state.score_history,
            trump_hands=trump_hands,
            duration_ms=duration
        )
        
        if log_actions and logger:
            return result, logger.events
        return result, None
    
    def run_batch(
        self, 
        profile1: str, 
        profile2: str, 
        num_games: int = 1000,
        base_seed: Optional[int] = None
    ) -> BatchResult:
        """Esegue un batch di simulazioni."""
        print(f"Simulando {num_games} partite: {profile1} vs {profile2}")
        
        batch = BatchResult(
            total_games=num_games,
            player1_profile=profile1,
            player2_profile=profile2
        )
        
        for i in range(num_games):
            seed = (base_seed + i) if base_seed else None
            result, _ = self.run_single_game(profile1, profile2, seed, log_actions=False)
            batch.results.append(result)
            
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{num_games} partite completate")
        
        batch.kpis = self.calculate_kpis(batch)
        return batch
    
    def calculate_kpis(self, batch: BatchResult) -> Dict[str, Any]:
        """Calcola tutti i KPI dal batch di risultati."""
        results = batch.results
        n = len(results)
        
        if n == 0:
            return {}
        
        # Win rates
        p1_wins = sum(1 for r in results if r.winner == "player1")
        p2_wins = sum(1 for r in results if r.winner == "player2")
        draws = sum(1 for r in results if r.winner is None)
        
        # Scores
        p1_scores = [r.player1_score for r in results]
        p2_scores = [r.player2_score for r in results]
        
        # Score differences
        score_diffs = [r.player1_score - r.player2_score for r in results]
        
        # Close games (within 10 points)
        close = sum(1 for r in results if abs(r.player1_score - r.player2_score) <= 10)
        
        # Blowouts (>40 point difference)
        blowouts = sum(1 for r in results if abs(r.player1_score - r.player2_score) >= 40)
        
        # Comeback analysis
        comebacks = self._analyze_comebacks(results)
        
        # Snowball analysis  
        snowball = self._analyze_snowball(results)
        
        return {
            "balance": {
                "player1_win_rate": p1_wins / n,
                "player2_win_rate": p2_wins / n,
                "draw_rate": draws / n,
                "first_player_advantage": (p1_wins - p2_wins) / n,
                "balance_score": 1 - abs(p1_wins - p2_wins) / n  # 1 = perfect
            },
            "scoring": {
                "player1_avg_score": statistics.mean(p1_scores),
                "player2_avg_score": statistics.mean(p2_scores),
                "player1_score_std": statistics.stdev(p1_scores) if n > 1 else 0,
                "player2_score_std": statistics.stdev(p2_scores) if n > 1 else 0,
                "avg_score_diff": statistics.mean(score_diffs),
                "max_score_diff": max(score_diffs),
                "min_score_diff": min(score_diffs)
            },
            "game_types": {
                "close_games_rate": close / n,
                "blowout_rate": blowouts / n,
                "avg_hands_per_game": statistics.mean([r.total_hands for r in results]),
                "avg_trump_usage": statistics.mean([r.trump_hands for r in results])
            },
            "snowball": snowball,
            "comebacks": comebacks,
            "performance": {
                "avg_game_duration_ms": statistics.mean([r.duration_ms for r in results]),
                "total_games": n
            }
        }
    
    def _analyze_comebacks(self, results: List[SimulationResult]) -> Dict[str, float]:
        """Analizza i comeback (rimonte)."""
        comeback_count = 0
        lead_changes = []
        
        for r in results:
            history = r.score_history
            if len(history) < 5:
                continue
            
            changes = 0
            leader = None
            was_behind = False
            
            for h in history:
                p1 = h.get("player1", 0)
                p2 = h.get("player2", 0)
                
                current_leader = "p1" if p1 > p2 else ("p2" if p2 > p1 else None)
                if current_leader and leader and current_leader != leader:
                    changes += 1
                leader = current_leader
                
                # Check if winner was ever behind by 15+ points
                if r.winner == "player1" and p2 - p1 >= 15:
                    was_behind = True
                elif r.winner == "player2" and p1 - p2 >= 15:
                    was_behind = True
            
            if was_behind and r.winner:
                comeback_count += 1
            lead_changes.append(changes)
        
        n = len(results)
        return {
            "comeback_rate": comeback_count / n if n > 0 else 0,
            "avg_lead_changes": statistics.mean(lead_changes) if lead_changes else 0,
            "max_lead_changes": max(lead_changes) if lead_changes else 0
        }
    
    def _analyze_snowball(self, results: List[SimulationResult]) -> Dict[str, float]:
        """Analizza il snowball effect."""
        early_lead_wins = 0
        decisive_hands = []
        
        for r in results:
            history = r.score_history
            if len(history) < 5 or not r.winner:
                continue
            
            # Check leader at hand 5
            mid_point = history[4] if len(history) > 4 else history[-1]
            p1_mid = mid_point.get("player1", 0)
            p2_mid = mid_point.get("player2", 0)
            
            early_leader = "player1" if p1_mid > p2_mid else "player2"
            if early_leader == r.winner:
                early_lead_wins += 1
            
            # Find decisive hand (when lead became insurmountable)
            for i, h in enumerate(history):
                diff = abs(h.get("player1", 0) - h.get("player2", 0))
                remaining = 120 - h.get("player1", 0) - h.get("player2", 0)
                if diff > remaining:
                    decisive_hands.append(i + 1)
                    break
        
        n = len([r for r in results if r.winner])
        return {
            "early_lead_win_rate": early_lead_wins / n if n > 0 else 0,
            "snowball_index": early_lead_wins / n - 0.5 if n > 0 else 0,
            "avg_decisive_hand": statistics.mean(decisive_hands) if decisive_hands else 0,
            "median_decisive_hand": statistics.median(decisive_hands) if decisive_hands else 0
        }

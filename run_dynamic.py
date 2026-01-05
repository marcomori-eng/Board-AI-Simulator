"""
Dynamic Simulation Runner
=========================
Esegue simulazioni di QUALSIASI gioco definito in regole.yaml.
Calcola KPI avanzati per bilanciamento e analisi.
"""

import argparse
import json
import statistics
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import yaml

# Importa i componenti dinamici
from simulator.engine.dynamic_engine import DynamicGameEngine
from simulator.engine.dynamic_agent import DynamicAgentFactory
from simulator.engine.strategy_engine import StrategyEngine
from simulator.engine.path_engine import PathEngine


class KPIAnalyzer:
    """Classe per calcolare KPI dai risultati grezzi."""
    
    @staticmethod
    def calculate(results: List[Dict[str, Any]], num_games: int, duration_sec: float) -> Dict[str, Any]:
        if not results:
            return {}
            
        # Dati base
        winners = [r['winner'] for r in results]
        p1_wins = winners.count('player1')
        p2_wins = winners.count('player2')
        draws = winners.count(None)
        
        # Balance
        balance = {
            "player1_win_rate": p1_wins / num_games,
            "player2_win_rate": p2_wins / num_games,
            "draw_rate": draws / num_games,
            "first_player_advantage": (p1_wins - p2_wins) / num_games, # Assumendo P1 inizi sempre o sia tracciato
            "balance_score": 1.0 - abs(p1_wins - p2_wins) / num_games
        }
        
        # Snowball & Comeback (se disponiamo di history)
        snowball_stats = KPIAnalyzer._analyze_snowball(results)
        comeback_stats = KPIAnalyzer._analyze_comebacks(results)
        
        # Scoring stats
        p1_scores = [r.get('p1_score', 0) for r in results]
        p2_scores = [r.get('p2_score', 0) for r in results]
        
        scoring = {
            "p1_avg_score": statistics.mean(p1_scores),
            "p2_avg_score": statistics.mean(p2_scores),
            "avg_diff": statistics.mean([abs(s1 - s2) for s1, s2 in zip(p1_scores, p2_scores)])
        }
        
        return {
            "balance": balance,
            "scoring": scoring,
            "snowball": snowball_stats,
            "comebacks": comeback_stats,
            "performance": {
                "total_duration_sec": duration_sec,
                "avg_game_ms": (duration_sec * 1000) / num_games
            }
        }
    
    @staticmethod
    def _analyze_snowball(results: List[Dict]) -> Dict[str, float]:
        early_lead_wins = 0
        valid_games = 0
        
        for r in results:
            history = r.get('score_history', [])
            if not history or len(history) < 3 or not r['winner']:
                continue
            
            valid_games += 1
            # Check leader a 1/3 della partita
            mid_idx = len(history) // 3
            mid_state = history[mid_idx]
            
            # Gestione dinamica chiave history
            p1_mid = mid_state.get('player1', 0)
            p2_mid = mid_state.get('player2', 0)
            
            leader_mid = 'player1' if p1_mid > p2_mid else ('player2' if p2_mid > p1_mid else None)
            
            if leader_mid == r['winner']:
                early_lead_wins += 1
                
        if valid_games == 0:
            return {"early_lead_win_rate": 0.0, "snowball_index": 0.0}
            
        rate = early_lead_wins / valid_games
        return {
            "early_lead_win_rate": rate,
            "snowball_index": rate - 0.5 # >0 significa che il vantaggio iniziale pesa
        }

    @staticmethod
    def _analyze_comebacks(results: List[Dict]) -> Dict[str, float]:
        comebacks = 0
        valid_games = 0
        
        for r in results:
            history = r.get('score_history', [])
            winner = r.get('winner')
            if not history or not winner:
                continue
                
            valid_games += 1
            max_deficit = 0
            
            for state in history:
                p1 = state.get('player1', 0)
                p2 = state.get('player2', 0)
                
                diff = p2 - p1 if winner == 'player1' else p1 - p2
                if diff > max_deficit:
                    max_deficit = diff
            
            # Definiamo comeback se si recupera da uno svantaggio significativo (es. > 10% soglia)
            # Per ora usiamo valore assoluto > 5
            if max_deficit >= 5: 
                comebacks += 1
                
        return {
            "comeback_rate": comebacks / valid_games if valid_games > 0 else 0.0
        }


def run_batch_dynamic(
    rules_path: Path,
    profile1: str,
    profile2: str,
    num_games: int,
    seed: int = None,
    verbose: bool = False,
    output_file: str = None
):
    """Esegue un batch di partite con regole dinamiche."""
    
    with open(rules_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    game_type = config.get('game', {}).get('type', 'card_game')
    game_name = config.get('game', {}).get('name', 'Unknown')
    board_type = config.get('components', {}).get('board', {}).get('type', 'map')
    
    print(f"🔄 Caricamento regole: {game_name} ({game_type})")
    
    start_time = datetime.now()
    results = []
    
    if game_type == 'card_game':
        results = _run_card_game_simulation(rules_path, profile1, profile2, num_games, seed, verbose)
    elif game_type == 'board_game':
        if board_type == 'path':
             results = _run_path_game_simulation(rules_path, profile1, profile2, num_games, seed, verbose)
        else:
             results = _run_board_game_simulation(rules_path, profile1, profile2, num_games, seed, verbose)
    else:
        print(f"❌ Tipo gioco non supportato: {game_type}")
        return

    duration = (datetime.now() - start_time).total_seconds()
    
    kpis = KPIAnalyzer.calculate(results, num_games, duration)
    _print_kpi_report(kpis, profile1, profile2, game_name)
    
    if output_file:
        _save_results(output_file, results, kpis, config, profile1, profile2)


def _run_path_game_simulation(rules_path, profile1, profile2, num_games, seed, verbose) -> List[Dict]:
    engine = PathEngine(rules_path)
    results = []
    
    for i in range(num_games):
        current_seed = (seed + i) if seed is not None else None
        state = engine.create_game(["player1", "player2"], seed=current_seed)
        
        turn_limit = 300
        history = [] # Track positions per turn
        
        while not state.is_game_over and state.turn_number < turn_limit:
            engine.play_turn(state)
            
            history.append({
                "player1": state.positions["player1"],
                "player2": state.positions["player2"]
            })
            
            if verbose and i == 0:
                print(f"Turno {state.turn_number}: {state.log[-1] if state.log else ''}")

        results.append({
            "winner": state.winner,
            "p1_score": state.positions["player1"], 
            "p2_score": state.positions["player2"],
            "score_history": history
        })
        if (i+1)%100==0: print(f".. {i+1} games")
        
    return results


def _run_card_game_simulation(rules_path, profile1, profile2, num_games, seed, verbose) -> List[Dict]:
    engine = DynamicGameEngine(rules_path)
    factory = DynamicAgentFactory()
    
    results = []
    for i in range(num_games):
        current_seed = (seed + i) if seed is not None else None
        
        p1 = factory.create_agent("player1", profile1, engine.rules)
        p2 = factory.create_agent("player2", profile2, engine.rules)
        
        state = engine.create_game(["player1", "player2"], seed=current_seed)
        
        while not state.is_game_over:
            p1_hand = state.player_hands["player1"]
            p2_hand = state.player_hands["player2"]
            current = state.current_player
            
            # (Codice identico a prima per carte)
            if current == "player1":
                card1 = p1.choose_card(p1_hand, state, None)
                p2.observe_card(card1, played_by_opponent=True)
                card2 = p2.choose_card(p2_hand, state, card1)
                p1.observe_card(card2, played_by_opponent=True)
            else:
                card2 = p2.choose_card(p2_hand, state, None)
                p1.observe_card(card2, played_by_opponent=True)
                card1 = p1.choose_card(p1_hand, state, card2)
                p2.observe_card(card1, played_by_opponent=True)
            
            res = engine.play_hand(state, {"player1": card1, "player2": card2})
            if verbose and i==0: print(f"Mano {res['hand_number']}: {res['winner']} vince")

        results.append({
            "winner": state.winner,
            "p1_score": state.player_scores["player1"],
            "p2_score": state.player_scores["player2"],
            "score_history": state.score_history
        })
        if (i+1)%100==0: print(f".. {i+1} games")
        
    return results


def _run_board_game_simulation(rules_path, profile1, profile2, num_games, seed, verbose) -> List[Dict]:
    engine = StrategyEngine(rules_path)
    results = []
    
    for i in range(num_games):
        current_seed = (seed + i) if seed is not None else None
        state = engine.create_game(["player1", "player2"], seed=current_seed)
        
        history = []
        turn_limit = 200
        while not state.is_game_over and state.turn_number < turn_limit:
            engine.play_turn(state, {})
            # Registra storia punteggi per KPI
            p1_terr = len([t for t in state.board.values() if t.owner == "player1"])
            p2_terr = len([t for t in state.board.values() if t.owner == "player2"])
            history.append({"player1": p1_terr, "player2": p2_terr})
            
            if verbose and i == 0:
                print(f"Turno {state.turn_number}: {state.action_log[-1] if state.action_log else ''}") # Fix log access
        
        winner = state.winner
        # Se finisce per limite turni
        if not winner:
            p1_terr = len([t for t in state.board.values() if t.owner == "player1"])
            p2_terr = len([t for t in state.board.values() if t.owner == "player2"])
            if p1_terr > p2_terr: winner = "player1"
            elif p2_terr > p1_terr: winner = "player2"
            
        results.append({
            "winner": winner,
            "p1_score": len([t for t in state.board.values() if t.owner == "player1"]),
            "p2_score": len([t for t in state.board.values() if t.owner == "player2"]),
            "score_history": history
        })
        if (i+1)%100==0: print(f".. {i+1} games")
        
    return results


def _print_kpi_report(kpis, p1, p2, game):
    bal = kpis['balance']
    snow = kpis['snowball']
    
    print(f"\n📊 REPORT KPI: {game}")
    print(f"{'='*50}")
    print(f"BILANCIAMENTO:")
    print(f"  P1 ({p1}) Win Rate: {bal['player1_win_rate']*100:.1f}%")
    print(f"  P2 ({p2}) Win Rate: {bal['player2_win_rate']*100:.1f}%")
    print(f"  First Mover Advantage: {bal['first_player_advantage']*100:+.1f}%")
    print(f"  Balance Score: {bal['balance_score']*100:.1f}% (100% = perfetto)")
    
    print(f"\nDINAMICHE GIOCO:")
    print(f"  Snowball Index: {snow['snowball_index']:+.2f} (Positivo = chi va in vantaggio vince)")
    print(f"  Early Lead Win Rate: {snow['early_lead_win_rate']*100:.1f}%")
    print(f"  Comeback Rate: {kpis['comebacks']['comeback_rate']*100:.1f}%")
    print(f"{'='*50}\n")


def _save_results(path, results, kpis, config, p1, p2):
    data = {
        "timestamp": datetime.now().isoformat(),
        "game": config.get('game', {}).get('name'),
        "players": {"p1": p1, "p2": p2},
        "kpis": kpis,
        "results": results[:50]
    }
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"💾 Risultati salvati in: {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", default="regole.yaml")
    parser.add_argument("--p1", default="balanced")
    parser.add_argument("--p2", default="balanced")
    parser.add_argument("--games", "-n", type=int, default=50)
    parser.add_argument("--seed", "-s", type=int, default=None)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--output", "-o", default=None)
    
    args = parser.parse_args()
    if Path(args.rules).exists():
        run_batch_dynamic(
            Path(args.rules), args.p1, args.p2, args.games, args.seed, args.verbose, args.output
        )
    else:
        print(f"File non trovato: {args.rules}")

if __name__ == "__main__":
    main()

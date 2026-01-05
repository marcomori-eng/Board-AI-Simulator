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
import math
import sys

try:
    import matplotlib.pyplot as plt
    import pandas as pd
    import numpy as np
except ImportError:
    print("Warning: matplotlib/pandas not found. Graphs will not be generated.")
    plt = None
    pd = None
    np = None

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
        score_diffs = [s1 - s2 for s1, s2 in zip(p1_scores, p2_scores)]
        
        scoring = {
            "p1_avg_score": statistics.mean(p1_scores) if p1_scores else 0,
            "p2_avg_score": statistics.mean(p2_scores) if p2_scores else 0,
            "avg_diff": statistics.mean([abs(d) for d in score_diffs]) if score_diffs else 0,
            "max_p1_score": max(p1_scores) if p1_scores else 0,
            "max_p2_score": max(p2_scores) if p2_scores else 0,
            "std_dev_diff": statistics.stdev(score_diffs) if len(score_diffs) > 1 else 0
        }

        # Advanced Stats (Luck, Phases, etc.)
        advanced = KPIAnalyzer._analyze_advanced(results)
        
        return {
            "balance": balance,
            "scoring": scoring,
            "snowball": snowball_stats,
            "comebacks": comeback_stats,
            "advanced": advanced,
            "performance": {
                "total_duration_sec": duration_sec,
                "avg_game_ms": (duration_sec * 1000) / num_games if num_games > 0 else 0
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

    @staticmethod
    def _analyze_advanced(results: List[Dict]) -> Dict[str, Any]:
        # Luck Analysis (Initial Hand Strength)
        luck_valid = 0
        stronger_wins = 0
        strength_diffs = []
        win_diff_corr = 0
        
        phase_wins = {'early': {'p1': 0, 'p2': 0}, 'mid': {'p1': 0, 'p2': 0}, 'late': {'p1': 0, 'p2': 0}}
        volatility_scores = []

        for r in results:
            # Luck
            if 'p1_initial_str' in r and 'p2_initial_str' in r:
                luck_valid += 1
                s1, s2 = r['p1_initial_str'], r['p2_initial_str']
                winner = r.get('winner')
                
                if s1 > s2 and winner == 'player1': stronger_wins += 1
                elif s2 > s1 and winner == 'player2': stronger_wins += 1
                
                strength_diffs.append(s1 - s2)
            
            # Phases & Volatility
            history = r.get('score_history', [])
            if len(history) >= 3:
                # Phases
                n = len(history)
                # Ensure indices are within bounds
                early_idx = min(n // 3, n - 1)
                mid_idx = min(2 * n // 3, n - 1)
                
                early = history[early_idx]
                mid = history[mid_idx]
                late = history[-1]
                
                if early.get('player1',0) > early.get('player2',0): phase_wins['early']['p1'] += 1
                elif early.get('player2',0) > early.get('player1',0): phase_wins['early']['p2'] += 1
                
                if mid.get('player1',0) > mid.get('player2',0): phase_wins['mid']['p1'] += 1
                elif mid.get('player2',0) > mid.get('player1',0): phase_wins['mid']['p2'] += 1
                
                if late.get('player1',0) > late.get('player2',0): phase_wins['late']['p1'] += 1
                elif late.get('player2',0) > late.get('player1',0): phase_wins['late']['p2'] += 1
                
                # Volatility: Avg change in score difference
                diffs = [h.get('player1',0) - h.get('player2',0) for h in history]
                if len(diffs) > 1:
                    changes = [abs(diffs[i] - diffs[i-1]) for i in range(1, len(diffs))]
                    if changes:
                        volatility_scores.append(statistics.mean(changes))

        # Correlation (simple approximation)
        correlation = 0
        if luck_valid > 5 and np is not None:
             # Calculate correlation of initial strength diff vs final score diff
             final_score_diffs = []
             valid_strength_diffs = []
             for i, r in enumerate(results):
                 if 'p1_initial_str' in r:
                     final_score_diffs.append(r['p1_score'] - r['p2_score'])
                     valid_strength_diffs.append(strength_diffs[len(final_score_diffs)-1])
             
             if len(set(valid_strength_diffs)) > 1 and len(set(final_score_diffs)) > 1:
                correlation = np.corrcoef(valid_strength_diffs, final_score_diffs)[0, 1]
                if np.isnan(correlation): correlation = 0

        return {
            "luck_factor": {
                "stronger_hand_win_rate": stronger_wins / luck_valid if luck_valid > 0 else 0,
                "correlation_strength_score": correlation
            },
            "phases": phase_wins,
            "avg_volatility": statistics.mean(volatility_scores) if volatility_scores else 0
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
    
    plot_filename = None
    if plt is not None and num_games > 0:
        plot_filename = f"report_{game_name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        try:
            _generate_graphs(results, kpis, profile1, profile2, game_name, plot_filename)
        except Exception as e:
            print(f"⚠️ Errore generazione grafici: {e}")
            import traceback
            traceback.print_exc()
    
    # Save JSON always
    json_filename = output_file or f"results_{game_name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    _save_results(json_filename, results, kpis, config, profile1, profile2, plot_filename)


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
        
        # Calculate Initial Hand Strength
        p1_hand_str = sum(c.strength for c in state.player_hands["player1"])
        p2_hand_str = sum(c.strength for c in state.player_hands["player2"])
        
        while not state.is_game_over:
            p1_hand = state.player_hands["player1"]
            p2_hand = state.player_hands["player2"]
            current = state.current_player
            
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
            "p1_initial_str": p1_hand_str,
            "p2_initial_str": p2_hand_str,
            "score_history": state.score_history
        })
        if (i+1)%100==0: print(f".. {i+1} games")
        
    return results


def _run_board_game_simulation(rules_path, profile1, profile2, num_games, seed, verbose) -> List[Dict]:
    engine = StrategyEngine(rules_path)
    # StrategyEngine might not be fully implemented in snippet, but assuming standard flow
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
                print(f"Turno {state.turn_number}: {p1_terr}-{p2_terr}")
        
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
    adv = kpis['advanced']
    scr = kpis['scoring']
    
    print(f"\n📊 DETAILED REPORT: {game}")
    print(f"{'='*60}")
    print(f"🏆 PERFORMANCE & BALANCE")
    print(f"  P1 ({p1}) Win: {bal['player1_win_rate']*100:.1f}% | Avg Score: {scr['p1_avg_score']:.1f}")
    print(f"  P2 ({p2}) Win: {bal['player2_win_rate']*100:.1f}% | Avg Score: {scr['p2_avg_score']:.1f}")
    print(f"  Draws: {bal['draw_rate']*100:.1f}%")
    print(f"  Balance Score: {bal['balance_score']*100:.1f}% (Ideal: 100%)")
    
    print(f"\n🎲 GAME DYNAMICS")
    print(f"  Snowball Effect: {snow['snowball_index']:+.2f} (Early lead determines winner?)")
    print(f"  Comeback Rate: {kpis['comebacks']['comeback_rate']*100:.1f}%")
    print(f"  Game Volatility: {adv['avg_volatility']:.2f} (Avg point swing per turn)")
    
    print(f"\n🍀 LUCK & STRATEGY")
    luck = adv['luck_factor']
    print(f"  Luck Influence: {luck['correlation_strength_score']:.2f} (Corr. Initial Hands vs Score)")
    print(f"  Stronger Start Win Rate: {luck['stronger_hand_win_rate']*100:.1f}%")
    
    phases = adv['phases']
    print(f"\n⏱️ PHASE DOMINANCE (Hands breakdown)")
    print(f"  Early Game: P1 {phases['early']['p1']} - P2 {phases['early']['p2']}")
    print(f"  Mid Game:   P1 {phases['mid']['p1']} - P2 {phases['mid']['p2']}")
    print(f"  Late Game:  P1 {phases['late']['p1']} - P2 {phases['late']['p2']}")
    print(f"{'='*60}\n")


def _generate_graphs(results, kpis, p1, p2, game_name, filename):
    """Genera grafici informativi usando Matplotlib."""
    if plt is None: return

    # Setup Plot
    fig = plt.figure(figsize=(16, 12))
    fig.suptitle(f"Game Analysis: {game_name}\n{p1} vs {p2}", fontsize=16)
    
    # 1. Win Distribution (Pie Chart)
    ax1 = plt.subplot(2, 3, 1)
    labels = [f'{p1} Wins', f'{p2} Wins', 'Draws']
    sizes = [kpis['balance']['player1_win_rate'], kpis['balance']['player2_win_rate'], kpis['balance']['draw_rate']]
    colors = ['#ff9999', '#66b3ff', '#99ff99']
    
    # Filter empty slices
    valid_labels = [l for i, l in enumerate(labels) if sizes[i] > 0]
    valid_sizes = [s for s in sizes if s > 0]
    valid_colors = [c for i, c in enumerate(colors) if sizes[i] > 0]

    if valid_sizes:
        ax1.pie(valid_sizes, labels=valid_labels, colors=valid_colors, autopct='%1.1f%%', startangle=90)
    else:
        ax1.text(0.5, 0.5, "No Data", ha='center')
    ax1.set_title('Win Distribution')

    # 2. Score Evolution (Line Plot with Std Dev)
    ax2 = plt.subplot(2, 3, 2)
    # Get max length
    max_len = 0
    for r in results:
        h = r.get('score_history', [])
        if len(h) > max_len: max_len = len(h)
    
    if max_len > 0:
        p1_trends = np.zeros(max_len)
        p2_trends = np.zeros(max_len)
        counts = np.zeros(max_len)
        
        for r in results:
            h = r.get('score_history', [])
            for i, state in enumerate(h):
                p1_trends[i] += state.get('player1', 0)
                p2_trends[i] += state.get('player2', 0)
                counts[i] += 1
                
        # Averaging (handling different lengths)
        valid_mask = counts > 0
        p1_avg = np.divide(p1_trends, counts, where=valid_mask)
        p2_avg = np.divide(p2_trends, counts, where=valid_mask)
        
        turns = range(1, len(p1_avg[valid_mask]) + 1)
        ax2.plot(turns, p1_avg[valid_mask], label=p1, color='red')
        ax2.plot(turns, p2_avg[valid_mask], label=p2, color='blue')
        ax2.set_xlabel('Turn / Hand')
        ax2.set_ylabel('Avg Score')
        ax2.set_title('Score Trajectory')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
    else:
        ax2.text(0.5, 0.5, "No Score History", ha='center')

    # 3. Score Difference Histogram
    ax3 = plt.subplot(2, 3, 3)
    score_diffs = [r['p1_score'] - r['p2_score'] for r in results]
    if score_diffs:
        ax3.hist(score_diffs, bins=min(20, len(set(score_diffs))+1), color='purple', alpha=0.7)
        ax3.axvline(0, color='black', linestyle='dashed', linewidth=1)
        ax3.set_title('Score Difference (P1 - P2)')
        ax3.set_xlabel('Margin')
    
    # 4. Phase Dominance (Bar Chart)
    ax4 = plt.subplot(2, 3, 4)
    phases = kpis['advanced']['phases']
    categories = ['Early', 'Mid', 'Late']
    p1_vals = [phases['early']['p1'], phases['mid']['p1'], phases['late']['p1']]
    p2_vals = [phases['early']['p2'], phases['mid']['p2'], phases['late']['p2']]
    
    x = np.arange(len(categories))
    width = 0.35
    ax4.bar(x - width/2, p1_vals, width, label=p1, color='red', alpha=0.6)
    ax4.bar(x + width/2, p2_vals, width, label=p2, color='blue', alpha=0.6)
    ax4.set_xticks(x)
    ax4.set_xticklabels(categories)
    ax4.set_title('Phase Dominance (Hands Leaders)')
    ax4.legend()

    # 5. Luck Correlation (Scatter)
    ax5 = plt.subplot(2, 3, 5)
    luck_diffs = []
    final_diffs = []
    for r in results:
        if 'p1_initial_str' in r:
            luck_diffs.append(r['p1_initial_str'] - r['p2_initial_str'])
            final_diffs.append(r['p1_score'] - r['p2_score'])
            
    if luck_diffs:
        ax5.scatter(luck_diffs, final_diffs, alpha=0.5, c='green', s=15)
        ax5.set_xlabel('Initial Hand Strength Diff (P1 - P2)')
        ax5.set_ylabel('Final Score Diff')
        ax5.set_title(f'Luck Factor (Corr: {kpis["advanced"]["luck_factor"]["correlation_strength_score"]:.2f})')
        ax5.grid(True, alpha=0.3)
        
        # Add trend line
        if len(luck_diffs) > 1:
             z = np.polyfit(luck_diffs, final_diffs, 1)
             p = np.poly1d(z)
             ax5.plot(luck_diffs, p(luck_diffs), "r--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(filename)
    print(f"📈 Grafico salvato: {filename}")
    plt.close()


def _save_results(path, results, kpis, config, p1, p2, plot_file=None):
    data = {
        "timestamp": datetime.now().isoformat(),
        "game": config.get('game', {}).get('name'),
        "players": {"p1": p1, "p2": p2},
        "kpis": kpis,
        "graphs": plot_file,
        "results": results[:50] # Limit size
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



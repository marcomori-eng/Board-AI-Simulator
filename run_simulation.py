"""
Board AI Simulator - CLI
========================
Script principale per eseguire simulazioni da linea di comando.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime

from simulator import Simulator


def main():
    parser = argparse.ArgumentParser(description="Board AI Simulator - Briscola")
    
    parser.add_argument(
        "--player1", "-p1",
        default="balanced",
        help="Profilo del player 1 (default: balanced)"
    )
    parser.add_argument(
        "--player2", "-p2", 
        default="balanced",
        help="Profilo del player 2 (default: balanced)"
    )
    parser.add_argument(
        "--games", "-n",
        type=int,
        default=100,
        help="Numero di partite (default: 100)"
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=None,
        help="Seed per riproducibilità"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="File JSON per salvare i risultati"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Output verboso"
    )
    parser.add_argument(
        "--profiles",
        action="store_true",
        help="Mostra i profili disponibili"
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Esegue una singola partita con log dettagliato delle azioni"
    )
    
    args = parser.parse_args()
    
    # Init simulator
    profiles_path = Path("simulator/config/agent_profiles.yaml")
    sim = Simulator(profiles_path if profiles_path.exists() else None)
    
    # Show profiles
    if args.profiles:
        print("\nProfili disponibili:")
        for p in sim.agent_factory.list_profiles():
            profile = sim.agent_factory.profiles[p]
            print(f"  - {p}: {profile.description}")
        return
    
    # Single game with log
    if args.log:
        print(f"\n{'='*60}")
        print(f"PARTITA SINGOLA CON LOG")
        print(f"{'='*60}")
        print(f"Player 1: {args.player1}")
        print(f"Player 2: {args.player2}")
        print(f"{'='*60}\n")
        
        result, events = sim.run_single_game(
            args.player1, args.player2, args.seed, log_actions=True
        )
        
        # Print game log
        print("📜 LOG DELLE AZIONI:\n")
        for event in events:
            event_type = event.get("type", "")
            data = event.get("data", {})
            
            if event_type == "game_start":
                print(f"🎮 INIZIO PARTITA {data.get('game_id')}")
                print(f"   Briscola: {data.get('trump_card')} ({data.get('trump_suit')})")
                print(f"   {data.get('player1')} ({data.get('player1_profile')}): {data.get('player1_hand')}")
                print(f"   {data.get('player2')} ({data.get('player2_profile')}): {data.get('player2_hand')}")
                print()
            
            elif event_type == "hand_start":
                print(f"--- Mano {data.get('hand_number')} (primo: {data.get('first_player')}) ---")
            
            elif event_type == "card_played":
                player = data.get("player")
                card = data.get("card")
                is_first = "gioca" if data.get("is_first") else "risponde con"
                print(f"   {player} {is_first}: {card} ({data.get('points')} pt)")
            
            elif event_type == "hand_result":
                winner = data.get("winner")
                points = data.get("points_won")
                trump = "🃏" if data.get("trump_used") else ""
                print(f"   ➜ Vince {winner} (+{points} pt) {trump}\n")
            
            elif event_type == "card_drawn":
                print(f"   📥 {data.get('player')} pesca: {data.get('card')}")
            
            elif event_type == "game_end":
                print(f"\n{'='*60}")
                print(f"🏁 FINE PARTITA")
                print(f"   {data.get('player1_score')} - {data.get('player2_score')}")
                print(f"   Vincitore: {data.get('winner') or 'PAREGGIO'}")
                print(f"   Mani giocate: {data.get('total_hands')}")
        
        # Save log to file
        if args.output:
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "config": {
                    "player1": args.player1,
                    "player2": args.player2,
                    "seed": args.seed
                },
                "result": {
                    "game_id": result.game_id,
                    "winner": result.winner,
                    "player1_score": result.player1_score,
                    "player2_score": result.player2_score,
                    "total_hands": result.total_hands
                },
                "events": events
            }
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Log salvato in: {args.output}")
        
        print(f"\n{'='*60}\n")
        return
    
    # Run simulation
    print(f"\n{'='*60}")
    print(f"BOARD AI SIMULATOR - BRISCOLA")
    print(f"{'='*60}")
    print(f"Player 1: {args.player1}")
    print(f"Player 2: {args.player2}")
    print(f"Partite: {args.games}")
    print(f"{'='*60}\n")
    
    batch = sim.run_batch(
        args.player1,
        args.player2,
        args.games,
        args.seed
    )
    
    # Print results
    kpis = batch.kpis
    
    print(f"\n{'='*60}")
    print("RISULTATI")
    print(f"{'='*60}")
    
    bal = kpis.get("balance", {})
    print(f"\n📊 BILANCIAMENTO:")
    print(f"  Win rate {args.player1}: {bal.get('player1_win_rate', 0)*100:.1f}%")
    print(f"  Win rate {args.player2}: {bal.get('player2_win_rate', 0)*100:.1f}%")
    print(f"  Pareggi: {bal.get('draw_rate', 0)*100:.1f}%")
    print(f"  Vantaggio primo giocatore: {bal.get('first_player_advantage', 0)*100:+.1f}%")
    print(f"  Balance Score: {bal.get('balance_score', 0)*100:.1f}%")
    
    scor = kpis.get("scoring", {})
    print(f"\n📈 PUNTEGGI:")
    print(f"  Media {args.player1}: {scor.get('player1_avg_score', 0):.1f}")
    print(f"  Media {args.player2}: {scor.get('player2_avg_score', 0):.1f}")
    print(f"  Differenza media: {scor.get('avg_score_diff', 0):+.1f}")
    
    game = kpis.get("game_types", {})
    print(f"\n🎮 TIPO PARTITE:")
    print(f"  Partite combattute (±10 pt): {game.get('close_games_rate', 0)*100:.1f}%")
    print(f"  Cappotti (±40 pt): {game.get('blowout_rate', 0)*100:.1f}%")
    print(f"  Mani medie: {game.get('avg_hands_per_game', 0):.1f}")
    
    snow = kpis.get("snowball", {})
    print(f"\n❄️ SNOWBALL:")
    print(f"  Chi va in vantaggio presto vince: {snow.get('early_lead_win_rate', 0)*100:.1f}%")
    print(f"  Snowball Index: {snow.get('snowball_index', 0):+.2f}")
    print(f"  Mano decisiva media: {snow.get('avg_decisive_hand', 0):.1f}")
    
    come = kpis.get("comebacks", {})
    print(f"\n🔄 COMEBACK:")
    print(f"  Tasso rimonte: {come.get('comeback_rate', 0)*100:.1f}%")
    print(f"  Cambi di leadership medi: {come.get('avg_lead_changes', 0):.1f}")
    
    # Save to file
    if args.output:
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "player1": args.player1,
                "player2": args.player2,
                "games": args.games,
                "seed": args.seed
            },
            "kpis": kpis,
            "games_summary": [
                {
                    "game_id": r.game_id,
                    "winner": r.winner,
                    "p1_score": r.player1_score,
                    "p2_score": r.player2_score,
                    "hands": r.total_hands
                }
                for r in batch.results
            ]
        }
        
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\n✅ Risultati salvati in: {args.output}")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()

"""
Game Engine
===========
Motore di gioco che gestisce lo svolgimento della partita di Briscola.
"""

from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import uuid
import yaml
from pathlib import Path

from .game_state import GameState, Card, Suit, Deck, HandResult, GameLogger
from .agent import Agent, AgentFactory


class BriscolaEngine:
    """Motore di gioco per la Briscola a 2 giocatori."""
    
    def __init__(self, rules_path: Optional[Path] = None):
        """
        Inizializza il motore di gioco.
        
        Args:
            rules_path: Percorso al file YAML delle regole (opzionale)
        """
        self.rules = None
        if rules_path and rules_path.exists():
            self._load_rules(rules_path)
    
    def _load_rules(self, path: Path):
        """Carica le regole dal file YAML."""
        with open(path, 'r', encoding='utf-8') as f:
            self.rules = yaml.safe_load(f)
    
    def create_game(
        self, 
        player1: Agent, 
        player2: Agent,
        seed: Optional[int] = None
    ) -> GameState:
        """
        Crea una nuova partita.
        
        Args:
            player1: Agente del primo giocatore
            player2: Agente del secondo giocatore
            seed: Seed per riproducibilità
        
        Returns:
            Lo stato iniziale del gioco
        """
        game_id = str(uuid.uuid4())[:8]
        
        # Crea e mescola il mazzo
        deck = Deck.create_deck()
        deck = Deck.shuffle(deck, seed)
        
        # Distribuisci le carte iniziali (3 per giocatore)
        player1_hand = [deck.pop() for _ in range(3)]
        player2_hand = [deck.pop() for _ in range(3)]
        
        # Determina la briscola (carta sotto il mazzo)
        trump_card = deck[0]  # La prima carta del mazzo rimanente
        trump_suit = trump_card.suit
        
        # Crea lo stato iniziale
        state = GameState(
            game_id=game_id,
            trump_suit=trump_suit,
            trump_card=trump_card,
            player1_id=player1.player_id,
            player2_id=player2.player_id,
            player1_hand=player1_hand,
            player2_hand=player2_hand,
            deck=deck,
            current_player=player1.player_id,
            start_time=datetime.now()
        )
        
        # Reset degli agenti
        player1.reset()
        player2.reset()
        
        return state
    
    def play_game(
        self, 
        player1: Agent, 
        player2: Agent,
        seed: Optional[int] = None,
        verbose: bool = False,
        log_actions: bool = False
    ) -> Tuple[GameState, Optional[GameLogger]]:
        """
        Gioca un'intera partita.
        
        Args:
            player1: Agente del primo giocatore
            player2: Agente del secondo giocatore
            seed: Seed per riproducibilità
            verbose: Se True, stampa lo svolgimento
            log_actions: Se True, restituisce il log dettagliato
        
        Returns:
            Tuple con lo stato finale del gioco e opzionalmente il logger
        """
        state = self.create_game(player1, player2, seed)
        logger = GameLogger(state.game_id)
        
        # Log iniziale
        logger.log_event("game_start", {
            "game_id": state.game_id,
            "trump_card": str(state.trump_card),
            "trump_suit": state.trump_suit.value,
            "player1": player1.player_id,
            "player1_profile": player1.profile.name,
            "player2": player2.player_id,
            "player2_profile": player2.profile.name,
            "player1_hand": [str(c) for c in state.player1_hand],
            "player2_hand": [str(c) for c in state.player2_hand]
        })
        
        if verbose:
            print(f"\n{'='*50}")
            print(f"PARTITA {state.game_id}")
            print(f"Briscola: {state.trump_card}")
            print(f"{'='*50}\n")
        
        agents = {player1.player_id: player1, player2.player_id: player2}
        
        # Gioca finché entrambi i giocatori hanno carte
        while not state.is_game_over:
            result = self._play_hand(state, agents, logger, verbose)
            
            if result:
                state.hands_history.append(result)
                state.hand_number += 1
            
            # Pesca carte se il mazzo non è vuoto
            self._draw_cards(state, result.winner if result else state.current_player, logger)
            
            # Controlla fine partita
            if (len(state.player1_hand) == 0 and 
                len(state.player2_hand) == 0):
                state.is_game_over = True
        
        # Determina il vincitore
        state.end_time = datetime.now()
        state.winner = self._determine_winner(state)
        
        logger.log_game_end(state)
        
        if verbose:
            print(f"\n{'='*50}")
            print(f"FINE PARTITA")
            print(f"Player 1: {state.player1_score} punti")
            print(f"Player 2: {state.player2_score} punti")
            print(f"Vincitore: {state.winner or 'Pareggio'}")
            print(f"{'='*50}\n")
        
        if log_actions:
            return state, logger
        return state, None
    
    def _play_hand(
        self, 
        state: GameState, 
        agents: Dict[str, Agent],
        logger: GameLogger,
        verbose: bool
    ) -> Optional[HandResult]:
        """Gioca una singola mano."""
        
        state.hand_number += 1
        first_player = state.current_player
        second_player = state.get_opponent(first_player)
        
        logger.log_hand_start(state.hand_number, first_player)
        
        first_agent = agents[first_player]
        second_agent = agents[second_player]
        
        first_hand = state.get_player_hand(first_player)
        second_hand = state.get_player_hand(second_player)
        
        if not first_hand or not second_hand:
            return None
        
        # Primo giocatore sceglie
        first_card = first_agent.choose_card(first_hand, state, None)
        first_hand.remove(first_card)
        
        logger.log_card_played(first_player, first_card, is_first=True)
        
        # Il secondo giocatore osserva e risponde
        second_agent.observe_card(first_card, played_by_opponent=True)
        second_card = second_agent.choose_card(second_hand, state, first_card)
        second_hand.remove(second_card)
        
        logger.log_card_played(second_player, second_card, is_first=False)
        
        # Il primo giocatore osserva la risposta
        first_agent.observe_card(second_card, played_by_opponent=True)
        
        # Determina vincitore della mano
        winner = self._determine_hand_winner(
            first_player, first_card,
            second_player, second_card,
            state.trump_suit
        )
        
        points = first_card.points + second_card.points
        trump_used = (first_card.suit == state.trump_suit or 
                      second_card.suit == state.trump_suit)
        
        # Aggiorna punteggio
        state.add_score(winner, points)
        
        # Aggiorna carte vinte
        won_cards = [first_card, second_card]
        if winner == state.player1_id:
            state.player1_won_cards.extend(won_cards)
        else:
            state.player2_won_cards.extend(won_cards)
        
        # Il vincitore gioca per primo nella prossima mano
        state.current_player = winner
        
        result = HandResult(
            hand_number=state.hand_number,
            cards_played={first_player: first_card, second_player: second_card},
            winner=winner,
            points_won=points,
            trump_used=trump_used,
            first_player=first_player
        )
        
        logger.log_hand_result(result)
        
        if verbose:
            print(f"Mano {state.hand_number}: {first_card} vs {second_card} "
                  f"-> {winner} (+{points})")
        
        return result
    
    def _determine_hand_winner(
        self,
        player1: str, card1: Card,
        player2: str, card2: Card,
        trump_suit: Suit
    ) -> str:
        """
        Determina chi vince la mano.
        
        Regole:
        1. Se nessuno gioca briscola: vince la carta più forte del primo seme
        2. Se qualcuno gioca briscola: vince la briscola più forte
        """
        card1_is_trump = card1.suit == trump_suit
        card2_is_trump = card2.suit == trump_suit
        
        # Caso 1: Entrambe briscole
        if card1_is_trump and card2_is_trump:
            return player1 if card1.strength < card2.strength else player2
        
        # Caso 2: Solo card1 è briscola
        if card1_is_trump:
            return player1
        
        # Caso 3: Solo card2 è briscola
        if card2_is_trump:
            return player2
        
        # Caso 4: Nessuna briscola - vince il primo seme
        if card2.suit == card1.suit:
            # Stesso seme: vince la più forte
            return player1 if card1.strength < card2.strength else player2
        else:
            # Seme diverso: vince il primo giocatore
            return player1
    
    def _draw_cards(self, state: GameState, hand_winner: str, logger: GameLogger):
        """
        Fa pescare una carta a ogni giocatore.
        Chi ha vinto la mano pesca per primo.
        """
        if len(state.deck) == 0:
            return
        
        # Ordine di pesca
        if hand_winner == state.player1_id:
            draw_order = [(state.player1_hand, "player1"), 
                         (state.player2_hand, "player2")]
        else:
            draw_order = [(state.player2_hand, "player2"), 
                         (state.player1_hand, "player1")]
        
        for hand, player_id in draw_order:
            if len(state.deck) > 0:
                card = state.deck.pop()
                hand.append(card)
                logger.log_event("card_drawn", {
                    "player": player_id,
                    "card": str(card),
                    "cards_remaining": len(state.deck)
                })
    
    def _determine_winner(self, state: GameState) -> Optional[str]:
        """Determina il vincitore della partita."""
        if state.player1_score > 60:
            return state.player1_id
        elif state.player2_score > 60:
            return state.player2_id
        elif state.player1_score == state.player2_score:
            return None  # Pareggio
        else:
            # Questo non dovrebbe accadere se i punteggi sono corretti
            return state.player1_id if state.player1_score > state.player2_score else state.player2_id

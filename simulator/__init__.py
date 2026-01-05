"""
Board AI Simulator - Main Package
"""

from .simulator import Simulator, SimulationResult, BatchResult
from .engine import (
    Card, Suit, GameState, Deck, BriscolaEngine,
    Agent, AgentProfile, AgentFactory
)

__version__ = "1.0.0"

__all__ = [
    'Simulator', 'SimulationResult', 'BatchResult',
    'Card', 'Suit', 'GameState', 'Deck', 'BriscolaEngine',
    'Agent', 'AgentProfile', 'AgentFactory'
]

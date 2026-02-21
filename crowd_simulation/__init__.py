"""
Crowd Simulation Engine for Pre-Event Stampede Risk Analysis

This module provides a backend simulation engine for analyzing crowd flow,
congestion, and potential stampede conditions in venues.
"""

from .simulation import CrowdSimulation
from .venue import Venue
from .agent import Agent
from .config import SimulationConfig

__version__ = "1.0.0"
__all__ = ["CrowdSimulation", "Venue", "Agent", "SimulationConfig"]

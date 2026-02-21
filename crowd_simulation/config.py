"""
Simulation Configuration and Tunable Parameters

This module defines all configurable parameters for the crowd simulation.
These parameters can be adjusted to create various scenarios including
high-risk/pre-stampede conditions for stress testing.
"""

from dataclasses import dataclass, field
from typing import Optional
import random


@dataclass
class SimulationConfig:
    """
    Configuration parameters for the crowd simulation.
    
    These parameters are intentionally tunable to allow:
    - Normal steady-state flow analysis
    - Stress testing with high crowd density
    - Deliberate creation of near-stampede conditions
    - What-if scenario exploration
    """
    
    # === Time Control ===
    timestep: float = 0.1  # Simulation timestep in seconds
    max_simulation_time: float = 3600.0  # Maximum simulation duration (seconds)
    
    # === Spawn Control ===
    spawn_rate_multiplier: float = 1.0  # Global multiplier for all spawn rates
    initial_spawn_burst: int = 0  # Number of agents to spawn at t=0
    
    # === Agent Properties ===
    agent_radius: float = 0.25  # Agent collision radius in meters
    preferred_speed_mean: float = 1.4  # Mean walking speed (m/s) - average human
    preferred_speed_std: float = 0.3  # Standard deviation of preferred speed
    min_speed: float = 0.1  # Minimum agent speed (m/s)
    max_speed: float = 2.5  # Maximum agent speed (m/s)
    
    # === Density & Congestion ===
    max_density_per_meter: float = 6.0  # Max agents per meter of path (critical density ~6-8)
    comfortable_density: float = 2.0  # Comfortable density (free flow)
    critical_density: float = 5.0  # Density where flow becomes unstable
    
    # === Speed Reduction Model ===
    # Speed = preferred_speed * (1 - (density / max_density)^congestion_exponent)
    congestion_exponent: float = 2.0  # How aggressively speed reduces with density
    density_speed_coefficient: float = 0.8  # Max speed reduction factor at high density
    
    # === Choke Point Effects ===
    choke_point_radius: float = 3.0  # Radius of influence for choke points (meters)
    choke_point_speed_factor: float = 0.7  # Speed multiplier near choke points
    choke_point_capacity_factor: float = 0.5  # Reduced capacity at choke points
    
    # === Stop-Go Wave Parameters ===
    stop_go_threshold: float = 4.0  # Density threshold for stop-go wave formation
    stop_go_wave_speed: float = 1.2  # Backward propagation speed of stop waves (m/s)
    reaction_time: float = 0.5  # Agent reaction time (seconds)
    
    # === Surge Events ===
    surge_enabled: bool = False  # Enable sudden surge events
    surge_start_time: float = 300.0  # When surge begins (seconds)
    surge_duration: float = 60.0  # How long surge lasts (seconds)
    surge_multiplier: float = 5.0  # Spawn rate multiplier during surge
    
    # === Exit Control ===
    exit_capacity: float = 2.0  # Agents per second per exit (normal)
    blocked_exits: list = field(default_factory=list)  # List of exit IDs to block
    partial_exit_capacity: dict = field(default_factory=dict)  # {exit_id: capacity_fraction}
    
    # === Path Properties ===
    default_path_width: float = 2.0  # Default width if not specified (meters)
    bidirectional_paths: bool = True  # Allow movement in both directions
    
    # === Random Seed ===
    random_seed: Optional[int] = None  # For deterministic simulation
    
    def __post_init__(self):
        """Initialize random seed for deterministic simulation."""
        if self.random_seed is not None:
            random.seed(self.random_seed)
    
    def get_current_spawn_multiplier(self, current_time: float) -> float:
        """Get the spawn rate multiplier at current simulation time."""
        if self.surge_enabled:
            if self.surge_start_time <= current_time < self.surge_start_time + self.surge_duration:
                return self.spawn_rate_multiplier * self.surge_multiplier
        return self.spawn_rate_multiplier
    
    def is_exit_blocked(self, exit_id: int) -> bool:
        """Check if an exit is blocked."""
        return exit_id in self.blocked_exits
    
    def get_exit_capacity(self, exit_id: int) -> float:
        """Get the effective capacity of an exit."""
        if self.is_exit_blocked(exit_id):
            return 0.0
        return self.exit_capacity * self.partial_exit_capacity.get(exit_id, 1.0)


@dataclass
class ScenarioPresets:
    """Pre-defined scenario configurations for common test cases."""
    
    @staticmethod
    def normal_flow() -> SimulationConfig:
        """Normal steady-state flow scenario."""
        return SimulationConfig(
            spawn_rate_multiplier=1.0,
            max_simulation_time=1800.0
        )
    
    @staticmethod
    def high_density() -> SimulationConfig:
        """High crowd density scenario."""
        return SimulationConfig(
            spawn_rate_multiplier=3.0,
            max_simulation_time=1800.0
        )
    
    @staticmethod
    def sudden_surge() -> SimulationConfig:
        """Sudden crowd surge scenario (e.g., event ending)."""
        return SimulationConfig(
            spawn_rate_multiplier=1.5,
            surge_enabled=True,
            surge_start_time=300.0,
            surge_duration=120.0,
            surge_multiplier=5.0,
            max_simulation_time=1800.0
        )
    
    @staticmethod
    def exit_blocked() -> SimulationConfig:
        """Scenario with one exit blocked."""
        return SimulationConfig(
            spawn_rate_multiplier=2.0,
            blocked_exits=[],  # Populate with actual exit IDs
            max_simulation_time=1800.0
        )
    
    @staticmethod
    def near_stampede() -> SimulationConfig:
        """
        High-risk near-stampede scenario.
        Combines high density, surge, and reduced exit capacity.
        """
        return SimulationConfig(
            spawn_rate_multiplier=4.0,
            surge_enabled=True,
            surge_start_time=180.0,
            surge_duration=180.0,
            surge_multiplier=3.0,
            exit_capacity=1.0,  # Reduced exit flow
            choke_point_speed_factor=0.5,
            max_simulation_time=1800.0
        )
    
    @staticmethod
    def stress_test() -> SimulationConfig:
        """Maximum stress test scenario."""
        return SimulationConfig(
            spawn_rate_multiplier=6.0,
            initial_spawn_burst=100,
            surge_enabled=True,
            surge_start_time=60.0,
            surge_duration=300.0,
            surge_multiplier=4.0,
            exit_capacity=0.5,
            choke_point_speed_factor=0.4,
            max_simulation_time=1800.0
        )

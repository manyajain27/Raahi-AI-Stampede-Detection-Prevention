"""
Main Simulation Module - Orchestrates the crowd simulation.

This is the primary entry point for running crowd simulations.
It coordinates all components: venue, agents, pathfinding, and dynamics.
"""

from typing import Dict, List, Optional, Callable, Generator
from dataclasses import dataclass, field
import random
import time

from .venue import Venue
from .agent import Agent, AgentState, AgentFactory
from .pathfinding import PathFinder
from .dynamics import CrowdDynamics, FlowMetrics, calculate_flow_metrics
from .config import SimulationConfig


@dataclass
class SimulationState:
    """Complete state of the simulation at a point in time."""
    timestamp: float
    agents: Dict[int, Agent]
    metrics: FlowMetrics
    
    # Summary statistics
    total_spawned: int = 0
    total_exited: int = 0
    average_travel_time: float = 0.0


@dataclass 
class SimulationResults:
    """Final results after simulation completes."""
    duration: float
    total_agents_spawned: int
    total_agents_exited: int
    
    # Time series data
    metrics_history: List[FlowMetrics] = field(default_factory=list)
    
    # Peak values
    peak_density: float = 0.0
    peak_agents: int = 0
    min_stability: float = 1.0
    
    # Travel time statistics
    average_travel_time: float = 0.0
    max_travel_time: float = 0.0
    min_travel_time: float = float('inf')
    
    # Congestion events
    congestion_duration: float = 0.0  # Total time with congestion > 50%
    jam_events: int = 0  # Number of times jam density was reached
    
    # Per-choke-point analysis
    choke_point_peaks: Dict[int, float] = field(default_factory=dict)


class SpawnManager:
    """Manages agent spawning at entry points."""
    
    def __init__(self, venue: Venue, config: SimulationConfig, 
                 agent_factory: AgentFactory, pathfinder: PathFinder):
        self.venue = venue
        self.config = config
        self.factory = agent_factory
        self.pathfinder = pathfinder
        
        # Track spawn accumulation (for fractional spawn rates)
        self.spawn_accumulator: Dict[int, float] = {
            entry_id: 0.0 for entry_id in venue.entries
        }
    
    def spawn_agents(self, current_time: float, dt: float) -> List[Agent]:
        """Spawn agents at entry points based on spawn rates."""
        new_agents = []
        
        spawn_multiplier = self.config.get_current_spawn_multiplier(current_time)
        
        for entry_id, entry in self.venue.entries.items():
            if entry.nearest_segment is None:
                continue
            
            # Calculate spawn rate for this timestep
            rate = entry.spawn_rate * spawn_multiplier * dt
            self.spawn_accumulator[entry_id] += rate
            
            # Spawn whole number of agents
            while self.spawn_accumulator[entry_id] >= 1.0:
                self.spawn_accumulator[entry_id] -= 1.0
                
                agent = self._create_agent(entry, current_time)
                if agent is not None:
                    new_agents.append(agent)
        
        return new_agents
    
    def spawn_initial_burst(self, current_time: float) -> List[Agent]:
        """Spawn initial burst of agents if configured."""
        if self.config.initial_spawn_burst <= 0:
            return []
        
        new_agents = []
        entries = list(self.venue.entries.values())
        
        for i in range(self.config.initial_spawn_burst):
            # Round-robin through entries
            entry = entries[i % len(entries)]
            if entry.nearest_segment is None:
                continue
            
            agent = self._create_agent(entry, current_time)
            if agent is not None:
                new_agents.append(agent)
        
        return new_agents
    
    def _create_agent(self, entry, current_time: float) -> Optional[Agent]:
        """Create a single agent at an entry point."""
        # Find best exit
        target_exit = self.pathfinder.find_best_exit(
            entry.nearest_segment,
            self.config.blocked_exits
        )
        
        if target_exit is None:
            return None
        
        # Determine movement direction
        direction = self.pathfinder.get_direction_on_segment(
            entry.nearest_segment, target_exit
        )
        
        agent = self.factory.create_agent(
            segment_id=entry.nearest_segment,
            progress=entry.segment_progress,
            target_exit_id=target_exit,
            direction=direction,
            spawn_time=current_time
        )
        
        # Set initial path
        agent.path = self.pathfinder.get_full_path(
            entry.nearest_segment, target_exit
        )
        
        return agent


class MovementManager:
    """Manages agent movement along paths."""
    
    def __init__(self, venue: Venue, config: SimulationConfig, 
                 pathfinder: PathFinder, dynamics: CrowdDynamics):
        self.venue = venue
        self.config = config
        self.pathfinder = pathfinder
        self.dynamics = dynamics
        self._current_agents: Dict[int, Agent] = {}  # Reference to agents for collision detection
    
    def update_agents(self, agents: Dict[int, Agent], dt: float, 
                     current_time: float) -> List[int]:
        """
        Update all agent positions.
        Returns list of agent IDs that have exited.
        """
        self._current_agents = agents  # Store reference for collision detection
        exited_agents = []
        
        for agent in agents.values():
            if agent.state == AgentState.EXITED:
                continue
            
            # Calculate target speed based on crowd dynamics
            target_speed = self.dynamics.calculate_target_speed(agent)
            
            # Update speed with reaction time
            agent.update_speed(target_speed, self.config.reaction_time, dt)
            
            # Move agent
            exited = self._move_agent(agent, dt, current_time)
            if exited:
                exited_agents.append(agent.id)
        
        return exited_agents
    
    def _move_agent(self, agent: Agent, dt: float, current_time: float) -> bool:
        """
        Move a single agent along its path.
        Returns True if agent has exited.
        """
        segment = self.venue.graph.segments.get(agent.segment_id)
        if segment is None:
            return False
        
        # Skip lane adjustment - just let agents flow
        # self._adjust_lane_position(agent, segment, dt)
        
        # Minimal collision avoidance - only for very close agents
        # Don't slow down too much - let flow continue
        agent_ahead_dist = self._get_distance_to_agent_ahead(agent, segment)
        min_dist = self.config.agent_radius  # 0.25m - physical collision distance
        
        if agent_ahead_dist is not None and agent_ahead_dist < min_dist:
            # Very close - reduce to 50% speed minimum (prevents complete stop)
            agent.current_speed = max(agent.preferred_speed * 0.5, agent.current_speed * 0.8)
        
        # Calculate movement distance
        distance = agent.current_speed * dt
        
        # Convert to progress along segment
        if segment.length > 0:
            progress_delta = distance / segment.length
        else:
            progress_delta = 0
        
        # Apply direction
        new_progress = agent.progress + progress_delta * agent.direction
        
        # Handle segment transitions
        if new_progress >= 1.0:
            # Reached end of segment
            return self._transition_segment(agent, from_end=True, current_time=current_time)
        elif new_progress <= 0.0:
            # Reached start of segment
            return self._transition_segment(agent, from_end=False, current_time=current_time)
        else:
            # Still on same segment
            agent.progress = new_progress
            return False
    
    def _transition_segment(self, agent: Agent, from_end: bool, 
                           current_time: float) -> bool:
        """
        Handle transition from one segment to another.
        Returns True if agent has exited.
        """
        # Check if at exit
        exit_point = self.venue.exits.get(agent.target_exit_id)
        if exit_point and exit_point.nearest_segment == agent.segment_id:
            # Check exit capacity
            exit_capacity = self.config.get_exit_capacity(agent.target_exit_id)
            if exit_capacity > 0:
                agent.state = AgentState.EXITED
                agent.exit_time = current_time
                return True
        
        # Find next segment
        current_segment = self.venue.graph.segments.get(agent.segment_id)
        if current_segment is None:
            return False
        
        # Get connected segments at the appropriate end
        if from_end:
            connected = current_segment.connected_at_end
        else:
            connected = current_segment.connected_at_start
        
        if not connected:
            # Dead end - stay at boundary
            agent.progress = 1.0 if from_end else 0.0
            return False
        
        # Choose next segment (prefer one on path to exit)
        next_seg_id = self._choose_next_segment(agent, connected)
        
        if next_seg_id is None:
            agent.progress = 1.0 if from_end else 0.0
            return False
        
        # Transition to new segment
        next_segment = self.venue.graph.segments.get(next_seg_id)
        if next_segment is None:
            return False
        
        agent.segment_id = next_seg_id
        
        # Determine entry point and direction on new segment
        if current_segment.end.distance_to(next_segment.start) < 0.5:
            agent.progress = 0.0
            agent.direction = 1
        elif current_segment.end.distance_to(next_segment.end) < 0.5:
            agent.progress = 1.0
            agent.direction = -1
        elif current_segment.start.distance_to(next_segment.start) < 0.5:
            agent.progress = 0.0
            agent.direction = 1
        else:
            agent.progress = 1.0
            agent.direction = -1
        
        # Update direction based on path to exit
        ideal_direction = self.pathfinder.get_direction_on_segment(
            next_seg_id, agent.target_exit_id
        )
        agent.direction = ideal_direction
        
        return False
    
    def _choose_next_segment(self, agent: Agent, 
                            connected: List[str]) -> Optional[str]:
        """Choose the best next segment for an agent."""
        if not connected:
            return None
        
        # Prefer segment on path to exit
        best_seg = None
        best_distance = float('inf')
        
        for seg_id in connected:
            distance = self.pathfinder.get_distance_to_exit(
                seg_id, agent.target_exit_id
            )
            if distance < best_distance:
                best_distance = distance
                best_seg = seg_id
        
        return best_seg if best_seg else connected[0]
    
    def _get_distance_to_agent_ahead(self, agent: Agent, segment: 'PathSegment') -> Optional[float]:
        """
        Get distance to the nearest agent ahead that would block this agent.
        Only blocks when agents are very close and directly ahead.
        
        Returns None if no blocking agent is ahead within detection range.
        """
        if not self._current_agents:
            return None
        
        min_distance = None
        agent_progress = agent.progress
        agent_direction = agent.direction
        
        # Much smaller detection range - only worry about very close agents
        min_safe_distance = self.config.agent_radius * 1.5  # ~0.375m
        
        for other_id, other in self._current_agents.items():
            if other_id == agent.id:
                continue
            if other.state == AgentState.EXITED:
                continue
            if other.segment_id != agent.segment_id:
                continue
            
            # Calculate longitudinal distance
            progress_diff = other.progress - agent_progress
            
            if other.direction == agent_direction:
                # Same direction traffic - only check agents directly ahead
                if agent_direction == 1:
                    if progress_diff <= 0:
                        continue  # Behind us
                    distance = progress_diff * segment.length
                else:
                    if progress_diff >= 0:
                        continue  # Behind us
                    distance = abs(progress_diff) * segment.length
                
                # Only block if very close
                if distance > min_safe_distance * 2:
                    continue
                    
            else:
                # Opposite direction traffic - mostly ignore, let lanes handle it
                distance = abs(progress_diff) * segment.length
                
                # Only care if about to collide head-on
                if distance > min_safe_distance:
                    continue
            
            if min_distance is None or distance < min_distance:
                min_distance = distance
        
        return min_distance
    
    def _adjust_lane_position(self, agent: Agent, segment: 'PathSegment', dt: float):
        """
        Adjust agent's lateral position to avoid collisions and maintain lane discipline.
        Implements "keep right" behavior - agents gradually drift to their natural side.
        """
        if not self._current_agents:
            return
        
        # Target lane based on direction (keep-right convention)
        # Direction +1 -> right side (positive offset ~0.5)
        # Direction -1 -> left side (negative offset ~-0.5)
        target_lane = 0.4 * agent.direction  # Reduced from 0.5 for tighter grouping
        
        # Slowly drift toward target lane (simple and predictable)
        lane_adjustment_speed = 0.5 * dt  # Slow adjustment
        
        lane_diff = target_lane - agent.lane_offset
        if abs(lane_diff) > 0.02:
            # Gradually move toward target
            adjustment = max(-lane_adjustment_speed, min(lane_adjustment_speed, lane_diff * 0.5))
            agent.lane_offset += adjustment
        
        # Clamp to valid range
        max_offset = 0.8  # Don't go all the way to edge
        agent.lane_offset = max(-max_offset, min(max_offset, agent.lane_offset))


class CrowdSimulation:
    """
    Main crowd simulation engine.
    
    Orchestrates all simulation components and provides the primary
    interface for running simulations.
    """
    
    def __init__(self, venue: Venue, config: Optional[SimulationConfig] = None):
        """
        Initialize the simulation.
        
        Args:
            venue: Loaded venue data
            config: Simulation configuration (uses defaults if not provided)
        """
        self.venue = venue
        self.config = config or SimulationConfig()
        
        # Initialize random seed for deterministic simulation
        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)
        
        # Initialize components
        self.agent_factory = AgentFactory(
            preferred_speed_mean=self.config.preferred_speed_mean,
            preferred_speed_std=self.config.preferred_speed_std,
            min_speed=self.config.min_speed,
            max_speed=self.config.max_speed
        )
        
        self.pathfinder = PathFinder(venue)
        self.dynamics = CrowdDynamics(venue, self.config)
        
        self.spawn_manager = SpawnManager(
            venue, self.config, self.agent_factory, self.pathfinder
        )
        
        self.movement_manager = MovementManager(
            venue, self.config, self.pathfinder, self.dynamics
        )
        
        # Simulation state
        self.agents: Dict[int, Agent] = {}
        self.current_time: float = 0.0
        self.total_spawned: int = 0
        self.total_exited: int = 0
        self.travel_times: List[float] = []
        
        # Results tracking
        self.metrics_history: List[FlowMetrics] = []
        self._is_running: bool = False
    
    def reset(self):
        """Reset simulation to initial state."""
        self.agents.clear()
        self.current_time = 0.0
        self.total_spawned = 0
        self.total_exited = 0
        self.travel_times.clear()
        self.metrics_history.clear()
        self.agent_factory.reset()
        
        # Re-seed random for reproducibility
        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)
    
    def step(self) -> SimulationState:
        """
        Advance simulation by one timestep.
        
        Returns:
            Current simulation state
        """
        dt = self.config.timestep
        
        # Spawn initial burst at t=0
        if self.current_time == 0.0:
            new_agents = self.spawn_manager.spawn_initial_burst(self.current_time)
            for agent in new_agents:
                self.agents[agent.id] = agent
            self.total_spawned += len(new_agents)
        
        # Spawn new agents
        new_agents = self.spawn_manager.spawn_agents(self.current_time, dt)
        for agent in new_agents:
            self.agents[agent.id] = agent
        self.total_spawned += len(new_agents)
        
        # Update crowd dynamics
        self.dynamics.update_segment_states(self.agents)
        self.dynamics.update_choke_states(self.agents)
        
        # Move agents
        exited = self.movement_manager.update_agents(
            self.agents, dt, self.current_time
        )
        
        # Track exits
        for agent_id in exited:
            agent = self.agents[agent_id]
            if agent.travel_time is not None:
                self.travel_times.append(agent.travel_time)
        self.total_exited += len(exited)
        
        # Advance time
        self.current_time += dt
        
        # Calculate metrics
        metrics = calculate_flow_metrics(
            self.dynamics, self.agents, self.current_time
        )
        self.metrics_history.append(metrics)
        
        # Build state
        avg_travel = (
            sum(self.travel_times) / len(self.travel_times) 
            if self.travel_times else 0.0
        )
        
        return SimulationState(
            timestamp=self.current_time,
            agents=self.agents.copy(),
            metrics=metrics,
            total_spawned=self.total_spawned,
            total_exited=self.total_exited,
            average_travel_time=avg_travel
        )
    
    def run(self, callback: Optional[Callable[[SimulationState], None]] = None,
            metrics_interval: float = 1.0) -> SimulationResults:
        """
        Run the complete simulation.
        
        Args:
            callback: Optional callback called each metrics_interval
            metrics_interval: How often to call callback (seconds)
            
        Returns:
            Complete simulation results
        """
        self.reset()
        self._is_running = True
        
        last_callback_time = 0.0
        
        while self._is_running and self.current_time < self.config.max_simulation_time:
            state = self.step()
            
            # Call callback periodically
            if callback and (self.current_time - last_callback_time) >= metrics_interval:
                callback(state)
                last_callback_time = self.current_time
            
            # Early termination if no agents and past initial phase
            if (self.current_time > 60 and 
                self.total_spawned > 0 and 
                len([a for a in self.agents.values() 
                     if a.state != AgentState.EXITED]) == 0):
                break
        
        self._is_running = False
        return self._compile_results()
    
    def run_generator(self, 
                     metrics_interval: float = 1.0) -> Generator[SimulationState, None, SimulationResults]:
        """
        Run simulation as a generator, yielding states periodically.
        
        Useful for real-time monitoring or integration with other systems.
        
        Yields:
            SimulationState at each metrics_interval
            
        Returns:
            Final SimulationResults
        """
        self.reset()
        self._is_running = True
        
        last_yield_time = 0.0
        
        while self._is_running and self.current_time < self.config.max_simulation_time:
            state = self.step()
            
            # Yield periodically
            if (self.current_time - last_yield_time) >= metrics_interval:
                yield state
                last_yield_time = self.current_time
            
            # Early termination
            if (self.current_time > 60 and 
                self.total_spawned > 0 and 
                len([a for a in self.agents.values() 
                     if a.state != AgentState.EXITED]) == 0):
                break
        
        self._is_running = False
        return self._compile_results()
    
    def stop(self):
        """Stop a running simulation."""
        self._is_running = False
    
    def _compile_results(self) -> SimulationResults:
        """Compile final simulation results."""
        results = SimulationResults(
            duration=self.current_time,
            total_agents_spawned=self.total_spawned,
            total_agents_exited=self.total_exited,
            metrics_history=self.metrics_history
        )
        
        # Calculate peaks and statistics
        for metrics in self.metrics_history:
            results.peak_density = max(results.peak_density, metrics.max_density)
            results.peak_agents = max(results.peak_agents, metrics.total_agents)
            results.min_stability = min(results.min_stability, metrics.min_stability)
            
            if metrics.congestion_severity > 0.5:
                results.congestion_duration += self.config.timestep
        
        # Travel time statistics
        if self.travel_times:
            results.average_travel_time = sum(self.travel_times) / len(self.travel_times)
            results.max_travel_time = max(self.travel_times)
            results.min_travel_time = min(self.travel_times)
        
        # Choke point peaks
        for choke_id in self.venue.choke_points:
            peak = max(
                (m.choke_metrics.get(choke_id, None) for m in self.metrics_history
                 if m.choke_metrics.get(choke_id)),
                key=lambda x: x.max_density_observed if x else 0,
                default=None
            )
            if peak:
                results.choke_point_peaks[choke_id] = peak.max_density_observed
        
        return results
    
    def get_current_metrics(self) -> Optional[FlowMetrics]:
        """Get the most recent flow metrics."""
        if self.metrics_history:
            return self.metrics_history[-1]
        return None
    
    def get_agent_positions(self) -> List[Dict]:
        """
        Get current positions of all active agents.
        
        Returns:
            List of {id, x, y, speed, state} dictionaries
        """
        positions = []
        
        for agent in self.agents.values():
            if agent.state == AgentState.EXITED:
                continue
            
            segment = self.venue.graph.segments.get(agent.segment_id)
            if segment is None:
                continue
            
            pos = segment.get_position_at(agent.progress)
            
            positions.append({
                'id': agent.id,
                'x': pos.x,
                'y': pos.y,
                'speed': agent.current_speed,
                'state': agent.state.value
            })
        
        return positions

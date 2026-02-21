"""
Crowd Dynamics Module - Models crowd behavior and congestion.

This module implements:
- Density-based speed reduction
- Stop-go wave formation
- Choke point effects
- Flow stability metrics
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import math

from .venue import Venue, PathSegment, ChokePoint
from .agent import Agent, AgentState
from .config import SimulationConfig


@dataclass
class SegmentState:
    """Current state of a path segment."""
    segment_id: str
    agent_count: int = 0
    density: float = 0.0  # agents per meter
    average_speed: float = 0.0
    speed_variance: float = 0.0
    flow_rate: float = 0.0  # agents per second passing through
    is_congested: bool = False
    is_jammed: bool = False
    
    # Stop-go wave tracking
    has_stop_wave: bool = False
    wave_position: float = 0.0  # Position of wave front (0-1)


@dataclass
class ChokePointState:
    """Current state of a choke point region."""
    choke_id: int
    name: str
    density: float = 0.0
    average_speed: float = 0.0
    speed_variance: float = 0.0
    flow_rate: float = 0.0
    agent_count: int = 0
    
    # Risk indicators
    congestion_level: float = 0.0  # 0-1 normalized
    stability_index: float = 1.0  # 1 = stable, 0 = unstable
    
    # Historical tracking for trend analysis
    density_history: List[float] = field(default_factory=list)
    max_density_observed: float = 0.0


class CrowdDynamics:
    """
    Manages crowd behavior simulation.
    
    Implements the fundamental diagram of pedestrian flow:
    - At low density: free flow, agents move at preferred speed
    - At moderate density: flow increases, speed decreases
    - At critical density: flow maximizes then decreases
    - At jam density: flow approaches zero
    """
    
    def __init__(self, venue: Venue, config: SimulationConfig):
        self.venue = venue
        self.config = config
        
        # Segment states
        self.segment_states: Dict[str, SegmentState] = {}
        for seg_id in venue.graph.segments:
            self.segment_states[seg_id] = SegmentState(segment_id=seg_id)
        
        # Choke point states
        self.choke_states: Dict[int, ChokePointState] = {}
        for choke_id, choke in venue.choke_points.items():
            self.choke_states[choke_id] = ChokePointState(
                choke_id=choke_id,
                name=choke.name
            )
    
    def update_segment_states(self, agents: Dict[int, Agent]):
        """Update all segment states based on current agent positions."""
        # Reset counts
        for state in self.segment_states.values():
            state.agent_count = 0
        
        # Count agents per segment and collect speeds
        segment_speeds: Dict[str, List[float]] = {seg_id: [] for seg_id in self.segment_states}
        
        for agent in agents.values():
            if agent.state == AgentState.EXITED:
                continue
            
            seg_id = agent.segment_id
            if seg_id in self.segment_states:
                self.segment_states[seg_id].agent_count += 1
                segment_speeds[seg_id].append(agent.current_speed)
        
        # Calculate metrics for each segment
        for seg_id, state in self.segment_states.items():
            segment = self.venue.graph.segments.get(seg_id)
            if segment is None or segment.length == 0:
                continue
            
            speeds = segment_speeds[seg_id]
            
            # Density - use AREA (length * width) for proper density calculation
            segment_area = segment.length * segment.width
            if segment_area > 0:
                state.density = state.agent_count / segment_area  # agents per sq meter
            else:
                state.density = 0
            
            # Speed statistics
            if speeds:
                state.average_speed = sum(speeds) / len(speeds)
                if len(speeds) > 1:
                    mean = state.average_speed
                    state.speed_variance = sum((s - mean)**2 for s in speeds) / len(speeds)
                else:
                    state.speed_variance = 0.0
            else:
                state.average_speed = 0.0
                state.speed_variance = 0.0
            
            # Flow rate (agents * speed / area)
            state.flow_rate = state.density * state.average_speed
            
            # Congestion classification - thresholds for area-based density (per sq meter)
            # Comfortable: < 1 person/m2, Congested: 1-2/m2, Jammed: > 2/m2
            state.is_congested = state.density > 1.0  # More than 1 agent per sq meter
            state.is_jammed = state.density > 2.5  # Critical density
            
            # Stop-go wave detection - threshold for area-based density
            state.has_stop_wave = (
                state.speed_variance > 0.3 and 
                state.density > 1.5  # 1.5 agents per sq meter
            )
    
    def update_choke_states(self, agents: Dict[int, Agent]):
        """Update choke point states."""
        for choke_id, choke in self.venue.choke_points.items():
            state = self.choke_states[choke_id]
            
            # Collect agents in affected segments
            choke_agents: List[Agent] = []
            for seg_id in choke.affected_segments:
                for agent in agents.values():
                    if agent.segment_id == seg_id and agent.state != AgentState.EXITED:
                        choke_agents.append(agent)
            
            state.agent_count = len(choke_agents)
            
            # Calculate area (sum of affected segment areas)
            total_area = sum(
                self.venue.graph.segments[seg_id].length * 
                self.venue.graph.segments[seg_id].width
                for seg_id in choke.affected_segments
                if seg_id in self.venue.graph.segments
            )
            
            if total_area > 0:
                state.density = state.agent_count / total_area
            else:
                state.density = 0.0
            
            # Speed statistics
            if choke_agents:
                speeds = [a.current_speed for a in choke_agents]
                state.average_speed = sum(speeds) / len(speeds)
                if len(speeds) > 1:
                    mean = state.average_speed
                    state.speed_variance = sum((s - mean)**2 for s in speeds) / len(speeds)
                else:
                    state.speed_variance = 0.0
            else:
                state.average_speed = 0.0
                state.speed_variance = 0.0
            
            # Flow rate
            state.flow_rate = state.density * state.average_speed
            
            # Congestion level (normalized 0-1)
            state.congestion_level = min(1.0, state.density / self.config.max_density_per_meter)
            
            # Stability index (based on speed variance and density)
            # Lower variance and lower density = more stable
            variance_factor = 1.0 / (1.0 + state.speed_variance * 5)
            density_factor = 1.0 - min(1.0, state.density / self.config.critical_density)
            state.stability_index = 0.6 * variance_factor + 0.4 * density_factor
            
            # Update history
            state.density_history.append(state.density)
            if len(state.density_history) > 100:
                state.density_history.pop(0)
            
            state.max_density_observed = max(state.max_density_observed, state.density)
    
    def calculate_target_speed(self, agent: Agent) -> float:
        """
        Calculate the target speed for an agent based on local conditions.
        
        Uses density-based speed reduction model.
        Density is area-based (agents per square meter).
        """
        segment = self.venue.graph.segments.get(agent.segment_id)
        if segment is None:
            return agent.preferred_speed
        
        state = self.segment_states.get(agent.segment_id)
        if state is None:
            return agent.preferred_speed
        
        # state.density is already area-based (agents per sq meter)
        # Max comfortable density is about 2-3 people per sq meter (free flow)
        # Critical is 4-5 per sq meter, jam is 6+ per sq meter
        max_area_density = 4.0  # agents per sq meter for jam condition
        
        density_ratio = state.density / max_area_density
        density_ratio = min(1.0, max(0.0, density_ratio))
        
        # Less aggressive speed reduction - linear model
        # At 0 density: 100% speed, at 4/m2: 60% speed
        speed_factor = 1.0 - 0.4 * density_ratio  # Max 40% reduction
        speed_factor = max(0.6, speed_factor)  # Always at least 60% speed
        
        target_speed = agent.preferred_speed * speed_factor
        
        # Apply choke point effects
        target_speed = self._apply_choke_effects(agent, target_speed)
        
        # Apply stop-go wave effects
        target_speed = self._apply_stopgo_effects(agent, state, target_speed)
        
        # Ensure minimum speed (agents don't completely stop unless jammed)
        if state.density < self.config.critical_density:
            target_speed = max(target_speed, self.config.min_speed)
        
        return target_speed
    
    def _apply_choke_effects(self, agent: Agent, speed: float) -> float:
        """Apply speed reduction near choke points - only when actually congested."""
        for choke_id, choke in self.venue.choke_points.items():
            if agent.segment_id in choke.affected_segments:
                choke_state = self.choke_states.get(choke_id)
                if choke_state and choke_state.density > 1.0:  # Only slow if actually congested
                    # Gradual slowdown based on choke congestion level
                    slowdown = 1.0 - (choke_state.congestion_level * 0.3)  # Max 30% reduction
                    speed *= max(0.7, slowdown)
                break
        return speed
    
    def _apply_stopgo_effects(self, agent: Agent, state: SegmentState, 
                              speed: float) -> float:
        """Apply stop-go wave dynamics."""
        if not state.has_stop_wave:
            return speed
        
        # Agents may need to stop if ahead is blocked
        # This creates backward-propagating stop waves
        if state.density > self.config.stop_go_threshold:
            # Random chance of temporary stop based on density
            stop_probability = (state.density - self.config.stop_go_threshold) / 2.0
            stop_probability = min(0.5, stop_probability)
            
            import random
            if random.random() < stop_probability * 0.1:  # Per timestep
                agent.reaction_delay = self.config.reaction_time
                return 0.0
        
        return speed
    
    def get_segment_capacity_factor(self, segment_id: str) -> float:
        """
        Get the available capacity factor for a segment (0-1).
        Used for spawn decisions and path selection.
        """
        state = self.segment_states.get(segment_id)
        if state is None:
            return 1.0
        
        # Reduce capacity near choke points
        capacity = 1.0
        for choke in self.venue.choke_points.values():
            if segment_id in choke.affected_segments:
                capacity *= self.config.choke_point_capacity_factor
        
        # Reduce based on current density
        density_factor = 1.0 - min(1.0, state.density / self.config.max_density_per_meter)
        
        return capacity * density_factor


@dataclass
class FlowMetrics:
    """Aggregate flow metrics for the entire venue."""
    timestamp: float
    total_agents: int
    agents_moving: int
    agents_slowed: int
    agents_stopped: int
    average_speed: float
    total_flow_rate: float
    
    # Per-choke-point metrics
    choke_metrics: Dict[int, ChokePointState] = field(default_factory=dict)
    
    # Risk indicators
    max_density: float = 0.0
    min_stability: float = 1.0
    congestion_severity: float = 0.0  # 0-1 overall congestion


def calculate_flow_metrics(dynamics: CrowdDynamics, 
                          agents: Dict[int, Agent],
                          timestamp: float) -> FlowMetrics:
    """Calculate aggregate flow metrics for the current state."""
    
    active_agents = [a for a in agents.values() if a.state != AgentState.EXITED]
    
    moving = sum(1 for a in active_agents if a.state == AgentState.MOVING)
    slowed = sum(1 for a in active_agents if a.state == AgentState.SLOWED)
    stopped = sum(1 for a in active_agents if a.state == AgentState.STOPPED)
    
    avg_speed = 0.0
    if active_agents:
        avg_speed = sum(a.current_speed for a in active_agents) / len(active_agents)
    
    total_flow = sum(s.flow_rate for s in dynamics.segment_states.values())
    
    # Max density from choke points
    choke_max_density = max(
        (s.density for s in dynamics.choke_states.values()),
        default=0.0
    )
    
    # Also consider segment densities (handles case with no choke points)
    segment_max_density = max(
        (s.density for s in dynamics.segment_states.values()),
        default=0.0
    )
    
    max_density = max(choke_max_density, segment_max_density)
    
    min_stability = min(
        (s.stability_index for s in dynamics.choke_states.values()),
        default=1.0
    )
    
    # Overall congestion severity
    congested_segments = sum(
        1 for s in dynamics.segment_states.values() if s.is_congested
    )
    total_segments = len(dynamics.segment_states)
    congestion_severity = congested_segments / total_segments if total_segments > 0 else 0.0
    
    return FlowMetrics(
        timestamp=timestamp,
        total_agents=len(active_agents),
        agents_moving=moving,
        agents_slowed=slowed,
        agents_stopped=stopped,
        average_speed=avg_speed,
        total_flow_rate=total_flow,
        choke_metrics={cid: state for cid, state in dynamics.choke_states.items()},
        max_density=max_density,
        min_stability=min_stability,
        congestion_severity=congestion_severity
    )

"""
Agent Module - Individual agent representation and behavior.

Each agent represents a person in the simulation with:
- Position on a path segment
- Velocity and movement state
- Target exit
- Interaction with other agents
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from enum import Enum
import random
import math


class AgentState(Enum):
    """Possible states of an agent."""
    SPAWNING = "spawning"  # Just entered, finding path
    MOVING = "moving"  # Normal movement toward exit
    SLOWED = "slowed"  # Slowed due to congestion
    STOPPED = "stopped"  # Completely stopped (high density)
    EXITING = "exiting"  # At exit, being processed
    EXITED = "exited"  # Successfully left venue


@dataclass
class Agent:
    """
    Represents a single person in the crowd simulation.
    """
    
    id: int
    
    # Current position
    segment_id: str  # Current path segment
    progress: float  # Position along segment (0.0 = start, 1.0 = end)
    direction: int  # +1 = toward end, -1 = toward start
    
    # Movement properties
    preferred_speed: float  # Desired walking speed (m/s)
    current_speed: float  # Actual current speed
    
    # Navigation
    target_exit_id: int  # Destination exit
    
    # === Fields with default values must come after non-default fields ===
    
    # Lateral position across corridor width
    # -1.0 = left edge, 0.0 = center, +1.0 = right edge
    # Normalized relative to corridor half-width
    lane_offset: float = 0.0
    
    path: List[str] = field(default_factory=list)  # Planned path of segment IDs
    path_index: int = 0  # Current position in path
    
    # State
    state: AgentState = AgentState.SPAWNING
    spawn_time: float = 0.0  # Simulation time when spawned
    exit_time: Optional[float] = None  # When exited (if exited)
    
    # For stop-go wave dynamics
    last_speed: float = 0.0
    stopped_time: float = 0.0  # How long agent has been stopped
    reaction_delay: float = 0.0  # Remaining reaction time
    
    @property
    def travel_time(self) -> Optional[float]:
        """Time taken to traverse venue (if exited)."""
        if self.exit_time is not None:
            return self.exit_time - self.spawn_time
        return None
    
    def get_world_position(self, segment_start: Tuple[float, float], 
                          segment_end: Tuple[float, float],
                          segment_width: float = 2.0) -> Tuple[float, float]:
        """
        Calculate world position from segment position, including lateral offset.
        
        Args:
            segment_start: (x, y) of segment start
            segment_end: (x, y) of segment end  
            segment_width: Width of the corridor in meters
        """
        # Position along the segment centerline
        center_x = segment_start[0] + self.progress * (segment_end[0] - segment_start[0])
        center_y = segment_start[1] + self.progress * (segment_end[1] - segment_start[1])
        
        # Calculate perpendicular offset for lateral position
        dx = segment_end[0] - segment_start[0]
        dy = segment_end[1] - segment_start[1]
        length = math.sqrt(dx * dx + dy * dy)
        
        if length > 0 and abs(self.lane_offset) > 0.01:
            # Perpendicular unit vector (rotated 90 degrees)
            perp_x = -dy / length
            perp_y = dx / length
            
            # Apply lateral offset - use a small fixed offset for visualization
            # Cap the visual offset to keep agents looking like they're on the path
            max_visual_offset = min(0.15, segment_width * 0.1)  # Max 15cm or 10% of width
            lateral_distance = self.lane_offset * max_visual_offset
            
            return (
                center_x + lateral_distance * perp_x,
                center_y + lateral_distance * perp_y
            )
        
        return (center_x, center_y)
    
    def update_speed(self, target_speed: float, reaction_time: float, dt: float):
        """
        Update speed with reaction time delay.
        This creates more realistic stop-go wave behavior.
        """
        self.last_speed = self.current_speed
        
        if self.reaction_delay > 0:
            self.reaction_delay -= dt
            return
        
        # Gradual speed adjustment
        speed_diff = target_speed - self.current_speed
        max_change = 2.0 * dt  # Max acceleration/deceleration per second
        
        if abs(speed_diff) <= max_change:
            self.current_speed = target_speed
        else:
            self.current_speed += max_change * (1 if speed_diff > 0 else -1)
        
        # Update state based on speed
        if self.current_speed < 0.05:
            self.state = AgentState.STOPPED
            self.stopped_time += dt
        elif self.current_speed < self.preferred_speed * 0.5:
            self.state = AgentState.SLOWED
            self.stopped_time = 0.0
        else:
            self.state = AgentState.MOVING
            self.stopped_time = 0.0


class AgentFactory:
    """Factory for creating agents with configurable properties."""
    
    def __init__(self, preferred_speed_mean: float = 1.4, 
                 preferred_speed_std: float = 0.3,
                 min_speed: float = 0.1,
                 max_speed: float = 2.5):
        self.preferred_speed_mean = preferred_speed_mean
        self.preferred_speed_std = preferred_speed_std
        self.min_speed = min_speed
        self.max_speed = max_speed
        self._next_id = 0
    
    def create_agent(self, segment_id: str, progress: float, 
                    target_exit_id: int, direction: int = 1,
                    spawn_time: float = 0.0) -> Agent:
        """Create a new agent with randomized properties."""
        
        # Generate preferred speed from normal distribution
        preferred_speed = random.gauss(self.preferred_speed_mean, self.preferred_speed_std)
        preferred_speed = max(self.min_speed, min(self.max_speed, preferred_speed))
        
        # Assign lane based on direction (keep-right convention)
        # Direction +1 (toward end) -> right side (positive offset)
        # Direction -1 (toward start) -> left side (negative offset)
        # Add small random variation to prevent perfect alignment
        base_lane = 0.3 * direction  # +0.3 or -0.3 (reduced from 0.5)
        lane_variation = random.uniform(-0.15, 0.15)  # Smaller variation
        lane_offset = max(-0.8, min(0.8, base_lane + lane_variation))
        
        agent = Agent(
            id=self._next_id,
            segment_id=segment_id,
            progress=progress,
            direction=direction,
            lane_offset=lane_offset,
            preferred_speed=preferred_speed,
            current_speed=preferred_speed,
            target_exit_id=target_exit_id,
            spawn_time=spawn_time
        )
        
        self._next_id += 1
        return agent
    
    def reset(self):
        """Reset the factory state."""
        self._next_id = 0

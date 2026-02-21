"""
Pathfinding Module - Route planning for agents.

Implements graph-based pathfinding to find optimal routes
from spawn points to exits.
"""

from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
import heapq

from .venue import Venue, PathSegment, Point


class PathFinder:
    """
    Pathfinding engine for the venue graph.
    
    Uses A* algorithm to find shortest paths from any segment to exits.
    Pre-computes paths for efficiency during simulation.
    """
    
    def __init__(self, venue: Venue):
        self.venue = venue
        self.graph = venue.graph
        
        # Pre-computed distances to each exit from each segment
        # {exit_id: {segment_id: (distance, next_segment_id)}}
        self.exit_paths: Dict[int, Dict[str, Tuple[float, Optional[str]]]] = {}
        
        # Pre-compute all paths
        self._precompute_paths()
    
    def _precompute_paths(self):
        """Pre-compute shortest paths from all segments to all exits."""
        for exit_id, exit_point in self.venue.exits.items():
            self.exit_paths[exit_id] = self._compute_paths_to_exit(exit_id)
    
    def _compute_paths_to_exit(self, exit_id: int) -> Dict[str, Tuple[float, Optional[str]]]:
        """
        Compute shortest paths from all segments to a specific exit.
        Uses Dijkstra's algorithm working backwards from the exit.
        
        Returns: {segment_id: (total_distance, next_segment_toward_exit)}
        """
        exit_point = self.venue.exits[exit_id]
        target_segment = exit_point.nearest_segment
        
        if target_segment is None:
            return {}
        
        # Distance from segment to exit
        distances: Dict[str, float] = {}
        # Next hop toward exit
        next_hop: Dict[str, Optional[str]] = {}
        
        # Priority queue: (distance, segment_id)
        pq = [(0.0, target_segment)]
        distances[target_segment] = 0.0
        next_hop[target_segment] = None  # At the exit
        
        visited: Set[str] = set()
        
        while pq:
            dist, current = heapq.heappop(pq)
            
            if current in visited:
                continue
            visited.add(current)
            
            # Explore neighbors
            segment = self.graph.segments.get(current)
            if segment is None:
                continue
            
            neighbors = self.graph.get_neighbors(current)
            
            for neighbor_id in neighbors:
                if neighbor_id in visited:
                    continue
                
                neighbor = self.graph.segments.get(neighbor_id)
                if neighbor is None:
                    continue
                
                # Cost is the length of the neighbor segment
                new_dist = dist + neighbor.length
                
                if neighbor_id not in distances or new_dist < distances[neighbor_id]:
                    distances[neighbor_id] = new_dist
                    next_hop[neighbor_id] = current
                    heapq.heappush(pq, (new_dist, neighbor_id))
        
        # Combine into result
        result = {}
        for seg_id in self.graph.segments:
            if seg_id in distances:
                result[seg_id] = (distances[seg_id], next_hop[seg_id])
            else:
                # Unreachable
                result[seg_id] = (float('inf'), None)
        
        return result
    
    def get_distance_to_exit(self, segment_id: str, exit_id: int) -> float:
        """Get the distance from a segment to an exit."""
        if exit_id not in self.exit_paths:
            return float('inf')
        
        paths = self.exit_paths[exit_id]
        if segment_id not in paths:
            return float('inf')
        
        return paths[segment_id][0]
    
    def get_next_segment(self, segment_id: str, exit_id: int) -> Optional[str]:
        """Get the next segment to move to when heading to an exit."""
        if exit_id not in self.exit_paths:
            return None
        
        paths = self.exit_paths[exit_id]
        if segment_id not in paths:
            return None
        
        return paths[segment_id][1]
    
    def get_full_path(self, start_segment: str, exit_id: int) -> List[str]:
        """Get the complete path from a segment to an exit."""
        path = [start_segment]
        current = start_segment
        
        visited = set()
        while current is not None:
            if current in visited:
                break  # Avoid infinite loops
            visited.add(current)
            
            next_seg = self.get_next_segment(current, exit_id)
            if next_seg is None:
                break
            
            path.append(next_seg)
            current = next_seg
        
        return path
    
    def find_best_exit(self, segment_id: str, 
                       blocked_exits: List[int] = None,
                       use_probabilistic: bool = True) -> Optional[int]:
        """
        Find a good exit from a segment, with optional probabilistic selection
        to distribute crowd load across multiple exits.
        
        Args:
            segment_id: Current segment
            blocked_exits: List of exit IDs that are blocked
            use_probabilistic: If True, select exit probabilistically based on distance
            
        Returns:
            Selected exit ID, or None if no exits reachable
        """
        import random
        blocked_exits = blocked_exits or []
        
        # Collect all reachable exits with their distances
        exit_distances = []
        for exit_id in self.venue.exits:
            if exit_id in blocked_exits:
                continue
            
            distance = self.get_distance_to_exit(segment_id, exit_id)
            if distance < float('inf'):
                exit_distances.append((exit_id, distance))
        
        if not exit_distances:
            return None
        
        if not use_probabilistic or len(exit_distances) == 1:
            # Return closest exit
            return min(exit_distances, key=lambda x: x[1])[0]
        
        # Probabilistic selection: closer exits have higher probability
        # Use inverse distance as weight, with softmax-like normalization
        min_dist = min(d for _, d in exit_distances)
        
        # Weight = exp(-distance_ratio), so closer exits get higher weight
        weights = []
        for exit_id, dist in exit_distances:
            # Normalize distance ratio and apply exponential weighting
            dist_ratio = dist / min_dist if min_dist > 0 else 1.0
            # Weight decreases exponentially with distance ratio
            weight = 1.0 / (dist_ratio ** 1.5)  # Closer exits strongly preferred
            weights.append(weight)
        
        # Normalize weights to probabilities
        total_weight = sum(weights)
        if total_weight <= 0:
            return exit_distances[0][0]
        
        probabilities = [w / total_weight for w in weights]
        
        # Select exit based on probabilities
        r = random.random()
        cumulative = 0.0
        for i, (exit_id, _) in enumerate(exit_distances):
            cumulative += probabilities[i]
            if r <= cumulative:
                return exit_id
        
        return exit_distances[-1][0]
    
    def get_direction_on_segment(self, segment_id: str, exit_id: int) -> int:
        """
        Determine which direction to move on a segment to reach an exit.
        
        Returns: +1 (toward end) or -1 (toward start)
        """
        segment = self.graph.segments.get(segment_id)
        if segment is None:
            return 1
        
        next_seg = self.get_next_segment(segment_id, exit_id)
        if next_seg is None:
            # At exit segment, check where exit is
            exit_point = self.venue.exits.get(exit_id)
            if exit_point and exit_point.nearest_segment == segment_id:
                if exit_point.segment_progress > 0.5:
                    return 1
                else:
                    return -1
            return 1
        
        # Check which end connects to next segment
        if next_seg in segment.connected_at_end:
            return 1  # Move toward end
        elif next_seg in segment.connected_at_start:
            return -1  # Move toward start
        
        return 1  # Default

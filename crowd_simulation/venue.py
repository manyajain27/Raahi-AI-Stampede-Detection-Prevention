"""
Venue Module - Loads and represents venue data from YAML files.

This module handles:
- Loading venue YAML files (indoor and outdoor)
- Converting raw coordinates to a navigable path graph
- Managing pathways, entry points, exits, choke points, and joints
"""

import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
import math


@dataclass
class Point:
    """A 2D point in the venue coordinate system."""
    x: float
    y: float
    
    def distance_to(self, other: 'Point') -> float:
        """Calculate Euclidean distance to another point."""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
    
    def __hash__(self):
        return hash((round(self.x, 2), round(self.y, 2)))
    
    def __eq__(self, other):
        if not isinstance(other, Point):
            return False
        return abs(self.x - other.x) < 0.01 and abs(self.y - other.y) < 0.01


@dataclass
class PathSegment:
    """
    A single segment of a pathway between two points.
    Agents move along these segments.
    """
    id: str  # Unique segment ID: "pathway_id-segment_index"
    pathway_id: int
    start: Point
    end: Point
    width: float  # Width in meters
    
    # Connected segments at each end
    connected_at_start: List[str] = field(default_factory=list)
    connected_at_end: List[str] = field(default_factory=list)
    
    # Runtime state
    agents: List[int] = field(default_factory=list)  # Agent IDs on this segment
    length: float = field(init=False)  # Calculated in __post_init__
    
    def __post_init__(self):
        self.length = self.start.distance_to(self.end)
    
    @property
    def direction(self) -> Tuple[float, float]:
        """Unit direction vector from start to end."""
        if self.length == 0:
            return (0.0, 0.0)
        return (
            (self.end.x - self.start.x) / self.length,
            (self.end.y - self.start.y) / self.length
        )
    
    @property
    def capacity(self) -> float:
        """Maximum number of agents this segment can hold."""
        # Based on width and length, assuming ~2 agents per square meter max
        return self.width * self.length * 2
    
    def get_density(self) -> float:
        """Current density (agents per meter of length)."""
        if self.length == 0:
            return 0.0
        return len(self.agents) / self.length
    
    def get_position_at(self, progress: float) -> Point:
        """Get world position at given progress (0.0 to 1.0) along segment."""
        return Point(
            self.start.x + progress * (self.end.x - self.start.x),
            self.start.y + progress * (self.end.y - self.start.y)
        )


@dataclass
class Pathway:
    """A complete pathway consisting of multiple connected segments."""
    id: int
    name: str
    width: float
    points: List[Point]
    segments: List[PathSegment] = field(default_factory=list)
    
    @property
    def total_length(self) -> float:
        return sum(seg.length for seg in self.segments)


@dataclass
class EntryPoint:
    """A spawn point where agents enter the venue."""
    id: int
    name: str
    position: Point
    spawn_rate: float  # Agents per second (base rate)
    nearest_segment: Optional[str] = None  # Segment ID where agents spawn
    segment_progress: float = 0.0  # Position along the segment (0-1)


@dataclass
class ExitPoint:
    """A destination where agents leave the venue."""
    id: int
    name: str
    position: Point
    exit_rate: float  # Processing rate
    nearest_segment: Optional[str] = None
    segment_progress: float = 1.0


@dataclass
class ChokePoint:
    """A region of interest for monitoring congestion."""
    id: int
    name: str
    position: Point
    radius: float = 3.0  # Influence radius in meters
    affected_segments: List[str] = field(default_factory=list)


@dataclass
class Joint:
    """An intersection where multiple pathways connect."""
    id: int
    name: str
    position: Point
    connected_pathways: List[int]
    connected_segments: List[str] = field(default_factory=list)


class PathGraph:
    """
    A graph representation of the venue's navigable paths.
    
    Nodes: Segment endpoints and connection points
    Edges: Path segments
    """
    
    def __init__(self):
        self.segments: Dict[str, PathSegment] = {}
        self.adjacency: Dict[str, Set[str]] = {}  # segment_id -> connected segment_ids
        self.node_segments: Dict[Point, List[str]] = {}  # point -> segments at that point
    
    def add_segment(self, segment: PathSegment):
        """Add a segment to the graph."""
        self.segments[segment.id] = segment
        self.adjacency[segment.id] = set()
        
        # Index by endpoints
        for point in [segment.start, segment.end]:
            if point not in self.node_segments:
                self.node_segments[point] = []
            self.node_segments[point].append(segment.id)
    
    def connect_segments(self):
        """Establish connections between segments that share endpoints."""
        for point, segment_ids in self.node_segments.items():
            for i, seg_id1 in enumerate(segment_ids):
                for seg_id2 in segment_ids[i+1:]:
                    self.adjacency[seg_id1].add(seg_id2)
                    self.adjacency[seg_id2].add(seg_id1)
                    
                    # Update segment connection lists
                    seg1 = self.segments[seg_id1]
                    seg2 = self.segments[seg_id2]
                    
                    if point == seg1.start or point == seg1.end:
                        if point == seg1.start:
                            seg1.connected_at_start.append(seg_id2)
                        else:
                            seg1.connected_at_end.append(seg_id2)
                    
                    if point == seg2.start or point == seg2.end:
                        if point == seg2.start:
                            seg2.connected_at_start.append(seg_id1)
                        else:
                            seg2.connected_at_end.append(seg_id1)
    
    def get_neighbors(self, segment_id: str) -> List[str]:
        """Get all segments connected to the given segment."""
        return list(self.adjacency.get(segment_id, set()))
    
    def find_nearest_segment(self, point: Point) -> Tuple[Optional[str], float]:
        """
        Find the nearest segment to a point.
        Returns (segment_id, progress_along_segment).
        """
        min_dist = float('inf')
        nearest_seg = None
        nearest_progress = 0.0
        
        for seg_id, segment in self.segments.items():
            dist, progress = self._point_to_segment_distance(point, segment)
            if dist < min_dist:
                min_dist = dist
                nearest_seg = seg_id
                nearest_progress = progress
        
        return nearest_seg, nearest_progress
    
    def _point_to_segment_distance(self, point: Point, segment: PathSegment) -> Tuple[float, float]:
        """
        Calculate distance from point to segment and progress along segment.
        Returns (distance, progress 0-1).
        """
        if segment.length == 0:
            return point.distance_to(segment.start), 0.0
        
        # Vector from start to end
        dx = segment.end.x - segment.start.x
        dy = segment.end.y - segment.start.y
        
        # Vector from start to point
        px = point.x - segment.start.x
        py = point.y - segment.start.y
        
        # Project point onto line
        t = max(0, min(1, (px * dx + py * dy) / (segment.length ** 2)))
        
        # Closest point on segment
        closest = Point(
            segment.start.x + t * dx,
            segment.start.y + t * dy
        )
        
        return point.distance_to(closest), t


class Venue:
    """
    Complete venue representation loaded from YAML.
    """
    
    def __init__(self):
        self.type: str = "indoor"  # "indoor" or "outdoor"
        self.pixels_per_meter: float = 50.0
        self.origin: Optional[Point] = None  # For outdoor venues
        self.max_capacity: int = 1000
        self.expected_attendance: int = 500
        
        self.pathways: Dict[int, Pathway] = {}
        self.entries: Dict[int, EntryPoint] = {}
        self.exits: Dict[int, ExitPoint] = {}
        self.choke_points: Dict[int, ChokePoint] = {}
        self.joints: Dict[int, Joint] = {}
        
        self.graph: PathGraph = PathGraph()
    
    @classmethod
    def from_yaml(cls, filepath: str) -> 'Venue':
        """Load a venue from a YAML file."""
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        
        venue = cls()
        venue._parse_yaml(data)
        venue._build_graph()
        venue._link_entries_exits()
        venue._identify_choke_segments()
        
        return venue
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Venue':
        """Load a venue from a dictionary."""
        venue = cls()
        venue._parse_yaml(data)
        venue._build_graph()
        venue._link_entries_exits()
        venue._identify_choke_segments()
        
        return venue
    
    def _parse_yaml(self, data: dict):
        """Parse YAML data into venue structures."""
        self.type = data.get('type', 'indoor')
        self.pixels_per_meter = data.get('pixelsPerMeter', 50.0)
        
        self.max_capacity = data.get('maxCapacity', 1000)
        self.expected_attendance = data.get('expectedAttendance', 500)
        
        # Handle outdoor origin
        if 'origin' in data:
            self.origin = Point(data['origin'].get('lat', 0), data['origin'].get('lng', 0))
        
        # Parse pathways
        for p_data in (data.get('pathways') or []):
            points = [
                self._convert_point(pt) 
                for pt in p_data.get('points', [])
            ]
            pathway = Pathway(
                id=p_data['id'],
                name=p_data.get('name', f"Pathway {p_data['id']}"),
                width=p_data.get('width', 2.0),
                points=points
            )
            self.pathways[pathway.id] = pathway
        
        # Parse entries
        for e_data in (data.get('entries') or []):
            entry = EntryPoint(
                id=e_data['id'],
                name=e_data.get('name', f"Entry {e_data['id']}"),
                position=self._convert_point(e_data),
                spawn_rate=e_data.get('spawnRate', 1.0)
            )
            self.entries[entry.id] = entry
        
        # Parse exits
        for e_data in (data.get('exits') or []):
            exit_point = ExitPoint(
                id=e_data['id'],
                name=e_data.get('name', f"Exit {e_data['id']}"),
                position=self._convert_point(e_data),
                exit_rate=e_data.get('exitRate', 1.0)
            )
            self.exits[exit_point.id] = exit_point
        
        # Parse choke points
        for c_data in (data.get('chokePoints') or []):
            choke = ChokePoint(
                id=c_data['id'],
                name=c_data.get('name', f"Choke {c_data['id']}"),
                position=self._convert_point(c_data)
            )
            self.choke_points[choke.id] = choke
        
        # Parse joints
        for j_data in (data.get('joints') or []):
            joint = Joint(
                id=j_data['id'],
                name=j_data.get('name', f"Joint {j_data['id']}"),
                position=self._convert_point(j_data),
                connected_pathways=j_data.get('connectedPathways', [])
            )
            self.joints[joint.id] = joint
    
    def _convert_point(self, data: dict) -> Point:
        """Convert coordinate data to Point, applying unit conversion."""
        x = data.get('x', 0)
        y = data.get('y', 0)
        
        # Convert pixels to meters for indoor venues
        if self.type == 'indoor' and self.pixels_per_meter > 0:
            x = x / self.pixels_per_meter
            y = y / self.pixels_per_meter
        
        return Point(x, y)
    
    def _point_on_segment(self, point: Point, start: Point, end: Point, tolerance: float = 0.1) -> Tuple[bool, float]:
        """
        Check if a point lies on a segment (not at endpoints).
        Returns (is_on_segment, progress_along_segment).
        """
        # Vector from start to end
        dx = end.x - start.x
        dy = end.y - start.y
        length_sq = dx * dx + dy * dy
        
        if length_sq == 0:
            return False, 0.0
        
        # Parameter t for projection of point onto line
        t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_sq
        
        # Check if projection falls within segment (not at endpoints)
        if t <= tolerance / (length_sq ** 0.5) or t >= 1 - tolerance / (length_sq ** 0.5):
            return False, t
        
        # Calculate closest point on segment
        closest_x = start.x + t * dx
        closest_y = start.y + t * dy
        
        # Check distance from point to closest point on segment
        dist = ((point.x - closest_x) ** 2 + (point.y - closest_y) ** 2) ** 0.5
        
        if dist < tolerance:
            return True, t
        
        return False, t
    
    def _build_graph(self):
        """Build the path graph from pathways, splitting segments at joints."""
        # First, collect all joint positions (already converted to meters)
        joint_positions = {jid: joint.position for jid, joint in self.joints.items()}
        
        # Tolerance for point matching (in meters for indoor, degrees for outdoor)
        tolerance = 0.5 if self.type == 'indoor' else 0.00001
        
        # Build initial segments, splitting at joints where necessary
        for pathway_id, pathway in self.pathways.items():
            points = pathway.points
            segment_counter = 0
            
            for i in range(len(points) - 1):
                start_point = points[i]
                end_point = points[i + 1]
                
                # Check if any joints lie on this segment
                joints_on_segment = []
                for jid, jpos in joint_positions.items():
                    on_seg, progress = self._point_on_segment(jpos, start_point, end_point, tolerance)
                    if on_seg:
                        joints_on_segment.append((progress, jpos, jid))
                
                # Sort joints by progress along segment
                joints_on_segment.sort(key=lambda x: x[0])
                
                # Create segments, splitting at joints
                current_start = start_point
                for progress, jpos, jid in joints_on_segment:
                    # Create segment from current_start to joint position
                    segment = PathSegment(
                        id=f"{pathway_id}-{segment_counter}",
                        pathway_id=pathway_id,
                        start=current_start,
                        end=jpos,
                        width=pathway.width
                    )
                    if segment.length > 0.01:  # Only add non-trivial segments
                        pathway.segments.append(segment)
                        self.graph.add_segment(segment)
                        segment_counter += 1
                    
                    current_start = jpos
                
                # Create final segment from last joint (or start) to end
                segment = PathSegment(
                    id=f"{pathway_id}-{segment_counter}",
                    pathway_id=pathway_id,
                    start=current_start,
                    end=end_point,
                    width=pathway.width
                )
                if segment.length > 0.01:  # Only add non-trivial segments
                    pathway.segments.append(segment)
                    self.graph.add_segment(segment)
                    segment_counter += 1
        
        # Connect segments at shared points
        self.graph.connect_segments()
        
        # Also connect segments at joint positions (handles case where joint
        # is at segment endpoints from different pathways)
        for joint in self.joints.values():
            joint_segments = []
            
            for seg_id, segment in self.graph.segments.items():
                dist_to_start = segment.start.distance_to(joint.position)
                dist_to_end = segment.end.distance_to(joint.position)
                
                if dist_to_start < tolerance or dist_to_end < tolerance:
                    joint_segments.append(seg_id)
            
            joint.connected_segments = joint_segments
            
            # Connect all segments that meet at this joint
            for i, seg_id1 in enumerate(joint_segments):
                for seg_id2 in joint_segments[i+1:]:
                    self.graph.adjacency[seg_id1].add(seg_id2)
                    self.graph.adjacency[seg_id2].add(seg_id1)
                    
                    seg1 = self.graph.segments[seg_id1]
                    seg2 = self.graph.segments[seg_id2]
                    
                    if seg1.start.distance_to(joint.position) < tolerance:
                        if seg_id2 not in seg1.connected_at_start:
                            seg1.connected_at_start.append(seg_id2)
                    else:
                        if seg_id2 not in seg1.connected_at_end:
                            seg1.connected_at_end.append(seg_id2)
                    
                    if seg2.start.distance_to(joint.position) < tolerance:
                        if seg_id1 not in seg2.connected_at_start:
                            seg2.connected_at_start.append(seg_id1)
                    else:
                        if seg_id1 not in seg2.connected_at_end:
                            seg2.connected_at_end.append(seg_id1)
    
    def _link_entries_exits(self):
        """Link entries and exits to their nearest path segments."""
        for entry in self.entries.values():
            seg_id, progress = self.graph.find_nearest_segment(entry.position)
            entry.nearest_segment = seg_id
            entry.segment_progress = progress
        
        for exit_point in self.exits.values():
            seg_id, progress = self.graph.find_nearest_segment(exit_point.position)
            exit_point.nearest_segment = seg_id
            exit_point.segment_progress = progress
    
    def _identify_choke_segments(self):
        """Identify which segments are affected by choke points."""
        for choke in self.choke_points.values():
            for seg_id, segment in self.graph.segments.items():
                # Check if segment passes through choke point radius
                dist, _ = self.graph._point_to_segment_distance(choke.position, segment)
                if dist <= choke.radius:
                    choke.affected_segments.append(seg_id)
    
    def get_all_segment_ids(self) -> List[str]:
        """Get all segment IDs in the venue."""
        return list(self.graph.segments.keys())
    
    def get_segment(self, segment_id: str) -> Optional[PathSegment]:
        """Get a segment by ID."""
        return self.graph.segments.get(segment_id)
    
    def get_exit_segments(self) -> Dict[int, str]:
        """Get mapping of exit IDs to their nearest segment IDs."""
        return {exit_id: e.nearest_segment for exit_id, e in self.exits.items()}

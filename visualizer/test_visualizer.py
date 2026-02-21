"""
Comprehensive Tests for the Crowd Simulation Visualizer

Tests cover:
1. Venue loading and data extraction
2. Simulation lifecycle (start, pause, stop, reset)
3. WebSocket message formats
4. API endpoints
5. Frame building and metrics
6. Concurrent access and thread safety
"""

import pytest
import sys
import json
import time
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask
from flask_socketio import SocketIO, SocketIOTestClient


class TestVisualizerImports:
    """Test that all required modules can be imported."""
    
    def test_import_app(self):
        """Test main app imports correctly."""
        from app import app, socketio, sim_manager
        assert app is not None
        assert socketio is not None
        assert sim_manager is not None
    
    def test_import_crowd_simulation(self):
        """Test crowd simulation module imports."""
        from crowd_simulation import CrowdSimulation, Venue, SimulationConfig
        assert CrowdSimulation is not None
        assert Venue is not None
        assert SimulationConfig is not None
    
    def test_import_scenario_presets(self):
        """Test scenario presets are available."""
        from crowd_simulation.config import ScenarioPresets
        assert hasattr(ScenarioPresets, 'normal_flow')
        assert hasattr(ScenarioPresets, 'high_density')
        assert hasattr(ScenarioPresets, 'sudden_surge')
        assert hasattr(ScenarioPresets, 'near_stampede')
        assert hasattr(ScenarioPresets, 'stress_test')


class TestVenueLoading:
    """Test venue file loading functionality."""
    
    @pytest.fixture
    def venue_path(self):
        """Path to test venue file."""
        return str(Path(__file__).parent.parent / 'floor_plan.yaml')
    
    @pytest.fixture
    def sim_manager(self):
        """Fresh simulation manager instance."""
        from app import SimulationManager
        return SimulationManager()
    
    def test_load_venue_success(self, sim_manager, venue_path):
        """Test successful venue loading."""
        venue_data = sim_manager.load_venue(venue_path)
        
        assert venue_data is not None
        assert 'type' in venue_data
        assert venue_data['type'] == 'venue_data'
        assert 'bounds' in venue_data
        assert 'roads' in venue_data
        assert 'entries' in venue_data
        assert 'exits' in venue_data
        assert 'choke_points' in venue_data
    
    def test_load_venue_sets_venue(self, sim_manager, venue_path):
        """Test that loading venue sets internal venue object."""
        sim_manager.load_venue(venue_path)
        assert sim_manager.venue is not None
        assert sim_manager.venue_path == venue_path
    
    def test_venue_data_structure(self, sim_manager, venue_path):
        """Test venue data has correct structure."""
        venue_data = sim_manager.load_venue(venue_path)
        
        # Check bounds
        bounds = venue_data['bounds']
        assert 'min_x' in bounds
        assert 'max_x' in bounds
        assert 'min_y' in bounds
        assert 'max_y' in bounds
        
        # Check roads
        assert len(venue_data['roads']) > 0
        road = venue_data['roads'][0]
        assert 'id' in road
        assert 'points' in road
        assert 'width' in road
        
        # Check entries
        assert len(venue_data['entries']) > 0
        entry = venue_data['entries'][0]
        assert 'id' in entry
        assert 'name' in entry
        assert 'x' in entry
        assert 'y' in entry
        
        # Check exits
        assert len(venue_data['exits']) > 0
        exit_point = venue_data['exits'][0]
        assert 'id' in exit_point
        assert 'name' in exit_point
        
        # Check choke points
        assert len(venue_data['choke_points']) > 0
        choke = venue_data['choke_points'][0]
        assert 'id' in choke
        assert 'name' in choke
        assert 'radius' in choke
    
    def test_load_nonexistent_venue(self, sim_manager):
        """Test loading nonexistent file raises error."""
        with pytest.raises(Exception):
            sim_manager.load_venue('/nonexistent/path.yaml')


class TestSimulationLifecycle:
    """Test simulation start/stop/pause/reset operations."""
    
    @pytest.fixture
    def venue_path(self):
        return str(Path(__file__).parent.parent / 'floor_plan.yaml')
    
    @pytest.fixture
    def sim_manager(self, venue_path):
        from app import SimulationManager
        manager = SimulationManager()
        manager.load_venue(venue_path)
        yield manager
        # Cleanup
        manager.stop()
    
    def test_start_without_venue(self):
        """Test starting simulation without loading venue fails."""
        from app import SimulationManager
        manager = SimulationManager()
        result = manager.start()
        assert result == False
    
    def test_start_with_venue(self, sim_manager):
        """Test starting simulation with loaded venue."""
        result = sim_manager.start(scenario='normal', speed=10.0)
        assert result == True
        assert sim_manager.running == True
        assert sim_manager.simulation is not None
    
    def test_start_all_scenarios(self, sim_manager):
        """Test starting simulation with all scenario presets."""
        scenarios = ['normal', 'high_density', 'surge', 'near_stampede', 'stress_test']
        
        for scenario in scenarios:
            sim_manager.reset()
            result = sim_manager.start(scenario=scenario, speed=10.0)
            assert result == True, f"Failed to start scenario: {scenario}"
            assert sim_manager.running == True
            sim_manager.stop()
    
    def test_stop_simulation(self, sim_manager):
        """Test stopping simulation."""
        sim_manager.start(speed=10.0)
        time.sleep(0.1)
        
        sim_manager.stop()
        
        assert sim_manager.running == False
    
    def test_pause_simulation(self, sim_manager):
        """Test pausing and resuming simulation."""
        sim_manager.start(speed=10.0)
        time.sleep(0.1)
        
        # Pause
        paused = sim_manager.pause()
        assert paused == True
        assert sim_manager.paused == True
        
        # Resume
        paused = sim_manager.pause()
        assert paused == False
        assert sim_manager.paused == False
    
    def test_reset_simulation(self, sim_manager):
        """Test resetting simulation."""
        sim_manager.start(speed=10.0)
        time.sleep(0.1)
        
        sim_manager.reset()
        
        assert sim_manager.running == False
        assert sim_manager.simulation is None
        assert sim_manager.venue is not None  # Venue should remain loaded
    
    def test_speed_control(self, sim_manager):
        """Test simulation speed control."""
        sim_manager.set_speed(2.0)
        assert sim_manager.speed == 2.0
        
        sim_manager.set_speed(0.5)
        assert sim_manager.speed == 0.5
        
        # Test bounds
        sim_manager.set_speed(0.01)  # Below min
        assert sim_manager.speed == 0.1
        
        sim_manager.set_speed(100.0)  # Above max
        assert sim_manager.speed == 10.0
    
    def test_double_start_fails(self, sim_manager):
        """Test that starting already running simulation fails."""
        result1 = sim_manager.start(speed=10.0)
        assert result1 == True
        
        result2 = sim_manager.start()
        assert result2 == False


class TestFrameBuilding:
    """Test simulation frame building for WebSocket."""
    
    @pytest.fixture
    def venue_path(self):
        return str(Path(__file__).parent.parent / 'floor_plan.yaml')
    
    @pytest.fixture
    def sim_manager(self, venue_path):
        from app import SimulationManager
        manager = SimulationManager()
        manager.load_venue(venue_path)
        yield manager
        manager.stop()
    
    def test_build_frame_structure(self, sim_manager):
        """Test frame has correct structure."""
        sim_manager.start(scenario='normal', speed=10.0)
        time.sleep(0.3)  # Let simulation run a bit
        
        # Get a frame by stepping simulation manually
        with sim_manager.lock:
            state = sim_manager.simulation.step()
            frame = sim_manager._build_frame(state)
        
        assert 'type' in frame
        assert frame['type'] == 'frame'
        assert 'time' in frame
        assert 'agents' in frame
        assert 'metrics' in frame
        assert 'choke_risks' in frame
    
    def test_frame_metrics_structure(self, sim_manager):
        """Test frame metrics have correct fields."""
        sim_manager.start(scenario='normal', speed=10.0)
        time.sleep(0.3)
        
        with sim_manager.lock:
            state = sim_manager.simulation.step()
            frame = sim_manager._build_frame(state)
        
        metrics = frame['metrics']
        assert 'total' in metrics
        assert 'moving' in metrics
        assert 'slowed' in metrics
        assert 'stopped' in metrics
        assert 'avg_speed' in metrics
        assert 'max_density' in metrics
        assert 'risk' in metrics
        
        # Risk should be valid value
        assert metrics['risk'] in ['LOW', 'MODERATE', 'HIGH', 'CRITICAL']
    
    def test_agent_format(self, sim_manager):
        """Test agent data format in frame."""
        sim_manager.start(scenario='high_density', speed=10.0)
        time.sleep(0.5)  # Let some agents spawn
        
        with sim_manager.lock:
            state = sim_manager.simulation.step()
            frame = sim_manager._build_frame(state)
        
        agents = frame['agents']
        if len(agents) > 0:
            agent = agents[0]
            # Format: [id, x, y, state_code]
            assert len(agent) == 4
            assert isinstance(agent[0], int)  # id
            assert isinstance(agent[1], float)  # x
            assert isinstance(agent[2], float)  # y
            assert agent[3] in [0, 1, 2, 3]  # state code


class TestAPIEndpoints:
    """Test Flask API endpoints."""
    
    @pytest.fixture
    def client(self):
        from app import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_index_route(self, client):
        """Test main page loads."""
        response = client.get('/')
        assert response.status_code == 200
    
    def test_list_venues(self, client):
        """Test venues listing endpoint."""
        response = client.get('/api/venues')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert isinstance(data, list)
        
        # Should find at least floor_plan.yaml
        names = [v['name'] for v in data]
        assert 'floor_plan.yaml' in names
    
    def test_load_venue_success(self, client):
        """Test loading venue via API."""
        venue_path = str(Path(__file__).parent.parent / 'floor_plan.yaml')
        
        response = client.post('/api/load', 
                               json={'path': venue_path},
                               content_type='application/json')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'venue' in data
    
    def test_load_venue_not_found(self, client):
        """Test loading nonexistent venue returns error."""
        response = client.post('/api/load',
                               json={'path': '/nonexistent/file.yaml'},
                               content_type='application/json')
        assert response.status_code == 404


class TestWebSocketEvents:
    """Test WebSocket event handling."""
    
    @pytest.fixture
    def socketio_client(self):
        from app import app, socketio, sim_manager
        
        # Reset sim_manager state
        sim_manager.stop()
        sim_manager.venue = None
        sim_manager.simulation = None
        
        client = socketio.test_client(app)
        yield client
        client.disconnect()
        sim_manager.stop()
    
    @pytest.fixture
    def venue_path(self):
        return str(Path(__file__).parent.parent / 'floor_plan.yaml')
    
    def test_connect_event(self, socketio_client):
        """Test client connection receives status."""
        received = socketio_client.get_received()
        
        # Should receive status event on connect
        event_names = [r['name'] for r in received]
        assert 'status' in event_names
    
    def test_load_venue_event(self, socketio_client, venue_path):
        """Test load_venue WebSocket event."""
        socketio_client.emit('load_venue', {'path': venue_path})
        
        received = socketio_client.get_received()
        event_names = [r['name'] for r in received]
        
        assert 'venue_data' in event_names
    
    def test_control_start_event(self, socketio_client, venue_path):
        """Test control start event."""
        # First load venue
        socketio_client.emit('load_venue', {'path': venue_path})
        socketio_client.get_received()  # Clear
        
        # Start simulation
        socketio_client.emit('control', {
            'action': 'start',
            'scenario': 'normal',
            'speed': 10.0
        })
        
        time.sleep(0.2)
        received = socketio_client.get_received()
        event_names = [r['name'] for r in received]
        
        assert 'status' in event_names
        
        # Should also start receiving frames
        time.sleep(0.3)
        received = socketio_client.get_received()
        event_names = [r['name'] for r in received]
        assert 'frame' in event_names
    
    def test_control_stop_event(self, socketio_client, venue_path):
        """Test control stop event."""
        socketio_client.emit('load_venue', {'path': venue_path})
        socketio_client.get_received()
        
        socketio_client.emit('control', {'action': 'start', 'scenario': 'normal', 'speed': 10.0})
        time.sleep(0.2)
        socketio_client.get_received()
        
        socketio_client.emit('control', {'action': 'stop'})
        received = socketio_client.get_received()
        
        status_events = [r for r in received if r['name'] == 'status']
        assert len(status_events) > 0
        assert status_events[-1]['args'][0]['running'] == False
    
    def test_control_pause_event(self, socketio_client, venue_path):
        """Test control pause event."""
        socketio_client.emit('load_venue', {'path': venue_path})
        socketio_client.get_received()
        
        socketio_client.emit('control', {'action': 'start', 'scenario': 'normal', 'speed': 10.0})
        time.sleep(0.2)
        socketio_client.get_received()
        
        socketio_client.emit('control', {'action': 'pause'})
        received = socketio_client.get_received()
        
        status_events = [r for r in received if r['name'] == 'status']
        assert len(status_events) > 0
        assert status_events[-1]['args'][0]['paused'] == True
    
    def test_control_speed_event(self, socketio_client, venue_path):
        """Test control speed event."""
        socketio_client.emit('load_venue', {'path': venue_path})
        socketio_client.get_received()
        
        socketio_client.emit('control', {'action': 'speed', 'speed': 2.5})
        received = socketio_client.get_received()
        
        status_events = [r for r in received if r['name'] == 'status']
        assert len(status_events) > 0
        assert status_events[-1]['args'][0]['speed'] == 2.5
    
    def test_control_reset_event(self, socketio_client, venue_path):
        """Test control reset event."""
        socketio_client.emit('load_venue', {'path': venue_path})
        socketio_client.get_received()
        
        socketio_client.emit('control', {'action': 'start', 'scenario': 'normal', 'speed': 10.0})
        time.sleep(0.2)
        socketio_client.get_received()
        
        socketio_client.emit('control', {'action': 'reset'})
        time.sleep(0.2)
        received = socketio_client.get_received()
        
        event_names = [r['name'] for r in received]
        assert 'venue_data' in event_names  # Should re-emit venue data
        assert 'status' in event_names


class TestCrowdSimulationModule:
    """Test the underlying crowd_simulation module."""
    
    @pytest.fixture
    def venue(self):
        from crowd_simulation import Venue
        venue_path = str(Path(__file__).parent.parent / 'floor_plan.yaml')
        return Venue.from_yaml(venue_path)
    
    def test_venue_loading(self, venue):
        """Test venue loads correctly."""
        assert venue is not None
        assert len(venue.pathways) > 0
        assert len(venue.entries) > 0
        assert len(venue.exits) > 0
    
    def test_path_graph(self, venue):
        """Test path graph is built correctly."""
        assert venue.graph is not None
        assert len(venue.graph.segments) > 0
    
    def test_simulation_step(self, venue):
        """Test simulation can step."""
        from crowd_simulation import CrowdSimulation, SimulationConfig
        from crowd_simulation.config import ScenarioPresets
        
        config = ScenarioPresets.normal_flow()
        config.max_simulation_time = 10
        
        sim = CrowdSimulation(venue, config)
        state = sim.step()
        
        assert state is not None
        assert state.timestamp > 0
        assert state.metrics is not None
    
    def test_simulation_multiple_steps(self, venue):
        """Test simulation can run multiple steps."""
        from crowd_simulation import CrowdSimulation, SimulationConfig
        from crowd_simulation.config import ScenarioPresets
        
        config = ScenarioPresets.normal_flow()
        config.max_simulation_time = 10
        
        sim = CrowdSimulation(venue, config)
        
        for i in range(50):
            state = sim.step()
            assert state is not None
        
        # Should have spawned some agents
        assert state.total_spawned > 0
    
    def test_all_scenario_presets(self, venue):
        """Test all scenario presets work."""
        from crowd_simulation import CrowdSimulation
        from crowd_simulation.config import ScenarioPresets
        
        presets = [
            ScenarioPresets.normal_flow,
            ScenarioPresets.high_density,
            ScenarioPresets.sudden_surge,
            ScenarioPresets.near_stampede,
            ScenarioPresets.stress_test
        ]
        
        for preset_fn in presets:
            config = preset_fn()
            config.max_simulation_time = 5
            
            sim = CrowdSimulation(venue, config)
            state = sim.step()
            assert state is not None, f"Failed for preset: {preset_fn.__name__}"


class TestJointConnectivity:
    """Test that joints properly connect pathway segments for pathfinding."""
    
    @pytest.fixture
    def venue(self):
        from crowd_simulation import Venue
        venue_path = str(Path(__file__).parent.parent / 'floor_plan.yaml')
        return Venue.from_yaml(venue_path)
    
    def test_joints_have_connected_segments(self, venue):
        """Test that joints identify connected segments."""
        for joint_id, joint in venue.joints.items():
            # Each joint should connect at least 2 segments
            assert len(joint.connected_segments) >= 2, \
                f"Joint {joint_id} should connect at least 2 segments, found {len(joint.connected_segments)}"
    
    def test_segments_split_at_joints(self, venue):
        """Test that pathway segments are split at joint positions."""
        # Check that segments have endpoints at joint positions
        for joint_id, joint in venue.joints.items():
            joint_pos = joint.position
            segments_at_joint = []
            
            for seg_id, segment in venue.graph.segments.items():
                # Check if segment start or end is at joint position
                dist_start = segment.start.distance_to(joint_pos)
                dist_end = segment.end.distance_to(joint_pos)
                
                if dist_start < 0.5 or dist_end < 0.5:
                    segments_at_joint.append(seg_id)
            
            assert len(segments_at_joint) >= 2, \
                f"Joint {joint_id} at ({joint_pos.x:.1f}, {joint_pos.y:.1f}) should have segments with endpoints there"
    
    def test_graph_adjacency_at_joints(self, venue):
        """Test that segments at joints are connected in the graph adjacency."""
        for joint_id, joint in venue.joints.items():
            connected_segs = joint.connected_segments
            
            # All connected segments should be in each other's adjacency lists
            for i, seg1 in enumerate(connected_segs):
                for seg2 in connected_segs[i+1:]:
                    adjacency_1 = venue.graph.adjacency.get(seg1, set())
                    adjacency_2 = venue.graph.adjacency.get(seg2, set())
                    
                    assert seg2 in adjacency_1, \
                        f"Segment {seg1} should be adjacent to {seg2} at joint {joint_id}"
                    assert seg1 in adjacency_2, \
                        f"Segment {seg2} should be adjacent to {seg1} at joint {joint_id}"
    
    def test_pathfinding_uses_joints(self, venue):
        """Test that pathfinding can route through joints to different exits."""
        from crowd_simulation.pathfinding import PathFinder
        
        pf = PathFinder(venue)
        
        # Get an entry point
        entry = list(venue.entries.values())[0]
        entry_segment = entry.nearest_segment
        
        # Check that we can reach multiple exits
        reachable_exits = 0
        for exit_id, paths in pf.exit_paths.items():
            if entry_segment in paths:
                dist, _ = paths[entry_segment]
                if dist < float('inf'):
                    reachable_exits += 1
        
        # Should be able to reach at least 2 exits via joints
        assert reachable_exits >= 2, \
            f"Should reach at least 2 exits via joints, but only reached {reachable_exits}"
    
    def test_all_exits_reachable(self, venue):
        """Test that all exits are reachable from all entries."""
        from crowd_simulation.pathfinding import PathFinder
        
        pf = PathFinder(venue)
        
        for entry_id, entry in venue.entries.items():
            entry_segment = entry.nearest_segment
            
            for exit_id, exit_point in venue.exits.items():
                paths = pf.exit_paths.get(exit_id, {})
                
                if entry_segment in paths:
                    dist, _ = paths[entry_segment]
                    assert dist < float('inf'), \
                        f"Exit {exit_id} should be reachable from entry {entry_id}, but distance is infinite"


class TestThreadSafety:
    """Test thread safety of simulation manager."""
    
    @pytest.fixture
    def venue_path(self):
        return str(Path(__file__).parent.parent / 'floor_plan.yaml')
    
    @pytest.fixture
    def sim_manager(self, venue_path):
        from app import SimulationManager
        manager = SimulationManager()
        manager.load_venue(venue_path)
        yield manager
        manager.stop()
    
    def test_concurrent_speed_changes(self, sim_manager):
        """Test concurrent speed changes don't cause issues."""
        sim_manager.start(scenario='normal', speed=10.0)
        time.sleep(0.1)
        
        errors = []
        
        def change_speed():
            try:
                for _ in range(10):
                    sim_manager.set_speed(1.0 + _ * 0.1)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=change_speed) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
    
    def test_rapid_start_stop(self, sim_manager):
        """Test rapid start/stop cycles don't cause issues."""
        errors = []
        
        try:
            for _ in range(5):
                sim_manager.start(scenario='normal', speed=10.0)
                time.sleep(0.05)
                sim_manager.stop()
        except Exception as e:
            errors.append(e)
        
        assert len(errors) == 0


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def venue_path(self):
        return str(Path(__file__).parent.parent / 'floor_plan.yaml')
    
    @pytest.fixture  
    def sim_manager(self, venue_path):
        from app import SimulationManager
        manager = SimulationManager()
        manager.load_venue(venue_path)
        yield manager
        manager.stop()
    
    def test_get_venue_data_without_venue(self):
        """Test getting venue data without loaded venue."""
        from app import SimulationManager
        manager = SimulationManager()
        
        data = manager._get_venue_data()
        assert data == {}
    
    def test_invalid_scenario(self, sim_manager):
        """Test invalid scenario defaults to normal."""
        result = sim_manager.start(scenario='invalid_scenario', speed=10.0)
        assert result == True  # Should still start with default
    
    def test_extreme_speed_values(self, sim_manager):
        """Test extreme speed values are clamped."""
        sim_manager.set_speed(-100)
        assert sim_manager.speed == 0.1
        
        sim_manager.set_speed(1000)
        assert sim_manager.speed == 10.0


def run_tests():
    """Run all tests and print results."""
    pytest.main([__file__, '-v', '--tb=short'])


if __name__ == '__main__':
    run_tests()

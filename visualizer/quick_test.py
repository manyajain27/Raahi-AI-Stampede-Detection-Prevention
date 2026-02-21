"""
Quick verification tests for the visualizer.
Run this to quickly validate all components work.
"""

import sys
import time
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test all imports work."""
    print("Testing imports...", end=" ")
    try:
        from app import app, socketio, sim_manager, SimulationManager
        from crowd_simulation import CrowdSimulation, Venue, SimulationConfig
        from crowd_simulation.config import ScenarioPresets
        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

def test_venue_loading():
    """Test venue loading."""
    print("Testing venue loading...", end=" ")
    try:
        from app import SimulationManager
        manager = SimulationManager()
        venue_path = str(Path(__file__).parent.parent / 'floor_plan.yaml')
        venue_data = manager.load_venue(venue_path)
        
        assert 'roads' in venue_data
        assert 'entries' in venue_data
        assert 'exits' in venue_data
        assert len(venue_data['roads']) > 0
        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

def test_simulation_start_stop():
    """Test simulation can start and stop."""
    print("Testing simulation start/stop...", end=" ")
    try:
        from app import SimulationManager
        manager = SimulationManager()
        venue_path = str(Path(__file__).parent.parent / 'floor_plan.yaml')
        manager.load_venue(venue_path)
        
        # Start
        result = manager.start(scenario='normal', speed=5.0)
        assert result == True, "Failed to start"
        assert manager.running == True
        
        # Let it run briefly
        time.sleep(0.3)
        
        # Stop
        manager.stop()
        assert manager.running == False
        
        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

def test_all_scenarios():
    """Test all scenario presets."""
    print("Testing all scenarios...", end=" ")
    try:
        from app import SimulationManager
        manager = SimulationManager()
        venue_path = str(Path(__file__).parent.parent / 'floor_plan.yaml')
        manager.load_venue(venue_path)
        
        scenarios = ['normal', 'high_density', 'surge', 'near_stampede', 'stress_test']
        for scenario in scenarios:
            manager.reset()
            result = manager.start(scenario=scenario, speed=10.0)
            assert result == True, f"Failed to start {scenario}"
            time.sleep(0.1)
            manager.stop()
        
        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

def test_frame_building():
    """Test frame building from simulation state."""
    print("Testing frame building...", end=" ")
    try:
        from app import SimulationManager
        manager = SimulationManager()
        venue_path = str(Path(__file__).parent.parent / 'floor_plan.yaml')
        manager.load_venue(venue_path)
        
        manager.start(scenario='normal', speed=10.0)
        time.sleep(0.3)
        
        # Manually step and build frame
        with manager.lock:
            state = manager.simulation.step()
            frame = manager._build_frame(state)
        
        manager.stop()
        
        # Validate frame structure
        assert 'type' in frame
        assert frame['type'] == 'frame'
        assert 'time' in frame
        assert 'agents' in frame
        assert 'metrics' in frame
        assert 'choke_risks' in frame
        
        # Validate metrics
        metrics = frame['metrics']
        assert 'total' in metrics
        assert 'moving' in metrics
        assert 'risk' in metrics
        assert metrics['risk'] in ['LOW', 'MODERATE', 'HIGH', 'CRITICAL']
        
        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test Flask API endpoints."""
    print("Testing API endpoints...", end=" ")
    try:
        from app import app
        app.config['TESTING'] = True
        
        with app.test_client() as client:
            # Test index
            response = client.get('/')
            assert response.status_code == 200, "Index failed"
            
            # Test venues list
            response = client.get('/api/venues')
            assert response.status_code == 200, "Venues list failed"
            
            # Test load venue
            venue_path = str(Path(__file__).parent.parent / 'floor_plan.yaml')
            response = client.post('/api/load',
                                   json={'path': venue_path},
                                   content_type='application/json')
            assert response.status_code == 200, "Load venue failed"
        
        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

def test_websocket_events():
    """Test WebSocket events."""
    print("Testing WebSocket events...", end=" ")
    try:
        from app import app, socketio, sim_manager
        
        # Reset state
        sim_manager.stop()
        sim_manager.venue = None
        sim_manager.simulation = None
        
        client = socketio.test_client(app)
        
        # Should receive status on connect
        received = client.get_received()
        event_names = [r['name'] for r in received]
        assert 'status' in event_names, "No status on connect"
        
        # Load venue
        venue_path = str(Path(__file__).parent.parent / 'floor_plan.yaml')
        client.emit('load_venue', {'path': venue_path})
        received = client.get_received()
        event_names = [r['name'] for r in received]
        assert 'venue_data' in event_names, "No venue_data after load"
        
        # Start simulation
        client.emit('control', {'action': 'start', 'scenario': 'normal', 'speed': 10.0})
        time.sleep(0.3)
        received = client.get_received()
        event_names = [r['name'] for r in received]
        assert 'frame' in event_names, "No frames emitted"
        
        # Stop
        client.emit('control', {'action': 'stop'})
        client.disconnect()
        
        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pause_resume():
    """Test pause and resume."""
    print("Testing pause/resume...", end=" ")
    try:
        from app import SimulationManager
        manager = SimulationManager()
        venue_path = str(Path(__file__).parent.parent / 'floor_plan.yaml')
        manager.load_venue(venue_path)
        
        manager.start(scenario='normal', speed=10.0)
        time.sleep(0.1)
        
        # Pause
        result = manager.pause()
        assert result == True
        assert manager.paused == True
        
        # Resume
        result = manager.pause()
        assert result == False
        assert manager.paused == False
        
        manager.stop()
        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

def test_speed_control():
    """Test speed control."""
    print("Testing speed control...", end=" ")
    try:
        from app import SimulationManager
        manager = SimulationManager()
        
        manager.set_speed(2.0)
        assert manager.speed == 2.0
        
        manager.set_speed(0.5)
        assert manager.speed == 0.5
        
        # Test bounds
        manager.set_speed(-10)
        assert manager.speed == 0.1
        
        manager.set_speed(100)
        assert manager.speed == 10.0
        
        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False

def run_all_tests():
    """Run all quick tests."""
    print("=" * 60)
    print("VISUALIZER QUICK TESTS")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_venue_loading,
        test_simulation_start_stop,
        test_all_scenarios,
        test_frame_building,
        test_api_endpoints,
        test_websocket_events,
        test_pause_resume,
        test_speed_control,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  Error running {test.__name__}: {e}")
            failed += 1
    
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

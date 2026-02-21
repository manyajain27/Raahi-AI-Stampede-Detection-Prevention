"""
Real-Time Crowd Simulation Visualizer

Flask + SocketIO backend that streams simulation state to web clients.
"""

import os
import sys
import threading
import time
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

# Add parent directory to path for crowd_simulation import
sys.path.insert(0, str(Path(__file__).parent.parent))

from crowd_simulation import CrowdSimulation, Venue, SimulationConfig
from crowd_simulation.config import ScenarioPresets

app = Flask(__name__)
app.config['SECRET_KEY'] = 'crowd-sim-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global simulation state
class SimulationManager:
    """Manages the simulation lifecycle and WebSocket streaming."""
    
    def __init__(self):
        self.venue = None
        self.simulation = None
        self.config = None
        self.running = False
        self.paused = False
        self.speed = 1.0
        self.thread = None
        self.lock = threading.Lock()
        self.venue_path = None
        
    def load_venue(self, yaml_path: str) -> dict:
        """Load venue and return static data for clients."""
        with self.lock:
            self.venue_path = yaml_path
            self.venue = Venue.from_yaml(yaml_path)
            return self._get_venue_data()
    
    def _get_venue_data(self) -> dict:
        """Extract static venue data for frontend rendering."""
        if not self.venue:
            return {}
        
        # Collect all segment points for bounds calculation
        # NOTE: Y is negated to convert from canvas coords (Y-down) to
        # Leaflet Simple CRS coords (Y-up) so the visualizer matches
        # the floor planner layout.
        all_x = []
        all_y = []
        
        roads = []
        for seg_id, segment in self.venue.graph.segments.items():
            points = [[segment.start.x, -segment.start.y], 
                      [segment.end.x, -segment.end.y]]
            roads.append({
                'id': seg_id,
                'points': points,
                'width': segment.width
            })
            all_x.extend([segment.start.x, segment.end.x])
            all_y.extend([-segment.start.y, -segment.end.y])
        
        entries = [
            {'id': e.id, 'name': e.name, 'x': e.position.x, 'y': -e.position.y}
            for e in self.venue.entries.values()
        ]
        
        exits = [
            {'id': e.id, 'name': e.name, 'x': e.position.x, 'y': -e.position.y}
            for e in self.venue.exits.values()
        ]
        
        choke_points = [
            {'id': c.id, 'name': c.name, 'x': c.position.x, 'y': -c.position.y, 
             'radius': c.radius}
            for c in self.venue.choke_points.values()
        ]
        
        joints = [
            {'id': j.id, 'name': j.name, 'x': j.position.x, 'y': -j.position.y}
            for j in self.venue.joints.values()
        ]
        
        # Calculate bounds with padding
        padding = 2.0
        bounds = {
            'min_x': min(all_x) - padding if all_x else 0,
            'max_x': max(all_x) + padding if all_x else 100,
            'min_y': min(all_y) - padding if all_y else 0,
            'max_y': max(all_y) + padding if all_y else 100
        }
        
        return {
            'type': 'venue_data',
            'bounds': bounds,
            'roads': roads,
            'entries': entries,
            'exits': exits,
            'choke_points': choke_points,
            'joints': joints,
            'pixels_per_meter': self.venue.pixels_per_meter
        }
    
    def start(self, scenario: str = 'normal', speed: float = 1.0):
        """Start the simulation in a background thread."""
        if not self.venue:
            return False
        
        with self.lock:
            if self.running:
                return False
            
            # Get scenario config
            preset_map = {
                'normal': ScenarioPresets.normal_flow,
                'high_density': ScenarioPresets.high_density,
                'surge': ScenarioPresets.sudden_surge,
                'near_stampede': ScenarioPresets.near_stampede,
                'stress_test': ScenarioPresets.stress_test
            }
            self.config = preset_map.get(scenario, ScenarioPresets.normal_flow)()
            self.config.max_simulation_time = 600  # 10 minutes max
            
            self.simulation = CrowdSimulation(self.venue, self.config)
            self.speed = speed
            self.running = True
            self.paused = False
            
        # Start background thread
        self.thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.thread.start()
        return True
    
    def stop(self):
        """Stop the simulation."""
        with self.lock:
            self.running = False
            self.paused = False
        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
    
    def pause(self):
        """Pause/unpause the simulation."""
        with self.lock:
            self.paused = not self.paused
        return self.paused
    
    def reset(self):
        """Reset the simulation."""
        self.stop()
        with self.lock:
            if self.venue_path:
                self.venue = Venue.from_yaml(self.venue_path)
            self.simulation = None
    
    def set_speed(self, speed: float):
        """Set simulation playback speed."""
        with self.lock:
            self.speed = max(0.1, min(10.0, speed))
    
    def _simulation_loop(self):
        """Background thread that runs simulation and emits frames."""
        base_timestep = self.config.timestep
        
        while self.running:
            if self.paused:
                time.sleep(0.05)
                continue
            
            with self.lock:
                if not self.running or not self.simulation:
                    break
                
                # Check max time
                if self.simulation.current_time >= self.config.max_simulation_time:
                    self.running = False
                    socketio.emit('simulation_end', {'reason': 'max_time_reached'})
                    break
                
                # Step simulation
                try:
                    state = self.simulation.step()
                except Exception as e:
                    print(f"Simulation error: {e}")
                    self.running = False
                    socketio.emit('simulation_end', {'reason': f'error: {str(e)}'})
                    break
                
                if state is None:
                    self.running = False
                    socketio.emit('simulation_end', {'reason': 'completed'})
                    break
                
                # Build frame data
                frame = self._build_frame(state)
            
            # Emit to all connected clients
            socketio.emit('frame', frame)
            
            # Sleep based on speed (faster speed = shorter sleep)
            time.sleep(base_timestep / self.speed)
        
        self.running = False
    
    def _build_frame(self, state) -> dict:
        """Build a frame packet from simulation state."""
        # Compact agent format: [id, x, y, state_code]
        # state_code: 0=moving, 1=slowed, 2=stopped, 3=exited
        state_map = {'moving': 0, 'slowed': 1, 'stopped': 2, 'exited': 3}
        
        agents = []
        for agent in state.agents.values():
            if agent.state.value == 'exited':
                continue
            
            # Get agent world position from segment
            segment = self.venue.graph.segments.get(agent.segment_id)
            if segment:
                x, y = agent.get_world_position(
                    (segment.start.x, segment.start.y),
                    (segment.end.x, segment.end.y),
                    segment.width
                )
            else:
                # Fallback - shouldn't happen
                x, y = 0, 0
            
            agents.append([
                agent.id,
                round(x, 2),
                round(-y, 2),  # Negate Y: canvas (Y-down) -> Leaflet (Y-up)
                state_map.get(agent.state.value, 0)
            ])
        
        # Choke point risk levels
        choke_risks = {}
        max_choke_density = 0
        for choke_id, choke in self.venue.choke_points.items():
            density = self._get_choke_density(choke, state)
            choke_risks[str(choke_id)] = round(density, 2)
            max_choke_density = max(max_choke_density, density)
        
        # Get metrics from state
        metrics = state.metrics
        max_density = metrics.max_density if metrics else 0
        
        # Calculate overall risk based on area-based density (agents per sq meter)
        # Low: < 0.5/m2, Moderate: 0.5-1.0/m2, High: 1.0-2.0/m2, Critical: > 2.0/m2
        if max_density > 2.0:
            risk = 'CRITICAL'
        elif max_density > 1.0:
            risk = 'HIGH'
        elif max_density > 0.5:
            risk = 'MODERATE'
        else:
            risk = 'LOW'
        
        return {
            'type': 'frame',
            'time': round(state.timestamp, 1),
            'agents': agents,
            'metrics': {
                'total': metrics.total_agents if metrics else 0,
                'moving': metrics.agents_moving if metrics else 0,
                'slowed': metrics.agents_slowed if metrics else 0,
                'stopped': metrics.agents_stopped if metrics else 0,
                'avg_speed': round(metrics.average_speed, 2) if metrics else 0,
                'max_density': round(max_density, 2),
                'risk': risk
            },
            'choke_risks': choke_risks
        }
    
    def _get_choke_density(self, choke, state) -> float:
        """Calculate density near a choke point."""
        if not state or not state.agents:
            return 0.0
        
        count = 0
        for agent in state.agents.values():
            if agent.state.value == 'exited':
                continue
            
            # Get agent world position from segment
            segment = self.venue.graph.segments.get(agent.segment_id)
            if segment:
                x, y = agent.get_world_position(
                    (segment.start.x, segment.start.y),
                    (segment.end.x, segment.end.y),
                    segment.width
                )
                dist = ((x - choke.position.x)**2 + (y - choke.position.y)**2)**0.5
                if dist <= choke.radius:
                    count += 1
        
        area = 3.14159 * choke.radius**2
        return count / area if area > 0 else 0

# Global manager instance
sim_manager = SimulationManager()


# =============================================================================
# Routes
# =============================================================================

@app.route('/')
def index():
    """Serve the visualization page."""
    return render_template('index.html')


@app.route('/api/venues')
def list_venues():
    """List available venue files."""
    venue_dir = Path(__file__).parent.parent
    venues = list(venue_dir.glob('*.yaml')) + list(venue_dir.glob('*.yml'))
    return jsonify([{'name': v.name, 'path': str(v)} for v in venues])


@app.route('/api/load', methods=['POST'])
def load_venue():
    """Load a venue file."""
    data = request.json
    path = data.get('path')
    
    if not path or not os.path.exists(path):
        return jsonify({'error': 'Venue file not found'}), 404
    
    try:
        venue_data = sim_manager.load_venue(path)
        return jsonify({'success': True, 'venue': venue_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# WebSocket Events
# =============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print(f"Client connected: {request.sid}")
    
    # Send current venue data if loaded
    if sim_manager.venue:
        emit('venue_data', sim_manager._get_venue_data())
    
    # Send current simulation status
    emit('status', {
        'venue_loaded': sim_manager.venue is not None,
        'running': sim_manager.running,
        'paused': sim_manager.paused,
        'speed': sim_manager.speed
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print(f"Client disconnected: {request.sid}")


@socketio.on('control')
def handle_control(data):
    """Handle simulation control commands."""
    action = data.get('action')
    
    if action == 'start':
        scenario = data.get('scenario', 'normal')
        speed = data.get('speed', 1.0)
        success = sim_manager.start(scenario, speed)
        emit('status', {'running': success, 'paused': False})
        
    elif action == 'stop':
        sim_manager.stop()
        emit('status', {'running': False, 'paused': False})
        
    elif action == 'pause':
        paused = sim_manager.pause()
        emit('status', {'running': sim_manager.running, 'paused': paused})
        
    elif action == 'reset':
        sim_manager.reset()
        if sim_manager.venue:
            emit('venue_data', sim_manager._get_venue_data())
        emit('status', {'running': False, 'paused': False})
        
    elif action == 'speed':
        speed = data.get('speed', 1.0)
        sim_manager.set_speed(speed)
        emit('status', {'speed': sim_manager.speed})


@socketio.on('load_venue')
def handle_load_venue(data):
    """Handle venue load request via WebSocket."""
    path = data.get('path')
    
    if not path:
        emit('error', {'message': 'No path provided'})
        return
    
    try:
        venue_data = sim_manager.load_venue(path)
        emit('venue_data', venue_data)
        emit('status', {'venue_loaded': True, 'running': False, 'paused': False})
    except Exception as e:
        emit('error', {'message': str(e)})


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("Crowd Simulation Visualizer")
    print("=" * 60)
    print("Open http://localhost:5001 in your browser")
    print("=" * 60)
    
    socketio.run(app, host='0.0.0.0', port=5001, debug=False)

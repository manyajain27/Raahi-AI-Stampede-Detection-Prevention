import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crowd_simulation import Venue, CrowdSimulation, SimulationConfig
from crowd_simulation.agent import AgentState

venue = Venue.from_yaml(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'floor_plan.yaml'))
config = SimulationConfig(spawn_rate_multiplier=1.0, timestep=0.1)
sim = CrowdSimulation(venue, config)

print('Time,Agents,Moving,Slowed,Stopped,AvgSpeed,MaxDensity')
for t in range(1, 61):
    while sim.current_time < t:
        sim.step()
    active = [a for a in sim.agents.values() if a.state != AgentState.EXITED]
    moving = sum(1 for a in active if a.state == AgentState.MOVING)
    slowed = sum(1 for a in active if a.state == AgentState.SLOWED)
    stopped = sum(1 for a in active if a.state == AgentState.STOPPED)
    speeds = [a.current_speed for a in active]
    avg = sum(speeds)/len(speeds) if speeds else 0
    max_d = max((s.density for s in sim.dynamics.segment_states.values()), default=0)
    print(f'{t},{len(active)},{moving},{slowed},{stopped},{avg:.2f},{max_d:.2f}')

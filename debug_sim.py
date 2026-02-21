import sys
import traceback

sys.path.insert(0, '.')

print("=== Step 1: Importing modules ===")
try:
    from crowd_simulation import CrowdSimulation, Venue, SimulationConfig
    from crowd_simulation.config import ScenarioPresets
    print("  OK - imports succeeded")
except Exception as e:
    print(f"  FAILED - {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== Step 2: Loading venue from floor_plan.yaml ===")
try:
    venue = Venue.from_yaml('floor_plan.yaml')
    print(f"  OK - Venue loaded")
    print(f"  Segments: {len(venue.graph.segments)}")
    print(f"  Entries:  {len(venue.entries)}")
    print(f"  Exits:    {len(venue.exits)}")
    print(f"  Chokes:   {len(venue.choke_points)}")
    print(f"  Joints:   {len(venue.joints)}")
except Exception as e:
    print(f"  FAILED - {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n=== Step 3: Checking entry nearest_segment ===")
for eid, entry in venue.entries.items():
    print(f"  Entry {eid} '{entry.name}': nearest_segment = {entry.nearest_segment}")

print("\n=== Step 4: Checking exit nearest_segment ===")
for xid, ex in venue.exits.items():
    print(f"  Exit {xid} '{ex.name}': nearest_segment = {ex.nearest_segment}")

print("\n=== Step 5: Running simulation for 5 seconds ===")
try:
    config = SimulationConfig()
    config.max_simulation_time = 5.0
    sim = CrowdSimulation(venue, config)
    results = sim.run()
    print(f"  OK - Simulation ran for {results.duration:.1f}s")
    print(f"  Agents spawned: {results.total_agents_spawned}")
    print(f"  Agents exited:  {results.total_agents_exited}")
except Exception as e:
    print(f"  FAILED - {e}")
    traceback.print_exc()

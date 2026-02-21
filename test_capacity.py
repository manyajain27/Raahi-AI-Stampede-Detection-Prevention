import os
import time

# Create a temporary YAML file representing a venue with expected attendance of 15
test_yaml_content = """
type: indoor
pixelsPerMeter: 50
maxCapacity: 100
expectedAttendance: 15
pathways:
  - id: 1
    name: "Main Hall"
    width: 2.0
    points:
      - x: 10
        y: 50
      - x: 90
        y: 50
entries:
  - id: 1
    name: "Main Entrance"
    x: 10
    y: 50
    spawnRate: 5.0  # Very high spawn rate to hit the cap quickly
exits:
  - id: 1
    name: "Emergency Exit"
    x: 90
    y: 50
    exitRate: 10.0
chokePoints: []
joints: []
"""

yaml_path = "test_capacity_venue.yaml"
with open(yaml_path, "w") as f:
    f.write(test_yaml_content)

print(f"[TEST 1] Created temporary YAML file with expectedAttendance = 15")

# Import the simulation components
from crowd_simulation.venue import Venue
from crowd_simulation.simulation import CrowdSimulation
from crowd_simulation.config import SimulationConfig

print("[TEST 2] Loading venue from YAML...")
# 1. Test that maxCapacity and expectedAttendance are parsed correctly
venue = Venue.from_yaml(yaml_path)

print(f"  -> Parsed max_capacity: {venue.max_capacity}")
print(f"  -> Parsed expected_attendance: {venue.expected_attendance}")

assert venue.max_capacity == 100, "Failed: max_capacity not parsed correctly"
assert venue.expected_attendance == 15, "Failed: expected_attendance not parsed correctly"
print("[OK] Venue parsed properties correctly!")

print("\n[TEST 3] Running Simulation to test spawn capping...")

# Configure a simulation that should spawn agents very quickly
config = SimulationConfig(
    timestep=0.1,
    max_simulation_time=10.0,
    spawn_rate_multiplier=1.0 # 5.0 agents per second from the entry
)

sim = CrowdSimulation(venue, config)

print("  -> Simulating 5 seconds of time (50 steps @ 0.1s)...")
for _ in range(50):
    sim.step()

# The entry spawns at 5.0 agents per second. Over 5 seconds, it normally would spawn 25 agents.
# However, our expectedAttendance cap is 15. So it should stop at 15.
print(f"  -> Total Agents Spawned: {sim.total_spawned}")

assert sim.total_spawned == 15, f"Failed: Expected exactly 15 agents spawned, but got {sim.total_spawned}"
print("[OK] Simulation properly capped the spawns at the expected attendance!")

# Clean up
os.remove(yaml_path)
print("\n[✓] All tests passed! The logic is working perfectly.")

"""
Command-line interface for the Crowd Simulation Engine.

Provides a simple CLI for running simulations from venue YAML files.
"""

import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crowd_simulation import CrowdSimulation, Venue, SimulationConfig
from crowd_simulation.config import ScenarioPresets
from crowd_simulation.output import JSONExporter, CSVExporter, RiskReport


def main():
    parser = argparse.ArgumentParser(
        description='Crowd Simulation Engine - Pre-event stampede risk analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m crowd_simulation venue.yaml
  python -m crowd_simulation venue.yaml --scenario high_density
  python -m crowd_simulation venue.yaml --spawn-rate 3.0 --duration 1800
  python -m crowd_simulation venue.yaml --output results.json --csv metrics.csv
        """
    )
    
    parser.add_argument('venue', help='Path to venue YAML file')
    
    # Scenario presets
    parser.add_argument(
        '--scenario', '-s',
        choices=['normal', 'high_density', 'surge', 'near_stampede', 'stress_test'],
        default='normal',
        help='Predefined scenario preset (default: normal)'
    )
    
    # Override parameters
    parser.add_argument('--spawn-rate', type=float, help='Spawn rate multiplier')
    parser.add_argument('--duration', type=float, help='Simulation duration (seconds)')
    parser.add_argument('--timestep', type=float, help='Simulation timestep (seconds)')
    parser.add_argument('--seed', type=int, help='Random seed for reproducibility')
    
    # Surge parameters
    parser.add_argument('--surge', action='store_true', help='Enable surge event')
    parser.add_argument('--surge-time', type=float, help='Surge start time (seconds)')
    parser.add_argument('--surge-duration', type=float, help='Surge duration (seconds)')
    parser.add_argument('--surge-multiplier', type=float, help='Surge spawn multiplier')
    
    # Exit control
    parser.add_argument('--block-exit', type=int, action='append', 
                       help='Block an exit by ID (can specify multiple)')
    
    # Output options
    parser.add_argument('--output', '-o', help='Output JSON file path')
    parser.add_argument('--csv', help='Output CSV file path for time series')
    parser.add_argument('--quiet', '-q', action='store_true', 
                       help='Suppress progress output')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Load venue
    if not os.path.exists(args.venue):
        print(f"Error: Venue file not found: {args.venue}", file=sys.stderr)
        sys.exit(1)
    
    try:
        venue = Venue.from_yaml(args.venue)
    except Exception as e:
        print(f"Error loading venue: {e}", file=sys.stderr)
        sys.exit(1)
    
    if args.verbose:
        print(f"Loaded venue: {args.venue}")
        print(f"  Pathways: {len(venue.pathways)}")
        print(f"  Entries: {len(venue.entries)}")
        print(f"  Exits: {len(venue.exits)}")
        print(f"  Choke points: {len(venue.choke_points)}")
        print(f"  Joints: {len(venue.joints)}")
        print(f"  Total segments: {len(venue.graph.segments)}")
    
    # Create config from scenario preset
    scenario_map = {
        'normal': ScenarioPresets.normal_flow,
        'high_density': ScenarioPresets.high_density,
        'surge': ScenarioPresets.sudden_surge,
        'near_stampede': ScenarioPresets.near_stampede,
        'stress_test': ScenarioPresets.stress_test
    }
    
    config = scenario_map[args.scenario]()
    
    # Apply overrides
    if args.spawn_rate:
        config.spawn_rate_multiplier = args.spawn_rate
    if args.duration:
        config.max_simulation_time = args.duration
    if args.timestep:
        config.timestep = args.timestep
    if args.seed:
        config.random_seed = args.seed
    if args.surge:
        config.surge_enabled = True
    if args.surge_time:
        config.surge_start_time = args.surge_time
    if args.surge_duration:
        config.surge_duration = args.surge_duration
    if args.surge_multiplier:
        config.surge_multiplier = args.surge_multiplier
    if args.block_exit:
        config.blocked_exits = args.block_exit
    
    # Create simulation
    sim = CrowdSimulation(venue, config)
    
    if args.verbose:
        print(f"\nSimulation configuration:")
        print(f"  Scenario: {args.scenario}")
        print(f"  Spawn rate multiplier: {config.spawn_rate_multiplier}")
        print(f"  Max duration: {config.max_simulation_time}s")
        print(f"  Timestep: {config.timestep}s")
        if config.surge_enabled:
            print(f"  Surge: {config.surge_start_time}s - {config.surge_start_time + config.surge_duration}s (x{config.surge_multiplier})")
        if config.blocked_exits:
            print(f"  Blocked exits: {config.blocked_exits}")
    
    # Progress callback
    def progress_callback(state):
        if not args.quiet:
            m = state.metrics
            bar_width = 30
            progress = min(1.0, state.timestamp / config.max_simulation_time)
            filled = int(bar_width * progress)
            bar = '=' * filled + '-' * (bar_width - filled)
            
            print(f"\r[{bar}] {state.timestamp:.0f}s | "
                  f"Agents: {m.total_agents:4d} | "
                  f"Moving: {m.agents_moving:3d} | "
                  f"Speed: {m.average_speed:.2f} | "
                  f"Congestion: {m.congestion_severity:.0%}", 
                  end='', flush=True)
    
    # Run simulation
    if not args.quiet:
        print(f"\nRunning simulation...")
    
    results = sim.run(callback=progress_callback, metrics_interval=1.0)
    
    if not args.quiet:
        print("\n")
    
    # Generate risk report
    report = RiskReport.generate(results)
    
    # Print summary
    print("=" * 60)
    print("SIMULATION RESULTS")
    print("=" * 60)
    print(f"Duration: {results.duration:.1f} seconds")
    print(f"Agents spawned: {results.total_agents_spawned}")
    print(f"Agents exited: {results.total_agents_exited}")
    print(f"Peak agents: {results.peak_agents}")
    print(f"Peak density: {results.peak_density:.2f} agents/m")
    print(f"Min stability: {results.min_stability:.2f}")
    congestion_pct = (results.congestion_duration / results.duration * 100) if results.duration > 0 else 0
    print(f"Congestion duration: {results.congestion_duration:.1f}s ({congestion_pct:.1f}%)")
    
    if results.total_agents_exited > 0:
        print(f"\nTravel times:")
        print(f"  Average: {results.average_travel_time:.1f}s")
        print(f"  Min: {results.min_travel_time:.1f}s")
        print(f"  Max: {results.max_travel_time:.1f}s")
    
    print(f"\n{'=' * 60}")
    print(f"RISK ASSESSMENT: {report['risk_level']}")
    print("=" * 60)
    
    for indicator, value in report['indicators'].items():
        if isinstance(value, float):
            print(f"  {indicator}: {value:.2%}")
        else:
            print(f"  {indicator}: {value}")
    
    if report['choke_point_risks']:
        print(f"\nChoke Point Analysis:")
        for choke_id, risk in report['choke_point_risks'].items():
            print(f"  Choke {choke_id}: {risk['risk_level']} (peak: {risk['peak_density']:.2f})")
    
    print(f"\nRecommendations:")
    for rec in report['recommendations']:
        print(f"  • {rec}")
    
    # Export results
    if args.output:
        JSONExporter.export_results(results, args.output)
        print(f"\nResults exported to: {args.output}")
    
    if args.csv:
        CSVExporter.export_time_series(results, args.csv)
        print(f"Time series exported to: {args.csv}")
    
    # Return exit code based on risk level
    if report['risk_level'] == 'CRITICAL':
        sys.exit(3)
    elif report['risk_level'] == 'HIGH':
        sys.exit(2)
    elif report['risk_level'] == 'MODERATE':
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()

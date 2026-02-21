"""
Output Module - Formats and exports simulation results.

Provides various output formats for simulation results to be consumed
by risk-scoring engines, visualization dashboards, or other systems.
"""

import json
import csv
from typing import Dict, List, Optional, TextIO
from dataclasses import asdict
from datetime import datetime

from .simulation import SimulationResults, SimulationState
from .dynamics import FlowMetrics, ChokePointState


class JSONExporter:
    """Export simulation results to JSON format."""
    
    @staticmethod
    def export_results(results: SimulationResults, filepath: str):
        """Export complete results to JSON file."""
        data = {
            'metadata': {
                'export_time': datetime.now().isoformat(),
                'simulation_duration': results.duration,
                'version': '1.0'
            },
            'summary': {
                'total_agents_spawned': results.total_agents_spawned,
                'total_agents_exited': results.total_agents_exited,
                'peak_density': results.peak_density,
                'peak_agents': results.peak_agents,
                'min_stability': results.min_stability,
                'congestion_duration': results.congestion_duration,
                'average_travel_time': results.average_travel_time,
                'max_travel_time': results.max_travel_time,
                'min_travel_time': results.min_travel_time if results.min_travel_time != float('inf') else None
            },
            'choke_point_analysis': {
                str(k): v for k, v in results.choke_point_peaks.items()
            },
            'time_series': JSONExporter._serialize_metrics_history(results.metrics_history)
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    @staticmethod
    def _serialize_metrics_history(history: List[FlowMetrics]) -> List[Dict]:
        """Serialize metrics history to JSON-compatible format."""
        serialized = []
        
        for metrics in history:
            entry = {
                'timestamp': metrics.timestamp,
                'total_agents': metrics.total_agents,
                'agents_moving': metrics.agents_moving,
                'agents_slowed': metrics.agents_slowed,
                'agents_stopped': metrics.agents_stopped,
                'average_speed': metrics.average_speed,
                'total_flow_rate': metrics.total_flow_rate,
                'max_density': metrics.max_density,
                'min_stability': metrics.min_stability,
                'congestion_severity': metrics.congestion_severity,
                'choke_points': {}
            }
            
            for choke_id, state in metrics.choke_metrics.items():
                entry['choke_points'][str(choke_id)] = {
                    'name': state.name,
                    'density': state.density,
                    'average_speed': state.average_speed,
                    'congestion_level': state.congestion_level,
                    'stability_index': state.stability_index,
                    'agent_count': state.agent_count
                }
            
            serialized.append(entry)
        
        return serialized
    
    @staticmethod
    def export_state(state: SimulationState, filepath: str):
        """Export a single simulation state to JSON."""
        data = {
            'timestamp': state.timestamp,
            'total_spawned': state.total_spawned,
            'total_exited': state.total_exited,
            'average_travel_time': state.average_travel_time,
            'metrics': {
                'total_agents': state.metrics.total_agents,
                'agents_moving': state.metrics.agents_moving,
                'agents_slowed': state.metrics.agents_slowed,
                'agents_stopped': state.metrics.agents_stopped,
                'average_speed': state.metrics.average_speed,
                'congestion_severity': state.metrics.congestion_severity
            },
            'agents': [
                {
                    'id': agent.id,
                    'segment': agent.segment_id,
                    'progress': agent.progress,
                    'speed': agent.current_speed,
                    'state': agent.state.value
                }
                for agent in state.agents.values()
                if agent.state.value != 'exited'
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)


class CSVExporter:
    """Export simulation results to CSV format."""
    
    @staticmethod
    def export_time_series(results: SimulationResults, filepath: str):
        """Export time series metrics to CSV."""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'timestamp',
                'total_agents',
                'agents_moving',
                'agents_slowed',
                'agents_stopped',
                'average_speed',
                'total_flow_rate',
                'max_density',
                'min_stability',
                'congestion_severity'
            ])
            
            # Data rows
            for metrics in results.metrics_history:
                writer.writerow([
                    f'{metrics.timestamp:.2f}',
                    metrics.total_agents,
                    metrics.agents_moving,
                    metrics.agents_slowed,
                    metrics.agents_stopped,
                    f'{metrics.average_speed:.3f}',
                    f'{metrics.total_flow_rate:.3f}',
                    f'{metrics.max_density:.3f}',
                    f'{metrics.min_stability:.3f}',
                    f'{metrics.congestion_severity:.3f}'
                ])
    
    @staticmethod
    def export_choke_point_series(results: SimulationResults, 
                                  choke_id: int, filepath: str):
        """Export time series for a specific choke point."""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            writer.writerow([
                'timestamp',
                'density',
                'average_speed',
                'congestion_level',
                'stability_index',
                'agent_count'
            ])
            
            for metrics in results.metrics_history:
                state = metrics.choke_metrics.get(choke_id)
                if state:
                    writer.writerow([
                        f'{metrics.timestamp:.2f}',
                        f'{state.density:.3f}',
                        f'{state.average_speed:.3f}',
                        f'{state.congestion_level:.3f}',
                        f'{state.stability_index:.3f}',
                        state.agent_count
                    ])


class StreamOutput:
    """Stream simulation output to a file or stdout."""
    
    def __init__(self, output: TextIO):
        self.output = output
        self._header_written = False
    
    def write_state(self, state: SimulationState):
        """Write a simulation state update."""
        if not self._header_written:
            self.output.write("timestamp,agents,moving,slowed,stopped,avg_speed,congestion\n")
            self._header_written = True
        
        m = state.metrics
        self.output.write(
            f"{state.timestamp:.1f},{m.total_agents},{m.agents_moving},"
            f"{m.agents_slowed},{m.agents_stopped},{m.average_speed:.2f},"
            f"{m.congestion_severity:.2f}\n"
        )
        self.output.flush()


class RiskReport:
    """Generate risk analysis report from simulation results."""
    
    @staticmethod
    def generate(results: SimulationResults) -> Dict:
        """
        Generate a risk assessment report.
        
        Returns a dictionary with risk indicators and recommendations.
        """
        report = {
            'risk_level': RiskReport._calculate_risk_level(results),
            'indicators': {},
            'choke_point_risks': {},
            'recommendations': []
        }
        
        # Calculate risk indicators
        report['indicators'] = {
            'peak_density_risk': RiskReport._density_risk(results.peak_density),
            'stability_risk': RiskReport._stability_risk(results.min_stability),
            'congestion_risk': RiskReport._congestion_risk(
                results.congestion_duration, results.duration
            ),
            'flow_efficiency': RiskReport._flow_efficiency(
                results.total_agents_exited, results.total_agents_spawned
            )
        }
        
        # Per-choke-point analysis
        for choke_id, peak_density in results.choke_point_peaks.items():
            risk = RiskReport._density_risk(peak_density)
            report['choke_point_risks'][choke_id] = {
                'peak_density': peak_density,
                'risk_level': risk
            }
        
        # Generate recommendations
        report['recommendations'] = RiskReport._generate_recommendations(
            report['indicators'], report['choke_point_risks']
        )
        
        return report
    
    @staticmethod
    def _calculate_risk_level(results: SimulationResults) -> str:
        """Calculate overall risk level."""
        score = 0
        
        # Density contribution
        if results.peak_density > 5.0:
            score += 3
        elif results.peak_density > 3.0:
            score += 2
        elif results.peak_density > 2.0:
            score += 1
        
        # Stability contribution
        if results.min_stability < 0.3:
            score += 3
        elif results.min_stability < 0.5:
            score += 2
        elif results.min_stability < 0.7:
            score += 1
        
        # Congestion contribution
        congestion_ratio = results.congestion_duration / max(results.duration, 1)
        if congestion_ratio > 0.5:
            score += 2
        elif congestion_ratio > 0.2:
            score += 1
        
        if score >= 6:
            return 'CRITICAL'
        elif score >= 4:
            return 'HIGH'
        elif score >= 2:
            return 'MODERATE'
        else:
            return 'LOW'
    
    @staticmethod
    def _density_risk(density: float) -> str:
        if density > 5.0:
            return 'CRITICAL'
        elif density > 3.0:
            return 'HIGH'
        elif density > 2.0:
            return 'MODERATE'
        return 'LOW'
    
    @staticmethod
    def _stability_risk(stability: float) -> str:
        if stability < 0.3:
            return 'CRITICAL'
        elif stability < 0.5:
            return 'HIGH'
        elif stability < 0.7:
            return 'MODERATE'
        return 'LOW'
    
    @staticmethod
    def _congestion_risk(congestion_duration: float, total_duration: float) -> str:
        ratio = congestion_duration / max(total_duration, 1)
        if ratio > 0.5:
            return 'HIGH'
        elif ratio > 0.2:
            return 'MODERATE'
        return 'LOW'
    
    @staticmethod
    def _flow_efficiency(exited: int, spawned: int) -> float:
        if spawned == 0:
            return 1.0
        return exited / spawned
    
    @staticmethod
    def _generate_recommendations(indicators: Dict, 
                                  choke_risks: Dict) -> List[str]:
        """Generate safety recommendations based on analysis."""
        recommendations = []
        
        if indicators.get('peak_density_risk') in ['CRITICAL', 'HIGH']:
            recommendations.append(
                "CRITICAL: Peak density exceeds safe limits. "
                "Consider reducing crowd capacity or adding alternative pathways."
            )
        
        if indicators.get('stability_risk') in ['CRITICAL', 'HIGH']:
            recommendations.append(
                "WARNING: Flow stability is compromised. "
                "Implement crowd management measures at choke points."
            )
        
        if indicators.get('congestion_risk') == 'HIGH':
            recommendations.append(
                "Prolonged congestion detected. "
                "Review exit capacity and consider staggered entry/exit times."
            )
        
        # Choke point specific
        for choke_id, risk_data in choke_risks.items():
            if risk_data['risk_level'] in ['CRITICAL', 'HIGH']:
                recommendations.append(
                    f"Choke point {choke_id}: High risk area. "
                    f"Peak density {risk_data['peak_density']:.1f}. "
                    "Consider widening or adding bypass routes."
                )
        
        if not recommendations:
            recommendations.append(
                "No critical risks identified under current scenario. "
                "Continue monitoring during actual event."
            )
        
        return recommendations

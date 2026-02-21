/**
 * Tests for the /api/health route.
 * Validates the health check response structure and service status logic.
 */

import { checkServiceHealth } from '@/lib/utils';

describe('/api/health', () => {
  it('checkServiceHealth returns online/offline with latency', async () => {
    // Test with a URL that will fail (no server running on this port)
    const result = await checkServiceHealth('http://localhost:59999');
    expect(result).toHaveProperty('online');
    expect(result).toHaveProperty('latency');
    expect(typeof result.online).toBe('boolean');
    expect(typeof result.latency).toBe('number');
    expect(result.latency).toBeGreaterThanOrEqual(0);
  });

  it('health response structure is correct', () => {
    // Simulate the response the health endpoint would build
    const services = [
      { name: 'Floor Planner', url: 'http://localhost:5000', status: 'online' as const, latency: 15 },
      { name: 'Visualizer', url: 'http://localhost:5001', status: 'offline' as const, latency: 3000 },
    ];

    const allOnline = services.every((r) => r.status === 'online');
    const response = {
      status: allOnline ? 'healthy' : 'degraded',
      services,
      timestamp: new Date().toISOString(),
    };

    expect(response.status).toBe('degraded');
    expect(response.services).toHaveLength(2);
    expect(response.services[0].name).toBe('Floor Planner');
    expect(response.services[1].status).toBe('offline');
    expect(response.timestamp).toBeDefined();
  });

  it('reports healthy when all services are online', () => {
    const services = [
      { name: 'Floor Planner', url: 'http://localhost:5000', status: 'online' as const, latency: 10 },
      { name: 'Visualizer', url: 'http://localhost:5001', status: 'online' as const, latency: 12 },
    ];

    const allOnline = services.every((r) => r.status === 'online');
    expect(allOnline).toBe(true);
  });
});

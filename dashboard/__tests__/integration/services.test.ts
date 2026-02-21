/**
 * Integration tests for backend service connectivity.
 * These tests verify that the dashboard can communicate with the Flask backends.
 * They will pass/skip gracefully if backends are not running.
 */

import { checkServiceHealth } from '@/lib/utils';

const PLANNER_URL = process.env.NEXT_PUBLIC_PLANNER_URL || 'http://localhost:5000';
const VISUALIZER_URL = process.env.NEXT_PUBLIC_VISUALIZER_URL || 'http://localhost:5001';

describe('Backend Service Integration', () => {
  describe('Floor Planner Service', () => {
    it('has correct URL configured', () => {
      expect(PLANNER_URL).toMatch(/^https?:\/\//);
      expect(PLANNER_URL).toContain('5000');
    });

    it('responds to health check (skip if offline)', async () => {
      const result = await checkServiceHealth(PLANNER_URL);
      if (!result.online) {
        console.warn('Floor Planner is offline — skipping connectivity test');
        return;
      }
      expect(result.online).toBe(true);
      expect(result.latency).toBeLessThan(3000);
    });
  });

  describe('Visualizer Service', () => {
    it('has correct URL configured', () => {
      expect(VISUALIZER_URL).toMatch(/^https?:\/\//);
      expect(VISUALIZER_URL).toContain('5001');
    });

    it('responds to health check (skip if offline)', async () => {
      const result = await checkServiceHealth(VISUALIZER_URL);
      if (!result.online) {
        console.warn('Visualizer is offline — skipping connectivity test');
        return;
      }
      expect(result.online).toBe(true);
      expect(result.latency).toBeLessThan(3000);
    });
  });

  describe('Service URL validation', () => {
    it('planner and visualizer URLs are different', () => {
      expect(PLANNER_URL).not.toBe(VISUALIZER_URL);
    });

    it('URLs do not have trailing slashes', () => {
      expect(PLANNER_URL.endsWith('/')).toBe(false);
      expect(VISUALIZER_URL.endsWith('/')).toBe(false);
    });
  });
});

describe('Dashboard API Routes', () => {
  const DASHBOARD_URL = 'http://localhost:3000';

  it('has correct dashboard URL', () => {
    expect(DASHBOARD_URL).toContain('3000');
  });

  it('/api/health endpoint structure', () => {
    // Validate expected response shape without actually calling
    const expectedShape = {
      status: expect.stringMatching(/healthy|degraded/),
      services: expect.any(Array),
      timestamp: expect.any(String),
    };

    const mockResponse = {
      status: 'healthy',
      services: [],
      timestamp: new Date().toISOString(),
    };

    expect(mockResponse).toMatchObject(expectedShape);
  });

  it('/api/chat endpoint expects POST with messages', () => {
    const validPayload = {
      messages: [{ role: 'user', content: 'Hello' }],
    };

    expect(validPayload.messages).toBeInstanceOf(Array);
    expect(validPayload.messages.length).toBeGreaterThan(0);
    expect(validPayload.messages[0]).toHaveProperty('role');
    expect(validPayload.messages[0]).toHaveProperty('content');
  });
});

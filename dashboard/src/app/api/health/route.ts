import { NextRequest } from 'next/server';

interface ServiceCheck {
  name: string;
  url: string;
  status: 'online' | 'offline';
  latency: number;
}

export async function GET(req: NextRequest) {
  const services = [
    { name: 'Floor Planner', url: process.env.NEXT_PUBLIC_PLANNER_URL || 'http://localhost:5000' },
    { name: 'Visualizer', url: process.env.NEXT_PUBLIC_VISUALIZER_URL || 'http://localhost:5001' },
  ];

  const results: ServiceCheck[] = await Promise.all(
    services.map(async (service) => {
      const start = Date.now();
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 3000);
        await fetch(service.url, { signal: controller.signal });
        clearTimeout(timeout);
        return {
          name: service.name,
          url: service.url,
          status: 'online' as const,
          latency: Date.now() - start,
        };
      } catch {
        return {
          name: service.name,
          url: service.url,
          status: 'offline' as const,
          latency: Date.now() - start,
        };
      }
    })
  );

  const allOnline = results.every((r) => r.status === 'online');

  return new Response(
    JSON.stringify({
      status: allOnline ? 'healthy' : 'degraded',
      services: results,
      timestamp: new Date().toISOString(),
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }
  );
}

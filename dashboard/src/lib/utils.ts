export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ');
}

export function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export async function checkServiceHealth(url: string): Promise<{ online: boolean; latency: number }> {
  const start = Date.now();
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    const response = await fetch(url, { signal: controller.signal, mode: 'no-cors' });
    clearTimeout(timeout);
    return { online: true, latency: Date.now() - start };
  } catch {
    return { online: false, latency: Date.now() - start };
  }
}

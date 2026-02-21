'use client';

import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { ExternalLink, AlertCircle, RefreshCw } from 'lucide-react';

const LIVE_DETECTION_URL = process.env.NEXT_PUBLIC_LIVE_DETECTION_URL || 'http://localhost:5002';

export default function MonitoringPage() {
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [iframeKey, setIframeKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const check = async () => {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 3000);
        await fetch(`${LIVE_DETECTION_URL}/api/health`, { signal: controller.signal, mode: 'no-cors' });
        clearTimeout(timeout);
        setIsOnline(true);
      } catch {
        setIsOnline(false);
      }
    };
    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col h-full bg-surface-1">
      {/* Header */}
      <div className="flex items-center justify-between px-7 py-3.5 border-b border-surface-3/60 bg-white">
        <h2 className="font-display text-[15px] font-semibold text-ink-900 tracking-[-0.02em]">Live Monitoring</h2>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <div className={cn(
              'w-1.5 h-1.5 rounded-full',
              isOnline === null ? 'bg-ink-200' : isOnline ? 'bg-emerald-500' : 'bg-red-400'
            )} />
            <span className="text-[11px] text-ink-400">
              {isOnline === null ? 'Checking...' : isOnline ? 'Online' : 'Offline'}
            </span>
          </div>

          <button
            onClick={() => { setIframeKey(k => k + 1); setIsLoading(true); }}
            className="p-1.5 rounded-lg hover:bg-surface-2 text-ink-300 hover:text-ink-500 transition-colors"
            title="Reload"
          >
            <RefreshCw size={14} />
          </button>

          <a
            href={LIVE_DETECTION_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium text-ink-400 hover:text-ink-600 hover:bg-surface-2 transition-colors"
          >
            <ExternalLink size={13} />
            Open
          </a>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 relative">
        {isOnline === false && (
          <div className="absolute inset-0 flex items-center justify-center bg-white z-10">
            <div className="text-center max-w-sm">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-red-50 mb-4">
                <AlertCircle size={24} className="text-red-400" />
              </div>
              <h3 className="font-display text-[15px] font-semibold text-ink-900 mb-2">
                Live Detection server is offline
              </h3>
              <p className="text-[13px] text-ink-400 mb-4 leading-relaxed">
                Start the live detection server:
              </p>
              <div className="bg-neutral-900 rounded-lg px-4 py-3 text-left">
                <code className="text-[12px] text-emerald-400 font-mono">
                  cd live_detection && python app.py
                </code>
              </div>
              <p className="text-[12px] text-ink-300 mt-4">
                Requires a webcam and a venue YAML file from the Floor Planner.
              </p>
            </div>
          </div>
        )}

        {isLoading && isOnline !== false && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/90 z-10">
            <div className="flex items-center gap-2 text-ink-400">
              <RefreshCw size={16} className="animate-spin" />
              <span className="text-[13px]">Loading live detection...</span>
            </div>
          </div>
        )}

        {isOnline !== false && (
          <iframe
            key={iframeKey}
            src={LIVE_DETECTION_URL}
            className="w-full h-full border-0"
            onLoad={() => setIsLoading(false)}
            allow="camera;microphone"
          />
        )}
      </div>
    </div>
  );
}

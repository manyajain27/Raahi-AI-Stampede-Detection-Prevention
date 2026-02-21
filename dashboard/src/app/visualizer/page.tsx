'use client';

import { useState, useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import { ExternalLink, AlertCircle, RefreshCw, X } from 'lucide-react';

interface EventData {
  capacity?: string;
  venueType?: string;
  eventType?: string;
  conversationSummary?: string;
}

const VISUALIZER_URL = process.env.NEXT_PUBLIC_VISUALIZER_URL || 'http://localhost:5001';

export default function VisualizerPage() {
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [iframeKey, setIframeKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [eventData, setEventData] = useState<EventData | null>(null);
  const [showContext, setShowContext] = useState(true);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Load event data from localStorage
  useEffect(() => {
    try {
      const raw = localStorage.getItem('raahi_event_data');
      if (raw) setEventData(JSON.parse(raw) as EventData);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    const check = async () => {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 3000);
        await fetch(VISUALIZER_URL, { signal: controller.signal, mode: 'no-cors' });
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

  const hasEventContext = eventData && (eventData.capacity || eventData.eventType);

  return (
    <div className="flex flex-col h-full bg-surface-1">
      {/* Header */}
      <div className="flex items-center justify-between px-7 py-3.5 border-b border-surface-3/60 bg-white">
        <h2 className="font-display text-[15px] font-semibold text-ink-900 tracking-[-0.02em]">Crowd Simulator</h2>

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
            href={VISUALIZER_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium text-ink-400 hover:text-ink-600 hover:bg-surface-2 transition-colors"
          >
            <ExternalLink size={13} />
            Open
          </a>
        </div>
      </div>

      {/* Event context banner */}
      {hasEventContext && showContext && (
        <div className="px-6 py-2.5 bg-amber-50 border-b border-amber-100 animate-fade-in">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4 text-[12px]">
              <span className="font-semibold text-amber-700">Simulating for your event</span>
              {eventData.eventType && (
                <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-600 font-medium capitalize">
                  {eventData.eventType}
                </span>
              )}
              {eventData.capacity && (
                <span className="text-amber-600">
                  {parseInt(eventData.capacity).toLocaleString()} capacity
                </span>
              )}
            </div>
            <button
              onClick={() => setShowContext(false)}
              className="p-1 rounded hover:bg-amber-100 text-amber-400 hover:text-amber-600 transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 relative">
        {isOnline === false && (
          <div className="absolute inset-0 flex items-center justify-center bg-white z-10">
            <div className="text-center max-w-sm">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-red-50 mb-4">
                <AlertCircle size={24} className="text-red-400" />
              </div>
              <h3 className="font-display text-[15px] font-semibold text-ink-900 mb-2">
                Visualizer backend is offline
              </h3>
              <p className="text-[13px] text-ink-400 mb-4 leading-relaxed">
                Start the Flask-SocketIO server to use the Simulator:
              </p>
              <div className="bg-neutral-900 rounded-lg px-4 py-3 text-left">
                <code className="text-[12px] text-emerald-400 font-mono">
                  cd visualizer && python app.py
                </code>
              </div>
              <p className="text-[12px] text-ink-300 mt-4">
                Make sure you have created a floor plan first using the Floor Planner.
              </p>
            </div>
          </div>
        )}

        {isLoading && isOnline !== false && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
            <div className="flex items-center gap-2 text-neutral-400">
              <RefreshCw size={16} className="animate-spin" />
              <span className="text-[13px]">Loading simulator...</span>
            </div>
          </div>
        )}

        {isOnline !== false && (
          <iframe
            ref={iframeRef}
            key={iframeKey}
            src={VISUALIZER_URL}
            className="w-full h-full border-0"
            title="Crowd Simulator"
            onLoad={() => setIsLoading(false)}
          />
        )}
      </div>
    </div>
  );
}

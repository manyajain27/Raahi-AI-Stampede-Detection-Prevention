'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { ExternalLink, AlertCircle, RefreshCw, X } from 'lucide-react';

interface EventData {
  capacity?: string;
  venueType?: string;
  eventType?: string;
  conversationSummary?: string;
  floorPlanImage?: string;
  floorPlanImageName?: string;
}

const PLANNER_URL = process.env.NEXT_PUBLIC_PLANNER_URL || 'http://localhost:5000';

export default function FloorPlannerPage() {
  const router = useRouter();
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [iframeKey, setIframeKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [eventData, setEventData] = useState<EventData | null>(null);
  const [showContext, setShowContext] = useState(true);
  const [dataSent, setDataSent] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Listen for "Run in Visualizer" clicks from the iframe
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'raahi_navigate' && event.data?.path === '/visualizer') {
        router.push('/visualizer');
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [router]);

  // Load event data from localStorage
  useEffect(() => {
    try {
      const raw = localStorage.getItem('raahi_event_data');
      if (raw) {
        const data = JSON.parse(raw) as EventData;
        setEventData(data);
      }
    } catch { /* ignore parse errors */ }
  }, []);

  // Check if planner backend is running
  useEffect(() => {
    const check = async () => {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 3000);
        await fetch(PLANNER_URL, { signal: controller.signal, mode: 'no-cors' });
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

  // Send pre-loaded data to iframe via postMessage after it loads
  const handleIframeLoad = useCallback(() => {
    setIsLoading(false);
    if (!eventData || dataSent) return;

    const iframe = iframeRef.current;
    if (!iframe?.contentWindow) return;

    // Small delay to ensure the iframe's JS is ready
    setTimeout(() => {
      // Send capacity data
      if (eventData.capacity) {
        iframe.contentWindow?.postMessage({
          type: 'raahi_set_capacity',
          maxCapacity: parseInt(eventData.capacity, 10),
          expectedAttendance: Math.round(parseInt(eventData.capacity, 10) * 0.85),
        }, '*');
      }

      // Send background image
      if (eventData.floorPlanImage) {
        iframe.contentWindow?.postMessage({
          type: 'raahi_load_image',
          dataUrl: eventData.floorPlanImage,
          fileName: eventData.floorPlanImageName || 'floor-plan.png',
        }, '*');
      }

      setDataSent(true);
    }, 1000);
  }, [eventData, dataSent]);

  const iframeSrc = PLANNER_URL;

  const hasEventContext = eventData && (eventData.capacity || eventData.eventType || eventData.floorPlanImageName);

  return (
    <div className="flex flex-col h-full bg-surface-1">
      {/* Header */}
      <div className="flex items-center justify-between px-7 py-3.5 border-b border-surface-3/60 bg-white">
        <div className="flex items-center gap-5">
          <h2 className="font-display text-[15px] font-semibold text-ink-900 tracking-[-0.02em]">Floor Planner</h2>

        </div>

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
            onClick={() => { setIframeKey(k => k + 1); setIsLoading(true); setDataSent(false); }}
            className="p-1.5 rounded-lg hover:bg-surface-2 text-ink-300 hover:text-ink-500 transition-colors"
            title="Reload"
          >
            <RefreshCw size={14} />
          </button>

          <a
            href={iframeSrc}
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
        <div className="px-7 py-2.5 bg-brand-50 border-b border-brand-100 animate-fade-in">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4 text-[12px]">
              <span className="font-semibold text-brand-700">Event data pre-loaded</span>
              {eventData.eventType && (
                <span className="px-2 py-0.5 rounded-full bg-brand-100 text-brand-600 font-medium capitalize">
                  {eventData.eventType}
                </span>
              )}
              {eventData.capacity && (
                <span className="text-brand-600">
                  {parseInt(eventData.capacity).toLocaleString()} capacity
                </span>
              )}
              {eventData.floorPlanImageName && (
                <span className="text-brand-600">
                  Image: {eventData.floorPlanImageName}
                </span>
              )}
              {dataSent && (
                <span className="text-emerald-600 font-medium">Sent to editor</span>
              )}
            </div>
            <button
              onClick={() => setShowContext(false)}
              className="p-1 rounded hover:bg-brand-100 text-brand-400 hover:text-brand-600 transition-colors"
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
                Floor Planner backend is offline
              </h3>
              <p className="text-[13px] text-ink-400 mb-4 leading-relaxed">
                Start the Flask server to use the Floor Planner:
              </p>
              <div className="bg-neutral-900 rounded-lg px-4 py-3 text-left">
                <code className="text-[12px] text-emerald-400 font-mono">
                  cd floor_planner && python app.py
                </code>
              </div>
            </div>
          </div>
        )}

        {isLoading && isOnline !== false && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/90 z-10">
            <div className="flex items-center gap-2 text-neutral-400">
              <RefreshCw size={16} className="animate-spin" />
              <span className="text-[13px]">Loading editor...</span>
            </div>
          </div>
        )}

        {isOnline !== false && (
          <iframe
            ref={iframeRef}
            key={iframeKey}
            src={iframeSrc}
            className="w-full h-full border-0"
            title="Floor Planner"
            onLoad={handleIframeLoad}
          />
        )}
      </div>
    </div>
  );
}

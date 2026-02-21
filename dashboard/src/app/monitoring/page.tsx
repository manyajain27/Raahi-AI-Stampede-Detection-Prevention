'use client';

export default function MonitoringPage() {
  return (
    <div className="flex flex-col items-center justify-center h-full bg-surface-1">
      <div className="text-center max-w-md">
        <h2 className="font-display text-[24px] font-semibold text-ink-900 tracking-[-0.03em] mb-3">
          Live Monitoring
        </h2>

        <p className="text-[14px] text-ink-400 leading-relaxed mb-8 max-w-sm mx-auto">
          Real-time crowd density tracking, alert systems, and live camera feeds
          will be available here.
        </p>

        <div className="inline-flex items-center px-4 py-2 rounded-full bg-amber-50 border border-amber-100">
          <span className="text-[12px] font-medium text-amber-600">Under Construction</span>
        </div>

        <div className="grid grid-cols-2 gap-2.5 mt-12">
          {[
            { title: 'Live Density Heatmap', desc: 'Real-time crowd density visualization' },
            { title: 'Alert System', desc: 'Automated stampede risk notifications' },
            { title: 'Camera Integration', desc: 'Live CCTV feed with AI analysis' },
            { title: 'Incident Logging', desc: 'Track and respond to events in real-time' },
          ].map((feature) => (
            <div
              key={feature.title}
              className="p-4 rounded-2xl border border-dashed border-surface-3 bg-white/50"
            >
              <div className="shimmer h-1.5 w-14 rounded-full mb-2.5" />
              <p className="text-[12px] font-medium text-ink-400">{feature.title}</p>
              <p className="text-[11px] text-ink-300 mt-0.5">{feature.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

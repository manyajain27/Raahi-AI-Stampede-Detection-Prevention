'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  {
    label: 'Event Setup',
    href: '/',
    badge: null,
  },
  {
    label: 'Floor Planner',
    href: '/floor-planner',
    badge: null,
  },
  {
    label: 'Simulator',
    href: '/visualizer',
    badge: null,
  },
  {
    label: 'Live Monitoring',
    href: '/monitoring',
    badge: 'Soon',
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[260px] bg-[#111118] text-white flex flex-col z-50">
      {/* Brand */}
      <div className="px-7 pt-8 pb-8">
        <Link href="/" className="group">
          <h1 className="font-display text-[22px] font-semibold tracking-[-0.03em] text-white">
            Raahi
          </h1>
          <p className="text-[11px] text-white/30 font-medium tracking-[0.08em] uppercase mt-0.5">
            Crowd Intelligence
          </p>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 space-y-0.5">
        <p className="text-[10px] font-medium text-white/20 uppercase tracking-[0.1em] px-3 mb-3">
          Platform
        </p>
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center justify-between px-3 py-2.5 rounded-xl transition-all duration-200',
                isActive
                  ? 'bg-white/[0.07] text-white'
                  : 'text-white/40 hover:bg-white/[0.04] hover:text-white/70'
              )}
            >
              <span className={cn(
                'text-[13.5px] font-medium tracking-[-0.01em]',
                isActive && 'text-white'
              )}>
                {item.label}
              </span>
              {item.badge && (
                <span className="text-[9px] font-semibold px-2 py-0.5 rounded-full bg-brand-500/15 text-brand-300 uppercase tracking-[0.05em]">
                  {item.badge}
                </span>
              )}
              {isActive && (
                <div className="w-1 h-1 rounded-full bg-brand-400" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-7 py-6">
        <p className="text-[10px] text-white/15 font-medium tracking-wide">
          v1.0 &middot; K-Hacks 2025
        </p>
      </div>
    </aside>
  );
}

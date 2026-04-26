'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState, type ReactNode } from 'react';

import { fetchJson, type SystemHealthResponse } from '@/lib/api';

type NavItem = {
  href: string;
  label: string;
  icon: ReactNode;
  description: string;
};

type NavGroup = {
  label: string;
  items: NavItem[];
};

const navGroups: NavGroup[] = [
  {
    label: 'Overview',
    items: [
      {
        href: '/',
        label: 'Home',
        description: 'Product overview',
        icon: <IconHome />,
      },
    ],
  },
  {
    label: 'OpenEnv',
    items: [
      {
        href: '/openenv',
        label: 'Environment',
        description: 'Reset / step playground',
        icon: <IconChip />,
      },
    ],
  },
  {
    label: 'Live Surfaces',
    items: [
      {
        href: '/command-center',
        label: 'Command Center',
        description: 'Realtime training feed',
        icon: <IconRadio />,
      },
      {
        href: '/alerts',
        label: 'Alerts',
        description: 'Live anomaly stream',
        icon: <IconBell />,
      },
    ],
  },
  {
    label: 'Pipeline',
    items: [
      {
        href: '/analytics',
        label: 'Analytics',
        description: 'Historical trends',
        icon: <IconChart />,
      },
      {
        href: '/inspector',
        label: 'Inspector',
        description: 'Prompt / output traces',
        icon: <IconSearch />,
      },
    ],
  },
  {
    label: 'Engine',
    items: [
      {
        href: '/remorph-engine',
        label: 'ReMorph Engine',
        description: 'API repair telemetry',
        icon: <IconShield />,
      },
    ],
  },
];

const flatNav: NavItem[] = navGroups.flatMap((group) => group.items);

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const active = flatNav.find((item) => item.href === pathname) ?? flatNav[0];

  return (
    <div className="app-shell">
      <Sidebar pathname={pathname} />
      <div className="shell-main">
        <Topbar active={active} />
        <main className="page-frame">{children}</main>
      </div>
    </div>
  );
}

function Sidebar({ pathname }: { pathname: string }) {
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = () => {
      fetchJson<SystemHealthResponse>('/api/realtime/system-health')
        .then((payload) => {
          if (!cancelled) {
            setHealth(payload);
          }
        })
        .catch(() => undefined);
    };
    tick();
    const interval = window.setInterval(tick, 2200);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <aside className="sidebar">
      <Link href="/" className="sidebar-brand">
        <span className="sidebar-brand-mark" aria-hidden />
        <span className="sidebar-brand-text">
          <strong>ReMorph</strong>
          <span>Observability OS</span>
        </span>
      </Link>

      <nav className="sidebar-nav">
        {navGroups.map((group) => (
          <div className="sidebar-group" key={group.label}>
            <div className="sidebar-section-label">{group.label}</div>
            {group.items.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={isActive ? 'sidebar-link active' : 'sidebar-link'}
                >
                  <span className="icon" aria-hidden>
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-footer-row">
          <span>System</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <span className="live-dot" />
            <strong>Online</strong>
          </span>
        </div>
        <div className="sidebar-footer-row">
          <span>Stream rate</span>
          <strong>{health ? `${health.stream_rate_per_sec.toFixed(0)} ev/s` : '—'}</strong>
        </div>
        <div className="sidebar-footer-row">
          <span>Active runs</span>
          <strong>{health ? health.active_run_count : '—'}</strong>
        </div>
        <div className="sidebar-footer-row">
          <span>Open alerts</span>
          <strong>{health ? health.alerts_open : '—'}</strong>
        </div>
      </div>
    </aside>
  );
}

function Topbar({ active }: { active: NavItem }) {
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = () => {
      fetchJson<SystemHealthResponse>('/api/realtime/system-health')
        .then((payload) => {
          if (!cancelled) {
            setHealth(payload);
          }
        })
        .catch(() => undefined);
    };
    tick();
    const interval = window.setInterval(tick, 2200);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="breadcrumb">
          <span>ReMorph</span>
          <IconChevron />
          <strong>{active.label}</strong>
          <span style={{ color: 'var(--text-faint)', marginLeft: 6 }}>· {active.description}</span>
        </div>
      </div>
      <div className="topbar-right">
        <span className="health-pill">
          <span className="dot" />
          <strong>{health ? `${health.ingest_rate_per_sec.toFixed(0)}` : '—'}</strong>
          <span>ingest/s</span>
        </span>
        <span className="health-pill">
          <strong>{health ? health.queue_depth : '—'}</strong>
          <span>queued</span>
        </span>
        <span className="health-pill">
          <strong>{health ? `${health.storage_latency_ms.toFixed(1)}ms` : '—'}</strong>
          <span>storage</span>
        </span>
        <button className="icon-btn" aria-label="Settings">
          <IconSettings />
        </button>
      </div>
    </header>
  );
}

/* ---------- Inline icons (kept lightweight & crisp) ---------- */
function IconHome() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="m3 11 9-8 9 8" />
      <path d="M5 10v10h14V10" />
    </svg>
  );
}

function IconChip() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 7h10v10H7z" />
      <path d="M7 3v2M17 3v2M7 19v2M17 19v2M3 7h2M3 17h2M19 7h2M19 17h2" />
    </svg>
  );
}

function IconRadio() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="2" />
      <path d="M16.24 7.76a6 6 0 0 1 0 8.49M7.76 16.24a6 6 0 0 1 0-8.49" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 19.07a10 10 0 0 1 0-14.14" />
    </svg>
  );
}

function IconBell() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  );
}

function IconChart() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18" />
      <path d="m7 14 4-4 4 4 5-6" />
    </svg>
  );
}

function IconSearch() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

function IconShield() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function IconChevron() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="m9 6 6 6-6 6" />
    </svg>
  );
}

function IconSun() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2.5M12 19.5V22M4.93 4.93l1.77 1.77M17.3 17.3l1.77 1.77M2 12h2.5M19.5 12H22M4.93 19.07l1.77-1.77M17.3 6.7l1.77-1.77" />
    </svg>
  );
}

function IconMoon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
    </svg>
  );
}

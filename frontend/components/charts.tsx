'use client';

import { useEffect, useRef, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { formatTimestamp, type Series } from '@/lib/api';

function normalizeSeries(series: Series[]) {
  const pointsByIndex = new Map<number, Record<string, string | number>>();
  series.forEach((entry) => {
    entry.points.forEach((point, index) => {
      const existing = pointsByIndex.get(index) ?? { timestamp: formatTimestamp(point.timestamp) };
      existing[entry.id] = point.value;
      pointsByIndex.set(index, existing);
    });
  });
  return Array.from(pointsByIndex.values());
}

type TooltipPayloadItem = {
  color?: string;
  name?: string | number;
  value?: number | string;
  dataKey?: string | number;
};

function GlassTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }
  return (
    <div
      style={{
        background: 'var(--tooltip-bg, rgba(8, 9, 14, 0.92))',
        backdropFilter: 'blur(22px) saturate(140%)',
        border: '1px solid var(--tooltip-border, rgba(255, 255, 255, 0.12))',
        borderRadius: 14,
        padding: '12px 14px',
        minWidth: 160,
        boxShadow: 'var(--tooltip-shadow, 0 18px 44px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.04) inset)',
        fontFamily: 'var(--font-sans)',
      }}
    >
      <div
        style={{
          fontSize: 11,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: 'var(--text-muted)',
          fontFeatureSettings: '"tnum"',
          marginBottom: 8,
        }}
      >
        {label}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {payload.map((entry, index) => (
          <div
            key={`${entry.dataKey ?? index}`}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14 }}
          >
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: 'var(--text-secondary)' }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 999,
                  background: entry.color ?? 'var(--electric)',
                  boxShadow: `0 0 10px ${entry.color ?? 'var(--electric)'}`,
                }}
              />
              {entry.name}
            </span>
            <strong
              style={{
                fontSize: 13,
                color: 'var(--text-primary)',
                fontWeight: 600,
                fontFeatureSettings: '"tnum"',
                letterSpacing: '-0.005em',
              }}
            >
              {typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}
            </strong>
          </div>
        ))}
      </div>
    </div>
  );
}

const axisTick = { fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-sans)' } as const;

function useChartSize(height: number) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 0, height });

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return undefined;

    const measure = () => {
      const width = Math.max(0, Math.floor(node.clientWidth));
      const measuredHeight = Math.max(0, Math.floor(node.clientHeight || height));
      setSize({ width, height: measuredHeight });
    };

    measure();
    const observer = new ResizeObserver(() => measure());
    observer.observe(node);
    return () => observer.disconnect();
  }, [height]);

  return { containerRef, width: size.width, height: size.height };
}

export function MultiSeriesChart({ series, height = 280 }: { series: Series[]; height?: number }) {
  const data = normalizeSeries(series);
  const { containerRef, width, height: measuredHeight } = useChartSize(height);
  return (
    <div ref={containerRef} className="chart-wrap" style={{ height }}>
      {width > 10 && measuredHeight > 10 ? (
        <AreaChart width={width} height={measuredHeight} data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
          <defs>
            {series.map((entry) => (
              <linearGradient key={entry.id} id={`gradient-${entry.id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={entry.color} stopOpacity={0.42} />
                <stop offset="100%" stopColor={entry.color} stopOpacity={0.0} />
              </linearGradient>
            ))}
            <filter id="glow-soft" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <CartesianGrid stroke="var(--chart-grid, rgba(255, 255, 255, 0.05))" vertical={false} />
          <XAxis dataKey="timestamp" tickLine={false} axisLine={false} tick={axisTick} minTickGap={32} />
          <YAxis tickLine={false} axisLine={false} tick={axisTick} width={42} />
          <Tooltip
            cursor={{ stroke: 'var(--chart-cursor, rgba(255, 255, 255, 0.1))', strokeDasharray: '3 3' }}
            content={<GlassTooltip />}
          />
          <Legend
            iconType="circle"
            wrapperStyle={{ paddingTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}
          />
          {series.map((entry) => (
            <Area
              key={entry.id}
              type="monotone"
              dataKey={entry.id}
              name={entry.label}
              stroke={entry.color}
              fill={`url(#gradient-${entry.id})`}
              strokeWidth={2.2}
              isAnimationActive
              animationDuration={780}
              animationEasing="ease-out"
              filter="url(#glow-soft)"
            />
          ))}
        </AreaChart>
      ) : null}
    </div>
  );
}

export function RealtimeLineChart({ series, height = 300 }: { series: Series[]; height?: number }) {
  const data = normalizeSeries(series);
  const { containerRef, width, height: measuredHeight } = useChartSize(height);
  return (
    <div ref={containerRef} className="chart-wrap" style={{ height }}>
      {width > 10 && measuredHeight > 10 ? (
        <LineChart width={width} height={measuredHeight} data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
          <defs>
            <filter id="glow-line" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <CartesianGrid stroke="var(--chart-grid, rgba(255, 255, 255, 0.05))" vertical={false} />
          <XAxis dataKey="timestamp" tickLine={false} axisLine={false} tick={axisTick} minTickGap={32} />
          <YAxis tickLine={false} axisLine={false} tick={axisTick} width={42} />
          <Tooltip cursor={{ stroke: 'var(--chart-cursor, rgba(255, 255, 255, 0.1))', strokeDasharray: '3 3' }} content={<GlassTooltip />} />
          <Legend
            iconType="circle"
            wrapperStyle={{ paddingTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}
          />
          <ReferenceLine y={0} stroke="var(--chart-cursor, rgba(255, 255, 255, 0.1))" />
          {series.map((item) => (
            <Line
              key={item.id}
              type="monotone"
              dataKey={item.id}
              stroke={item.color}
              strokeWidth={2.4}
              dot={false}
              name={item.label}
              filter="url(#glow-line)"
              isAnimationActive
              animationDuration={680}
              animationEasing="ease-out"
            />
          ))}
        </LineChart>
      ) : null}
    </div>
  );
}

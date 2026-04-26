'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';

/**
 * Hero pipeline visualization:
 *   Failed Request  →  AI Repair Engine  →  Healed Response
 *
 * Built with layered SVG + CSS depth tricks for a premium 3D feel:
 *   - Floating cards with subtle Y bob
 *   - Glowing connecting paths with animated flow
 *   - Concentric pulse rings around the engine
 *   - Streaming particles along the path
 *   - Mouse-reactive parallax tilt
 */
const BROKEN_CASES = [
  {
    request: 'POST /api/v1/users',
    detail: '422 Validation Error',
    note: 'payload.amount expected integer cents',
  },
  {
    request: 'GET /api/v2/orders',
    detail: '404 Route Not Found',
    note: 'v2 route drifted from active contract',
  },
  {
    request: 'POST /login',
    detail: '401 Unauthorized',
    note: 'missing bearer token in auth chain',
  },
  {
    request: 'PUT /billing',
    detail: '500 Schema Drift',
    note: 'response schema mismatched upstream',
  },
];

const HEALED_CASES = [
  {
    request: 'POST /api/v1/users',
    detail: '200 OK',
    note: 'payload normalized + retry passed',
  },
  {
    request: 'GET /api/v1/orders',
    detail: 'Success',
    note: 'route remapped to supported version',
  },
  {
    request: 'POST /login',
    detail: 'Auth Fixed',
    note: 'token injected from policy adapter',
  },
  {
    request: 'PUT /billing',
    detail: 'Retry Passed',
    note: 'schema coerced to canonical format',
  },
];

const ENGINE_PHASES = [
  'Detecting Error',
  'Reading Schema',
  'Repairing Payload',
  'Validating Route',
  'Safe Retry Ready',
];

export function HeroPipeline() {
  const stageRef = useRef<HTMLDivElement | null>(null);
  const [caseIndex, setCaseIndex] = useState(0);
  const [phaseIndex, setPhaseIndex] = useState(0);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return undefined;

    const handleMove = (event: MouseEvent) => {
      const rect = stage.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width - 0.5;
      const y = (event.clientY - rect.top) / rect.height - 0.5;
      stage.style.setProperty('--rotX', `${(-y * 6).toFixed(2)}deg`);
      stage.style.setProperty('--rotY', `${(x * 8).toFixed(2)}deg`);
      stage.style.setProperty('--mx', `${(x * 24).toFixed(2)}px`);
      stage.style.setProperty('--my', `${(y * 24).toFixed(2)}px`);
    };

    const handleLeave = () => {
      stage.style.setProperty('--rotX', `0deg`);
      stage.style.setProperty('--rotY', `0deg`);
      stage.style.setProperty('--mx', `0px`);
      stage.style.setProperty('--my', `0px`);
    };

    stage.addEventListener('mousemove', handleMove);
    stage.addEventListener('mouseleave', handleLeave);
    return () => {
      stage.removeEventListener('mousemove', handleMove);
      stage.removeEventListener('mouseleave', handleLeave);
    };
  }, []);

  useEffect(() => {
    const caseTimer = window.setInterval(() => {
      setCaseIndex((index) => (index + 1) % BROKEN_CASES.length);
    }, 3200);
    const phaseTimer = window.setInterval(() => {
      setPhaseIndex((index) => (index + 1) % ENGINE_PHASES.length);
    }, 1200);

    return () => {
      window.clearInterval(caseTimer);
      window.clearInterval(phaseTimer);
    };
  }, []);

  const broken = BROKEN_CASES[caseIndex];
  const healed = HEALED_CASES[caseIndex];
  const enginePhase = ENGINE_PHASES[phaseIndex];
  const particleSeeds = useMemo(() => Array.from({ length: 18 }, (_, index) => index), []);

  return (
    <div
      ref={stageRef}
      className="hero-stage"
      style={
        {
          '--rotX': '0deg',
          '--rotY': '0deg',
          '--mx': '0px',
          '--my': '0px',
        } as CSSProperties
      }
    >
      <div className="hero-stage-bg">
        {particleSeeds.map((seed) => (
          <span
            key={`star-${seed}`}
            className="hero-star"
            style={
              {
                '--sx': `${(seed * 31) % 100}%`,
                '--sy': `${(seed * 47) % 100}%`,
                '--sd': `${2 + (seed % 4)}s`,
                '--so': `${0.25 + (seed % 5) * 0.08}`,
              } as CSSProperties
            }
          />
        ))}
      </div>

      <div
        className="hero-pipeline"
        style={{
          transform:
            'rotateX(var(--rotX)) rotateY(var(--rotY)) translate3d(calc(var(--mx) * 0.2), calc(var(--my) * 0.2), 0)',
          transition: 'transform 240ms cubic-bezier(0.22, 1, 0.36, 1)',
        }}
      >
        <motion.article
          className="pipe-node pipe-node-failed"
          initial={{ opacity: 0, x: -18 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        >
          <strong>Broken Request</strong>
          <AnimatePresence mode="wait">
            <motion.div
              key={`broken-${caseIndex}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35 }}
            >
              <span className="row error">{broken.request}</span>
              <span className="row">{broken.detail}</span>
              <span className="row">{broken.note}</span>
            </motion.div>
          </AnimatePresence>
        </motion.article>

        <div className="pipe-flow" aria-hidden>
          <FlowSegment id="flow-in" />
        </div>

        <motion.article
          className="pipe-node-engine"
          whileHover={{ scale: 1.03 }}
          transition={{ type: 'spring', stiffness: 180, damping: 18 }}
        >
          <span>ReMorph</span>
          <strong>AI Engine</strong>
          <AnimatePresence mode="wait">
            <motion.em
              key={`phase-${phaseIndex}`}
              className="engine-phase"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.25 }}
            >
              {enginePhase}
            </motion.em>
          </AnimatePresence>
          <div className="engine-diagnostics" aria-hidden>
            <span />
            <span />
            <span />
            <span />
          </div>
          <EnginePulse />
        </motion.article>

        <div className="pipe-flow" aria-hidden>
          <FlowSegment id="flow-out" reverse />
        </div>

        <motion.article
          className="pipe-node pipe-node-healed"
          initial={{ opacity: 0, x: 18 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        >
          <strong>Healed Response</strong>
          <AnimatePresence mode="wait">
            <motion.div
              key={`healed-${caseIndex}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35 }}
            >
              <span className="row ok">{healed.request}</span>
              <span className="row ok">{healed.detail}</span>
              <span className="row">{healed.note}</span>
              <span className="row ok">confidence: 0.96</span>
            </motion.div>
          </AnimatePresence>
        </motion.article>
      </div>
    </div>
  );
}

function FlowSegment({ id, reverse = false }: { id: string; reverse?: boolean }) {
  const startColor = reverse ? 'rgba(34, 211, 238, 0.05)' : 'rgba(79, 140, 255, 0.05)';
  const midColor = reverse ? 'rgba(52, 211, 153, 0.78)' : 'rgba(139, 92, 246, 0.78)';
  const endColor = reverse ? 'rgba(52, 211, 153, 0.05)' : 'rgba(34, 211, 238, 0.05)';
  const pathD = 'M 4 30 C 60 4, 180 56, 236 30';
  const particleColor = reverse ? '#6ee7b7' : '#a78bfa';

  return (
    <svg className="pipe-flow-svg" viewBox="0 0 240 60" preserveAspectRatio="none" aria-hidden>
      <defs>
        <linearGradient id={`${id}-grad`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={startColor} />
          <stop offset="50%" stopColor={midColor} />
          <stop offset="100%" stopColor={endColor} />
        </linearGradient>
        <filter id={`${id}-glow`} x="-20%" y="-50%" width="140%" height="200%">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <path
        d={pathD}
        stroke={`url(#${id}-grad)`}
        strokeWidth="1.6"
        fill="none"
        filter={`url(#${id}-glow)`}
      />
      {[0, 1, 2, 3, 4].map((dot) => (
        <circle
          key={dot}
          r="2.4"
          fill={particleColor}
          style={{
            filter: `drop-shadow(0 0 6px ${particleColor})`,
            offsetPath: `path("${pathD}")`,
            offsetRotate: '0deg',
            animation: `flowParticle 2.4s ${dot * 0.48}s linear infinite`,
          }}
        />
      ))}
    </svg>
  );
}

function EnginePulse() {
  return (
    <svg
      width="100%"
      height="100%"
      viewBox="0 0 100 100"
      preserveAspectRatio="xMidYMid meet"
      style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
      aria-hidden
    >
      <defs>
        <radialGradient id="engine-core" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(255, 255, 255, 0.85)" />
          <stop offset="26%" stopColor="rgba(79, 140, 255, 0.55)" />
          <stop offset="58%" stopColor="rgba(139, 92, 246, 0.3)" />
          <stop offset="100%" stopColor="rgba(139, 92, 246, 0)" />
        </radialGradient>
      </defs>
      <circle cx="50" cy="50" r="22" fill="url(#engine-core)" opacity="0.8" />
      <circle cx="50" cy="50" r="30" className="engine-rotor rotor-a" />
      <circle cx="50" cy="50" r="35" className="engine-rotor rotor-b" />
      <circle cx="50" cy="50" r="14" className="engine-core-dot" />
      <line x1="10" y1="50" x2="90" y2="50" className="engine-scan" />
    </svg>
  );
}

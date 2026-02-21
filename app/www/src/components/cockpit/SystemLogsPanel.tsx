import { useEffect, useRef, useState } from 'react';
import { Box, Text } from '@mantine/core';
import { useWebRTC } from '@/context/WebRTCContext';

const LOG_THROTTLE_MS = 1000;
const MAX_LINES = 200;

function formatTime() {
  const d = new Date();
  return d.toTimeString().slice(0, 8);
}

export function SystemLogsPanel() {
  const { telemetry } = useWebRTC();
  const [lines, setLines] = useState<string[]>([]);
  const lastLogRef = useRef(0);
  const scrollRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (!telemetry) return;
    const now = Date.now();
    if (now - lastLogRef.current < LOG_THROTTLE_MS) return;
    lastLogRef.current = now;

    const speed =
      telemetry.speed != null && Number.isFinite(telemetry.speed)
        ? Number(telemetry.speed).toFixed(2)
        : '—';
    const heading =
      telemetry.orientation != null
        ? ((Number(telemetry.orientation) / 255) * 360).toFixed(0)
        : '—';
    const signal =
      telemetry.signal_level != null && Number.isFinite(telemetry.signal_level)
        ? Number(telemetry.signal_level).toFixed(1)
        : '—';

    const line = `[${formatTime()}] SPE KPH ${speed} m/s, Heading: ${heading}°, Signal: ${signal}`;
    setLines((prev) => [...prev.slice(-(MAX_LINES - 1)), line]);
  }, [telemetry]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  return (
    <Box
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: 0,
        backgroundColor: 'var(--mantine-color-dark-7)',
        border: '1px solid var(--mantine-color-dark-4)',
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      <Text size="sm" fw={600} p="xs" style={{ borderBottom: '1px solid var(--mantine-color-dark-4)' }}>
        System Logs & Telemetry
      </Text>
      <pre
        ref={scrollRef}
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          backgroundColor: '#0d1117',
          color: '#c9d1d9',
          fontFamily: 'ui-monospace, monospace',
          fontSize: '0.75rem',
          margin: 0,
          padding: 'var(--mantine-spacing-xs)',
        }}
      >
        {lines.length === 0 ? (
          <span style={{ color: 'var(--mantine-color-dark-3)' }}>Waiting for telemetry…</span>
        ) : (
          lines.map((line, i) => (
            <span key={`${i}-${line}`} style={{ display: 'block' }}>
              {line}
            </span>
          ))
        )}
      </pre>
    </Box>
  );
}

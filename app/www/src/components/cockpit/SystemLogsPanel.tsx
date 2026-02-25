import { useEffect, useRef } from 'react';
import { Box, Text } from '@mantine/core';
import { useWebRTC } from '@/context/WebRTCContext';

const LOG_THROTTLE_MS = 1000;

function formatTime() {
  const d = new Date();
  return d.toTimeString().slice(0, 8);
}

export function SystemLogsPanel() {
  const { telemetry, systemLogLines, appendSystemLog } = useWebRTC();
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
      telemetry.orientation != null && Number.isFinite(Number(telemetry.orientation))
        ? Number(telemetry.orientation).toFixed(0)
        : '—';

    const line = `[${formatTime()}] SPE KPH ${speed} m/s, Heading: ${heading}°`;
    appendSystemLog(line);
  }, [telemetry, appendSystemLog]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [systemLogLines]);

  return (
    <Box
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: 0,
        backgroundColor: 'var(--mantine-color-dark-9)',
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
          backgroundColor: 'var(--mantine-color-dark-9)',
          color: '#c9d1d9',
          fontFamily: 'ui-monospace, monospace',
          fontSize: '0.75rem',
          margin: 0,
          padding: 'var(--mantine-spacing-xs)',
        }}
      >
        {systemLogLines.length === 0 ? (
          <span style={{ color: 'var(--mantine-color-dark-3)' }}>Waiting for telemetry…</span>
        ) : (
          systemLogLines.map((line, i) => (
            <span key={`${i}-${line}`} style={{ display: 'block' }}>
              {line}
            </span>
          ))
        )}
      </pre>
    </Box>
  );
}

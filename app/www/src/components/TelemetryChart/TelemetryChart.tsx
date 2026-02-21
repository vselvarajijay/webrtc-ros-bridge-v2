import { Group, Text } from '@mantine/core';

export interface TelemetryChartMetrics {
  speed?: number | null;
  heading?: number | null;
  signal?: number | null;
  battery?: number | null;
}

export interface TelemetryChartProps {
  /** Metrics to display (speed m/s, heading degrees, signal level, battery %) */
  metrics?: TelemetryChartMetrics | null;
  /** Label for speed (default: "Speed") */
  speedLabel?: string;
  /** Label for heading (default: "Heading") */
  headingLabel?: string;
  /** Label for signal (default: "Signal") */
  signalLabel?: string;
  /** Label for battery (default: "Battery") */
  batteryLabel?: string;
  /** Empty state message when no metrics */
  emptyMessage?: string;
  /** Compact layout (single row, smaller text) */
  compact?: boolean;
  className?: string;
}

function formatSpeed(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return Number(v).toFixed(2);
}

function formatHeading(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return Number(v).toFixed(1);
}

function formatSignal(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return Number(v).toFixed(1);
}

function formatBattery(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return `${Math.round(Number(v))}%`;
}

export function TelemetryChart({
  metrics,
  speedLabel = 'Speed',
  headingLabel = 'Heading',
  signalLabel = 'Signal',
  batteryLabel = 'Battery',
  emptyMessage = 'No telemetry data',
  compact = false,
  className,
}: TelemetryChartProps) {
  const speed = formatSpeed(metrics?.speed);
  const heading = formatHeading(metrics?.heading);
  const signal = formatSignal(metrics?.signal);
  const battery = formatBattery(metrics?.battery);

  const hasAny =
    (metrics?.speed != null && Number.isFinite(metrics.speed)) ||
    (metrics?.heading != null && Number.isFinite(metrics.heading)) ||
    (metrics?.signal != null && Number.isFinite(metrics.signal)) ||
    (metrics?.battery != null && Number.isFinite(metrics.battery));

  if (!hasAny) {
    return (
      <Text size={compact ? 'xs' : 'sm'} c="dimmed" className={className}>
        {emptyMessage}
      </Text>
    );
  }

  const itemSize = compact ? 'xs' : 'sm';
  const labelSize = compact ? 'xs' : 'xs';

  return (
    <Group gap="lg" wrap="nowrap" className={className}>
      <Group gap="xs" wrap="nowrap">
        <Text size={labelSize} c="dimmed">
          {speedLabel}
        </Text>
        <Text size={itemSize} fw={600}>
          {speed} m/s
        </Text>
      </Group>
      <Group gap="xs" wrap="nowrap">
        <Text size={labelSize} c="dimmed">
          {headingLabel}
        </Text>
        <Text size={itemSize} fw={600}>
          {heading}°
        </Text>
      </Group>
      <Group gap="xs" wrap="nowrap">
        <Text size={labelSize} c="dimmed">
          {signalLabel}
        </Text>
        <Text size={itemSize} fw={600}>
          {signal}
        </Text>
      </Group>
      <Group gap="xs" wrap="nowrap">
        <Text size={labelSize} c="dimmed">
          {batteryLabel}
        </Text>
        <Text size={itemSize} fw={600}>
          {battery}
        </Text>
      </Group>
    </Group>
  );
}

import { Group, Text } from '@mantine/core';
import { Battery, Wifi } from 'lucide-react';
import { useWebRTC } from '@/context/WebRTCContext';

export function SystemTray() {
  const { connectionDebug, telemetry } = useWebRTC();

  const battery =
    telemetry?.battery != null && Number.isFinite(telemetry.battery)
      ? Math.round(Number(telemetry.battery))
      : null;
  const isConnected = connectionDebug.conn === 'connected';

  return (
    <Group gap="lg" wrap="nowrap" className="text-sm">
      <Group gap="xs" wrap="nowrap">
        <Battery
          size={16}
          className={battery != null && battery < 20 ? 'text-red-500' : undefined}
          aria-hidden
        />
        <Text size="sm" c="dimmed" component="span">
          Battery
        </Text>
        <Text
          size="sm"
          fw={500}
          component="span"
          className={battery != null && battery < 20 ? 'text-red-500' : ''}
        >
          {battery != null ? `${battery}%` : '—'}
        </Text>
      </Group>
      <Group gap="xs" wrap="nowrap">
        <Wifi size={16} aria-hidden />
        <Text size="sm" c="dimmed" component="span">
          Connection
        </Text>
        <Text
          size="sm"
          fw={500}
          c={isConnected ? 'green' : 'red'}
          component="span"
        >
          {isConnected ? 'Connected' : connectionDebug.conn || 'Disconnected'}
        </Text>
      </Group>
    </Group>
  );
}

import { Box, Button, Group, Stack, Text } from '@mantine/core';
import { useWebRTC } from '@/context/WebRTCContext';

export function TelemetryHeader() {
  const { connectionDebug, telemetry, eStop } = useWebRTC();

  const battery = telemetry?.battery != null && Number.isFinite(telemetry.battery)
    ? Math.round(Number(telemetry.battery))
    : null;
  const isConnected = connectionDebug.conn === 'connected';

  return (
    <Group justify="space-between" wrap="nowrap" gap="sm">
      <Button
        color="red"
        variant="filled"
        size="sm"
        onClick={eStop}
        aria-label="Emergency stop"
      >
        E-STOP
      </Button>
      <Group gap="lg" wrap="nowrap">
        <Group gap="xs" wrap="nowrap">
          <Box
            className="size-2 rounded-full shrink-0"
            style={{ backgroundColor: isConnected ? 'var(--mantine-color-green-6)' : 'var(--mantine-color-gray-5)' }}
            aria-hidden
          />
          <Text size="sm" fw={500} c={isConnected ? 'green' : 'dimmed'}>
            {isConnected ? 'connected' : connectionDebug.conn}
          </Text>
        </Group>
        <Stack gap={0} align="flex-end">
          <Text size="xs" c="dimmed">Battery</Text>
          <Text size="sm" fw={600}>{battery != null ? `${battery}%` : '—'}</Text>
        </Stack>
      </Group>
    </Group>
  );
}

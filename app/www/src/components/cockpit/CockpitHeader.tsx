import { Box, Button, Group, Text, Title } from '@mantine/core';
import { useWebRTC } from '@/context/WebRTCContext';

export function CockpitHeader() {
  const { connectionDebug, telemetry, eStop } = useWebRTC();

  const battery =
    telemetry?.battery != null && Number.isFinite(telemetry.battery)
      ? Math.round(Number(telemetry.battery))
      : null;
  const isConnected = connectionDebug.conn === 'connected';

  return (
    <Group justify="space-between" wrap="nowrap" style={{ width: '100%' }} gap="md">
      <Group wrap="nowrap" gap="sm">
        <Title order={4}>ConnectX</Title>
        <Group gap="xs" wrap="nowrap">
          <Box
            className="size-2 rounded-full shrink-0"
            style={{
              backgroundColor: isConnected ? 'var(--mantine-color-green-6)' : 'var(--mantine-color-gray-5)',
            }}
            aria-hidden
          />
          <Text size="sm" fw={500} c={isConnected ? 'green' : 'dimmed'}>
            {isConnected ? 'connected' : connectionDebug.conn}
          </Text>
        </Group>
      </Group>

      <Box
        px="md"
        py="xs"
        style={{
          borderRadius: 6,
          backgroundColor: 'var(--mantine-color-green-8)',
          color: 'var(--mantine-color-white)',
          fontWeight: 600,
          fontSize: '0.9rem',
        }}
      >
        Teleop Mode
      </Box>

      <Group wrap="nowrap" gap="md">
        <Group gap="xs" wrap="nowrap">
          <Text size="sm" c="dimmed">
            Battery
          </Text>
          <Text size="sm" fw={600}>
            {battery != null ? `${battery}%` : '—'}
          </Text>
        </Group>
        <Button
          color="red"
          variant="filled"
          size="md"
          onClick={eStop}
          aria-label="Emergency stop"
        >
          E-STOP
        </Button>
      </Group>
    </Group>
  );
}

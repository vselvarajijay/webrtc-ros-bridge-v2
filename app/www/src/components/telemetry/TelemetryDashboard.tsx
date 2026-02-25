import { Group, Text } from '@mantine/core';
import { useTelemetry } from '@/hooks/useTelemetry';
import { useWebRTC } from '@/context/WebRTCContext';

export function TelemetryDashboard() {
  const polled = useTelemetry();
  const { telemetry: webrtcTelemetry } = useWebRTC();
  const telemetry = webrtcTelemetry ?? polled;

  const speed = telemetry?.speed != null && Number.isFinite(telemetry.speed)
    ? Number(telemetry.speed).toFixed(2)
    : '—';
  const heading = telemetry?.orientation != null && Number.isFinite(Number(telemetry.orientation))
    ? Number(telemetry.orientation).toFixed(1)
    : '—';

  return (
    <Group
      gap="lg"
      wrap="nowrap"
    >
      <Group gap="xs" wrap="nowrap">
        <Text size="xs" c="dimmed">Speed</Text>
        <Text size="sm" fw={600}>{speed} m/s</Text>
      </Group>
      <Group gap="xs" wrap="nowrap">
        <Text size="xs" c="dimmed">Heading</Text>
        <Text size="sm" fw={600}>{heading}°</Text>
      </Group>
      {!telemetry && (
        <Text size="xs" c="dimmed">
          Waiting for robot telemetry. Ensure bridge and webrtc are running.
        </Text>
      )}
    </Group>
  );
}

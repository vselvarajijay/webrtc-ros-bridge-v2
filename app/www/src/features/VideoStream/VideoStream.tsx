import { Box, Card, Text } from '@mantine/core';
import { useWebRTC } from '@/context/WebRTCContext';
import { VideoFeed } from '@/components/VideoFeed';

const hudStyle: React.CSSProperties = {
  position: 'absolute',
  background: 'rgba(0,0,0,0.6)',
  color: '#fff',
  padding: '4px 8px',
  fontSize: '0.75rem',
  fontFamily: 'monospace',
  borderRadius: 4,
};

export function VideoStream() {
  const { videoRef, pipelineState, telemetry, connectionDebug } = useWebRTC();

  const isConnected = connectionDebug.conn === 'connected';
  const battery =
    telemetry?.battery != null && Number.isFinite(telemetry.battery)
      ? Number(telemetry.battery)
      : null;
  const speed =
    telemetry?.speed != null && Number.isFinite(telemetry.speed)
      ? Number(telemetry.speed)
      : null;
  const heading =
    telemetry?.orientation != null
      ? (Number(telemetry.orientation) / 255) * 360
      : null;
  const signal =
    telemetry?.signal_level != null && Number.isFinite(telemetry.signal_level)
      ? Number(telemetry.signal_level)
      : null;

  return (
    <Card
      withBorder
      padding="sm"
      className="overflow-hidden"
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--mantine-color-dark-9)',
        borderColor: 'var(--mantine-color-dark-4)',
        borderRadius: 8,
      }}
    >
      <Text size="sm" fw={600} mb="xs">
        Live View
      </Text>
      <Box
        className="relative rounded overflow-hidden flex-1 min-h-0 flex items-center justify-center"
        style={{ backgroundColor: 'var(--mantine-color-dark-9)' }}
      >
        <VideoFeed
          videoRef={videoRef}
          hasVideo={pipelineState.video}
          placeholder="Waiting for robot stream…"
          className="w-full h-full"
        />

        <Box style={{ ...hudStyle, top: 8, left: 8 }}>
          Speed: {speed != null ? speed.toFixed(2) : '—'} m/s
        </Box>
        <Box style={{ ...hudStyle, top: 8, right: 8 }}>
          Heading: {heading != null ? heading.toFixed(1) : '—'}°
        </Box>
        <Box style={{ ...hudStyle, top: 32, left: 8 }}>
          Battery: {battery != null ? `${Math.round(battery)}%` : '—'}
        </Box>
        <Box style={{ ...hudStyle, bottom: 8, right: 8 }}>
          Signal: {signal != null ? signal.toFixed(1) : '—'}
        </Box>
        <Box style={{ ...hudStyle, bottom: 8, left: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
          <Box
            className="size-2 rounded-full shrink-0"
            style={{
              backgroundColor: isConnected ? 'var(--mantine-color-green-6)' : 'var(--mantine-color-gray-5)',
            }}
            aria-hidden
          />
          {isConnected ? 'connected' : connectionDebug.conn}
        </Box>
      </Box>
    </Card>
  );
}

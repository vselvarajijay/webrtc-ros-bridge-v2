import { Box, Card, Text } from '@mantine/core';
import { useWebRTC } from '@/context/WebRTCContext';

export function LiveViewWithHUD() {
  const { videoRef, pipelineState, telemetry, connectionDebug } = useWebRTC();

  const isConnected = connectionDebug.conn === 'connected';
  const battery =
    telemetry?.battery != null && Number.isFinite(telemetry.battery)
      ? Math.round(Number(telemetry.battery))
      : null;

  const speed =
    telemetry?.speed != null && Number.isFinite(telemetry.speed)
      ? Number(telemetry.speed).toFixed(2)
      : '0.00';
  const heading =
    telemetry?.orientation != null
      ? ((Number(telemetry.orientation) / 255) * 360).toFixed(1)
      : '0.0';
  const signal =
    telemetry?.signal_level != null && Number.isFinite(telemetry.signal_level)
      ? Number(telemetry.signal_level).toFixed(1)
      : '0.0';

  const hudStyle: React.CSSProperties = {
    position: 'absolute',
    background: 'rgba(0,0,0,0.6)',
    color: '#fff',
    padding: '4px 8px',
    fontSize: '0.75rem',
    fontFamily: 'monospace',
    borderRadius: 4,
  };

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
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-contain"
          style={{ maxHeight: '100%' }}
        />
        {!pipelineState.video && (
          <Text
            size="sm"
            c="dimmed"
            className="absolute inset-0 flex items-center justify-center"
          >
            Waiting for robot stream…
          </Text>
        )}

        <Box style={{ ...hudStyle, top: 8, left: 8 }}>
          Speed: {speed} m/s
        </Box>
        <Box style={{ ...hudStyle, top: 8, right: 8 }}>
          Heading: {heading}°
        </Box>
        <Box style={{ ...hudStyle, top: 32, left: 8 }}>
          Battery: {battery != null ? `${battery}%` : '—'}
        </Box>
        <Box style={{ ...hudStyle, bottom: 8, right: 8 }}>
          Signal: {signal}
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

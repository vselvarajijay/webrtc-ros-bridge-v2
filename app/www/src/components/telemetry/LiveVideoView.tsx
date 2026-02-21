import { Box, Card, Text } from '@mantine/core';
import { useWebRTC } from '@/context/WebRTCContext';

export function LiveVideoView() {
  const { videoRef, pipelineState } = useWebRTC();

  return (
    <Card withBorder padding="sm" className="overflow-hidden" style={{ backgroundColor: 'var(--mantine-color-dark-9)' }}>
      <Text size="sm" fw={600} mb="xs">Live view</Text>
      <Text size="xs" c="dimmed" mb="xs">Live camera (WebRTC)</Text>
      <Box
        className="relative rounded overflow-hidden min-h-[200px] flex items-center justify-center"
        style={{ backgroundColor: 'var(--mantine-color-dark-9)', aspectRatio: '4/3' }}
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
          <Text size="sm" c="dimmed" className="absolute inset-0 flex items-center justify-center">
            Waiting for robot stream…
          </Text>
        )}
      </Box>
    </Card>
  );
}

import { Box, Card, Text } from '@mantine/core';
import { useWebRTC } from '@/context/WebRTCContext';
import { VideoFeed } from '@/components/VideoFeed';

export function VideoStream() {
  const { videoRef, pipelineState } = useWebRTC();

  return (
    <Card
      withBorder
      padding="sm"
      className="overflow-hidden flex flex-col min-h-0"
      style={{
        height: '100%',
        minHeight: 0,
        maxHeight: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--mantine-color-dark-9)',
        borderColor: 'var(--mantine-color-dark-4)',
        borderRadius: 8,
      }}
    >
      <Text size="sm" fw={600} mb="xs" className="shrink-0">
        Live View
      </Text>
      <Box
        className="relative rounded overflow-hidden flex-1 min-h-0 flex items-center justify-center"
        style={{ backgroundColor: 'var(--mantine-color-dark-9)', minHeight: 0 }}
      >
        <VideoFeed
          videoRef={videoRef}
          hasVideo={pipelineState.video}
          placeholder="Waiting for robot stream…"
          className="w-full h-full"
        />
      </Box>
    </Card>
  );
}

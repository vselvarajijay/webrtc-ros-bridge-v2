import { Box, Card, Text } from '@mantine/core';
import { usePerceptionImage } from '@/hooks/usePerceptionImage';

export function OpticalFlowView() {
  const imageUrl = usePerceptionImage('optical_flow');

  return (
    <Card withBorder padding="sm" className="overflow-hidden">
      <Text size="sm" fw={600} mb="xs">Optical Flow</Text>
      <Text size="xs" c="dimmed" mb="xs">Vector arrows (direction and magnitude)</Text>
      <Box
        className="relative rounded overflow-hidden bg-gray-900 min-h-[200px] flex items-center justify-center"
        style={{ aspectRatio: '4/3' }}
      >
        {imageUrl ? (
          <img
            src={imageUrl}
            alt="Optical flow"
            className="w-full h-full object-contain"
          />
        ) : (
          <Text size="sm" c="dimmed">Waiting for optical flow…</Text>
        )}
      </Box>
    </Card>
  );
}

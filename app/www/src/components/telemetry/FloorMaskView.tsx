import { Box, Card, Text } from '@mantine/core';
import { usePerceptionImage } from '@/hooks/usePerceptionImage';

export function FloorMaskView() {
  const imageUrl = usePerceptionImage('floor_mask');

  return (
    <Card withBorder padding="sm" className="overflow-hidden">
      <Text size="sm" fw={600} mb="xs">Floor Mask</Text>
      <Text size="xs" c="dimmed" mb="xs">Floor detection (green = floor)</Text>
      <Box
        className="relative rounded overflow-hidden bg-gray-900 min-h-[200px] flex items-center justify-center"
        style={{ aspectRatio: '4/3' }}
      >
        {imageUrl ? (
          <img
            src={imageUrl}
            alt="Floor mask"
            className="w-full h-full object-contain"
          />
        ) : (
          <Text size="sm" c="dimmed">Waiting for floor mask…</Text>
        )}
      </Box>
    </Card>
  );
}

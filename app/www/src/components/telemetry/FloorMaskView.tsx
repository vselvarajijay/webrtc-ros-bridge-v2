import { Box, Card, Text } from '@mantine/core';
import { usePerceptionImage } from '@/hooks/usePerceptionImage';

export function FloorMaskView() {
  const imageUrl = usePerceptionImage('floor_mask');

  return (
    <Card
      withBorder
      padding="sm"
      className="overflow-hidden"
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--mantine-color-dark-7)',
        borderColor: 'var(--mantine-color-dark-4)',
        borderRadius: 8,
      }}
    >
      <Text size="sm" fw={600} mb="xs">Floor Mask</Text>
      <Box
        className="relative rounded overflow-hidden flex-1 min-h-0 flex items-center justify-center"
        style={{ backgroundColor: 'var(--mantine-color-dark-8)' }}
      >
        {imageUrl ? (
          <img
            src={imageUrl}
            alt="Floor mask"
            className="w-full h-full object-contain"
            style={{ maxHeight: '100%' }}
          />
        ) : (
          <Text size="sm" c="dimmed">Waiting for floor mask…</Text>
        )}
      </Box>
    </Card>
  );
}

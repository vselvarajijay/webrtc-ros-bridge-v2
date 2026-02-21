import { Box } from '@mantine/core';
import { CockpitLayout } from '@/components/cockpit';

export function TelemetryPage() {
  return (
    <Box style={{ flex: 1, minHeight: 0, height: '100%' }}>
      <CockpitLayout />
    </Box>
  );
}

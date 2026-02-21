import { Box, SimpleGrid, Stack } from '@mantine/core';
import {
  TelemetryHeader,
  LiveVideoView,
  OpticalFlowView,
  FloorMaskView,
  TelemetryDashboard,
} from '@/components/telemetry';

export function TelemetryPage() {
  return (
    <Stack gap="md" style={{ flex: 1, minHeight: 0 }} className="h-full">
      <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md" style={{ flex: 1, minHeight: 0 }}>
        <LiveVideoView />
        <OpticalFlowView />
        <FloorMaskView />
      </SimpleGrid>
      <Box style={{ flexShrink: 0 }}>
        <TelemetryDashboard />
      </Box>
    </Stack>
  );
}

export function TelemetryPageHeader() {
  return <TelemetryHeader />;
}

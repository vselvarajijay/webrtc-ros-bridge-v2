import { Box } from '@mantine/core';
import { OpticalFlowView, FloorMaskView } from '@/components/telemetry';
import { ChatPanel } from '@/features/ChatPanel';
import { VideoStream } from '@/features/VideoStream';
import { RobotControl } from '@/features/RobotControl';
import { SystemLogsPanel } from './SystemLogsPanel';

export function CockpitLayout() {
  return (
    <Box
      style={{
        display: 'grid',
        gridTemplateAreas: '"left center right" "chat chat right" "logs logs right"',
        gridTemplateColumns: '1fr 3fr 1fr',
        gridTemplateRows: '1fr 180px 200px',
        gap: '1rem',
        height: '100%',
        minHeight: 0,
      }}
    >
      <Box
        style={{
          gridArea: 'left',
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem',
        }}
      >
        <Box style={{ flex: 1, minHeight: 0 }}>
          <OpticalFlowView />
        </Box>
        <Box style={{ flex: 1, minHeight: 0 }}>
          <FloorMaskView />
        </Box>
      </Box>

      <Box style={{ gridArea: 'center', minHeight: 0 }}>
        <VideoStream />
      </Box>

      <Box style={{ gridArea: 'right', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <RobotControl />
      </Box>

      <Box style={{ gridArea: 'chat', minHeight: 0 }}>
        <ChatPanel />
      </Box>

      <Box style={{ gridArea: 'logs', minHeight: 0 }}>
        <SystemLogsPanel />
      </Box>
    </Box>
  );
}

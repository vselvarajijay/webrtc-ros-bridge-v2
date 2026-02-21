import { Box } from '@mantine/core';
import { OpticalFlowView, FloorMaskView } from '@/components/telemetry';
import { LiveViewWithHUD } from './LiveViewWithHUD';
import { ControlPanel } from './ControlPanel';
import { SystemLogsPanel } from './SystemLogsPanel';

export function CockpitLayout() {
  return (
    <Box
      style={{
        display: 'grid',
        gridTemplateAreas: '"left center right" "logs logs right"',
        gridTemplateColumns: '1fr 3fr 1fr',
        gridTemplateRows: '1fr 200px',
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
        <LiveViewWithHUD />
      </Box>

      <Box style={{ gridArea: 'right', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <ControlPanel />
      </Box>

      <Box style={{ gridArea: 'logs', minHeight: 0 }}>
        <SystemLogsPanel />
      </Box>
    </Box>
  );
}

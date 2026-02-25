import { Tabs } from '@mantine/core';
import { OpticalFlowView, FloorMaskView } from '@/components/telemetry';
import { VideoStream } from '@/features/VideoStream';

export function LiveViewTabs() {
  return (
    <Tabs
      defaultValue="live"
      className="flex-1 min-h-0 flex flex-col overflow-hidden"
      style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}
      styles={{
        panel: {
          flex: 1,
          minHeight: 0,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        },
      }}
    >
      <Tabs.List>
        <Tabs.Tab value="live">Live View</Tabs.Tab>
        <Tabs.Tab value="optical-flow">Optical Flow</Tabs.Tab>
        <Tabs.Tab value="floor-mask">Floor Mask</Tabs.Tab>
      </Tabs.List>

      <Tabs.Panel value="live" style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <VideoStream />
      </Tabs.Panel>
      <Tabs.Panel value="optical-flow" style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <OpticalFlowView />
      </Tabs.Panel>
      <Tabs.Panel value="floor-mask" style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <FloorMaskView />
      </Tabs.Panel>
    </Tabs>
  );
}

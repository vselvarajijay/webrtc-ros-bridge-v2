import { Tabs } from '@mantine/core';
import { useWebRTC } from '@/context/WebRTCContext';
import { Button } from '@/components/Button';
import { RobotControl } from '@/features/RobotControl';
import { ChatPanel } from '@/features/ChatPanel';

const PANEL_BG = '#1e2128';
const BORDER = '1px solid #242730';

export function ControlAndChatPanel() {
  const { eStop } = useWebRTC();

  return (
    <div
      className="flex flex-col flex-1 min-h-0 rounded-lg overflow-hidden"
      style={{ backgroundColor: PANEL_BG, border: BORDER }}
    >
      <Tabs
        defaultValue="controls"
        className="flex flex-col flex-1 min-h-0 overflow-hidden"
        styles={{
          root: {
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
            minHeight: 0,
            overflow: 'hidden',
          },
          panel: {
            flex: 1,
            minHeight: 0,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          },
        }}
      >
        {/* Persistent header: Controls/Chat tabs + STOP. Teleop/Autonomous is selected inside RobotControl. */}
        <div className="shrink-0 flex flex-col gap-2 p-3" style={{ borderBottom: '1px solid #242730' }}>
          <Tabs.List className="w-full" grow>
            <Tabs.Tab value="controls">Controls</Tabs.Tab>
            <Tabs.Tab value="chat">Chat</Tabs.Tab>
          </Tabs.List>
          <Button
            color="red"
            variant="filled"
            size="md"
            onClick={eStop}
            aria-label="Emergency stop"
            className="w-full"
          >
            STOP
          </Button>
        </div>

        <Tabs.Panel value="controls" className="flex-1 min-h-0 overflow-y-auto p-3">
          <RobotControl hideStop />
        </Tabs.Panel>
        <Tabs.Panel value="chat" className="flex flex-col flex-1 min-h-0 overflow-hidden p-0" style={{ height: '100%' }}>
          <div className="flex flex-col flex-1 min-h-0 overflow-hidden h-full">
            <ChatPanel />
          </div>
        </Tabs.Panel>
      </Tabs>
    </div>
  );
}

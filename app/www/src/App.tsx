import { createTheme, MantineProvider } from '@mantine/core';
import { AppLayout } from '@/components/layout';
import { CockpitHeader } from '@/components/cockpit';
import { RobotSidebar } from '@/components/fleet';
import { WebRTCProvider } from '@/context/WebRTCContext';
import { RobotFleetProvider, useRobotFleet } from '@/context/RobotFleetContext';
import { TelemetryPage } from '@/pages/TelemetryPage';

const cockpitTheme = createTheme({
  primaryColor: 'dark',
  colors: {
    dark: [
      '#f1f3f5',
      '#e9ecef',
      '#dee2e6',
      '#ced4da',
      '#adb5bd',
      '#868e96',
      '#495057',
      '#373a40',
      '#27272a', /* zinc-800 */
      '#18181b', /* zinc-900 - main background */
    ],
  },
});

/** Inner app that consumes the fleet context to wire the active robot to WebRTC. */
function AppInner() {
  const { activeRobotId } = useRobotFleet();

  return (
    <WebRTCProvider robotId={activeRobotId} isActive>
      <AppLayout
        headerLeft={<CockpitHeader />}
        navbar={<RobotSidebar />}
        padding="md"
      >
        <TelemetryPage />
      </AppLayout>
    </WebRTCProvider>
  );
}

function App() {
  return (
    <MantineProvider theme={cockpitTheme} defaultColorScheme="dark">
      <RobotFleetProvider>
        <AppInner />
      </RobotFleetProvider>
    </MantineProvider>
  );
}

export default App;

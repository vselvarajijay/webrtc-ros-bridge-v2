import { MantineProvider, Title } from '@mantine/core';
import { AppLayout } from '@/components/layout';
import { DriveControls } from '@/components/telemetry';
import { WebRTCProvider } from '@/context/WebRTCContext';
import { TelemetryPage, TelemetryPageHeader } from '@/pages/TelemetryPage';

function App() {
  return (
    <MantineProvider>
      <WebRTCProvider>
        <AppLayout
          headerLeft={<Title order={4}>ConnectX</Title>}
          headerRight={<TelemetryPageHeader />}
          aside={<DriveControls />}
          padding="md"
        >
          <TelemetryPage />
        </AppLayout>
      </WebRTCProvider>
    </MantineProvider>
  );
}

export default App;

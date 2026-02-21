import { createTheme, MantineProvider } from '@mantine/core';
import { AppLayout } from '@/components/layout';
import { CockpitHeader } from '@/components/cockpit';
import { WebRTCProvider } from '@/context/WebRTCContext';
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
      '#25262b',
      '#1a1b1e',
    ],
  },
});

function App() {
  return (
    <MantineProvider theme={cockpitTheme} defaultColorScheme="dark">
      <WebRTCProvider>
        <AppLayout
          headerLeft={<CockpitHeader />}
          padding="md"
        >
          <TelemetryPage />
        </AppLayout>
      </WebRTCProvider>
    </MantineProvider>
  );
}

export default App;

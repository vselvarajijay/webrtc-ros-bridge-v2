import type { Preview } from '@storybook/react-vite';
import { createTheme, MantineProvider } from '@mantine/core';
import '../src/index.css';

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
      '#27272a',
      '#18181b',
    ],
  },
});

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
  decorators: [
    (Story) => (
      <MantineProvider theme={cockpitTheme} defaultColorScheme="dark">
        <Story />
      </MantineProvider>
    ),
  ],
};

export default preview;

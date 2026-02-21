import type { Meta, StoryObj } from '@storybook/react-vite';
import { VideoStream } from './VideoStream';
import { MockWebRTCProvider } from '@/test-utils/mockWebRTC';

const meta: Meta<typeof VideoStream> = {
  component: VideoStream,
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <MockWebRTCProvider>
        <div style={{ width: 480, height: 360 }}>
          <Story />
        </div>
      </MockWebRTCProvider>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof VideoStream>;

export const Default: Story = {};

export const WithMockTelemetry: Story = {
  decorators: [
    (Story) => (
      <MockWebRTCProvider
        telemetry={{
          speed: 0.45,
          orientation: 128,
          signal_level: 4.2,
          battery: 87,
        }}
      >
        <div style={{ width: 480, height: 360 }}>
          <Story />
        </div>
      </MockWebRTCProvider>
    ),
  ],
};

export const SimulatedVideo: Story = {
  decorators: [
    (Story) => (
      <MockWebRTCProvider video={true} telemetry={{ battery: 90, speed: 0.1 }}>
        <div style={{ width: 480, height: 360 }}>
          <Story />
        </div>
      </MockWebRTCProvider>
    ),
  ],
};

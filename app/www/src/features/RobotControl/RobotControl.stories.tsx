import type { Meta, StoryObj } from '@storybook/react-vite';
import { RobotControl } from './RobotControl';
import { MockWebRTCProvider } from '@/test-utils/mockWebRTC';

const meta: Meta<typeof RobotControl> = {
  component: RobotControl,
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <MockWebRTCProvider commandsReady={true}>
        <div style={{ width: 280, maxHeight: 420 }}>
          <Story />
        </div>
      </MockWebRTCProvider>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof RobotControl>;

export const Default: Story = {};

export const CommandsNotReady: Story = {
  decorators: [
    (Story) => (
      <MockWebRTCProvider commandsReady={false}>
        <div style={{ width: 280, maxHeight: 420 }}>
          <Story />
        </div>
      </MockWebRTCProvider>
    ),
  ],
};

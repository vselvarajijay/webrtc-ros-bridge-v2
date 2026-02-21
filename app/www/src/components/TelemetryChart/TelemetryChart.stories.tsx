import type { Meta, StoryObj } from '@storybook/react-vite';
import { TelemetryChart } from './TelemetryChart';

const meta: Meta<typeof TelemetryChart> = {
  component: TelemetryChart,
  tags: ['autodocs'],
  argTypes: {
    compact: { control: 'boolean' },
    emptyMessage: { control: 'text' },
  },
};
export default meta;

type Story = StoryObj<typeof TelemetryChart>;

export const WithSampleData: Story = {
  args: {
    metrics: {
      speed: 0.45,
      heading: 180,
      signal: 4.2,
      battery: 87,
    },
  },
};

export const PartialData: Story = {
  args: {
    metrics: {
      speed: 0.12,
      heading: 90,
      signal: undefined,
      battery: 100,
    },
  },
};

export const Empty: Story = {
  args: {
    metrics: null,
    emptyMessage: 'Waiting for robot telemetry.',
  },
};

export const Compact: Story = {
  args: {
    metrics: {
      speed: 0.33,
      heading: 270,
      signal: 3.1,
      battery: 72,
    },
    compact: true,
  },
};

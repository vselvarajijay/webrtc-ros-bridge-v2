import type { Meta, StoryObj } from '@storybook/react-vite';
import { useRef } from 'react';
import { VideoFeed } from './VideoFeed';

const meta: Meta<typeof VideoFeed> = {
  component: VideoFeed,
  tags: ['autodocs'],
  argTypes: {
    hasVideo: { control: 'boolean' },
    placeholder: { control: 'text' },
  },
};
export default meta;

type Story = StoryObj<typeof VideoFeed>;

export const NoStream: Story = {
  args: {
    videoRef: { current: null },
    hasVideo: false,
    placeholder: 'Waiting for robot stream…',
  },
};

export const WithStream: Story = {
  render: function WithStreamStory() {
    const videoRef = useRef<HTMLVideoElement | null>(null);
    return (
      <div style={{ width: 320, height: 240 }}>
        <VideoFeed
          videoRef={videoRef}
          hasVideo={true}
          placeholder="Waiting for robot stream…"
        />
      </div>
    );
  },
};

export const CustomPlaceholder: Story = {
  args: {
    videoRef: { current: null },
    hasVideo: false,
    placeholder: 'No camera connected',
  },
};

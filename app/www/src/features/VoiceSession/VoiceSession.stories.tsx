import type { Meta, StoryObj } from '@storybook/react-vite';
import { VoiceSession } from './VoiceSession';

const meta: Meta<typeof VoiceSession> = {
  component: VoiceSession,
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof VoiceSession>;

export const Default: Story = {};

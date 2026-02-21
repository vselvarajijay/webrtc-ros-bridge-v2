import type { Meta, StoryObj } from '@storybook/react-vite';
import { Card } from './Card';
import { Text } from '@mantine/core';

const meta: Meta<typeof Card> = {
  component: Card,
  tags: ['autodocs'],
  argTypes: {
    padding: {
      control: 'select',
      options: ['xs', 'sm', 'md', 'lg'],
    },
  },
};
export default meta;

type Story = StoryObj<typeof Card>;

export const Default: Story = {
  args: {
    padding: 'md',
    withBorder: true,
    children: <Text size="sm">Card content</Text>,
  },
};

export const WithTitle: Story = {
  args: {
    padding: 'md',
    withBorder: true,
    children: (
      <>
        <Text size="sm" fw={600} mb="xs">
          Card title
        </Text>
        <Text size="xs" c="dimmed">
          Optional description or body text.
        </Text>
      </>
    ),
  },
};

export const NoBorder: Story = {
  args: {
    padding: 'sm',
    withBorder: false,
    children: <Text size="sm">Card without border</Text>,
  },
};

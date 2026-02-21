import type { Meta, StoryObj } from '@storybook/react-vite';
import { Input } from './Input';

const meta: Meta<typeof Input> = {
  component: Input,
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['xs', 'sm', 'md', 'lg', 'xl'],
    },
  },
};
export default meta;

type Story = StoryObj<typeof Input>;

export const Default: Story = {
  args: {
    placeholder: 'Enter text…',
    label: 'Label',
    size: 'sm',
  },
};

export const WithDescription: Story = {
  args: {
    placeholder: 'Optional helper text',
    label: 'Field name',
    description: 'Helper text below the input.',
    size: 'sm',
  },
};

export const WithError: Story = {
  args: {
    placeholder: 'Invalid value',
    label: 'Field name',
    error: 'This field is required.',
  },
};

export const Disabled: Story = {
  args: {
    placeholder: 'Disabled',
    label: 'Disabled',
    disabled: true,
    defaultValue: 'Read-only value',
  },
};

export const Sizes: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 300 }}>
      <Input size="xs" placeholder="xs" label="xs" />
      <Input size="sm" placeholder="sm" label="sm" />
      <Input size="md" placeholder="md" label="md" />
    </div>
  ),
};

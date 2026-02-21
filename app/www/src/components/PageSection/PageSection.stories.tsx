import type { Meta, StoryObj } from '@storybook/react-vite';
import { PageSection } from './PageSection';
import { Text } from '@mantine/core';

const meta: Meta<typeof PageSection> = {
  component: PageSection,
  tags: ['autodocs'],
};
export default meta;

type Story = StoryObj<typeof PageSection>;

export const Default: Story = {
  args: {
    children: <Text size="sm">Section content goes here.</Text>,
  },
};

export const WithTitle: Story = {
  args: {
    title: 'Section title',
    children: <Text size="sm">Content under the title.</Text>,
  },
};

export const WithTitleAndDescription: Story = {
  args: {
    title: 'Section title',
    description: 'Optional description or subtitle for the section.',
    children: <Text size="sm">Main section content.</Text>,
  },
};

import { Button, Stack, Text } from '@mantine/core';
import { DriveControls } from '@/components/telemetry';

export function ControlPanel() {
  return (
    <Stack
      gap="md"
      style={{
        flex: 1,
        minHeight: 0,
        backgroundColor: 'var(--mantine-color-dark-7)',
        border: '1px solid var(--mantine-color-dark-4)',
        borderRadius: 8,
        padding: '1rem',
      }}
    >
      <DriveControls />
      <Stack gap="xs">
        <Text size="sm" fw={600}>
          System Commands
        </Text>
        <Button variant="light" size="sm" fullWidth>
          Create system
        </Button>
        <Button variant="light" size="sm" fullWidth leftSection={<span aria-hidden>★</span>}>
          Direct board
        </Button>
        <Button variant="light" size="sm" fullWidth>
          Commands
        </Button>
      </Stack>
    </Stack>
  );
}

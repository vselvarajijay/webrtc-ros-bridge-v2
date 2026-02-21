import { Stack } from '@mantine/core';
import { DriveControls } from '@/components/telemetry';

export function ControlPanel() {
  return (
    <Stack
      gap="md"
      style={{
        flex: 1,
        minHeight: 0,
        backgroundColor: 'var(--mantine-color-dark-9)',
        border: '1px solid var(--mantine-color-dark-4)',
        borderRadius: 8,
        padding: '1rem',
      }}
    >
      <DriveControls />
    </Stack>
  );
}

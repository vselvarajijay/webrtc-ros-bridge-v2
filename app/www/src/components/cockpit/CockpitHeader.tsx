import { Group, Title } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { Button } from '@/components/Button';
import { useDashboard } from '@/features/Dashboard';

export function CockpitHeader() {
  const { handleReset } = useDashboard();
  const [confirming, { open: startConfirm, close: cancelConfirm }] = useDisclosure(false);

  const handleConfirmedReset = () => {
    handleReset();
    cancelConfirm();
  };

  return (
    <Group gap="sm" wrap="nowrap">
      <Title order={4}>ConnectX</Title>
      {confirming ? (
        <Group gap="xs" wrap="nowrap">
          <Button size="xs" color="red" variant="filled" onClick={handleConfirmedReset}>
            Confirm Reset
          </Button>
          <Button size="xs" variant="subtle" onClick={cancelConfirm}>
            Cancel
          </Button>
        </Group>
      ) : (
        <Button size="xs" variant="subtle" onClick={startConfirm} aria-label="Reset layout">
          Reset Layout
        </Button>
      )}
    </Group>
  );
}

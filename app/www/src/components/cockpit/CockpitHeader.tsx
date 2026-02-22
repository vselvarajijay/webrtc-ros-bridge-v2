import { Group, Title } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { Button } from '@/components/Button';
import { useDashboard } from '@/features/Dashboard';

export function CockpitHeader() {
  const { isEditing, enterEditMode, exitEditMode, handleReset } = useDashboard();
  const [confirming, { open: startConfirm, close: cancelConfirm }] = useDisclosure(false);

  const handleConfirmedReset = () => {
    handleReset();
    cancelConfirm();
  };

  const handleSave = () => {
    cancelConfirm();
    exitEditMode();
  };

  return (
    <Group gap="sm" wrap="nowrap">
      <Title order={4}>ConnectX</Title>

      {isEditing ? (
        <Group gap="xs" wrap="nowrap">
          {confirming ? (
            <>
              <Button size="xs" color="red" variant="filled" onClick={handleConfirmedReset}>
                Confirm Reset
              </Button>
              <Button size="xs" variant="subtle" onClick={cancelConfirm}>
                Cancel
              </Button>
            </>
          ) : (
            <>
              <Button size="xs" color="green" variant="filled" onClick={handleSave} aria-label="Save layout">
                Save Layout
              </Button>
              <Button size="xs" variant="subtle" onClick={startConfirm} aria-label="Reset layout">
                Reset Layout
              </Button>
            </>
          )}
        </Group>
      ) : (
        <Button size="xs" variant="subtle" onClick={enterEditMode} aria-label="Edit layout">
          Edit Layout
        </Button>
      )}
    </Group>
  );
}

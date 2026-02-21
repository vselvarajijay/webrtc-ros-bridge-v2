import { useState } from 'react';
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Group,
  Loader,
  Menu,
  Stack,
  Text,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import { useRobotFleet } from '@/context/RobotFleetContext';
import { useWebRTC } from '@/context/WebRTCContext';
import { AddRobotModal } from './AddRobotModal';
import type { RobotProfile } from '@/api/robots';

/** Online/offline indicator dot. */
function StatusDot({ online }: { online: boolean }) {
  return (
    <Box
      style={{
        width: 8,
        height: 8,
        borderRadius: '50%',
        backgroundColor: online ? '#40c057' : '#868e96',
        flexShrink: 0,
      }}
    />
  );
}

interface RobotRowProps {
  robot: RobotProfile;
  isActive: boolean;
  onSelect: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

function RobotRow({ robot, isActive, onSelect, onEdit, onDelete }: RobotRowProps) {
  // Show live telemetry only for the active robot (the WebRTC context is scoped to it)
  const { telemetry, pipelineState } = useWebRTC();
  const online = isActive ? pipelineState.robot : false;
  const battery = isActive && telemetry?.battery != null ? telemetry.battery : null;

  return (
    <UnstyledButton
      onClick={onSelect}
      style={{
        width: '100%',
        borderRadius: 6,
        padding: '8px 10px',
        backgroundColor: isActive
          ? 'var(--mantine-color-dark-6)'
          : 'transparent',
        border: isActive ? '1px solid var(--mantine-color-dark-4)' : '1px solid transparent',
        cursor: 'pointer',
      }}
    >
      <Group justify="space-between" wrap="nowrap">
        <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
          <StatusDot online={online} />
          <Text size="sm" fw={isActive ? 600 : 400} truncate>
            {robot.name}
          </Text>
        </Group>
        <Group gap={4} wrap="nowrap">
          {battery != null && (
            <Badge size="xs" variant="light" color={battery < 20 ? 'red' : 'gray'}>
              {Math.round(battery)}%
            </Badge>
          )}
          <Menu withinPortal position="right-start" shadow="md">
            <Menu.Target>
              <ActionIcon
                size="xs"
                variant="subtle"
                onClick={(e) => e.stopPropagation()}
                aria-label="Robot options"
              >
                ⋮
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item onClick={onEdit}>Edit</Menu.Item>
              <Menu.Item color="red" onClick={onDelete}>Delete</Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>

      <Group gap="xs" mt={2} pl={16}>
        <Text size="xs" c="dimmed" truncate>
          {robot.robot_type.replace(/_/g, ' ')}
        </Text>
        {online && (
          <Text size="xs" c="green">
            online
          </Text>
        )}
      </Group>
    </UnstyledButton>
  );
}

export function RobotSidebar() {
  const { robots, activeRobotId, setActiveRobotId, removeRobot, loading } = useRobotFleet();
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [editProfile, setEditProfile] = useState<RobotProfile | null>(null);

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this robot profile?')) return;
    try {
      await removeRobot(id);
    } catch (err) {
      console.error('Failed to delete robot:', err);
    }
  };

  return (
    <>
      <Stack gap="xs" style={{ height: '100%' }}>
        <Group justify="space-between" mb={4}>
          <Text size="sm" fw={700} c="dimmed" tt="uppercase">
            Fleet
          </Text>
          <Tooltip label="Add robot">
            <Button
              size="xs"
              variant="subtle"
              onClick={() => setAddModalOpen(true)}
              aria-label="Add robot"
            >
              + Add
            </Button>
          </Tooltip>
        </Group>

        {loading && <Loader size="xs" />}

        {!loading && robots.length === 0 && (
          <Text size="xs" c="dimmed" ta="center" mt="md">
            No robots configured.{' '}
            <UnstyledButton
              style={{ color: 'var(--mantine-color-blue-4)', fontSize: 'inherit' }}
              onClick={() => setAddModalOpen(true)}
            >
              Add one
            </UnstyledButton>
          </Text>
        )}

        {robots.map((robot) => (
          <RobotRow
            key={robot.id}
            robot={robot}
            isActive={robot.id === activeRobotId}
            onSelect={() => setActiveRobotId(robot.id)}
            onEdit={() => setEditProfile(robot)}
            onDelete={() => handleDelete(robot.id)}
          />
        ))}
      </Stack>

      <AddRobotModal
        opened={addModalOpen}
        onClose={() => setAddModalOpen(false)}
      />
      <AddRobotModal
        opened={!!editProfile}
        onClose={() => setEditProfile(null)}
        editProfile={editProfile}
      />
    </>
  );
}

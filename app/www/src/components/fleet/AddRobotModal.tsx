import { useEffect, useState } from 'react';
import {
  Button,
  Group,
  Modal,
  NumberInput,
  Select,
  Stack,
  Switch,
  Text,
  TextInput,
} from '@mantine/core';
import { fetchRobotTypes, testRobotConnection, type RobotProfile, type RobotProfileCreate } from '@/api/robots';
import { useRobotFleet } from '@/context/RobotFleetContext';

interface AddRobotModalProps {
  opened: boolean;
  onClose: () => void;
  /** When provided the modal edits an existing profile instead of creating one. */
  editProfile?: RobotProfile | null;
}

const DEFAULT_FORM: RobotProfileCreate = {
  name: '',
  robot_type: 'generic_ros2',
  host: 'localhost',
  port: 8001,
  optical_flow: false,
  floor_mask: false,
};

export function AddRobotModal({ opened, onClose, editProfile }: AddRobotModalProps) {
  const { addRobot, editRobot } = useRobotFleet();
  const [form, setForm] = useState<RobotProfileCreate>(DEFAULT_FORM);
  const [robotTypes, setRobotTypes] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; detail: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Populate form when editing an existing profile
  useEffect(() => {
    if (editProfile) {
      setForm({
        name: editProfile.name,
        robot_type: editProfile.robot_type,
        host: editProfile.host,
        port: editProfile.port,
        optical_flow: editProfile.optical_flow,
        floor_mask: editProfile.floor_mask,
      });
    } else {
      setForm(DEFAULT_FORM);
    }
    setTestResult(null);
    setError(null);
  }, [editProfile, opened]);

  // Fetch available robot types from backend
  useEffect(() => {
    if (!opened) return;
    fetchRobotTypes()
      .then(setRobotTypes)
      .catch(() => setRobotTypes(['generic_ros2', 'earth_rover', 'spot', 'go2', 'custom']));
  }, [opened]);

  const handleSave = async () => {
    if (!form.name.trim()) {
      setError('Name is required');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (editProfile) {
        await editRobot(editProfile.id, form);
      } else {
        await addRobot(form);
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save robot profile');
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    if (!editProfile) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testRobotConnection(editProfile.id);
      setTestResult(result);
    } catch {
      setTestResult({ ok: false, detail: 'Connection test failed' });
    } finally {
      setTesting(false);
    }
  };

  const typeOptions = robotTypes.map((t) => ({ value: t, label: t.replace(/_/g, ' ') }));

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={editProfile ? 'Edit Robot' : 'Add Robot'}
      centered
    >
      <Stack gap="sm">
        <TextInput
          label="Name"
          placeholder="My Robot"
          required
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.currentTarget.value }))}
        />

        <Select
          label="Robot Type"
          data={typeOptions.length ? typeOptions : [{ value: 'generic_ros2', label: 'generic ros2' }]}
          value={form.robot_type}
          onChange={(v) => setForm((f) => ({ ...f, robot_type: v ?? 'generic_ros2' }))}
        />

        <TextInput
          label="Host / IP"
          placeholder="localhost"
          value={form.host}
          onChange={(e) => setForm((f) => ({ ...f, host: e.currentTarget.value }))}
        />

        <NumberInput
          label="Port"
          value={form.port}
          min={1}
          max={65535}
          onChange={(v) => setForm((f) => ({ ...f, port: v === '' ? f.port : Number(v) }))}
        />

        <Group>
          <Switch
            label="Optical Flow overlay"
            checked={form.optical_flow}
            onChange={(e) => setForm((f) => ({ ...f, optical_flow: e.currentTarget.checked }))}
          />
          <Switch
            label="Floor Mask overlay"
            checked={form.floor_mask}
            onChange={(e) => setForm((f) => ({ ...f, floor_mask: e.currentTarget.checked }))}
          />
        </Group>

        {error && <Text c="red" size="sm">{error}</Text>}

        {testResult && (
          <Text c={testResult.ok ? 'green' : 'red'} size="sm">
            {testResult.ok ? '✓' : '✗'} {testResult.detail}
          </Text>
        )}

        <Group justify="space-between" mt="md">
          {editProfile && (
            <Button
              variant="outline"
              loading={testing}
              onClick={handleTestConnection}
            >
              Test Connection
            </Button>
          )}
          <Group ml="auto">
            <Button variant="subtle" onClick={onClose}>Cancel</Button>
            <Button loading={saving} onClick={handleSave}>
              {editProfile ? 'Save Changes' : 'Add Robot'}
            </Button>
          </Group>
        </Group>
      </Stack>
    </Modal>
  );
}

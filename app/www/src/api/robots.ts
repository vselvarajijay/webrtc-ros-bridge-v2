export interface RobotProfile {
  id: string;
  name: string;
  robot_type: string;
  host: string;
  port: number;
  optical_flow: boolean;
  floor_mask: boolean;
}

export type RobotProfileCreate = Omit<RobotProfile, 'id'>;
export type RobotProfileUpdate = Partial<RobotProfileCreate>;

const BASE = '/api';

export async function fetchRobotTypes(): Promise<string[]> {
  const res = await fetch(`${BASE}/robot_types`);
  if (!res.ok) throw new Error(`Failed to fetch robot types: ${res.status}`);
  const data = await res.json() as { robot_types: string[] };
  return data.robot_types;
}

export async function listRobots(): Promise<RobotProfile[]> {
  const res = await fetch(`${BASE}/robots`);
  if (!res.ok) throw new Error(`Failed to list robots: ${res.status}`);
  return res.json() as Promise<RobotProfile[]>;
}

export async function createRobot(profile: RobotProfileCreate): Promise<RobotProfile> {
  const res = await fetch(`${BASE}/robots`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  });
  if (!res.ok) throw new Error(`Failed to create robot: ${res.status}`);
  return res.json() as Promise<RobotProfile>;
}

export async function getRobot(id: string): Promise<RobotProfile> {
  const res = await fetch(`${BASE}/robots/${id}`);
  if (!res.ok) throw new Error(`Failed to get robot: ${res.status}`);
  return res.json() as Promise<RobotProfile>;
}

export async function updateRobot(id: string, update: RobotProfileUpdate): Promise<RobotProfile> {
  const res = await fetch(`${BASE}/robots/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
  if (!res.ok) throw new Error(`Failed to update robot: ${res.status}`);
  return res.json() as Promise<RobotProfile>;
}

export async function deleteRobot(id: string): Promise<void> {
  const res = await fetch(`${BASE}/robots/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to delete robot: ${res.status}`);
}

export async function testRobotConnection(id: string): Promise<{ ok: boolean; detail: string }> {
  const res = await fetch(`${BASE}/robots/${id}/test_connection`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to test connection: ${res.status}`);
  return res.json() as Promise<{ ok: boolean; detail: string }>;
}

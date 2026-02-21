export interface TelemetryData {
  battery?: number;
  speed?: number;
  orientation?: number;
  signal_level?: number;
  gps_signal?: number;
  latitude?: number;
  longitude?: number;
  timestamp?: number;
  rpms?: number[];
  accels?: number[];
  gyros?: number[];
  mags?: number[];
  optical_flow?: { left?: number[]; center?: number[]; right?: number[] };
  [key: string]: unknown;
}

const dataUrl = '/data';

export async function fetchTelemetry(): Promise<TelemetryData | null> {
  const res = await fetch(dataUrl);
  if (!res.ok) return null;
  const data = await res.json();
  return data && typeof data === 'object' ? data : null;
}

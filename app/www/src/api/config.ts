export interface ApiConfig {
  iceServers?: RTCIceServer[];
  camera?: {
    fx: number;
    cx: number;
    cy: number;
    width: number;
    height: number;
  };
}

const configUrl = '/api/config';

export async function fetchConfig(): Promise<ApiConfig> {
  const res = await fetch(configUrl);
  if (!res.ok) throw new Error(`Config failed: ${res.status}`);
  return res.json() as Promise<ApiConfig>;
}

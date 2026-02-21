import { useEffect, useState } from 'react';
import type { TelemetryData } from '@/api/telemetry';
import { fetchTelemetry } from '@/api/telemetry';

const POLL_MS = 4000;

export function useTelemetry(): TelemetryData | null {
  const [data, setData] = useState<TelemetryData | null>(null);

  useEffect(() => {
    let cancelled = false;
    function poll() {
      fetchTelemetry().then((d) => {
        if (!cancelled && d) setData(d);
      });
    }
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return data;
}

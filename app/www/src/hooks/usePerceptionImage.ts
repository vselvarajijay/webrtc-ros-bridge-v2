import { useEffect, useState } from 'react';

const INTERVAL_MS = 100;
const BACKOFF_MS = 2000;

export type PerceptionImageType = 'optical_flow' | 'floor_mask';

const ENDPOINTS: Record<PerceptionImageType, string> = {
  optical_flow: '/api/optical_flow_image',
  floor_mask: '/api/floor_mask_image',
};

export function usePerceptionImage(type: PerceptionImageType): string | null {
  const [url, setUrl] = useState<string | null>(null);
  const endpoint = ENDPOINTS[type];

  useEffect(() => {
    let lastUpdate = 0;
    let interval = INTERVAL_MS;
    let currentUrl: string | null = null;
    let cancelled = false;

    function tick() {
      if (cancelled) return;
      const now = Date.now();
      if (now - lastUpdate < interval) {
        requestAnimationFrame(tick);
        return;
      }
      lastUpdate = now;

      fetch(`${endpoint}?t=${now}`)
        .then((res) => {
          if (!res.ok || !(res.headers.get('content-type') ?? '').startsWith('image/')) {
            if (res.status === 503) interval = BACKOFF_MS;
            throw new Error('Not an image');
          }
          interval = INTERVAL_MS;
          return res.blob();
        })
        .then((blob) => {
          if (cancelled) return;
          const next = URL.createObjectURL(blob);
          if (currentUrl) URL.revokeObjectURL(currentUrl);
          currentUrl = next;
          setUrl(next);
        })
        .catch(() => {
          if (!cancelled) setUrl(null);
        })
        .finally(() => {
          if (!cancelled) requestAnimationFrame(tick);
        });
    }

    const raf = requestAnimationFrame(tick);
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      if (currentUrl) URL.revokeObjectURL(currentUrl);
    };
  }, [endpoint, type]);

  return url;
}

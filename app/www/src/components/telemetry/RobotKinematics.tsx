import { Box, Card, Stack, Text } from '@mantine/core';
import { useWebRTC } from '@/context/WebRTCContext';

const MAX_SPEED_MPS = 2.0;
const COMPASS_SIZE = 48;

function getPositionFromTelemetry(telemetry: Record<string, unknown> | null): {
  x: number | null;
  y: number | null;
} {
  if (!telemetry || typeof telemetry !== 'object') return { x: null, y: null };
  const x =
    typeof telemetry.position_x === 'number' && Number.isFinite(telemetry.position_x)
      ? telemetry.position_x
      : typeof telemetry.x === 'number' && Number.isFinite(telemetry.x)
        ? telemetry.x
        : null;
  const y =
    typeof telemetry.position_y === 'number' && Number.isFinite(telemetry.position_y)
      ? telemetry.position_y
      : typeof telemetry.y === 'number' && Number.isFinite(telemetry.y)
        ? telemetry.y
        : null;
  return { x, y };
}

export function RobotKinematics() {
  const { telemetry } = useWebRTC();

  const speed =
    telemetry?.speed != null && Number.isFinite(telemetry.speed)
      ? Number(telemetry.speed)
      : null;
  const rawHeading =
    telemetry?.orientation != null && Number.isFinite(Number(telemetry.orientation))
      ? Number(telemetry.orientation)
      : null;
  /** Normalize to 0–360 so display and compass match (e.g. 360° shows as 0, -10° as 350°). */
  const headingDeg =
    rawHeading != null ? ((rawHeading % 360) + 360) % 360 : null;
  const { x: posX, y: posY } = getPositionFromTelemetry(telemetry ?? null);

  const speedPercent =
    speed != null ? Math.min(100, (speed / MAX_SPEED_MPS) * 100) : 0;

  return (
    <Card
      withBorder
      padding="sm"
      className="overflow-hidden flex flex-col min-h-0"
      style={{
        height: '100%',
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--mantine-color-dark-9)',
        borderColor: 'var(--mantine-color-dark-4)',
        borderRadius: 8,
      }}
    >
      <Text
        size="xs"
        fw={600}
        c="dimmed"
        tt="uppercase"
        mb="xs"
        className="shrink-0"
      >
        Kinematics & Odometry
      </Text>
      <Stack gap="sm" className="flex-1 min-h-0">
        {/* SPD */}
        <Box>
          <div className="flex items-baseline justify-between gap-2 mb-0.5">
            <Text size="xs" c="dimmed" component="span">
              SPD
            </Text>
            <Text
              size="sm"
              component="span"
              className="font-mono tabular-nums"
              style={{ fontVariantNumeric: 'tabular-nums' }}
            >
              {speed != null ? `${speed.toFixed(2)} m/s` : '— m/s'}
            </Text>
          </div>
          <div
            className="h-1 rounded-full overflow-hidden bg-[var(--mantine-color-dark-5)]"
            role="progressbar"
            aria-valuenow={speed ?? 0}
            aria-valuemin={0}
            aria-valuemax={MAX_SPEED_MPS}
          >
            <div
              className="h-full rounded-full bg-[var(--mantine-color-dark-2)] transition-[width] duration-150"
              style={{ width: `${speedPercent}%` }}
            />
          </div>
        </Box>

        {/* HDG */}
        <Box>
          <div className="flex items-center gap-2 mb-1">
            <Text size="xs" c="dimmed" component="span">
              HDG
            </Text>
            <Text
              size="sm"
              component="span"
              className="font-mono tabular-nums"
              style={{ fontVariantNumeric: 'tabular-nums' }}
            >
              {headingDeg != null ? `${Math.round(headingDeg)}°` : '—°'}
            </Text>
          </div>
          <div
            className="relative rounded-full border border-[var(--mantine-color-dark-4)] flex items-center justify-center"
            style={{
              width: COMPASS_SIZE,
              height: COMPASS_SIZE,
              backgroundColor: 'var(--mantine-color-dark-8)',
            }}
            aria-hidden
          >
            <svg
              viewBox="0 0 24 24"
              className="w-full h-full"
              style={{ transform: `rotate(${headingDeg ?? 0}deg)` }}
            >
              <polygon
                points="12,4 14,20 12,16 10,20"
                fill="var(--mantine-color-dark-2)"
              />
            </svg>
          </div>
        </Box>

        {/* POS */}
        <Box>
          <Text size="xs" c="dimmed" component="span" className="block mb-0.5">
            POS
          </Text>
          <Text
            size="sm"
            className="font-mono tabular-nums"
            style={{ fontVariantNumeric: 'tabular-nums' }}
          >
            X: {posX != null ? posX.toFixed(2) : '—'}, Y:{' '}
            {posY != null ? posY.toFixed(2) : '—'}
          </Text>
        </Box>
      </Stack>
    </Card>
  );
}

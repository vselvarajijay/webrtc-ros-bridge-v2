import { useCallback, useEffect, useRef, useState } from 'react';
import { Box, Button, Slider, Stack, Text } from '@mantine/core';
import { useWebRTC } from '@/context/WebRTCContext';

const LINEAR_VEL = 0.8;
const ANGULAR_VEL = 1.0;
const SPEED_MULTIPLIERS = [0.2, 0.4, 0.6, 0.8, 1.0];
const CONTROL_SEND_INTERVAL_MS = 50;
const JOYSTICK_MAX = 22;

const GRID_BUTTONS: { linear: number; angular: number; label: string }[] = [
  { linear: 1, angular: 1, label: '↖' },
  { linear: 1, angular: 0, label: '↑' },
  { linear: 1, angular: -1, label: '↗' },
  { linear: 0, angular: 1, label: '←' },
  { linear: 0, angular: -1, label: '→' },
  { linear: -1, angular: 1, label: '↙' },
  { linear: -1, angular: 0, label: '↓' },
  { linear: -1, angular: -1, label: '↘' },
];

function headingToArrow(deg: number): string {
  const arrows = ['→', '↗', '↑', '↖', '←', '↙', '↓', '↘'];
  const idx = Math.round(((deg % 360) + 360) % 360 / 45) % 8;
  return arrows[idx];
}

export function DriveControls() {
  const { sendControl, sendWander, commandsReady, telemetry } = useWebRTC();
  const [speedLevel, setSpeedLevel] = useState(3);
  const [direction, setDirection] = useState<{ linear: number; angular: number }>({ linear: 0, angular: 0 });
  const [joystick, setJoystick] = useState({ x: 0, y: 0 });
  const [joystickActive, setJoystickActive] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const joystickWrapRef = useRef<HTMLDivElement>(null);

  const mul = SPEED_MULTIPLIERS[Math.min(4, Math.max(0, speedLevel - 1))];
  const headingDeg = telemetry?.orientation != null
    ? ((Number(telemetry.orientation) / 255) * 360) % 360
    : null;
  const headingLabel = headingDeg != null
    ? `${headingToArrow(headingDeg)} ${headingDeg.toFixed(1)}°`
    : '—';

  const applyVelocity = useCallback(() => {
    let linearX = 0;
    let angularZ = 0;
    if (joystickActive) {
      linearX = LINEAR_VEL * mul * joystick.y;
      angularZ = -ANGULAR_VEL * mul * joystick.x;
      if (Math.abs(linearX) > 0.01 && Math.abs(angularZ) > 0.01) {
        const factor = 1 / Math.sqrt(2);
        linearX *= factor;
        angularZ *= factor;
      }
    } else {
      linearX = LINEAR_VEL * mul * direction.linear;
      angularZ = ANGULAR_VEL * mul * direction.angular;
    }
    sendControl(linearX, angularZ);
  }, [joystickActive, joystick, direction, mul, sendControl]);

  const hasInput = direction.linear !== 0 || direction.angular !== 0 || joystickActive;

  useEffect(() => {
    if (hasInput) {
      if (!intervalRef.current) {
        intervalRef.current = setInterval(applyVelocity, CONTROL_SEND_INTERVAL_MS);
      }
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
        sendControl(0, 0);
      }
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [hasInput, applyVelocity, sendControl]);

  const handleGridButton = (linear: number, angular: number) => {
    setDirection({ linear, angular });
    setJoystickActive(false);
    setJoystick({ x: 0, y: 0 });
  };

  const handleJoystickMove = useCallback(
    (clientX: number, clientY: number) => {
      const wrap = joystickWrapRef.current;
      if (!wrap) return;
      const rect = wrap.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = clientX - cx;
      const dy = clientY - cy;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 1e-6) {
        setJoystick({ x: 0, y: 0 });
        return;
      }
      const r = Math.min(1, dist / JOYSTICK_MAX);
      setJoystick({
        x: (r * dx) / dist,
        y: (-r * dy) / dist,
      });
    },
    []
  );

  const onPointerDown = (e: React.PointerEvent) => {
    e.preventDefault();
    setJoystickActive(true);
    setDirection({ linear: 0, angular: 0 });
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    handleJoystickMove(e.clientX, e.clientY);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!joystickActive) return;
    e.preventDefault();
    handleJoystickMove(e.clientX, e.clientY);
  };

  const onPointerUp = (e: React.PointerEvent) => {
    e.preventDefault();
    setJoystickActive(false);
    setJoystick({ x: 0, y: 0 });
    sendControl(0, 0);
    (e.target as HTMLElement).releasePointerCapture?.(e.pointerId);
  };

  return (
    <Stack gap="md" style={{ flex: 1, minHeight: 0 }}>
      <Text size="xs" c="dimmed">
        Commands: {commandsReady ? 'connected' : 'connecting…'}
      </Text>

      <Stack gap="xs">
        <Text size="xs">Speed: {(LINEAR_VEL * mul).toFixed(2)} m/s</Text>
        <Slider
          min={1}
          max={5}
          step={1}
          value={speedLevel}
          onChange={setSpeedLevel}
          marks={[{ value: 1, label: '1' }, { value: 3, label: '3' }, { value: 5, label: '5' }]}
        />
      </Stack>

      <Text size="sm" fw={600}>
        Heading {headingLabel}
      </Text>

      <div className="grid grid-cols-3 gap-1 w-[150px] mx-auto">
        {[0, 1, 2, 3, -1, 4, 5, 6, 7].map((idx) =>
          idx === -1 ? (
            <Box key="joy" className="flex items-center justify-center">
              <Box
                ref={joystickWrapRef}
                className="relative w-12 h-12 rounded-full border-2 border-gray-600 cursor-grab active:cursor-grabbing"
                role="group"
                aria-label="Joystick"
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                onPointerLeave={onPointerUp}
              >
                <div
                  className="absolute w-3 h-3 rounded-full bg-blue-500 top-1/2 left-1/2"
                  style={{
                    transform: `translate(calc(-50% + ${joystick.x * JOYSTICK_MAX}px), calc(-50% + ${-joystick.y * JOYSTICK_MAX}px))`,
                  }}
                />
              </Box>
            </Box>
          ) : (
            <Button
              key={idx}
              variant={direction.linear === GRID_BUTTONS[idx].linear && direction.angular === GRID_BUTTONS[idx].angular ? 'filled' : 'light'}
              size="xs"
              onClick={() => handleGridButton(GRID_BUTTONS[idx].linear, GRID_BUTTONS[idx].angular)}
              disabled={!commandsReady}
            >
              {GRID_BUTTONS[idx].label}
            </Button>
          )
        )}
      </div>

      <Stack gap="sm" mt="md">
        <Button size="sm" onClick={() => sendWander(true)} disabled={!commandsReady}>
          Start wandering
        </Button>
        <Button size="sm" variant="light" onClick={() => sendWander(false)} disabled={!commandsReady}>
          Stop wandering
        </Button>
        <Text size="xs" c="dimmed">Requires wander_node on robot</Text>
      </Stack>
    </Stack>
  );
}

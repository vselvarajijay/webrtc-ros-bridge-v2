import type { ReactNode } from 'react';
import { useRef, useCallback, useState } from 'react';
import { WebRTCContext } from '@/context/WebRTCContext';
import type { TelemetryData } from '@/api/telemetry';

export interface MockWebRTCProviderProps {
  children: ReactNode;
  /** Simulate connected state with commands ready */
  commandsReady?: boolean;
  /** Simulate video stream active */
  video?: boolean;
  /** Mock telemetry (e.g. speed, battery, signal_level, orientation) */
  telemetry?: TelemetryData | null;
  /** Connection status label (e.g. "connected", "connecting") */
  conn?: string;
}

export function MockWebRTCProvider({
  children,
  commandsReady = true,
  video = false,
  telemetry = null,
  conn = 'connected',
}: MockWebRTCProviderProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [driveMode, setDriveMode] = useState<'teleop' | 'autonomous'>('teleop');
  const [robotTarget, setRobotTarget] = useState<'physical' | 'simulator'>('physical');

  const sendControl = useCallback((_linearX: number, _angularZ: number) => {
    // no-op in storybook
  }, []);
  const sendWander = useCallback((_enable: boolean) => {}, []);
  const eStop = useCallback(() => {}, []);

  const value = {
    videoRef,
    pipelineState: {
      signaling: true,
      robot: true,
      video,
    },
    connectionDebug: {
      signaling: 'connected',
      offer: 'sent',
      answer: 'received',
      ice: 'connected',
      conn,
      data: 'open',
    },
    telemetry,
    commandsReady,
    lastControlSent: null,
    systemLogLines: [],
    appendSystemLog: () => {},
    lampOn: false,
    setLampOn: () => {},
    driveMode,
    setDriveMode,
    robotTarget,
    setRobotTarget,
    sendControl,
    sendWander,
    eStop,
  };

  return (
    <WebRTCContext.Provider value={value}>
      {children}
    </WebRTCContext.Provider>
  );
}

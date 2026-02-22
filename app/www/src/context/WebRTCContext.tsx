import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { TelemetryData } from '@/api/telemetry';
import { fetchConfig } from '@/api/config';

export interface PipelineState {
  signaling: boolean;
  robot: boolean;
  video: boolean;
}

export interface ConnectionDebug {
  signaling: string;
  offer: string;
  answer: string;
  ice: string;
  conn: string;
  data: string;
}

export type DriveMode = 'teleop' | 'autonomous';

export interface LastControlSent {
  linearX: number;
  angularZ: number;
  at: number;
}

const SYSTEM_LOG_MAX_LINES = 200;

interface WebRTCContextValue {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  pipelineState: PipelineState;
  connectionDebug: ConnectionDebug;
  telemetry: TelemetryData | null;
  commandsReady: boolean;
  /** Last control message actually sent over the WebRTC data channel (throttled updates for display). */
  lastControlSent: LastControlSent | null;
  /** Lines for System Logs & Telemetry panel (control, wander, telemetry). */
  systemLogLines: string[];
  appendSystemLog: (line: string) => void;
  lampOn: boolean;
  setLampOn: (on: boolean) => void;
  driveMode: DriveMode;
  setDriveMode: (mode: DriveMode) => void;
  sendControl: (linearX: number, angularZ: number) => void;
  sendWander: (enable: boolean) => void;
  eStop: () => void;
}

const defaultDebug: ConnectionDebug = {
  signaling: '—',
  offer: '—',
  answer: '—',
  ice: '—',
  conn: '—',
  data: '—',
};

export const WebRTCContext = createContext<WebRTCContextValue | null>(null);

function getWsUrl(): string {
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${scheme}//${window.location.host}/ws/signaling`;
}

/** When true, control is sent over the signaling WebSocket (browser → API → bridge) so you can see it in Network tab. */
function useSignalingForControl(): boolean {
  if (typeof window === 'undefined') return false;
  return new URLSearchParams(window.location.search).get('control_via_signaling') === '1';
}

/** Merge new telemetry into previous; do not overwrite with null/undefined (avoids heartbeat/partial flicker). */
function mergeTelemetry(
  prev: TelemetryData | null,
  next: Record<string, unknown>
): TelemetryData {
  if (!prev || typeof prev !== 'object') {
    return next as TelemetryData;
  }
  const out = { ...prev };
  for (const key of Object.keys(next)) {
    const v = next[key];
    if (v !== null && v !== undefined) {
      (out as Record<string, unknown>)[key] = v;
    }
  }
  return out as TelemetryData;
}

export function WebRTCProvider({ children }: { children: ReactNode }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [pipelineState, setPipelineState] = useState<PipelineState>({
    signaling: false,
    robot: false,
    video: false,
  });
  const [connectionDebug, setConnectionDebug] = useState<ConnectionDebug>(defaultDebug);
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [commandsReady, setCommandsReady] = useState(false);
  const [lastControlSent, setLastControlSent] = useState<LastControlSent | null>(null);
  const [lampOn, setLampOn] = useState(false);
  const [driveMode, setDriveMode] = useState<DriveMode>('teleop');

  const wsRef = useRef<WebSocket | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);
  const iceServersRef = useRef<RTCIceServer[]>([{ urls: 'stun:stun.l.google.com:19302' }]);
  const lastControlRef = useRef<{ linearX: number; angularZ: number }>({ linearX: 0, angularZ: 0 });
  const lastControlSentDisplayRef = useRef(0);
  const lastControlLogTimeRef = useRef(0);
  const LAST_SENT_DISPLAY_MS = 400;
  const CONTROL_LOG_THROTTLE_MS = 500;
  const controlViaSignaling = useSignalingForControl();

  const [systemLogLines, setSystemLogLines] = useState<string[]>([]);
  const appendSystemLog = useCallback((line: string) => {
    setSystemLogLines((prev) => [...prev.slice(-(SYSTEM_LOG_MAX_LINES - 1)), line]);
  }, []);

  const setDebug = useCallback((key: keyof ConnectionDebug, value: string, _ok?: boolean) => {
    setConnectionDebug((prev) => ({ ...prev, [key]: value }));
  }, []);

  const hideVideoPlaceholder = useCallback(() => {
    const video = videoRef.current;
    if (video && video.srcObject) {
      const placeholder = document.getElementById('videoPlaceholder');
      if (placeholder) placeholder.hidden = true;
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    const wsUrl = getWsUrl();
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setPipelineState((p) => ({ ...p, signaling: true }));
      setDebug('signaling', 'connected', true);
      if (controlViaSignaling) setCommandsReady(true);
      ws.send(JSON.stringify({ role: 'browser' }));
      setTimeout(() => {
        if (!pcRef.current && wsRef.current?.readyState === WebSocket.OPEN) {
          createOffer();
        }
      }, 500);
    };

    ws.onclose = () => {
      setDebug('signaling', 'disconnected', false);
      setPipelineState({ signaling: false, robot: false, video: false });
      setCommandsReady(false);
      setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      setDebug('signaling', 'error', false);
    };

    ws.onmessage = (event) => {
      let msg: { type?: string; sdp?: string; data?: TelemetryData; candidate?: RTCIceCandidateInit; [k: string]: unknown };
      try {
        msg = JSON.parse(event.data as string);
      } catch {
        return;
      }
      const typ = msg.type;

      if (typ === 'welcome') {
        createOffer();
        return;
      }

      if (typ === 'telemetry') {
        setPipelineState((p) => ({ ...p, robot: true }));
        const data = msg.data && typeof msg.data === 'object' ? msg.data : {};
        setTelemetry((prev) => mergeTelemetry(prev, data as Record<string, unknown>));
        return;
      }

      if (typ === 'answer' && msg.sdp) {
        const pc = pcRef.current;
        if (!pc || pc.signalingState !== 'have-local-offer') return;
        setDebug('answer', 'received', true);
        setPipelineState((p) => ({ ...p, robot: true }));
        pc.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp: msg.sdp }))
          .then(() => attachRemoteVideoTrack())
          .catch((err) => {
            console.error('setRemoteDescription failed', err);
            setDebug('answer', 'setRemote failed', false);
          });
        return;
      }

      if (typ === 'ice' || typ === 'ice-candidate' || typ === 'icecandidate') {
        const cand = msg.candidate;
        const pc = pcRef.current;
        if (!pc || !cand) return;
        const candidate = typeof cand === 'string' ? { candidate: cand } : cand;
        pc.addIceCandidate(new RTCIceCandidate(candidate)).catch((err) =>
          console.error('addIceCandidate failed', err)
        );
      }
    };
  }, [setDebug, controlViaSignaling]);

  const attachRemoteVideoTrack = useCallback(() => {
    const pc = pcRef.current;
    const video = videoRef.current;
    if (!pc || !video) return;
    try {
      const receivers = pc.getReceivers?.() ?? [];
      for (const rec of receivers) {
        const track = rec.track;
        if (track?.kind === 'video') {
          const existing = video.srcObject as MediaStream | null;
          const alreadyHas = existing?.getTracks?.().includes(track);
          if (alreadyHas) return;
          setPipelineState((p) => ({ ...p, video: true }));
          hideVideoPlaceholder();
          const stream = new MediaStream([track]);
          video.srcObject = stream;
          track.enabled = true;
          video.play().catch(() => {});
          return;
        }
      }
    } catch (e) {
      console.debug('attachRemoteVideoTrack', e);
    }
  }, [hideVideoPlaceholder]);

  const createOffer = useCallback(() => {
    if (pcRef.current) return;
    setPipelineState((p) => ({ ...p, video: false }));
    const config = { iceServers: iceServersRef.current };
    const pc = new RTCPeerConnection(config);
    pcRef.current = pc;
    pc.addTransceiver('video', { direction: 'recvonly' });

    pc.onicecandidate = (event) => {
      if (event.candidate && wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: 'ice',
            candidate: event.candidate.toJSON?.() ?? event.candidate,
          })
        );
      }
    };

    pc.ontrack = (event) => {
      setPipelineState((p) => ({ ...p, video: true }));
      hideVideoPlaceholder();
      const video = videoRef.current;
      if (!video) return;
      const stream = event.streams?.[0] ?? new MediaStream([event.track]);
      video.srcObject = stream;
      event.track.enabled = true;
      video.play().catch(() => {});
    };

    pc.onconnectionstatechange = () => {
      setConnectionDebug((prev) => ({
        ...prev,
        conn: pc.connectionState ?? '—',
        data: dataChannelRef.current?.readyState ?? prev.data,
      }));
      if (pc.connectionState === 'connected') {
        setPipelineState((p) => ({ ...p, signaling: true, robot: true }));
      }
    };

    pc.oniceconnectionstatechange = () => {
      setConnectionDebug((prev) => ({
        ...prev,
        ice: pc.iceConnectionState ?? '—',
      }));
      if (pc.iceConnectionState === 'connected') {
        attachRemoteVideoTrack();
        setTimeout(attachRemoteVideoTrack, 200);
      }
    };

    // Use ordered reliable channel so control messages are not dropped (unordered can drop under load)
    const dc = pc.createDataChannel('control', { ordered: true });
    dataChannelRef.current = dc;
    dc.onopen = () => {
      setCommandsReady(true);
      setDebug('data', 'open', true);
    };
    dc.onclose = () => {
      setCommandsReady(false);
      setDebug('data', dc.readyState ?? 'closed', false);
    };
    dc.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string);
        if (msg.type === 'telemetry' && msg.data && typeof msg.data === 'object') {
          setTelemetry((prev) => mergeTelemetry(prev, msg.data as Record<string, unknown>));
        }
        if (msg.type === 'planning' && typeof msg.line === 'string') {
          appendSystemLog(msg.line);
        }
      } catch {}
    };

    pc.createOffer()
      .then((offer) => pc.setLocalDescription(offer))
      .then(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(
            JSON.stringify({ type: 'offer', sdp: pc.localDescription?.sdp })
          );
          setDebug('offer', 'sent', true);
        }
      })
      .catch((err) => {
        console.error('createOffer failed', err);
        setDebug('offer', 'failed', false);
      });
  }, [attachRemoteVideoTrack, hideVideoPlaceholder, setDebug, appendSystemLog]);

  useEffect(() => {
    fetchConfig()
      .then((data) => {
        if (data.iceServers?.length) iceServersRef.current = data.iceServers;
      })
      .catch(() => {})
      .finally(connect);
    return () => {
      if (pcRef.current) {
        pcRef.current.close();
        pcRef.current = null;
      }
      dataChannelRef.current = null;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const sendControl = useCallback(
    (linearX: number, angularZ: number) => {
      lastControlRef.current = { linearX, angularZ };
      const now = Date.now();
      const updateSentDisplay = () => {
        if (now - lastControlSentDisplayRef.current >= LAST_SENT_DISPLAY_MS) {
          lastControlSentDisplayRef.current = now;
          setLastControlSent({ linearX, angularZ, at: now });
        }
      };
      const maybeLogControl = () => {
        if (now - lastControlLogTimeRef.current >= CONTROL_LOG_THROTTLE_MS) {
          lastControlLogTimeRef.current = now;
          const ts = new Date().toTimeString().slice(0, 8);
          setSystemLogLines((prev) => [
            ...prev.slice(-(SYSTEM_LOG_MAX_LINES - 1)),
            `[${ts}] Control: linear=${linearX.toFixed(2)} angular=${angularZ.toFixed(2)}`,
          ]);
        }
      };

      if (controlViaSignaling) {
        // Path: browser → API (WebSocket) → bridge (visible in Network tab)
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        try {
          ws.send(
            JSON.stringify({
              type: 'control',
              data: { linear_x: linearX, angular_z: angularZ },
            })
          );
          updateSentDisplay();
          maybeLogControl();
        } catch (_) {}
        return;
      }

      // Default: path browser → WebRTC data channel → bridge (lower latency)
      const dc = dataChannelRef.current;
      if (!dc || dc.readyState !== 'open') return;
      const maxBufferedBytes = 32 * 1024;
      if (dc.bufferedAmount > maxBufferedBytes) return;
      try {
        dc.send(
          JSON.stringify({
            linear_x: linearX,
            angular_z: angularZ,
            lamp: lampOn ? 1 : 0,
          })
        );
        updateSentDisplay();
        maybeLogControl();
      } catch (_) {}
    },
    [lampOn, controlViaSignaling]
  );

  const sendWander = useCallback(
    (enable: boolean) => {
      const dc = dataChannelRef.current;
      if (!dc || dc.readyState !== 'open') return;
      try {
        dc.send(JSON.stringify({ command: enable ? 'wander_start' : 'wander_stop' }));
        const ts = new Date().toTimeString().slice(0, 8);
        appendSystemLog(`[${ts}] Autonomous: wander ${enable ? 'started' : 'stopped'}`);
      } catch (_) {}
    },
    [appendSystemLog]
  );

  const eStop = useCallback(() => {
    // Send autonomy stop so that if wander is active, it turns off and webrtc can publish (0,0)
    const dc = dataChannelRef.current;
    if (dc && dc.readyState === 'open') {
      try {
        dc.send(JSON.stringify({ command: 'wander_stop' }));
      } catch (_) {}
    }
    sendControl(0, 0);
  }, [sendControl]);

  // When lamp changes, resend last control so lamp is included
  useEffect(() => {
    const { linearX, angularZ } = lastControlRef.current;
    if (commandsReady && (linearX !== 0 || angularZ !== 0 || lampOn)) {
      sendControl(linearX, angularZ);
    }
  }, [lampOn, commandsReady, sendControl]);

  const value: WebRTCContextValue = {
    videoRef,
    pipelineState,
    connectionDebug,
    telemetry,
    commandsReady,
    lastControlSent,
    systemLogLines,
    appendSystemLog,
    lampOn,
    setLampOn,
    driveMode,
    setDriveMode,
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

export function useWebRTC(): WebRTCContextValue {
  const ctx = useContext(WebRTCContext);
  if (!ctx) throw new Error('useWebRTC must be used within WebRTCProvider');
  return ctx;
}

/** Widget configuration interface used by the layout system. */
export interface WidgetConfig {
  /** Unique stable identifier for the widget. */
  id: string;
  /** Human-readable label shown in the title bar. */
  label: string;
  /** Default position (pixels from top-left of the dashboard canvas). */
  defaultPosition: { x: number; y: number };
  /** Default dimensions in pixels. */
  defaultSize: { width: number; height: number };
  /** Minimum allowed dimensions in pixels. */
  minSize: { width: number; height: number };
}

/**
 * Central registry of all dashboard widgets.
 * Adding a new entry here is the only step needed to give a new widget
 * drag/resize/persistence behaviour.
 */
export const WIDGET_REGISTRY: WidgetConfig[] = [
  {
    id: 'optical-flow',
    label: 'Optical Flow',
    defaultPosition: { x: 0, y: 0 },
    defaultSize: { width: 320, height: 280 },
    minSize: { width: 200, height: 150 },
  },
  {
    id: 'floor-mask',
    label: 'Floor Mask',
    defaultPosition: { x: 0, y: 300 },
    defaultSize: { width: 320, height: 280 },
    minSize: { width: 200, height: 150 },
  },
  {
    id: 'video-stream',
    label: 'Live View',
    defaultPosition: { x: 340, y: 0 },
    defaultSize: { width: 640, height: 480 },
    minSize: { width: 320, height: 240 },
  },
  {
    id: 'robot-control',
    label: 'Robot Control',
    defaultPosition: { x: 1000, y: 0 },
    defaultSize: { width: 300, height: 500 },
    minSize: { width: 220, height: 300 },
  },
  {
    id: 'system-logs',
    label: 'System Logs & Telemetry',
    defaultPosition: { x: 0, y: 600 },
    defaultSize: { width: 980, height: 200 },
    minSize: { width: 300, height: 120 },
  },
];

/** Convenience map from widget id → config for O(1) lookup. */
export const WIDGET_MAP: Record<string, WidgetConfig> = Object.fromEntries(
  WIDGET_REGISTRY.map((w) => [w.id, w]),
);

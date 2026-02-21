import { OpticalFlowView, FloorMaskView } from '@/components/telemetry';
import { VideoStream } from '@/features/VideoStream';
import { RobotControl } from '@/features/RobotControl';
import { SystemLogsPanel } from '@/components/cockpit/SystemLogsPanel';
import { DraggableResizableWidget } from './DraggableResizableWidget';
import { useDashboard } from './useDashboard';
import { WIDGET_MAP } from './widget-registry';
import type { WidgetLayout } from './LayoutManager';

/** Helper – returns the persisted layout for a widget or its registered defaults. */
function widgetLayout(id: string, widgets: Record<string, WidgetLayout>): WidgetLayout {
  if (widgets[id]) return widgets[id];
  const cfg = WIDGET_MAP[id];
  return {
    x: cfg.defaultPosition.x,
    y: cfg.defaultPosition.y,
    width: cfg.defaultSize.width,
    height: cfg.defaultSize.height,
  };
}

/**
 * Freehand dashboard canvas.
 * All widgets are absolutely positioned and freely draggable / resizable.
 * Layout state is managed by DashboardContext and persisted to localStorage.
 */
export function DashboardCanvas() {
  const { layout, updateWidget } = useDashboard();

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        // Use Mantine AppShell CSS variables injected at :root by AppShellMediaStyles.
        // --app-shell-header-offset: header height (60px default)
        // --app-shell-padding: AppShell `padding` prop value (var(--mantine-spacing-md) = 16px default)
        height: 'calc(100dvh - var(--app-shell-header-offset) - 2 * var(--app-shell-padding))',
        overflow: 'hidden',
      }}
    >
      <DraggableResizableWidget
        config={WIDGET_MAP['optical-flow']}
        layout={widgetLayout('optical-flow', layout.widgets)}
        onLayoutChange={updateWidget}
      >
        <OpticalFlowView />
      </DraggableResizableWidget>

      <DraggableResizableWidget
        config={WIDGET_MAP['floor-mask']}
        layout={widgetLayout('floor-mask', layout.widgets)}
        onLayoutChange={updateWidget}
      >
        <FloorMaskView />
      </DraggableResizableWidget>

      <DraggableResizableWidget
        config={WIDGET_MAP['video-stream']}
        layout={widgetLayout('video-stream', layout.widgets)}
        onLayoutChange={updateWidget}
      >
        <VideoStream />
      </DraggableResizableWidget>

      <DraggableResizableWidget
        config={WIDGET_MAP['robot-control']}
        layout={widgetLayout('robot-control', layout.widgets)}
        onLayoutChange={updateWidget}
      >
        <RobotControl />
      </DraggableResizableWidget>

      <DraggableResizableWidget
        config={WIDGET_MAP['system-logs']}
        layout={widgetLayout('system-logs', layout.widgets)}
        onLayoutChange={updateWidget}
      >
        <SystemLogsPanel />
      </DraggableResizableWidget>
    </div>
  );
}

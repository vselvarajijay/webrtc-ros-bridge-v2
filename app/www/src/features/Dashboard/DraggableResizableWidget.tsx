import type { ReactNode } from 'react';
import { Rnd } from 'react-rnd';
import type { WidgetLayout } from './LayoutManager';
import type { WidgetConfig } from './widget-registry';

export interface DraggableResizableWidgetProps {
  config: WidgetConfig;
  layout: WidgetLayout;
  isEditing: boolean;
  onLayoutChange: (id: string, layout: WidgetLayout) => void;
  children: ReactNode;
}

/** CSS for the 8 resize handles (visible only in edit mode). */
const HANDLE_STYLE: React.CSSProperties = {
  background: 'rgba(99,179,237,0.6)',
  borderRadius: 2,
  zIndex: 10,
};

const HANDLE_STYLES = {
  top: { ...HANDLE_STYLE, left: '50%', transform: 'translateX(-50%)', width: 32, height: 6, top: 0 },
  bottom: { ...HANDLE_STYLE, left: '50%', transform: 'translateX(-50%)', width: 32, height: 6, bottom: 0 },
  left: { ...HANDLE_STYLE, top: '50%', transform: 'translateY(-50%)', width: 6, height: 32, left: 0 },
  right: { ...HANDLE_STYLE, top: '50%', transform: 'translateY(-50%)', width: 6, height: 32, right: 0 },
  topLeft: { ...HANDLE_STYLE, width: 10, height: 10, top: 0, left: 0 },
  topRight: { ...HANDLE_STYLE, width: 10, height: 10, top: 0, right: 0 },
  bottomLeft: { ...HANDLE_STYLE, width: 10, height: 10, bottom: 0, left: 0 },
  bottomRight: { ...HANDLE_STYLE, width: 10, height: 10, bottom: 0, right: 0 },
};

/** Invisible handle styles used when not editing — keeps react-rnd happy but hides affordances. */
const HIDDEN_HANDLE_STYLES = {
  top: { display: 'none' },
  bottom: { display: 'none' },
  left: { display: 'none' },
  right: { display: 'none' },
  topLeft: { display: 'none' },
  topRight: { display: 'none' },
  bottomLeft: { display: 'none' },
  bottomRight: { display: 'none' },
};

export function DraggableResizableWidget({
  config,
  layout,
  isEditing,
  onLayoutChange,
  children,
}: DraggableResizableWidgetProps) {
  return (
    <Rnd
      position={{ x: layout.x, y: layout.y }}
      size={{ width: layout.width, height: layout.height }}
      minWidth={config.minSize.width}
      minHeight={config.minSize.height}
      maxWidth="95vw"
      maxHeight="95vh"
      bounds="parent"
      disableDragging={!isEditing}
      enableResizing={isEditing}
      dragHandleClassName="widget-drag-handle"
      resizeHandleStyles={isEditing ? HANDLE_STYLES : HIDDEN_HANDLE_STYLES}
      onDragStop={(_e, d) => {
        onLayoutChange(config.id, { ...layout, x: d.x, y: d.y });
      }}
      onResizeStop={(_e, _dir, ref, _delta, position) => {
        onLayoutChange(config.id, {
          x: position.x,
          y: position.y,
          width: ref.offsetWidth,
          height: ref.offsetHeight,
        });
      }}
      style={{
        display: 'flex',
        flexDirection: 'column',
        outline: isEditing ? '1px dashed rgba(99,179,237,0.4)' : 'none',
      }}
      className="dashboard-widget"
    >
      {/* Drag handle title bar — only visible in edit mode */}
      {isEditing && (
        <div
          className="widget-drag-handle"
          style={{
            padding: '4px 8px',
            fontSize: '0.7rem',
            fontWeight: 600,
            color: 'var(--mantine-color-dark-2)',
            background: 'var(--mantine-color-dark-8)',
            borderBottom: '1px solid var(--mantine-color-dark-5)',
            borderRadius: '8px 8px 0 0',
            cursor: 'grab',
            userSelect: 'none',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
          }}
          onMouseDown={(e) => {
            const el = e.currentTarget.closest<HTMLElement>('.dashboard-widget');
            if (el) el.style.zIndex = '100';
          }}
          onMouseUp={(e) => {
            const el = e.currentTarget.closest<HTMLElement>('.dashboard-widget');
            if (el) el.style.zIndex = '';
          }}
        >
          {config.label}
        </div>
      )}

      {/* Widget content */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {children}
      </div>
    </Rnd>
  );
}

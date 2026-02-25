import { OpticalFlowView, FloorMaskView } from '@/components/telemetry';
import { VideoStream } from '@/features/VideoStream';

const gridCellClass = 'min-h-0 overflow-hidden';

export function LiveViewTabs() {
  return (
    <div
      className="flex-1 min-h-0 overflow-hidden"
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gridTemplateRows: '1fr 1fr',
        gap: 8,
      }}
    >
      <div className={gridCellClass}>
        <VideoStream />
      </div>
      <div className={gridCellClass}>
        <OpticalFlowView />
      </div>
      <div className={gridCellClass}>
        <FloorMaskView />
      </div>
      <div className={gridCellClass} />
    </div>
  );
}

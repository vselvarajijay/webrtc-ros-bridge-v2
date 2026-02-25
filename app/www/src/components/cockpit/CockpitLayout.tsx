import { LiveViewTabs } from './LiveViewTabs';
import { SystemLogsPanel } from './SystemLogsPanel';
import { ControlAndChatPanel } from './ControlAndChatPanel';

/** Left ~2/3: Video (flex-grow) + System Logs (fixed height). Right ~1/3: Control + Chat tabbed panel. */
export function CockpitLayout() {
  return (
    <div className="h-full w-full min-h-0 flex overflow-hidden gap-4">
      {/* Left column: Video & Logs (~2/3 width) */}
      <div className="flex-[2] min-w-0 min-h-0 flex flex-col gap-4 overflow-hidden">
        {/* Video feed: flex-grow fills all available space */}
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden rounded-lg border border-[#242730] bg-[#1e2128]">
          <LiveViewTabs />
        </div>
        {/* System logs: fixed height, internal list scrolls with overflow-y-auto */}
        <div className="h-48 shrink-0 min-h-0 flex flex-col overflow-hidden rounded-lg border border-[#242730] bg-[#1e2128]">
          <SystemLogsPanel />
        </div>
      </div>

      {/* Right column: Controls & Chat (~1/3 width), full height within viewport */}
      <div className="flex-1 min-w-0 min-h-0 flex flex-col overflow-hidden">
        <ControlAndChatPanel />
      </div>
    </div>
  );
}

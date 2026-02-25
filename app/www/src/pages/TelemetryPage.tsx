import { CockpitLayout } from '@/components/cockpit';

export function TelemetryPage() {
  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-[#18181b] text-white px-4 pt-4 pb-6">
      <div className="flex-1 min-h-0 overflow-hidden min-w-0">
        <CockpitLayout />
      </div>
    </div>
  );
}

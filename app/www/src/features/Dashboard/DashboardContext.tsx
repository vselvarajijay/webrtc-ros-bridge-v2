import { createContext } from 'react';
import type { DashboardLayout, WidgetLayout } from './LayoutManager';

export interface DashboardContextValue {
  layout: DashboardLayout;
  updateWidget: (id: string, widgetLayout: WidgetLayout) => void;
  handleReset: () => void;
}

export const DashboardContext = createContext<DashboardContextValue | null>(null);

import { createContext } from 'react';
import type { DashboardLayout, WidgetLayout } from './LayoutManager';

export interface DashboardContextValue {
  layout: DashboardLayout;
  isEditing: boolean;
  updateWidget: (id: string, widgetLayout: WidgetLayout) => void;
  handleReset: () => void;
  enterEditMode: () => void;
  exitEditMode: () => void;
}

export const DashboardContext = createContext<DashboardContextValue | null>(null);

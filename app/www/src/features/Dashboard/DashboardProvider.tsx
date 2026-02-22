import { useCallback, useState, type ReactNode } from 'react';
import { loadLayout, saveLayout, resetLayout } from './LayoutManager';
import { DashboardContext } from './DashboardContext';
import type { DashboardLayout, WidgetLayout } from './LayoutManager';

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [layout, setLayout] = useState<DashboardLayout>(() => loadLayout());
  const [isEditing, setIsEditing] = useState(false);

  const updateWidget = useCallback((id: string, widgetLayout: WidgetLayout) => {
    setLayout((prev) => {
      const next: DashboardLayout = {
        ...prev,
        widgets: { ...prev.widgets, [id]: widgetLayout },
      };
      saveLayout(next);
      return next;
    });
  }, []);

  const handleReset = useCallback(() => {
    const defaults = resetLayout();
    setLayout(defaults);
  }, []);

  const enterEditMode = useCallback(() => setIsEditing(true), []);
  const exitEditMode = useCallback(() => setIsEditing(false), []);

  return (
    <DashboardContext.Provider value={{ layout, isEditing, updateWidget, handleReset, enterEditMode, exitEditMode }}>
      {children}
    </DashboardContext.Provider>
  );
}

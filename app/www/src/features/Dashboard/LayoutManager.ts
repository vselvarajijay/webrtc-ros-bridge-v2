import { WIDGET_REGISTRY, type WidgetConfig } from './widget-registry';

/** Persisted shape for a single widget in localStorage. */
export interface WidgetLayout {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Full layout state stored in localStorage. */
export interface DashboardLayout {
  schemaVersion: number;
  widgets: Record<string, WidgetLayout>;
}

const STORAGE_KEY = 'dashboard_layout_v1';
const SCHEMA_VERSION = 1;
const DEBOUNCE_MS = 300;

/** Derive the factory-default layout from the widget registry. */
export function getDefaultLayout(): DashboardLayout {
  const widgets: Record<string, WidgetLayout> = {};
  for (const cfg of WIDGET_REGISTRY) {
    widgets[cfg.id] = {
      x: cfg.defaultPosition.x,
      y: cfg.defaultPosition.y,
      width: cfg.defaultSize.width,
      height: cfg.defaultSize.height,
    };
  }
  return { schemaVersion: SCHEMA_VERSION, widgets };
}

/** Clamp widget dimensions to configured minimums. */
export function clampToMinimums(
  layout: DashboardLayout,
  registry: WidgetConfig[],
): DashboardLayout {
  const widgets = { ...layout.widgets };
  for (const cfg of registry) {
    const w = widgets[cfg.id];
    if (!w) continue;
    widgets[cfg.id] = {
      ...w,
      width: Math.max(w.width, cfg.minSize.width),
      height: Math.max(w.height, cfg.minSize.height),
    };
  }
  return { ...layout, widgets };
}

/**
 * Load the persisted layout from localStorage.
 * Falls back to factory default on missing or schema-mismatched data.
 */
export function loadLayout(): DashboardLayout {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return getDefaultLayout();
    const parsed: DashboardLayout = JSON.parse(raw);
    if (parsed.schemaVersion !== SCHEMA_VERSION) {
      // Stale schema — wipe and fall back to defaults
      localStorage.removeItem(STORAGE_KEY);
      return getDefaultLayout();
    }
    return clampToMinimums(parsed, WIDGET_REGISTRY);
  } catch {
    return getDefaultLayout();
  }
}

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

/** Persist layout to localStorage, debounced by 300ms. */
export function saveLayout(layout: DashboardLayout): void {
  if (debounceTimer !== null) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
    } catch {
      // Quota exceeded or private mode — ignore
    }
    debounceTimer = null;
  }, DEBOUNCE_MS);
}

/**
 * Reset to factory defaults: clear localStorage and return the default layout.
 * Cancels any pending debounced save.
 */
export function resetLayout(): DashboardLayout {
  if (debounceTimer !== null) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
  return getDefaultLayout();
}

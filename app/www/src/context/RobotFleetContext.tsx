import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import {
  listRobots,
  createRobot,
  updateRobot,
  deleteRobot,
  type RobotProfile,
  type RobotProfileCreate,
  type RobotProfileUpdate,
} from '@/api/robots';

interface RobotFleetContextValue {
  /** All configured robot profiles */
  robots: RobotProfile[];
  /** ID of the currently active robot (or null if none) */
  activeRobotId: string | null;
  /** Set the active robot by id */
  setActiveRobotId: (id: string | null) => void;
  /** The active robot profile (derived) */
  activeRobot: RobotProfile | null;
  /** Reload the robot list from the API */
  refreshRobots: () => Promise<void>;
  /** Add a new robot and return the created profile */
  addRobot: (profile: RobotProfileCreate) => Promise<RobotProfile>;
  /** Update an existing robot and return the updated profile */
  editRobot: (id: string, update: RobotProfileUpdate) => Promise<RobotProfile>;
  /** Delete a robot by id */
  removeRobot: (id: string) => Promise<void>;
  /** True while the initial robot list is being fetched */
  loading: boolean;
}

const RobotFleetContext = createContext<RobotFleetContextValue | null>(null);

export function RobotFleetProvider({ children }: { children: ReactNode }) {
  const [robots, setRobots] = useState<RobotProfile[]>([]);
  const [activeRobotId, setActiveRobotId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshRobots = useCallback(async () => {
    try {
      const data = await listRobots();
      setRobots(data);
      // If the previously active robot was deleted, clear it
      setActiveRobotId((prev) => {
        if (prev && !data.find((r) => r.id === prev)) return null;
        // Auto-select the first robot when we first load and nothing is active
        if (!prev && data.length > 0) return data[0].id;
        return prev;
      });
    } catch (err) {
      console.error('Failed to load robots:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshRobots();
  }, [refreshRobots]);

  const addRobot = useCallback(
    async (profile: RobotProfileCreate): Promise<RobotProfile> => {
      const created = await createRobot(profile);
      setRobots((prev) => [...prev, created]);
      // Auto-select the first robot added
      setActiveRobotId((prev) => prev ?? created.id);
      return created;
    },
    []
  );

  const editRobot = useCallback(
    async (id: string, update: RobotProfileUpdate): Promise<RobotProfile> => {
      const updated = await updateRobot(id, update);
      setRobots((prev) => prev.map((r) => (r.id === id ? updated : r)));
      return updated;
    },
    []
  );

  const removeRobot = useCallback(async (id: string): Promise<void> => {
    await deleteRobot(id);
    // Capture the next candidate active robot id while filtering the list
    let nextActiveId: string | null = null;
    setRobots((prev) => {
      const remaining = prev.filter((r) => r.id !== id);
      nextActiveId = remaining[0]?.id ?? null;
      return remaining;
    });
    setActiveRobotId((prev) => {
      if (prev !== id) return prev;
      return nextActiveId;
    });
  }, []);

  const activeRobot = robots.find((r) => r.id === activeRobotId) ?? null;

  const value: RobotFleetContextValue = {
    robots,
    activeRobotId,
    setActiveRobotId,
    activeRobot,
    refreshRobots,
    addRobot,
    editRobot,
    removeRobot,
    loading,
  };

  return (
    <RobotFleetContext.Provider value={value}>
      {children}
    </RobotFleetContext.Provider>
  );
}

export function useRobotFleet(): RobotFleetContextValue {
  const ctx = useContext(RobotFleetContext);
  if (!ctx) throw new Error('useRobotFleet must be used within RobotFleetProvider');
  return ctx;
}

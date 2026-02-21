import type { ReactNode } from 'react';
import { Burger, Button, Group } from '@mantine/core';

export interface AppHeaderProps {
  /** Left section (e.g. logo + title) */
  left?: ReactNode;
  /** Right section (e.g. nav links) */
  right?: ReactNode;
  /** Burger menu open state; when set, shows Burger for mobile */
  burgerOpened?: boolean;
  onBurgerClick?: () => void;
  /** Hide Burger above this breakpoint */
  burgerHiddenFrom?: string;
  /** Right panel (aside) open on mobile; when set with onAsideToggle, shows Drive panel toggle */
  asideOpened?: boolean;
  onAsideToggle?: () => void;
  /** Breakpoint below which the aside toggle is shown (e.g. 'md') */
  asideBreakpoint?: string;
}

export function AppHeader({
  left,
  right,
  burgerOpened = false,
  onBurgerClick,
  burgerHiddenFrom = 'sm',
  asideOpened = false,
  onAsideToggle,
  asideBreakpoint = 'md',
}: AppHeaderProps) {
  return (
    <Group justify="space-between" h="100%" px="md" wrap="nowrap">
      <Group wrap="nowrap" gap="sm">
        {onBurgerClick && (
          <Burger
            opened={burgerOpened}
            onClick={onBurgerClick}
            hiddenFrom={burgerHiddenFrom}
            size="sm"
            aria-label="Toggle navigation"
          />
        )}
        {left}
      </Group>
      <Group wrap="nowrap" gap="xs">
        {right}
        {onAsideToggle && (
          <Button
            variant={asideOpened ? 'light' : 'filled'}
            size="xs"
            onClick={onAsideToggle}
            hiddenFrom={asideBreakpoint}
            aria-label={asideOpened ? 'Close Drive panel' : 'Open Drive panel'}
          >
            {asideOpened ? 'Close' : 'Drive'}
          </Button>
        )}
      </Group>
    </Group>
  );
}

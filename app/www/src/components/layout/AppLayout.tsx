import type { ReactNode } from 'react';
import { AppShell, Box } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { AppHeader } from './AppHeader';

export interface AppLayoutProps {
  children: ReactNode;
  /** Optional header left content (e.g. logo, title) */
  headerLeft?: ReactNode;
  /** Optional header right content */
  headerRight?: ReactNode;
  /** Optional navbar content; when provided, enables mobile Burger toggle */
  navbar?: ReactNode;
  /** Optional right panel (aside) content, e.g. drive controls / autonomous */
  aside?: ReactNode;
  /** Main content padding */
  padding?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
}

export function AppLayout({
  children,
  headerLeft,
  headerRight,
  navbar,
  aside,
  padding = 'md',
}: AppLayoutProps) {
  const [opened, { toggle }] = useDisclosure(false);
  const [asideOpened, { toggle: toggleAside }] = useDisclosure(false);

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={
        navbar
          ? {
              width: 300,
              breakpoint: 'sm',
              collapsed: { mobile: !opened },
            }
          : undefined
      }
      aside={
        aside
          ? {
              width: 320,
              breakpoint: 'md',
              collapsed: { mobile: !asideOpened },
            }
          : undefined
      }
      padding={padding}
    >
      <AppShell.Header>
        <AppHeader
          left={headerLeft}
          right={headerRight}
          burgerOpened={opened}
          onBurgerClick={navbar ? toggle : undefined}
          burgerHiddenFrom="sm"
          asideOpened={asideOpened}
          onAsideToggle={aside ? toggleAside : undefined}
          asideBreakpoint="md"
        />
      </AppShell.Header>
      {navbar && <AppShell.Navbar p="md">{navbar}</AppShell.Navbar>}
      <AppShell.Main>{children}</AppShell.Main>
      {aside && (
        <AppShell.Aside p="md" style={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
          <Box style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            {aside}
          </Box>
        </AppShell.Aside>
      )}
    </AppShell>
  );
}

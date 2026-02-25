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
      styles={{
        root: {
          height: '100vh',
          maxHeight: '100vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        },
      }}
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
      padding={0}
    >
      <AppShell.Header style={{ backgroundColor: 'var(--mantine-color-dark-9)' }}>
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
      {navbar && <AppShell.Navbar p="md" style={{ backgroundColor: 'var(--mantine-color-dark-9)' }}>{navbar}</AppShell.Navbar>}
      <AppShell.Main
        p={padding}
        pt={60}
        style={{
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          flex: 1,
          overflow: 'hidden',
        }}
      >
        <Box style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>{children}</Box>
      </AppShell.Main>
      {aside && (
        <AppShell.Aside p="md" style={{ display: 'flex', flexDirection: 'column', minHeight: '100%', backgroundColor: 'var(--mantine-color-dark-9)' }}>
          <Box style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            {aside}
          </Box>
        </AppShell.Aside>
      )}
    </AppShell>
  );
}

import type { ReactNode } from 'react';
import { Box, Text, Title } from '@mantine/core';

export interface PageSectionProps {
  /** Section title (optional) */
  title?: ReactNode;
  /** Optional description or subtitle */
  description?: ReactNode;
  /** Section content */
  children: ReactNode;
  /** Root element class name */
  className?: string;
}

export function PageSection({
  title,
  description,
  children,
  className,
}: PageSectionProps) {
  return (
    <Box className={className}>
      {(title || description) && (
        <Box mb="md">
          {title && (
            <Title order={3} mb={description ? 'xs' : 0}>
              {title}
            </Title>
          )}
          {description && (
            <Text size="sm" c="dimmed">
              {description}
            </Text>
          )}
        </Box>
      )}
      {children}
    </Box>
  );
}

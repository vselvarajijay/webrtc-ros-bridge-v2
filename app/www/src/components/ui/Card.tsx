import type { CardProps as MantineCardProps } from '@mantine/core';
import { Card as MantineCard } from '@mantine/core';

export type CardProps = MantineCardProps;

export function Card({
  padding = 'md',
  withBorder = true,
  className,
  ...props
}: CardProps) {
  return (
    <MantineCard
      padding={padding}
      withBorder={withBorder}
      className={className}
      {...props}
    />
  );
}

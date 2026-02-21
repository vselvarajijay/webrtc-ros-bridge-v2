import type { ComponentPropsWithoutRef } from 'react';
import type { ButtonProps as MantineButtonProps } from '@mantine/core';
import { Button as MantineButton } from '@mantine/core';

export type ButtonProps = MantineButtonProps & ComponentPropsWithoutRef<'button'>;

export function Button({
  variant = 'filled',
  size = 'sm',
  className,
  ...props
}: ButtonProps) {
  return (
    <MantineButton
      variant={variant}
      size={size}
      className={className}
      {...props}
    />
  );
}

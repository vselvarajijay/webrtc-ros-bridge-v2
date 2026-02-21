import type { TextInputProps as MantineTextInputProps } from '@mantine/core';
import { TextInput as MantineTextInput } from '@mantine/core';

export type InputProps = MantineTextInputProps;

export function Input({
  size = 'sm',
  className,
  ...props
}: InputProps) {
  return (
    <MantineTextInput
      size={size}
      className={className}
      {...props}
    />
  );
}

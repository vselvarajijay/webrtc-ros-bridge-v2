import type { RefObject } from 'react';
import { Box, Text } from '@mantine/core';

export interface VideoFeedProps {
  /** Ref to attach to the video element */
  videoRef: RefObject<HTMLVideoElement | null>;
  /** Whether video stream is active (hides placeholder when true) */
  hasVideo?: boolean;
  /** Placeholder text when no stream */
  placeholder?: string;
  /** Optional class name for the container */
  className?: string;
}

export function VideoFeed({
  videoRef,
  hasVideo = false,
  placeholder = 'Waiting for robot stream…',
  className,
}: VideoFeedProps) {
  return (
    <Box
      className={className}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        minHeight: 0,
        backgroundColor: 'var(--mantine-color-dark-9)',
        borderRadius: 8,
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="w-full h-full object-contain"
        style={{ maxHeight: '100%' }}
      />
      {!hasVideo && (
        <Text
          size="sm"
          c="dimmed"
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {placeholder}
        </Text>
      )}
    </Box>
  );
}

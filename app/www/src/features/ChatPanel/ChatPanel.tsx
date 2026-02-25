import { useRef, useState } from 'react';
import { Box, Button, ScrollArea, Text, Textarea } from '@mantine/core';
import { useStream } from '@langchain/langgraph-sdk/react';

const PANEL_STYLE: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  flex: 1,
  minHeight: 0,
  height: '100%',
  width: '100%',
  backgroundColor: 'var(--mantine-color-dark-9)',
  border: '1px solid var(--mantine-color-dark-4)',
  borderRadius: 8,
  overflow: 'hidden',
};

/** Base URL for the LangGraph-style chat API (ConnectX proxy at /api/chat). */
function getChatApiUrl(): string {
  if (typeof window === 'undefined') return '';
  return `${window.location.origin}/api/chat`;
}

export function ChatPanel() {
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  const stream = useStream({
    apiUrl: getChatApiUrl(),
    assistantId: 'chat_agent',
    reconnectOnMount: true,
    onMetadataEvent: (meta) => {
      console.log('meta', meta);
    },
  });

  const send = () => {
    const text = input.trim();
    if (!text || stream.isLoading) return;
    setInput('');
    stream.submit({ messages: [{ type: 'human', content: text }] });
  };

  return (
    <Box style={PANEL_STYLE} className="min-h-0">
      <Box
        component="header"
        style={{ flexShrink: 0, borderBottom: '1px solid var(--mantine-color-dark-4)' }}
      >
        <Text size="sm" fw={600} p="xs">
          Chat (LangGraph)
        </Text>
      </Box>
      <ScrollArea
        viewportRef={scrollRef}
        style={{ flex: 1, minHeight: 0, overflow: 'auto' }}
        type="auto"
        styles={{
          root: { flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' },
          viewport: {
            '& > div': { display: 'block !important' },
            flex: 1,
            minHeight: 0,
          },
        }}
      >
        <Box p="xs" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {stream.messages.length === 0 && !stream.error && (
            <Text size="xs" c="dimmed">
              Send instructions to the robot agent. Ask for state, drive, or turn commands.
            </Text>
          )}
          {stream.messages.map((m, idx) => {
            if (m.type === 'ai') {
              const toolCalls = stream.getToolCalls(m);
              const meta = stream.getMessagesMetadata(m);
              const content = typeof m.content === 'string' ? m.content : '';
              return (
                <Box
                  key={m.id ?? idx}
                  style={{
                    alignSelf: 'flex-start',
                    maxWidth: '85%',
                    padding: '6px 10px',
                    borderRadius: 8,
                    backgroundColor: 'var(--mantine-color-dark-6)',
                  }}
                >
                  <Text size="xs" fw={500} c="gray.3">
                    Agent
                  </Text>
                  <Text size="sm" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {content || (stream.isLoading ? '…' : '')}
                  </Text>
                  {meta != null && Object.keys(meta).length > 0 && (
                    <Box mt="xs" style={{ borderTop: '1px solid var(--mantine-color-dark-4)', paddingTop: '6px' }}>
                      <Text size="xs" fw={600} c="gray.4" mb={4}>
                        Metadata
                      </Text>
                      <Text
                        component="pre"
                        size="xs"
                        c="gray.5"
                        style={{
                          fontFamily: 'ui-monospace, monospace',
                          fontSize: '0.7rem',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {JSON.stringify(meta, null, 2)}
                      </Text>
                    </Box>
                  )}
                  {toolCalls.length > 0 && (
                    <Box mt="xs" style={{ borderTop: '1px solid var(--mantine-color-dark-4)', paddingTop: '6px' }}>
                      <Text size="xs" fw={600} c="gray.4" mb={4}>
                        Tool calls
                      </Text>
                      {toolCalls.map((tc) => (
                        <Box
                          key={tc.id}
                          mb="xs"
                          p="xs"
                          style={{
                            backgroundColor: 'var(--mantine-color-dark-8)',
                            borderRadius: 4,
                            fontFamily: 'ui-monospace, monospace',
                            fontSize: '0.7rem',
                          }}
                        >
                          <Text size="xs" fw={600} c="gray.3" component="span">
                            {(tc as { name?: string }).name ?? (tc as { call?: { name?: string } }).call?.name ?? 'tool'}
                          </Text>
                          <Text
                            component="pre"
                            size="xs"
                            c="gray.5"
                            mt={4}
                            style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}
                          >
                            {JSON.stringify(tc, null, 2)}
                          </Text>
                        </Box>
                      ))}
                    </Box>
                  )}
                </Box>
              );
            }
            const content = typeof m.content === 'string' ? m.content : '';
            return (
              <Box
                key={m.id ?? idx}
                style={{
                  alignSelf: 'flex-end',
                  maxWidth: '85%',
                  padding: '6px 10px',
                  borderRadius: 8,
                  backgroundColor: 'var(--mantine-color-blue-9)',
                }}
              >
                <Text size="xs" fw={500} c="white">
                  You
                </Text>
                <Text size="sm" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {content}
                </Text>
              </Box>
            );
          })}
          {stream.error ? (
            <Text size="xs" c="red">
              {String(stream.error)}
            </Text>
          ) : null}
          {/* Global tool calls (optional debug) */}
          {stream.toolCalls != null && stream.toolCalls.length > 0 && (
            <Box mt="md" style={{ borderTop: '1px solid var(--mantine-color-dark-4)', paddingTop: '8px' }}>
              <Text size="xs" fw={600} c="gray.5" mb={4}>
                All tool calls (thread)
              </Text>
              <Text
                component="pre"
                size="xs"
                c="gray.5"
                style={{
                  fontFamily: 'ui-monospace, monospace',
                  fontSize: '0.7rem',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {JSON.stringify(stream.toolCalls, null, 2)}
              </Text>
            </Box>
          )}
        </Box>
      </ScrollArea>
      <Box
        p="xs"
        style={{
          flexShrink: 0,
          borderTop: '1px solid var(--mantine-color-dark-4)',
          display: 'flex',
          gap: '0.5rem',
          alignItems: 'flex-end',
        }}
      >
        <Textarea
          placeholder="Type a message…"
          value={input}
          onChange={(e) => setInput(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          minRows={1}
          maxRows={3}
          disabled={stream.isLoading}
          style={{ flex: 1 }}
          autosize
        />
        <Button onClick={send} disabled={stream.isLoading || !input.trim()} size="sm">
          {stream.isLoading ? '…' : 'Send'}
        </Button>
      </Box>
    </Box>
  );
}

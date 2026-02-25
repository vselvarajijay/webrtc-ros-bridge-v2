/**
 * Chat API: create threads and stream runs against the LangGraph chat agent (proxied via ConnectX app).
 */

export interface ToolCallDisplay {
  name: string;
  input: unknown;
  output: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCallDisplay[];
}

const ASSISTANT_ID = 'chat_agent';

export async function createThread(): Promise<{ thread_id: string }> {
  const res = await fetch('/api/chat/threads', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Failed to create chat thread');
  }
  const data = (await res.json()) as { thread_id?: string };
  const thread_id = data?.thread_id ?? (data as Record<string, unknown>)?.['thread_id'];
  if (!thread_id || typeof thread_id !== 'string') {
    throw new Error('Invalid thread response: missing thread_id');
  }
  return { thread_id };
}

/**
 * Convert UI messages to LangChain-style messages for the ReAct agent.
 * ReAct agent expects input.messages: HumanMessage / AIMessage style.
 */
function toLangGraphMessages(messages: ChatMessage[]): Array<{ type: string; content: string }> {
  return messages.map((m) => ({
    type: m.role === 'user' ? 'human' : 'ai',
    content: m.content,
  }));
}

/**
 * Start a streamed run and return the response body as a ReadableStream.
 * Caller should read the stream (e.g. NDJSON) and update UI.
 */
export async function streamRun(
  threadId: string,
  messages: ChatMessage[]
): Promise<Response> {
  const body = {
    assistant_id: ASSISTANT_ID,
    input: { messages: toLangGraphMessages(messages) },
    stream_mode: 'values',
  };
  const res = await fetch(`/api/chat/threads/${encodeURIComponent(threadId)}/runs/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Chat request failed');
  }
  return res;
}

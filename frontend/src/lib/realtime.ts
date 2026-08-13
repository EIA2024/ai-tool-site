import type {
  RealtimeConnection,
  RealtimeServerEvent,
  RealtimeStatus,
} from "../types";

/**
 * WebSocket URL for a realtime operation, under the unified
 * `/ws/tools/{toolId}/operations/{operationId}` path.
 */
export function realtimeUrl(toolId: string, operation: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/tools/${toolId}/operations/${operation}`;
}

let requestCounter = 0;

/** A short, collision-resistant request id for one invoke frame. */
export function nextRequestId(): string {
  requestCounter += 1;
  return `req-${requestCounter}-${Date.now().toString(36)}`;
}

/**
 * A thin WebSocket wrapper implementing the Host realtime frame protocol.
 *
 * The client sends `{type:"invoke", request_id, payload}` and the server
 * answers `ready | progress | delta | result | error`. Custom plugins never
 * construct this themselves — `ToolClient.connect` hands them a bound one.
 */
export class RealtimeClient implements RealtimeConnection {
  private ws: WebSocket | null = null;
  private eventHandler: ((event: RealtimeServerEvent) => void) | null = null;
  private statusHandler: ((status: RealtimeStatus) => void) | null = null;

  readonly url: string;
  readonly toolId: string;
  readonly operation: string;

  constructor(toolId: string, operation: string) {
    this.toolId = toolId;
    this.operation = operation;
    this.url = realtimeUrl(toolId, operation);
  }

  get isOpen(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  onEvent(handler: (event: RealtimeServerEvent) => void): void {
    this.eventHandler = handler;
  }

  onStatus(handler: (status: RealtimeStatus) => void): void {
    this.statusHandler = handler;
  }

  open(): void {
    this.close();
    const ws = new WebSocket(this.url);
    this.ws = ws;
    ws.onopen = () => this.statusHandler?.("connected");
    ws.onclose = () => this.statusHandler?.("disconnected");
    ws.onerror = () => this.statusHandler?.("error");
    ws.onmessage = (event) => {
      try {
        this.eventHandler?.(JSON.parse(event.data) as RealtimeServerEvent);
      } catch {
        // Ignore malformed frames — the server owns the protocol.
      }
    };
  }

  send(payload: Record<string, unknown>): string {
    const requestId = nextRequestId();
    if (this.isOpen) {
      this.ws?.send(JSON.stringify({ type: "invoke", request_id: requestId, payload }));
    }
    return requestId;
  }

  close(): void {
    if (this.ws) {
      const ws = this.ws;
      this.ws = null;
      // Detach onclose so an intentional close never schedules a reconnect.
      ws.onclose = null;
      ws.close();
    }
  }
}

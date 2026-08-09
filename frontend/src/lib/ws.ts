import type { WsMessage } from "../types";

type MessageHandler = (msg: WsMessage) => void;
type StatusHandler = (status: string) => void;

const BASE_DELAY_MS = 1_000;
const MAX_DELAY_MS = 30_000;

function wsUrl(sessionId?: string | null): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  return `${protocol}//${window.location.host}/ws/chat${query}`;
}

export class WsClient {
  private ws: WebSocket | null = null;
  private onMessage: MessageHandler;
  private onStatus: StatusHandler;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;
  private attempt = 0;
  private sessionId: string | null = null;

  constructor(onMessage: MessageHandler, onStatus: StatusHandler) {
    this.onMessage = onMessage;
    this.onStatus = onStatus;
  }

  connect(sessionId?: string | null) {
    const prev = this.ws;
    if (prev) {
      // Detach the handler before closing: this is an intentional switch, so
      // the old socket's onclose must not schedule a spurious reconnect that
      // would close the fresh socket and loop forever.
      prev.onclose = null;
      prev.close();
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.sessionId = sessionId ?? null;
    this.shouldReconnect = true;
    this.attempt = 0;
    this.ws = new WebSocket(wsUrl(this.sessionId));

    this.ws.onopen = () => {
      this.attempt = 0; // healthy again — reset backoff
      this.onStatus("connected");
    };
    this.ws.onclose = () => {
      this.onStatus("disconnected");
      this.scheduleReconnect();
    };
    this.ws.onerror = () => {
      this.onStatus("error");
    };
    this.ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        this.onMessage(msg);
      } catch {
        console.warn("Failed to parse WS message", event.data);
      }
    };
  }

  send(content: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "message", content }));
    }
  }

  disconnect() {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }

  private scheduleReconnect() {
    if (!this.shouldReconnect) return;
    const delay = Math.min(BASE_DELAY_MS * 2 ** this.attempt, MAX_DELAY_MS);
    this.attempt += 1;
    this.onStatus(`reconnecting (${Math.round(delay / 1000)}s)`);
    this.reconnectTimer = setTimeout(() => {
      this.connect(this.sessionId);
    }, delay);
  }
}

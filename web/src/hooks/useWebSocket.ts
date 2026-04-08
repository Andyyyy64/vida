import { useEffect, useRef, useCallback, useState } from 'react';

export interface WSEvent {
  type: string;
  [key: string]: unknown;
}

type EventHandler = (event: WSEvent) => void;

interface UseWebSocketOptions {
  /** WebSocket server URL. Default: ws://127.0.0.1:3004 */
  url?: string;
  /** Auto-reconnect on disconnect. Default: true */
  autoReconnect?: boolean;
  /** Reconnect interval in ms. Default: 3000 */
  reconnectInterval?: number;
  /** Event handler called for every incoming message */
  onEvent?: EventHandler;
}

interface UseWebSocketReturn {
  connected: boolean;
  clientCount: number;
  lastEvent: WSEvent | null;
  send: (data: object) => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    url = 'ws://127.0.0.1:3004',
    autoReconnect = true,
    reconnectInterval = 3000,
    onEvent,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const [connected, setConnected] = useState(false);
  const [clientCount, setClientCount] = useState(0);
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as WSEvent;
          setLastEvent(data);

          if (data.type === 'connected') {
            setClientCount(data.clients as number);
          }

          onEventRef.current?.(data);
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (autoReconnect) {
          reconnectTimer.current = setTimeout(connect, reconnectInterval);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      if (autoReconnect) {
        reconnectTimer.current = setTimeout(connect, reconnectInterval);
      }
    }
  }, [url, autoReconnect, reconnectInterval]);

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on intentional close
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { connected, clientCount, lastEvent, send };
}

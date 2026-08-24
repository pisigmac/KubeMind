"use client";

import { useEffect, useRef, useState, useCallback } from "react";

interface SpanEvent {
  type: "span" | "heartbeat";
  data?: any;
  timestamp?: string;
}

export function useSentinelStream(workspaceId = "default") {
  const [connected, setConnected] = useState(false);
  const [spans, setSpans] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_SENTINEL_WS || "ws://localhost:9083/v1/stream";
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      ws.send(JSON.stringify({ type: "subscribe", workspace_id: workspaceId }));
    };

    ws.onmessage = (event) => {
      try {
        const msg: SpanEvent = JSON.parse(event.data);
        if (msg.type === "span" && msg.data) {
          setSpans((prev) => [msg.data, ...prev].slice(0, 100));
        }
      } catch {
        // ignore malformed
      }
    };

    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    return () => ws.close();
  }, [workspaceId]);

  const sendPing = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "ping" }));
  }, []);

  return { connected, spans, sendPing };
}

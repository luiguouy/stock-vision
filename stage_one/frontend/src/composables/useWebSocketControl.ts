// useWebSocketControl.ts
// Antigravity MCP / CLI 双向 WebSocket 控制管道
import { ref, onMounted, onUnmounted } from 'vue';

export interface WSControlMessage {
  action:
    | 'open'
    | 'add_markers'
    | 'draw_lines'
    | 'draw_boxes'
    | 'draw_channel_lines'
    | 'draw_wave_lines'
    | 'clear'
    | 'run_strategy'
    | 'capture_chart'
    | 'refresh_watchlist'
    | 'ping';
  symbol?: string;
  period?: string;
  mode?: string;
  markers?: any[];
  lines?: any[];
  boxes?: any[];
  channel_lines?: any[];
  wave_lines?: any;
  kind?: string;
  request_id?: string;
}

export function useWebSocketControl(handlers: {
  onOpenChart?: (symbol: string, period?: string) => void;
  onAddMarkers?: (markers: any[], symbol?: string) => void;
  onDrawLines?: (lines: any[], symbol?: string) => void;
  onDrawBoxes?: (boxes: any[], symbol?: string) => void;
  onDrawChannelLines?: (channelLines: any[], symbol?: string) => void;
  onDrawWaveLines?: (waveLines: any, symbol?: string) => void;
  onClearAnnotations?: (kind?: string, symbol?: string) => void;
  onRunStrategy?: (mode?: string, symbol?: string) => void;
  onCaptureChart?: (requestId?: string) => Promise<string | null> | (string | null);
  onRefreshWatchlist?: () => void;
}) {
  const isConnected = ref(false);
  let ws: WebSocket | null = null;
  let reconnectTimer: any = null;
  let isClosedManually = false;

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || '127.0.0.1:8000';
    const url = `${protocol}//${host}/ws/control`;

    try {
      ws = new WebSocket(url);

      ws.onopen = () => {
        isConnected.value = true;
        // 注册控制客户端
        ws?.send(JSON.stringify({ type: 'register', role: 'frontend' }));
      };

      ws.onmessage = async (evt) => {
        try {
          const msg: WSControlMessage = JSON.parse(evt.data);
          if (msg.action === 'ping') {
            ws?.send(JSON.stringify({ type: 'pong' }));
            return;
          }
          if (msg.action === 'open' && msg.symbol && handlers.onOpenChart) {
            handlers.onOpenChart(msg.symbol, msg.period);
          } else if (msg.action === 'add_markers' && msg.markers && handlers.onAddMarkers) {
            handlers.onAddMarkers(msg.markers, msg.symbol);
          } else if (msg.action === 'draw_lines' && msg.lines && handlers.onDrawLines) {
            handlers.onDrawLines(msg.lines, msg.symbol);
          } else if (msg.action === 'draw_boxes' && msg.boxes && handlers.onDrawBoxes) {
            handlers.onDrawBoxes(msg.boxes, msg.symbol);
          } else if (msg.action === 'draw_channel_lines' && msg.channel_lines && handlers.onDrawChannelLines) {
            handlers.onDrawChannelLines(msg.channel_lines, msg.symbol);
          } else if (msg.action === 'draw_wave_lines' && msg.wave_lines && handlers.onDrawWaveLines) {
            handlers.onDrawWaveLines(msg.wave_lines, msg.symbol);
          } else if (msg.action === 'clear' && handlers.onClearAnnotations) {
            handlers.onClearAnnotations(msg.kind, msg.symbol);
          } else if (msg.action === 'run_strategy' && handlers.onRunStrategy) {
            handlers.onRunStrategy(msg.mode, msg.symbol);
          } else if (msg.action === 'capture_chart' && handlers.onCaptureChart) {
            const dataUrl = await handlers.onCaptureChart(msg.request_id);
            if (dataUrl) {
              ws?.send(
                JSON.stringify({
                  type: 'capture_result',
                  request_id: msg.request_id,
                  image_base64: dataUrl,
                })
              );
            }
          } else if (msg.action === 'refresh_watchlist' && handlers.onRefreshWatchlist) {
            handlers.onRefreshWatchlist();
          }
        } catch (e) {
          console.warn('WS message parse error:', e);
        }
      };

      ws.onclose = () => {
        isConnected.value = false;
        if (!isClosedManually) {
          reconnectTimer = setTimeout(connect, 2000);
        }
      };

      ws.onerror = () => {
        ws?.close();
      };
    } catch (e) {
      if (!isClosedManually) {
        reconnectTimer = setTimeout(connect, 3000);
      }
    }
  }

  function sendState(state: { symbol: string; period: string; current_price?: number }) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'client_state_update', ...state }));
    }
  }

  onMounted(() => {
    isClosedManually = false;
    connect();
  });

  onUnmounted(() => {
    isClosedManually = true;
    clearTimeout(reconnectTimer);
    if (ws) ws.close();
  });

  return {
    isConnected,
    sendState,
  };
}

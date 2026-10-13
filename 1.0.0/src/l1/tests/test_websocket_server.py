"""
L1 WebSocketAdapter Real Test - WebSocket Server
使用 WebSocket 客户端(浏览器/Postman)连接测试

运行: python src/l1/tests/test_websocket_server.py
测试: 用浏览器访问 http://localhost:8080 或 Postman 连接 ws://localhost:8765
"""
import sys
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import websockets
import json
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

from src.l1.l1_user_interaction import WebSocketAdapter

# L1 WebSocket Adapter
adapter = WebSocketAdapter()

# 存储所有连接的客户端
connected_clients = set()


async def handle_client(websocket):
    """处理 WebSocket 客户端连接"""
    client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    connected_clients.add(websocket)

    print(f"\n[+] Client connected: {client_id}")
    print(f"    Total clients: {len(connected_clients)}")

    try:
        async for message in websocket:
            print(f"\n{'='*70}")
            print(f"Received from {client_id}:")
            print(f"{'='*70}")

            try:
                # 解析收到的 JSON
                raw_data = json.loads(message)
                print(f"Raw JSON: {json.dumps(raw_data, indent=2, ensure_ascii=False)}")

                # 检查是否能处理
                if adapter.can_handle(raw_data):
                    print(f"\n[Adapter] can_handle() = True")

                    # 使用 L1 解析
                    event = adapter.parse(raw_data)

                    print(f"\n[L1 Output] StandardEvent:")
                    print(f"  channel: {event.channel}")
                    print(f"  user_id: {event.user_id}")
                    print(f"  content: {event.content}")
                    print(f"  timestamp: {event.timestamp}")
                    print(f"  metadata: {event.metadata}")

                    # 发送成功响应给客户端
                    response = {
                        "status": "success",
                        "message": "L1 parse successful",
                        "standard_event": {
                            "channel": event.channel,
                            "user_id": event.user_id,
                            "content": event.content,
                            "timestamp": event.timestamp,
                            "metadata": event.metadata
                        }
                    }
                else:
                    print(f"\n[Adapter] can_handle() = False")
                    print("  Reason: Missing 'type' or 'user_id' field")

                    response = {
                        "status": "error",
                        "message": "Invalid format. Required fields: 'type', 'user_id'"
                    }

            except json.JSONDecodeError as e:
                print(f"[Error] Invalid JSON: {e}")
                response = {
                    "status": "error",
                    "message": f"Invalid JSON: {str(e)}"
                }
            except Exception as e:
                print(f"[Error] Parse failed: {type(e).__name__}: {e}")
                response = {
                    "status": "error",
                    "message": f"Parse error: {str(e)}"
                }

            # 发送响应
            await websocket.send(json.dumps(response, indent=2, ensure_ascii=False))
            print(f"\n[Response sent to client]")

    except websockets.exceptions.ConnectionClosed:
        print(f"\n[-] Client disconnected: {client_id}")
    finally:
        connected_clients.remove(websocket)
        print(f"    Total clients: {len(connected_clients)}")


async def main():
    print("""
+-----------------------------------------------------------------------+
|     L1 WebSocketAdapter Real Test - WebSocket Server                  |
+-----------------------------------------------------------------------+

Server starting...

Connect via WebSocket: ws://localhost:8765
Or open browser: http://localhost:8080 (simple test page)

Test message format:
{
    "type": "message",
    "user_id": "test_user_123",
    "content": "Hello from WebSocket client",
    "timestamp": 1704067200
}

Press Ctrl+C to stop
""")

    # 启动 WebSocket 服务器
    ws_server = await websockets.serve(handle_client, "localhost", 8765)
    print("[OK] WebSocket server started on ws://localhost:8765")

    # 启动简单的 HTTP 服务器(用于提供测试页面)
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    import threading

    class TestPageHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(TEST_HTML_PAGE.encode('utf-8'))
            else:
                self.send_error(404)

        def log_message(self, format, *args):
            pass  # 禁用 HTTP 日志

    http_server = HTTPServer(('localhost', 8080), TestPageHandler)
    http_thread = threading.Thread(target=http_server.serve_forever)
    http_thread.daemon = True
    http_thread.start()
    print("[OK] HTTP test page at http://localhost:8080")

    print("\nWaiting for connections...\n")

    await asyncio.Future()  # 永久运行


# 简单的 HTML 测试页面
TEST_HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>L1 WebSocket Test</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
        h1 { color: #333; }
        .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
        .connected { background: #d4edda; color: #155724; }
        .disconnected { background: #f8d7da; color: #721c24; }
        input, textarea, button { width: 100%; padding: 10px; margin: 5px 0; box-sizing: border-box; }
        button { background: #007bff; color: white; border: none; cursor: pointer; }
        button:hover { background: #0056b3; }
        button:disabled { background: #ccc; }
        #output { background: #f8f9fa; padding: 15px; border-radius: 5px; min-height: 200px; white-space: pre-wrap; font-family: monospace; }
        .example { background: #e9ecef; padding: 10px; border-radius: 5px; margin: 10px 0; }
    </style>
</head>
<body>
    <h1>L1 WebSocket Adapter Test</h1>

    <div id="connectionStatus" class="status disconnected">Disconnected</div>

    <div>
        <input type="text" id="wsUrl" value="ws://localhost:8765" placeholder="WebSocket URL">
        <button id="connectBtn" onclick="connect()">Connect</button>
        <button id="disconnectBtn" onclick="disconnect()" disabled>Disconnect</button>
    </div>

    <div class="example">
        <strong>Example message format:</strong>
        <pre>{
    "type": "message",
    "user_id": "test_user_123",
    "content": "Hello from WebSocket client",
    "timestamp": 1704067200
}</pre>
    </div>

    <div>
        <textarea id="messageInput" rows="6" placeholder="Enter JSON message here...">{
    "type": "message",
    "user_id": "browser_user",
    "content": "Hello from browser!",
    "timestamp": 1704067200
}</textarea>
        <button id="sendBtn" onclick="sendMessage()" disabled>Send Message</button>
    </div>

    <h3>Output:</h3>
    <div id="output">Waiting for connection...</div>

    <script>
        let ws = null;
        const statusDiv = document.getElementById('connectionStatus');
        const outputDiv = document.getElementById('output');
        const connectBtn = document.getElementById('connectBtn');
        const disconnectBtn = document.getElementById('disconnectBtn');
        const sendBtn = document.getElementById('sendBtn');

        function log(msg) {
            outputDiv.textContent += msg + '\\n';
            outputDiv.scrollTop = outputDiv.scrollHeight;
        }

        function connect() {
            const url = document.getElementById('wsUrl').value;
            log('Connecting to ' + url + '...');

            ws = new WebSocket(url);

            ws.onopen = () => {
                statusDiv.textContent = 'Connected';
                statusDiv.className = 'status connected';
                connectBtn.disabled = true;
                disconnectBtn.disabled = false;
                sendBtn.disabled = false;
                log('Connected successfully!');
            };

            ws.onmessage = (event) => {
                log('\\n[Received]\\n' + event.data);
            };

            ws.onclose = () => {
                statusDiv.textContent = 'Disconnected';
                statusDiv.className = 'status disconnected';
                connectBtn.disabled = false;
                disconnectBtn.disabled = true;
                sendBtn.disabled = true;
                log('Connection closed.');
            };

            ws.onerror = (error) => {
                log('Error: ' + error);
            };
        }

        function disconnect() {
            if (ws) {
                ws.close();
            }
        }

        function sendMessage() {
            if (!ws || ws.readyState !== WebSocket.OPEN) {
                log('Not connected!');
                return;
            }

            const input = document.getElementById('messageInput').value;
            try {
                // Validate JSON
                JSON.parse(input);
                ws.send(input);
                log('\\n[Sent]\\n' + input);
            } catch (e) {
                log('Invalid JSON: ' + e.message);
            }
        }

        // Auto-connect on page load
        window.onload = connect;
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nServer stopped.")

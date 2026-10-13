"""
L1 HttpWebhookAdapter Real Test - HTTP Webhook Server
使用 curl 或 Postman 发送 POST 请求测试

运行: python src/l1/tests/test_webhook_server.py
测试: curl -X POST http://localhost:8000/webhook -H "Content-Type: application/json" -d '{...}'
"""
import sys
from pathlib import Path

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn
import json

from src.l1.l1_user_interaction import HttpWebhookAdapter

# L1 Webhook Adapter
adapter = HttpWebhookAdapter()

app = FastAPI(title="L1 Webhook Test Server")


@app.post("/webhook")
async def receive_webhook(request: Request):
    """接收 Webhook POST 请求"""
    print(f"\n{'='*70}")
    print("Received Webhook Request")
    print(f"{'='*70}")

    # 获取原始数据
    try:
        raw_data = await request.json()
    except:
        raw_data = {}

    print(f"Method: {request.method}")
    print(f"URL: {request.url}")
    print(f"Headers: {dict(request.headers)}")
    print(f"\nBody:")
    print(json.dumps(raw_data, indent=2, ensure_ascii=False))

    # 检查是否能处理
    if adapter.can_handle(raw_data):
        print(f"\n[Adapter] can_handle() = True")

        try:
            # 使用 L1 解析
            event = adapter.parse(raw_data)

            print(f"\n[L1 Output] StandardEvent:")
            print(f"  channel: {event.channel}")
            print(f"  user_id: {event.user_id}")
            print(f"  content: {event.content}")
            print(f"  timestamp: {event.timestamp}")
            print(f"  metadata: {event.metadata}")

            return JSONResponse({
                "status": "success",
                "message": "L1 parse successful",
                "standard_event": {
                    "channel": event.channel,
                    "user_id": event.user_id,
                    "content": event.content,
                    "timestamp": event.timestamp,
                    "metadata": event.metadata
                }
            })

        except Exception as e:
            print(f"\n[Error] Parse failed: {type(e).__name__}: {e}")
            return JSONResponse({
                "status": "error",
                "message": f"Parse error: {str(e)}"
            }, status_code=400)
    else:
        print(f"\n[Adapter] can_handle() = False")
        print("  Reason: Missing required fields")
        print("  Expected: {event, payload} OR {user_id, content/body, headers/webhook_type}")

        return JSONResponse({
            "status": "error",
            "message": "Invalid webhook format",
            "expected_formats": [
                "{event: '...', payload: {user_id: '...', message: '...'}}",
                "{user_id: '...', content: '...', headers: {...}}",
                "{user_id: '...', body: '...', webhook_type: '...'}"
            ]
        }, status_code=400)


@app.get("/")
async def root():
    """提供测试页面"""
    return HTMLResponse(content=WEBHOOK_TEST_PAGE)


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "running", "service": "L1 Webhook Test"}


# 简单的 HTML 测试页面 - 使用原始字符串避免转义问题
WEBHOOK_TEST_PAGE = r"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>L1 Webhook Test</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 900px; margin: 30px auto; padding: 20px; }
        h1 { color: #333; }
        .section { background: #f8f9fa; padding: 15px; margin: 15px 0; border-radius: 5px; }
        h3 { margin-top: 0; }
        pre { background: #e9ecef; padding: 10px; border-radius: 5px; overflow-x: auto; }
        button { background: #28a745; color: white; border: none; padding: 10px 20px; cursor: pointer; margin: 5px; }
        button:hover { background: #218838; }
        input, textarea { width: 100%; padding: 10px; margin: 5px 0; box-sizing: border-box; }
        #output { background: #f8f9fa; padding: 15px; border-radius: 5px; min-height: 150px; white-space: pre-wrap; font-family: monospace; }
        .format-btn { background: #007bff; }
        .format-btn:hover { background: #0056b3; }
    </style>
</head>
<body>
    <h1>L1 HttpWebhookAdapter Test</h1>

    <div class="section">
        <h3>Supported Formats</h3>
        <p><strong>Format 1: Event/Payload (通用Webhook格式)</strong></p>
        <pre id="format1">{
  "event": "user_message",
  "payload": {
    "user_id": "webhook_user_1",
    "message": "Hello from webhook",
    "timestamp": 1704067200
  }
}</pre>
        <button class="format-btn" onclick="loadFormat('format1')">Load Format 1</button>

        <p><strong>Format 2: Simple Format (直接字段)</strong></p>
        <pre id="format2">{
  "user_id": "webhook_user_2",
  "content": "Simple webhook message",
  "timestamp": 1704067200,
  "headers": {
    "Content-Type": "application/json",
    "X-Signature": "sha256=abc123"
  },
  "webhook_type": "incoming_message"
}</pre>
        <button class="format-btn" onclick="loadFormat('format2')">Load Format 2</button>

        <p><strong>Format 3: Body Field (替代content)</strong></p>
        <pre id="format3">{
  "user_id": "webhook_user_3",
  "body": "Message in body field",
  "headers": {}
}</pre>
        <button class="format-btn" onclick="loadFormat('format3')">Load Format 3</button>
    </div>

    <div class="section">
        <h3>Send Test Request</h3>
        <textarea id="requestBody" rows="10" placeholder="Enter JSON payload here..."></textarea>
        <button onclick="sendRequest()">Send POST to /webhook</button>
    </div>

    <div class="section">
        <h3>Response:</h3>
        <div id="output">Waiting for request...</div>
    </div>

    <div class="section">
        <h3>Test with curl</h3>
        <pre>curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "payload": {
      "user_id": "test_user",
      "message": "Hello from curl"
    }
  }'</pre>
    </div>

    <script>
        function loadFormat(formatId) {
            const content = document.getElementById(formatId).textContent;
            document.getElementById('requestBody').value = content;
        }

        async function sendRequest() {
            const body = document.getElementById('requestBody').value;
            const output = document.getElementById('output');

            try {
                JSON.parse(body);
            } catch (e) {
                output.textContent = 'Invalid JSON: ' + e.message;
                return;
            }

            output.textContent = 'Sending request...';

            try {
                const response = await fetch('/webhook', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: body
                });

                const data = await response.json();
                output.textContent = 'Status: ' + response.status + String.fromCharCode(10, 10) + JSON.stringify(data, null, 2);
            } catch (error) {
                output.textContent = 'Error: ' + error.message;
            }
        }
    </script>
</body>
</html>"""


def main():
    print("""
+-----------------------------------------------------------------------+
|     L1 HttpWebhookAdapter Real Test - HTTP Server                     |
+-----------------------------------------------------------------------+

Server starting on http://localhost:8000

Test URLs:
- Browser UI: http://localhost:8000/
- Webhook endpoint: POST http://localhost:8000/webhook
- Health check: GET http://localhost:8000/health

Test with curl:
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"event": "message", "payload": {"user_id": "test", "message": "Hello"}}'

Supported Formats:
1. Event/Payload: {"event": "...", "payload": {"user_id": "...", "message": "..."}}
2. Simple: {"user_id": "...", "content": "...", "headers": {...}}
3. Body field: {"user_id": "...", "body": "...", ...}

Press Ctrl+C to stop
""")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

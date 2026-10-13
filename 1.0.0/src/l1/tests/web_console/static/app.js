/**
 * VClaw Web Test Console - Frontend Logic
 */

// Navigation
const navItems = document.querySelectorAll('.nav-menu li');
const panels = document.querySelectorAll('.panel');
const pageTitle = document.getElementById('page-title');

const titles = {
  dashboard: '总览 Dashboard',
  l1: 'L1 用户交互层测试',
  l2: 'L2 控制网关层测试',
  l3: 'L3 逻辑编排层测试',
  l4: 'L4 记忆知识层测试',
  l5: 'L5 工具能力层测试',
  l6: 'L6 环境执行层测试',
  e2e: 'E2E 端到端对话测试'
};

navItems.forEach(item => {
  item.addEventListener('click', () => {
    const panel = item.dataset.panel;
    navItems.forEach(n => n.classList.remove('active'));
    item.classList.add('active');
    panels.forEach(p => p.classList.remove('active'));
    document.getElementById(`panel-${panel}`).classList.add('active');
    pageTitle.textContent = titles[panel];
  });
});

function scrollToE2E() {
  const e2eNav = document.querySelector('[data-panel="e2e"]');
  if (e2eNav) e2eNav.click();
}

// Helpers
function setResult(id, data, isError = false) {
  const el = document.getElementById(id);
  el.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  el.className = 'result-box ' + (isError ? 'error' : 'success');
}

async function postJson(url, payload) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = { status: res.status, detail: text };
  }
  if (!res.ok) {
    const err = data.detail || JSON.stringify(data);
    throw new Error(`HTTP ${res.status}: ${err}`);
  }
  return data;
}

// Status
async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    const data = await res.json();

    const llmOk = data.llm_available;
    const dockerOk = data.docker_available;

    document.getElementById('llm-status-dot').className = 'status-dot ' + (llmOk ? 'ok' : 'error');
    document.getElementById('llm-status-text').textContent = llmOk ? '可用' : '不可用';
    document.getElementById('docker-status-dot').className = 'status-dot ' + (dockerOk ? 'ok' : 'error');
    document.getElementById('docker-status-text').textContent = dockerOk ? '可用' : '不可用';

    document.getElementById('card-llm').className = 'status-card ' + (llmOk ? 'ok' : 'error');
    document.getElementById('card-llm-value').textContent = llmOk ? '可用' : '不可用';
    document.getElementById('card-docker').className = 'status-card ' + (dockerOk ? 'ok' : 'error');
    document.getElementById('card-docker-value').textContent = dockerOk ? '可用' : '不可用';
    document.getElementById('card-api-value').textContent = data.api_base_url || '-';
    document.getElementById('card-model-value').textContent = data.test_llm_model || '-';

    const toolsList = document.getElementById('tools-list');
    if (data.tools && data.tools.length) {
      toolsList.innerHTML = data.tools.map(t => `<span class="preset-tag">${t}</span>`).join('');
    } else {
      toolsList.innerHTML = '<span class="preset-tag">无可用工具</span>';
    }
  } catch (e) {
    console.error(e);
    alert('加载配置失败: ' + e.message);
  }
}

// L1 helpers
function setL1Channel(ch) {
  document.getElementById('l1-channel').value = ch;
  const presets = {
    telegram: '{"update_id": 1, "message": {"chat": {"id": 1}, "text": "hello"}}',
    webhook: '{"user_id": "u1", "message": {"text": "hello"}}',
    websocket: '{"event": "message", "payload": {"user_id": "u1", "message": "hello"}}'
  };
  if (presets[ch]) document.getElementById('l1-raw').value = presets[ch];
}

async function runL1Adapter() {
  const channel = document.getElementById('l1-channel').value;
  let raw;
  try { raw = JSON.parse(document.getElementById('l1-raw').value); }
  catch (e) { setResult('l1-adapter-result', 'JSON 解析错误: ' + e.message, true); return; }
  try {
    const data = await postJson('/api/l1/test_adapter', { channel, raw_data: raw });
    setResult('l1-adapter-result', data);
  } catch (e) { setResult('l1-adapter-result', e.message, true); }
}

async function runL1Validator() {
  let eventDict;
  try { eventDict = JSON.parse(document.getElementById('l1-event').value); }
  catch (e) { setResult('l1-validator-result', 'JSON 解析错误: ' + e.message, true); return; }
  try {
    const data = await postJson('/api/l1/test_validator', { event_dict: eventDict });
    setResult('l1-validator-result', data);
  } catch (e) { setResult('l1-validator-result', e.message, true); }
}

// L2
async function runL2RateLimit() {
  try {
    const data = await postJson('/api/l2/test_rate_limit', {
      user_id: document.getElementById('l2-user').value,
      ip: document.getElementById('l2-ip').value
    });
    setResult('l2-rate-result', data);
  } catch (e) { setResult('l2-rate-result', e.message, true); }
}

async function runL2Session() {
  try {
    const data = await postJson('/api/l2/test_session', {
      user_id: document.getElementById('l2-session-user').value,
      content: document.getElementById('l2-session-content').value
    });
    setResult('l2-session-result', data);
  } catch (e) { setResult('l2-session-result', e.message, true); }
}

// L3
async function runL3React() {
  let history;
  try { history = JSON.parse(document.getElementById('l3-react-history').value); }
  catch (e) { setResult('l3-react-result', 'JSON 解析错误: ' + e.message, true); return; }
  try {
    const data = await postJson('/api/l3/test_react', {
      user_id: document.getElementById('l3-react-user').value,
      query: document.getElementById('l3-react-query').value,
      history: history
    });
    setResult('l3-react-result', data);
  } catch (e) { setResult('l3-react-result', e.message, true); }
}

async function runL3Security() {
  try {
    const data = await postJson('/api/l3/test_security', {
      query: document.getElementById('l3-sec-query').value
    });
    setResult('l3-sec-result', data);
  } catch (e) { setResult('l3-sec-result', e.message, true); }
}

// L4
async function runL4Memory() {
  let messages;
  try { messages = JSON.parse(document.getElementById('l4-messages').value); }
  catch (e) { setResult('l4-memory-result', 'JSON 解析错误: ' + e.message, true); return; }
  try {
    const data = await postJson('/api/l4/test_memory', {
      session_id: document.getElementById('l4-session').value,
      messages: messages
    });
    setResult('l4-memory-result', data);
  } catch (e) { setResult('l4-memory-result', e.message, true); }
}

async function runL4Search() {
  try {
    const data = await postJson('/api/l4/test_search', {
      query: document.getElementById('l4-query').value,
      top_k: parseInt(document.getElementById('l4-topk').value, 10)
    });
    setResult('l4-search-result', data);
  } catch (e) { setResult('l4-search-result', e.message, true); }
}

// L5
function setL5Tool(action, paramsJson) {
  document.getElementById('l5-action').value = action;
  document.getElementById('l5-params').value = paramsJson;
}

async function runL5Tool() {
  let params;
  try { params = JSON.parse(document.getElementById('l5-params').value); }
  catch (e) { setResult('l5-tool-result', 'JSON 解析错误: ' + e.message, true); return; }
  try {
    const data = await postJson('/api/l5/test_tool', {
      action: document.getElementById('l5-action').value,
      params: params,
      user_permissions: []
    });
    setResult('l5-tool-result', data);
  } catch (e) { setResult('l5-tool-result', e.message, true); }
}

async function runL5Bash() {
  try {
    const data = await postJson('/api/l5/test_bash', {
      command: document.getElementById('l5-bash').value
    });
    setResult('l5-bash-result', data);
  } catch (e) { setResult('l5-bash-result', e.message, true); }
}

// L6
function setL6Code(lang, code) {
  document.getElementById('l6-lang').value = lang;
  document.getElementById('l6-code').value = code;
}

async function runL6Runtime() {
  try {
    const data = await postJson('/api/l6/test_runtime', {
      language: document.getElementById('l6-lang').value,
      code: document.getElementById('l6-code').value,
      timeout: parseInt(document.getElementById('l6-timeout').value, 10)
    });
    setResult('l6-runtime-result', data);
  } catch (e) { setResult('l6-runtime-result', e.message, true); }
}

// E2E Chat
const E2E_USER_ID = 'web-console-user';
let e2eHasMessages = false;

function setE2E(text) {
  document.getElementById('e2e-input').value = text;
}

function appendChatMessage(role, text, meta) {
  const container = document.getElementById('chat-messages');
  if (!e2eHasMessages) {
    container.innerHTML = '';
    e2eHasMessages = true;
  }
  const div = document.createElement('div');
  div.className = `chat-message ${role}`;
  div.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>${meta ? `<div class="meta">${escapeHtml(meta)}</div>` : ''}`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[m]));
}

async function sendE2E() {
  const input = document.getElementById('e2e-input');
  const content = input.value.trim();
  if (!content) return;
  appendChatMessage('user', content);
  input.value = '';

  const detailBox = document.getElementById('e2e-react-detail');
  detailBox.textContent = '请求处理中...';
  detailBox.className = 'result-box';

  try {
    const data = await postJson('/api/e2e/chat', {
      user_id: E2E_USER_ID,
      content: content,
      channel: 'web'
    });
    appendChatMessage('assistant', data.final_answer || '(无回复)', `session: ${data.session_id || '-'} | ${data.elapsed_ms || 0}ms`);

    if (data.react_steps && data.react_steps.length) {
      detailBox.innerHTML = data.react_steps.map(step => `
        <div class="react-step">
          <div class="step-title">Iteration ${step.iteration} — ${escapeHtml(step.action)}</div>
          <div><strong>Thought:</strong></div>
          <pre>${escapeHtml(step.thought)}</pre>
          ${step.action_input && Object.keys(step.action_input).length ? `<div><strong>Action Input:</strong></div><pre>${JSON.stringify(step.action_input, null, 2)}</pre>` : ''}
          ${step.observation ? `<div><strong>Observation:</strong></div><pre>${escapeHtml(String(step.observation))}</pre>` : ''}
          <div><strong>Status:</strong> ${escapeHtml(step.status)}</div>
        </div>
      `).join('');
    } else {
      detailBox.textContent = '无 ReAct 步骤（直接回答）';
    }
  } catch (e) {
    appendChatMessage('assistant', '请求失败: ' + e.message, '');
    detailBox.textContent = e.message;
    detailBox.className = 'result-box error';
  }
}

async function resetE2E() {
  try {
    const data = await postJson('/api/e2e/reset', { user_id: E2E_USER_ID });
    document.getElementById('chat-messages').innerHTML = '<div class="empty-hint">会话已重置，在下方输入消息开始 E2E 测试对话</div>';
    e2eHasMessages = false;
    document.getElementById('e2e-react-detail').textContent = '等待对话开始...';
    document.getElementById('e2e-react-detail').className = 'result-box';
  } catch (e) {
    alert('重置失败: ' + e.message);
  }
}

// Init
loadConfig();

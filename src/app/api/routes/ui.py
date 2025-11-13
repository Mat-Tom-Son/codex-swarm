from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter()


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_console(run_id: str) -> HTMLResponse:
    html = f"""
<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8' />
  <title>Run Console · {run_id}</title>
  <style>
    :root {{ font-family: 'SF Mono', 'Inter', sans-serif; background:#05060a; color:#e5e7eb; }}
    body {{ margin:0; padding:24px; max-width:1200px; margin:0 auto; }}
    h1 {{ margin-bottom: 8px; }}
    .pill {{ display:inline-block; padding:4px 10px; border-radius:999px; background:#1f2937; margin-right:8px; font-size:12px; }}

    /* Progress bar */
    #progress-container {{ margin-top:16px; }}
    #progress-bar {{ width:100%; height:6px; background:#1f2937; border-radius:999px; overflow:hidden; }}
    #progress-fill {{ width:0%; height:100%; background:linear-gradient(90deg, #3b82f6, #10b981); transition:width 0.3s ease; }}
    #progress-message {{ margin-top:8px; font-size:14px; color:#9ca3af; }}
    #elapsed-time {{ float:right; color:#6b7280; }}

    /* Events */
    #events {{ margin-top:16px; max-height:60vh; overflow:auto; border:1px solid #1f2937; border-radius:12px; padding:12px; background:#0b0c12; }}
    .event {{ padding:8px 10px; margin-bottom:8px; border-left:3px solid #1f2937; padding-left:12px; }}
    .event:last-child {{ margin-bottom:0; }}

    /* Event types */
    .event-status {{ border-left-color:#3b82f6; }}
    .event-progress {{ border-left-color:#10b981; }}
    .event-step {{ border-left-color:#8b5cf6; }}
    .event-error {{ border-left-color:#ef4444; background:rgba(239,68,68,0.1); }}
    .event-artifact {{ border-left-color:#f59e0b; }}

    .event-time {{ color:#6b7280; font-size:11px; }}
    .event-content {{ margin-top:4px; }}
    .code {{ font-family:'SFMono-Regular', ui-monospace, monospace; font-size:12px; background:#11131b; padding:8px; border-radius:6px; display:block; margin-top:4px; overflow-x:auto; }}

    /* Icons */
    .icon {{ margin-right:6px; }}
  </style>
</head>
<body>
  <h1>🚀 Run Console</h1>
  <div>
    <span class='pill'>Run ID: {run_id}</span>
    <span class='pill' id='status'>status: pending</span>
  </div>

  <!-- Progress bar -->
  <div id='progress-container'>
    <div id='progress-bar'>
      <div id='progress-fill'></div>
    </div>
    <div id='progress-message'>
      <span id='message-text'>Initializing...</span>
      <span id='elapsed-time'></span>
    </div>
  </div>

  <div id='events'></div>

  <script>
    const eventsContainer = document.getElementById('events');
    const statusPill = document.getElementById('status');
    const progressFill = document.getElementById('progress-fill');
    const messageText = document.getElementById('message-text');
    const elapsedTime = document.getElementById('elapsed-time');
    const source = new EventSource('/runs/{run_id}/stream');

    function formatEventContent(data) {{
      const type = data.type;

      if (type === 'status') {{
        const status = data.status;
        const statusColors = {{
          'queued': '#6b7280',
          'running': '#f59e0b',
          'succeeded': '#10b981',
          'failed': '#ef4444'
        }};
        statusPill.textContent = `status: ${{status}}`;
        statusPill.style.background = statusColors[status] || '#1f2937';
        return `<span class="icon">📋</span>Status changed to: <strong>${{status}}</strong>`;
      }}

      if (type === 'progress') {{
        const percent = data.percent || 0;
        const message = data.message || '';
        const elapsed = data.elapsed;

        progressFill.style.width = percent + '%';
        messageText.textContent = message;

        if (elapsed) {{
          elapsedTime.textContent = `${{elapsed.toFixed(1)}}s`;
        }}

        return `<span class="icon">⏳</span>[${{percent}}%] ${{message}}`;
      }}

      if (type === 'step') {{
        const role = data.role;
        const content = (data.content || '').substring(0, 200);
        const icons = {{ assistant: '🤖', user: '👤', tool: '🔧' }};
        return `<span class="icon">${{icons[role] || '📝'}}</span><strong>${{role}}:</strong> ${{content}}...`;
      }}

      if (type === 'error') {{
        const error = data.error || {{}};
        return `<span class="icon">⚠️</span><strong>Error:</strong> ${{error.error || 'Unknown error'}}<br>
                <small>💡 ${{error.suggestion || 'Check the logs'}}</small>`;
      }}

      if (type === 'artifact') {{
        const path = data.path || '';
        const bytes = data.bytes || 0;
        return `<span class="icon">📄</span>Artifact saved: <code>${{path}}</code> (${{bytes}} bytes)`;
      }}

      if (type === 'workspace') {{
        const action = data.action || '';
        if (action === 'cloned') {{
          const entries = data.entries || [];
          return `<span class="icon">📁</span>Workspace cloned: ${{entries.length}} items`;
        }}
        return `<span class="icon">📁</span>Workspace: ${{action}}`;
      }}

      if (type === 'diff') {{
        const diff = data.diff || {{}};
        const files = diff.files || [];
        return `<span class="icon">📝</span>Git diff: ${{files.length}} files changed`;
      }}

      return `<span class="icon">•</span>${{type}}`;
    }}

    function addEvent(data) {{
      const wrapper = document.createElement('div');
      wrapper.className = `event event-${{data.type}}`;

      const ts = new Date().toLocaleTimeString();
      wrapper.innerHTML = `
        <div class="event-time">${{ts}}</div>
        <div class="event-content">${{formatEventContent(data)}}</div>
      `;

      eventsContainer.insertBefore(wrapper, eventsContainer.firstChild);

      // Keep only last 100 events
      while (eventsContainer.children.length > 100) {{
        eventsContainer.removeChild(eventsContainer.lastChild);
      }}
    }}

    source.addEventListener('message', (event) => {{
      try {{
        const payload = JSON.parse(event.data);
        addEvent(payload);
      }} catch (err) {{
        console.error('Failed to parse event:', err);
      }}
    }});

    source.onerror = () => {{
      statusPill.textContent = 'status: disconnected';
      statusPill.style.background = '#7f1d1d';
      messageText.textContent = 'Connection lost';
    }};
  </script>
</body>
</html>
"""

    return HTMLResponse(content=html)

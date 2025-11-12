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
    body {{ margin:0; padding:24px; }}
    h1 {{ margin-bottom: 8px; }}
    .pill {{ display:inline-block; padding:4px 10px; border-radius:999px; background:#1f2937; margin-right:8px; font-size:12px; }}
    #events {{ margin-top:16px; max-height:70vh; overflow:auto; border:1px solid #1f2937; border-radius:12px; padding:12px; background:#0b0c12; }}
    .event {{ padding:8px 10px; border-bottom:1px solid rgba(255,255,255,0.05); }}
    .event:last-child {{ border-bottom:none; }}
    .code {{ font-family:'SFMono-Regular', ui-monospace, monospace; font-size:12px; background:#11131b; padding:4px 6px; border-radius:6px; display:inline-block; margin-top:4px; }}
  </style>
</head>
<body>
  <h1>Run Console</h1>
  <div>
    <span class='pill'>Run ID: {run_id}</span>
    <span class='pill' id='status'>status: pending</span>
  </div>
  <p>Streaming events from <code>/runs/{run_id}/stream</code>. Keep this tab open to watch Codex activity in real time.</p>
  <div id='events'></div>

  <script>
    const target = document.getElementById('events');
    const statusPill = document.getElementById('status');
    const source = new EventSource('/runs/{run_id}/stream');

    function pushEvent(data) {{
      const wrapper = document.createElement('div');
      wrapper.className = 'event';
      const ts = new Date().toLocaleTimeString();
      wrapper.innerHTML = `<strong>[${{ts}}]</strong> ${{data.type}}`;
      const pre = document.createElement('pre');
      pre.className = 'code';
      pre.textContent = JSON.stringify(data, null, 2);
      wrapper.appendChild(pre);
      target.prepend(wrapper);
    }}

    source.addEventListener('message', (event) => {{
      try {{
        const payload = JSON.parse(event.data);
        pushEvent(payload);
        if (payload.type === 'status') {{
          statusPill.textContent = `status: ${{payload.status}}`;
        }}
      }} catch (err) {{
        console.error(err);
      }}
    }});

    source.onerror = () => {{
      statusPill.textContent = 'status: disconnected';
      statusPill.style.background = '#7f1d1d';
    }};
  </script>
</body>
</html>
"""

    return HTMLResponse(content=html)

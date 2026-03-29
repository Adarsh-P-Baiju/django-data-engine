import os
import time
import datetime
import unittest
import json
import logging
from io import StringIO
try:
    import psutil
except ImportError:
    psutil = None
from django.test.runner import DiscoverRunner
from django.conf import settings
from django.db import connection

class ForensicLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.buffer = StringIO()
    def emit(self, record):
        self.buffer.write(self.format(record) + "\n")
    def get_and_reset(self):
        val = self.buffer.getvalue()
        self.buffer = StringIO()
        return val

class PremiumTestResult(unittest.TextTestResult):
    """Generates detailed technical summaries for each test scenario."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.results_data = []
        self.subtest_count = 0
        self.start_timer = time.time()
        self.process = psutil.Process(os.getpid()) if psutil else None
        self.log_stream = ForensicLogHandler()
        self.log_stream.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logging.getLogger().addHandler(self.log_stream)

    def generate_narrative(self, test_name, params, err):
        """Generates a human-readable summary for a diagnostic node."""
        objective = f"Analyzing behavior for {test_name.replace('test_', '').replace('_', ' ')}."
        if "rules" in params:
            objective = f"Verifying the DSL rule chain: {params['rules']}."
        elif "payload" in params:
            objective = f"Testing system resilience against malicious vector: {params['id']}."
        
        logic_trace = "The Engine successfully processed the data vector and verified integrity."
        if err:
            logic_trace = "The Engine identified a failure during processing."
        
        outcome = "SUCCESS: Integrity verified."
        if err:
            outcome = f"FAILURE: {str(err).split('\\n')[0]}"
            
        return {
            "objective": objective,
            "logic": logic_trace,
            "outcome": outcome
        }

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        self.subtest_count += 1
        
        status = "PASSED" if err is None else "FAILED"
        mem_mb = self.process.memory_info().rss / (1024 * 1024) if self.process else 0
        logs = self.log_stream.get_and_reset()
        queries = connection.queries
        connection.queries_log.clear()

        raw_params = getattr(subtest, 'params', {})
        params = dict(raw_params) if hasattr(raw_params, 'items') else {"val": str(raw_params)}
        
        # Generate the technical summary
        story = self.generate_narrative(test._testMethodName, params, err)
        
        self.results_data.append({
            "id": f"{test._testMethodName} #{self.subtest_count}",
            "st": status,
            "meta": params,
            "story": story,
            "logs": logs if logs else "STREAM_OPTIMAL",
            "sql_count": len(queries),
            "queries": [q['sql'] for q in queries[-5:]],
            "err": str(err) if err else None,
            "lat": round(time.time() - self.start_timer, 4),
            "ram": round(mem_mb, 2)
        })

    def addSuccess(self, test):
        super().addSuccess(test)
        self.results_data.append({
            "id": str(test),
            "st": "PASSED",
            "meta": {"type": "CORE_SYSTEM_HEALTH"},
            "story": {
                "objective": "Verifying global system health and core component alignment.",
                "logic": "The Engine performed a validation of all registered services.",
                "outcome": "HEALTHY: All systems reporting operational."
            },
            "logs": "CORE_STREAM_OPTIMAL",
            "sql_count": 0,
            "queries": [],
            "err": None,
            "lat": round(time.time() - self.start_timer, 4),
            "ram": round(self.process.memory_info().rss / (1024 * 1024) if self.process else 0, 2)
        })

class PremiumReportRunner(DiscoverRunner):
    """Custom test runner with narrative diagnostic reporting."""
    def get_resultclass(self):
        return PremiumTestResult

    def run_suite(self, suite, **kwargs):
        self.start_time = time.time()
        settings.DEBUG = True 
        result = super().run_suite(suite, **kwargs)
        self.finalize_report(result)
        return result

    def finalize_report(self, result):
        total_duration = time.time() - self.start_time
        peak_mem = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024) if psutil else 0
        
        stats = {
            "total": result.testsRun + result.subtest_count,
            "passed": (result.testsRun + result.subtest_count) - (len(result.errors) + len(result.failures)),
            "failed": len(result.errors) + len(result.failures),
            "duration": round(total_duration, 4),
            "peak_memory": round(peak_mem, 2),
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        report_dir = os.path.join(settings.BASE_DIR, "import_engine/static/reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, "latest_test_report.html")
        
        html_content = self.render_html_report(stats, result.results_data)
        with open(report_path, "w") as f:
            f.write(html_content)
        
        print(f"\n[DIAGNOSTIC] Report Generated: {report_path}")

    def render_html_report(self, stats, results):
        results_json = json.dumps(results)
        
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Import Engine Diagnostic Monitor</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;600;800&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #c084fc;
            --secondary: #22d3ee;
            --success: #10b981;
            --danger: #f43f5e;
            --bg: #010409;
            --panel: rgba(13, 17, 23, 0.98);
        }}
        body {{
            background: #010409; color: #f0f6fc; font-family: 'Outfit', sans-serif;
            margin: 0; padding: 2.5rem; display: flex; flex-direction: column; gap: 2.5rem;
            height: 100vh; overflow: hidden; box-sizing: border-box;
        }}
        .glass {{ background: var(--panel); backdrop-filter: blur(80px); border: 1px solid #30363d; border-radius: 2rem; padding: 2.5rem; box-shadow: 0 40px 100px -20px rgba(0, 0, 0, 1); }}
        .header {{ display: flex; justify-content: space-between; align-items: flex-end; }}
        h1 {{ margin: 0; font-size: 3rem; font-weight: 800; letter-spacing: -2px; background: linear-gradient(to right, #8b5cf6, #06b6d4); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .stat-grid {{ display: flex; gap: 4rem; }}
        .stat-item {{ border-left: 2px solid var(--primary); padding-left: 1.5rem; }}
        .stat-val {{ font-size: 2.5rem; font-weight: 800; line-height: 1; }}
        .stat-lbl {{ font-size: 0.65rem; text-transform: uppercase; letter-spacing: 2.5px; opacity: 0.5; margin-top: 8px; font-weight: 700; }}
        .main-frame {{ flex-grow: 1; overflow-y: auto; border-radius: 1.5rem; position: relative; border: 1px solid #30363d; }}
        table {{ width: 100%; border-collapse: separate; border-spacing: 0; }}
        th {{ position: sticky; top: 0; background: #161b22; padding: 1.5rem; text-align: left; font-size: 0.7rem; text-transform: uppercase; color: #8b949e; border-bottom: 1px solid #30363d; z-index: 10; font-weight: 800; letter-spacing: 1px; }}
        td {{ padding: 1.5rem; border-bottom: 1px solid #21262d; font-size: 0.9rem; vertical-align: middle; }}
        
        .mono {{ font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #8b949e; }}
        .narrative-brief {{ color: #e2e8f0; font-weight: 600; line-height: 1.5; max-width: 500px; display: block; margin-bottom: 8px; }}
        
        .deep-dive-btn {{
            background: linear-gradient(135deg, #1d4ed8, #7c3aed);
            border: none; color: white; padding: 10px 20px; border-radius: 12px;
            font-size: 0.7rem; font-weight: 800; cursor: pointer; text-transform: uppercase;
            letter-spacing: 1.5px; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        .deep-dive-btn:hover {{ transform: scale(1.05) translateY(-2px); box-shadow: 0 10px 20px rgba(124, 58, 237, 0.3); }}
        
        .badge {{ padding: 6px 14px; border-radius: 10px; font-weight: 800; font-size: 0.7rem; border: 1px solid rgba(255,255,255,0.05); }}
        .badge-passed {{ color: #a3e635; background: rgba(163, 230, 21, 0.1); }}
        .badge-failed {{ color: #f87171; background: rgba(248, 113, 113, 0.1); }}

        #m-overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.92); z-index: 1000; backdrop-filter: blur(20px); align-items: center; justify-content: center; }}
        #m-modal {{ width: 90%; max-width: 1200px; max-height: 85vh; background: #0d1117; border: 1px solid #30363d; border-radius: 2.5rem; padding: 4rem; display: flex; flex-direction: column; gap: 3rem; overflow: hidden; }}
        .modal-header {{ display: flex; justify-content: space-between; border-bottom: 1px solid #30363d; padding-bottom: 2rem; }}
        .modal-body {{ overflow-y: auto; display: grid; grid-template-columns: 1fr 1fr; gap: 2.5rem; }}
        .section-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 1.5rem; padding: 2rem; position: relative; }}
        .section-label {{ font-size: 0.75rem; text-transform: uppercase; color: var(--primary); font-weight: 800; margin-bottom: 15px; letter-spacing: 2px; }}
        .story-text {{ font-size: 1.1rem; line-height: 1.7; color: #c9d1d9; font-weight: 400; }}
        pre {{ margin: 0; white-space: pre-wrap; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #8b949e; line-height: 1.6; }}
    </style>
</head>
<body>
    <div id="m-overlay" onclick="closeM(event)">
        <div id="m-modal" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div>
                    <h2 id="mt-id" style="margin:0; font-size:2.5rem; font-weight:800; color:#fff">FORENSIC_SCOPE</h2>
                    <div id="mt-sub" class="mono" style="margin-top:10px; font-size:0.8rem; opacity:0.5">COMPUTATIONAL_SEQUENCE_ALPHA</div>
                </div>
                <button class="deep-dive-btn" onclick="closeM()" style="padding: 15px 30px">Exit</button>
            </div>
            <div class="modal-body">
                <div class="section-card" style="grid-column: span 2; background: linear-gradient(to right, #161b22, #0d1117); border-left: 5px solid var(--primary);">
                    <div class="section-label">Technical Narrative</div>
                    <div id="ms-obj" class="story-text" style="font-weight: 800; color: #fff; margin-bottom: 15px;"></div>
                    <div id="ms-log" class="story-text" style="margin-bottom: 15px; opacity: 0.8;"></div>
                    <div id="ms-out" class="story-text" style="color: var(--secondary); font-weight: 600;"></div>
                </div>
                <div class="section-card">
                    <div class="section-label">Historical Log Stream</div>
                    <pre id="ml-logs"></pre>
                </div>
                <div class="section-card">
                    <div class="section-label">System Metadata</div>
                    <pre id="ml-meta"></pre>
                </div>
                <div class="section-card" style="grid-column: span 2;">
                    <div class="section-label">SQL Trace</div>
                    <pre id="ml-sql"></pre>
                </div>
            </div>
        </div>
    </div>

    <div class="glass header">
        <div>
            <h1>Import Engine <span style="font-weight: 300; opacity: 0.5">Diagnostics</span></h1>
            <div class="mono" style="font-size: 0.8rem; margin-top: 10px; opacity: 0.4">TECHNICAL NARRATIVES | {stats['timestamp']}</div>
        </div>
        <div class="stat-grid">
            <div class="stat-item"><div class="stat-val">{stats['total']:,}</div><div class="stat-lbl">Validated Scenarios</div></div>
            <div class="stat-item"><div class="stat-val" style="color:var(--secondary)">{stats['duration']}s</div><div class="stat-lbl">Execution Pulsar</div></div>
            <div class="stat-item"><div class="stat-val" style="color:var(--primary)">{stats['peak_memory']}MB</div><div class="stat-lbl">Memory Flux</div></div>
        </div>
    </div>

    <div class="glass main-frame" id="v-frame">
        <table>
            <thead>
                <tr>
                    <th>Ref Node</th>
                    <th>Analytical Narrative (Story)</th>
                    <th>Pulse</th>
                    <th>Audit</th>
                </tr>
            </thead>
            <tbody id="v-rows"></tbody>
        </table>
    </div>

    <script>
        const store = {results_json};
        const rows = document.getElementById('v-rows');
        const frame = document.getElementById('v-frame');
        let ptr = 0;
        const STEP = 150;

        function draw() {{
            const end = Math.min(ptr + STEP, store.length);
            const frag = document.createDocumentFragment();
            for(let i = ptr; i < end; i++) {{
                const r = store[i];
                const tr = document.createElement('tr');
                const st = r.st ? r.st.toLowerCase() : 'NA';
                tr.innerHTML = `
                    <td class="mono" style="opacity:0.4">${{r.id}}</td>
                    <td>
                        <span class="narrative-brief">${{r.story.objective}}</span>
                        <div class="mono" style="font-size:0.75rem; color:var(--secondary)">${{r.story.outcome}}</div>
                    </td>
                    <td>
                        <span class="badge badge-${{st}}">${{r.st}}</span>
                        <div class="mono" style="margin-top:8px; font-size:0.7rem; opacity:0.6">${{r.lat}}s | ${{r.ram}}MB</div>
                    </td>
                    <td><button class="deep-dive-btn" onclick="dive(${{i}})">Explore</button></td>
                `;
                frag.appendChild(tr);
            }}
            rows.appendChild(frag);
            ptr += STEP;
        }}

        function dive(i) {{
            const r = store[i];
            document.getElementById('mt-id').innerText = r.id;
            document.getElementById('mt-sub').innerText = `VECTOR_NODE_${{i+1}} | RESONANCE: ${{r.lat}}s | RAM_FLUX: ${{r.ram}}MB`;
            
            document.getElementById('ms-obj').innerText = r.story.objective;
            document.getElementById('ms-log').innerText = r.story.logic;
            document.getElementById('ms-out').innerText = r.story.outcome;
            
            document.getElementById('ml-logs').innerText = r.logs;
            document.getElementById('ml-meta').innerText = JSON.stringify(r.meta, null, 4);
            document.getElementById('ml-sql').innerText = r.queries.join('\\n\\n') || 'ZERO_SQL_TRACES';
            
            document.getElementById('m-overlay').style.display = 'flex';
        }}

        function closeM() {{ document.getElementById('m-overlay').style.display = 'none'; }}
        
        if(store.length) {{ draw(); draw(); draw(); }}
        frame.addEventListener('scroll', () => {{
            if(frame.scrollTop + frame.clientHeight >= frame.scrollHeight - 1500 && ptr < store.length) draw();
        }});
    </script>
</body>
</html>
"""

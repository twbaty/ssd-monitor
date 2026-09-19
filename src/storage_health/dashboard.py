from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .history import load_snapshots


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SSD Monitor</title><style>
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#e8eef8;background:#0c1422}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 90% 0%,#172d45,#0c1422 48%)}
main{max-width:1120px;margin:auto;padding:42px 24px 70px}header{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:34px}
.eyebrow{color:#64d9c6;font-size:12px;font-weight:800;letter-spacing:.18em;text-transform:uppercase}h1{font-size:clamp(32px,5vw,48px);margin:5px 0 8px;letter-spacing:-.04em}p{color:#9fb0c6;margin:0}
.pill{border:1px solid #334458;border-radius:999px;padding:9px 14px;font-size:13px;color:#b9cbdf;white-space:nowrap}.pill.good{border-color:#236e62;color:#7ce8ca;background:#12372f}.pill.bad{border-color:#85484b;color:#ffc1c1;background:#47272c}
.grid{display:grid;grid-template-columns:1.2fr repeat(3,1fr);gap:16px}.card{background:#152235;border:1px solid #263a50;border-radius:20px;padding:23px;box-shadow:0 14px 40px #06101d55}
.label{color:#93a9c2;font-size:13px;font-weight:650}.value{font-size:32px;letter-spacing:-.04em;font-weight:750;margin:15px 0 5px}.unit{font-size:16px;color:#9bb2c9}.sub{font-size:12px;color:#91a7bd}.meter{height:9px;background:#2c4054;border-radius:20px;margin:20px 0 11px;overflow:hidden}.meter>span{display:block;background:linear-gradient(90deg,#42aaba,#7ce8ca);height:100%;border-radius:20px}
.section{margin-top:18px}.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}.chart{height:245px;width:100%;margin-top:20px;overflow:visible}.axis{stroke:#34506a;stroke-width:1}.trace{fill:none;stroke:#6be2cd;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}.trace.temp{stroke:#f6b86f}.point{fill:#6be2cd}.point.temp{fill:#f6b86f}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:18px}.stat-value{font-size:28px;font-weight:750;margin-top:10px}.foot{display:flex;justify-content:space-between;gap:15px;margin-top:28px;font-size:13px;color:#839ab3}.empty{padding:50px 20px;text-align:center;color:#a9bfd5}.empty strong{display:block;color:#e8eef8;font-size:20px;margin-bottom:10px}code{color:#7ce8ca}
@media(max-width:800px){.grid{grid-template-columns:1fr 1fr}.two{grid-template-columns:1fr}}@media(max-width:520px){main{padding:28px 16px}header{display:block}.pill{display:inline-block;margin-top:16px}.grid,.stats{grid-template-columns:1fr}.card{padding:19px}.foot{display:block}}
</style></head><body><main><header><div><div class="eyebrow">Local storage telemetry</div><h1>SSD Monitor</h1><p id="device">Loading drive history…</p></div><div id="status" class="pill">Loading</div></header>
<div id="empty" class="card empty" hidden><strong>No saved scans yet</strong><span>Run <code>storage-health record</code> to create your first snapshot.</span></div>
<div id="content" hidden><section class="grid"><div class="card"><div class="label">Lifetime remaining</div><div class="value" id="life">—</div><div class="meter"><span id="life-bar" style="width:0%"></span></div><div class="sub">From the drive’s SMART wear attribute</div></div>
<div class="card"><div class="label">Temperature</div><div class="value" id="temp">—</div><div class="sub">Latest reading</div></div><div class="card"><div class="label">Power on</div><div class="value" id="hours">—</div><div class="sub">Hours of operation</div></div><div class="card"><div class="label">Saved scans</div><div class="value" id="scans">—</div><div class="sub" id="last">Latest snapshot</div></div></section>
<section class="two section"><div class="card"><div class="label">Lifetime remaining over time</div><svg id="life-chart" class="chart" viewBox="0 0 500 220" role="img" aria-label="Lifetime remaining chart"></svg></div><div class="card"><div class="label">Temperature over time</div><svg id="temp-chart" class="chart" viewBox="0 0 500 220" role="img" aria-label="Temperature chart"></svg></div></section>
<section class="stats"><div class="card"><div class="label">Reallocated NAND blocks</div><div class="stat-value" id="reallocated">—</div></div><div class="card"><div class="label">Uncorrectable errors</div><div class="stat-value" id="uncorrectable">—</div></div><div class="card"><div class="label">Interface CRC errors</div><div class="stat-value" id="crc">—</div></div></section>
<div class="foot"><span>Readings are saved locally. Missing values appear as —.</span><span id="updated"></span></div></div></main><script>
const $=id=>document.getElementById(id), fmt=n=>n==null?'—':Number(n).toLocaleString();
function draw(id,items,key,kind){const svg=$(id),ns='http://www.w3.org/2000/svg';svg.replaceChildren();const points=items.filter(x=>typeof x[key]==='number'&&Number.isFinite(x[key]));const line=(tag,attrs)=>{const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);svg.append(e);return e};for(const y of [28,104,180])line('line',{x1:38,y1:y,x2:480,y2:y,class:'axis'});if(!points.length){line('text',{x:180,y:110,fill:'#93a9c2'}).textContent='No readings yet';return}const values=points.map(x=>x[key]);let min=Math.min(...values),max=Math.max(...values);if(kind==='life'){min=0;max=100}else{min=Math.floor((min-3)/5)*5;max=Math.ceil((max+3)/5)*5;if(min===max)max=min+5}const xy=points.map((p,i)=>[38+(points.length===1?221:i*442/(points.length-1)),180-(p[key]-min)*152/(max-min)]);line('text',{x:0,y:32,fill:'#93a9c2','font-size':12}).textContent=String(max);line('text',{x:0,y:183,fill:'#93a9c2','font-size':12}).textContent=String(min);if(xy.length>1)line('polyline',{points:xy.map(p=>p.join(',')).join(' '),class:'trace '+(kind==='temp'?'temp':'')});for(const [x,y] of xy)line('circle',{cx:x,cy:y,r:4,class:'point '+(kind==='temp'?'temp':'')})}
fetch('/api/snapshots').then(r=>r.json()).then(rows=>{if(!rows.length){$('empty').hidden=false;$('status').textContent='No scans';return}const device=rows[rows.length-1].device,items=rows.filter(x=>x.device===device),last=items[items.length-1];$('content').hidden=false;$('device').textContent=(last.model||'Unknown drive')+' · '+(device||'Unknown device');$('status').textContent=last.smart_passed===true?'SMART passed':last.smart_passed===false?'SMART warning':'SMART unknown';$('status').className='pill '+(last.smart_passed===true?'good':last.smart_passed===false?'bad':'');$('life').textContent=last.lifetime_remaining_percent==null?'—':last.lifetime_remaining_percent+'%';$('life-bar').style.width=Math.max(0,Math.min(100,last.lifetime_remaining_percent||0))+'%';$('temp').textContent=last.temperature_celsius==null?'—':last.temperature_celsius+'°C';$('hours').textContent=fmt(last.power_on_hours);$('scans').textContent=fmt(items.length);$('reallocated').textContent=fmt(last.reallocated_nand_blocks);$('uncorrectable').textContent=fmt(last.reported_uncorrectable_errors);$('crc').textContent=fmt(last.interface_crc_errors);const date=new Date(last.timestamp);$('last').textContent=Number.isNaN(date.getTime())?'Latest snapshot':date.toLocaleString();$('updated').textContent='Last recorded '+$('last').textContent;draw('life-chart',items,'lifetime_remaining_percent','life');draw('temp-chart',items,'temperature_celsius','temp')}).catch(()=>{$('empty').hidden=false;$('empty').querySelector('strong').textContent='Unable to load scans';$('status').textContent='Unavailable'});
</script></body></html>"""


def serve(data_dir: Path, port: int = 8765) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/":
                payload = PAGE.encode("utf-8")
                content_type = "text/html; charset=utf-8"
            elif self.path == "/api/snapshots":
                payload = json.dumps(load_snapshots(data_dir)).encode("utf-8")
                content_type = "application/json; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"SSD Monitor dashboard: http://127.0.0.1:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

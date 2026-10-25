"""FastAPI routes and a small built-in export UI for Module II."""
from __future__ import annotations

import re
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from module2.data_export.service import (
    MAX_EXPORT_ROWS,
    SUPPORTED_FORMATS,
    fetch_dataset,
    list_export_datasets,
    render_export,
)

router = APIRouter()
_DATASET_PATTERN = re.compile(r"^m2_[A-Za-z0-9_]+$")


@router.get("/ui", response_class=HTMLResponse, include_in_schema=False)
def export_ui() -> str:
    """A small UI that works without changes to the existing frontend."""
    return r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>DepartmentAI | Data Export</title>
<style>
:root{color-scheme:light;--navy:#16324f;--blue:#245b8f;--ink:#1e293b;--muted:#64748b;--line:#dbe3ec;--bg:#f3f6fa}
*{box-sizing:border-box}body{margin:0;background:var(--bg);font:15px/1.5 Inter,Segoe UI,Arial,sans-serif;color:var(--ink)}
header{background:linear-gradient(115deg,#102a43,#245b8f);color:white;padding:28px max(24px,calc((100% - 1040px)/2))}
header small{letter-spacing:.12em;text-transform:uppercase;opacity:.8;font-weight:700}h1{margin:5px 0;font-size:clamp(24px,4vw,34px)}header p{margin:0;opacity:.88}
main{max-width:1040px;margin:30px auto;padding:0 20px}.panel{background:white;border:1px solid var(--line);border-radius:16px;padding:24px;box-shadow:0 8px 28px #1e293b0a}
h2{font-size:19px;margin:0 0 6px}.intro{margin:0 0 22px;color:var(--muted)}
.grid{display:grid;grid-template-columns:2fr 1fr;gap:18px}@media(max-width:650px){.grid{grid-template-columns:1fr}}
label{display:block;font-weight:650;margin:0 0 7px}select,input{width:100%;padding:12px;border:1px solid #cbd5e1;border-radius:9px;background:white;color:var(--ink);font:inherit}
.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}button{border:0;border-radius:9px;padding:12px 18px;font:inherit;font-weight:700;cursor:pointer}
.primary{background:var(--blue);color:white}.secondary{background:#e8eef5;color:var(--navy)}button:disabled{opacity:.55;cursor:wait}
.note{font-size:13px;color:var(--muted);margin-top:16px}.status{margin-top:18px;padding:12px;border-radius:9px;background:#f1f5f9;color:#334155;white-space:pre-wrap}.status.error{background:#fff1f2;color:#9f1239}
.dataset-list{margin-top:24px;border-top:1px solid var(--line);padding-top:18px}.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.chip{font-size:12px;padding:5px 9px;border-radius:999px;background:#eef3f8;color:#334e68}
</style></head>
<body>
<header><small>DepartmentAI · Module II</small><h1>Data Export Centre</h1><p>Download stored Module II records in the format you need.</p></header>
<main><section class="panel"><h2>Create an export</h2><p class="intro">Choose an available dataset and a file format. Exports use database records, not generated summaries.</p>
<div class="grid">
<div><label for="dataset">Dataset</label><select id="dataset"><option value="">Loading datasets…</option></select></div>
<div><label for="format">Download format</label><select id="format"><option value="csv">CSV (.csv)</option><option value="xlsx">Excel (.xlsx)</option><option value="pdf">PDF (.pdf)</option><option value="docx">Word (.docx)</option></select></div>
</div>
<div class="grid" style="margin-top:18px"><div><label for="limit">Optional row limit</label><input id="limit" type="number" min="1" max="100000" placeholder="Leave blank to export all rows (up to 100,000)"></div><div><label>Included data</label><div class="status" style="margin:0">All columns · Real stored rows · UTF-8 text</div></div></div>
<div class="actions"><button class="primary" id="download">Download file</button><button class="secondary" id="refresh">Refresh datasets</button></div>
<div class="status" id="status" role="status" aria-live="polite">Loading available datasets…</div>
<div class="dataset-list"><strong>Available datasets</strong><div class="chips" id="chips"></div><p class="note">Only base tables in PostgreSQL's public schema with names beginning <code>m2_</code> are listed. Exports larger than the configured safety limit require an explicit row limit or a reviewed configuration change.</p></div>
</section></main>
<script>
const $=id=>document.getElementById(id);let datasets=[];
function message(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error)}
async function loadDatasets(){ $('refresh').disabled=true; message('Loading available datasets…'); try{
 const r=await fetch('/module2/export/datasets');const body=await r.json();if(!r.ok)throw new Error(body.detail||'Could not load datasets');
 datasets=body.datasets||[];const sel=$('dataset');sel.replaceChildren();
 if(!datasets.length){sel.add(new Option('No m2_ tables found',''));message('No exportable Module II tables were found.',true)}
 else{for(const d of datasets)sel.add(new Option(`${d.name} (${d.columns.length} columns)`,d.name));message(`${datasets.length} dataset(s) available. Choose a dataset and format.`)}
 $('chips').replaceChildren();for(const d of datasets){const el=document.createElement('span');el.className='chip';el.textContent=d.name;$('chips').appendChild(el)}
 }catch(e){message('Could not load datasets: '+e.message,true)}finally{$('refresh').disabled=false}}
$('refresh').addEventListener('click',loadDatasets);
$('download').addEventListener('click',async()=>{const dataset=$('dataset').value,format=$('format').value,limit=$('limit').value.trim();if(!dataset){message('Choose a dataset first.',true);return}
 if(limit&&(!Number.isInteger(Number(limit))||Number(limit)<1||Number(limit)>100000)){message('Row limit must be an integer from 1 to 100000.',true);return}
 const url='/module2/export/'+encodeURIComponent(dataset)+'/download?format='+encodeURIComponent(format)+(limit?'&limit='+encodeURIComponent(limit):'');
 $('download').disabled=true;message('Preparing your file…');try{const r=await fetch(url);if(!r.ok){let detail='Export failed';try{const b=await r.json();detail=b.detail||detail}catch{}throw new Error(detail)}
 const blob=await r.blob();const objectUrl=URL.createObjectURL(blob);const a=document.createElement('a');a.href=objectUrl;a.download=(r.headers.get('content-disposition')||'').match(/filename="?([^";]+)"?/i)?.[1]||`${dataset}.${format}`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(objectUrl);message(`Download started: ${a.download}`)
 }catch(e){message('Could not create export: '+e.message,true)}finally{$('download').disabled=false}});
loadDatasets();
</script></body></html>"""


@router.get("/datasets")
def get_export_datasets() -> dict:
    try:
        return {"datasets": list_export_datasets(), "formats": sorted(SUPPORTED_FORMATS)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not discover export datasets: {exc}") from exc


@router.get("/{dataset}/download")
def download_dataset(
    dataset: str,
    format: str = Query(..., description="One of: csv, xlsx, pdf, docx"),
    limit: int | None = Query(None, ge=1, le=MAX_EXPORT_ROWS),
) -> Response:
    if not _DATASET_PATTERN.fullmatch(dataset):
        raise HTTPException(status_code=400, detail="Invalid dataset name.")
    file_format = format.lower().strip().lstrip(".")
    if file_format not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported format. Choose csv, xlsx, pdf, or docx.")
    try:
        columns, rows, truncated = fetch_dataset(dataset, limit=limit)
        content, media_type, extension = render_export(dataset, columns, rows, file_format)
        filename = f"{dataset}.{extension}"
        headers = {
            "Content-Disposition": f'attachment; filename="{quote(filename)}"',
            "X-Export-Row-Count": str(len(rows)),
            "X-Export-Truncated": "true" if truncated else "false",
        }
        return Response(content=content, media_type=media_type, headers=headers)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OverflowError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

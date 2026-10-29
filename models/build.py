'''Build the historical valuation payload and its single-file browser demo.'''

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from .common import embedded_json, load_original_inputs, stable_hash
from .dcf import build_scenarios, evaluate_dcf
from .methods import get_methods


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'models' / 'out'
WEB = ROOT / 'web'


def read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def source_model_hash(index: Path) -> str:
    text = index.read_text(encoding='utf-8')
    tail = text.split('const BUNDLED_BOOK=', 1)[1]
    _, end = json.JSONDecoder().raw_decode(tail)
    literal = tail[:end]
    engine = text[text.index('class FormulaError extends Error'):
                  text.index('const $=')]
    return hashlib.sha256((literal + '\n' + engine).encode()).hexdigest()


def replace_once(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if text.count(old) != 1:
        raise ValueError(f'Expected one page integration anchor: {old[:80]}')
    return text.replace(old, new, 1)


def replace_region(text: str, name: str, body: str, anchor: str) -> str:
    start, end = f'/*{name}-START*/', f'/*{name}-END*/'
    replacement = start + body + end
    if start in text or end in text:
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError(f'Duplicate or incomplete {name} markers.')
        left = text.index(start)
        right = text.index(end, left) + len(end)
        return text[:left] + replacement + text[right:]
    if text.count(anchor) != 1:
        raise ValueError(f'Expected one insertion anchor for {name}.')
    return text.replace(anchor, replacement + '\n' + anchor, 1)


def patch_page(text: str, payload: dict) -> str:
    for name, anchor, file in (
        ('range', '<section class="card ask-card">', 'valuation.html'),
        ('reverse', '<section class="card forecast-card">', 'reverse.html'),
        ('questions', '<section class="card forecast-card">', 'questions.html'),
    ):
        marker = f'<!--{name.upper()}-CARD-->'
        start = f'<!--{name.upper()}-CARD-START-->'
        end = f'<!--{name.upper()}-CARD-END-->'
        replacement = start + (WEB / file).read_text() + end
        if start in text:
            if text.count(start) != 1 or text.count(end) != 1:
                raise ValueError(f'Invalid {name} card markers.')
            left = text.index(start)
            right = text.index(end, left) + len(end)
            text = text[:left] + replacement + text[right:]
        elif marker in text:
            text, count = re.subn(re.escape(marker) + r'.*?</section>',
                                  lambda _: replacement, text, count=1,
                                  flags=re.DOTALL)
            if count != 1:
                raise ValueError(f'Cannot replace legacy {name} card.')
        else:
            text = replace_once(
                text, anchor, replacement + anchor,
            )
    text = replace_once(text, 'ESTIMATED VALUE / SHARE',
                        'DCF VALUE / SHARE (REVIEWED INPUTS)')
    text = replace_once(
        text, 'const proposals=()=>data.proposals;',
        'const proposals=()=>[...data.proposals,...valuationExtraProposals()];',
    )
    text = replace_once(
        text, 'renderHero();renderInputs();renderChart();renderAudit();',
        'renderHero();renderInputs();renderChart();renderAudit();renderValuation();',
    )
    text = replace_once(
        text, '[book,data]=[BUNDLED_BOOK,BUNDLED_CASE];',
        '[book,data]=[BUNDLED_BOOK,BUNDLED_CASE];initValuationBook();',
    )
    text = replace_once(text, 'query,validate};}catch(e)',
                        'query,validate};bindValuation();}catch(e)')
    text = replace_once(
        text, 'function query(q){const started=',
        "function query(q){if(valuationPayload()?.questions?.questions?.some(x=>x.id===q)){questionDetails(q);return;}const started=",
    )
    text = replace_once(
        text, "function cellValue(id){if(currentCase==='research'&&!complete())",
        "function cellValue(id){if(id.startsWith('WD40_'))return activeEngine().safe(id);if(currentCase==='research'&&!complete())",
    )
    text = replace_once(
        text,
        "const p=proposalFor(id),r=e.safe(id),v=currentCase==='research'&&!complete()?p?p.value:'Review pending':r.error??r.value;",
        'const r=cellValue(id),v=r.error??r.value;',
    )
    text = replace_once(
        text, "$('formula-badge').textContent=book.summary.formulaCount.toLocaleString();",
        "$('formula-badge').textContent=Object.values(book.cells).filter(c=>c.formula).length.toLocaleString();",
    )
    # Permit the already-supported terminal-ROIC branch, with active checks.
    text = text.replace("'Input sheet!B48':'No',", '', 1)
    terminal_check = (
        "const enabled=p.cell==='Input sheet!B48'?v:current('Input sheet!B48');"
        "if(enabled==='Yes'){const roic=p.cell==='Input sheet!B49'?v:current('Input sheet!B49');"
        "if(!(roic>0))return 'Choose a scenario with an explicit terminal ROIC, then edit that assumption.';"
        "if(g/roic<0||g/roic>1)return 'Terminal reinvestment must be between 0% and 100% for this stable-growth case.';}"
    )
    text = replace_once(
        text, "if(typeof p.value==='number'&&!Number.isFinite(v))",
        terminal_check + "if(typeof p.value==='number'&&!Number.isFinite(v))",
    )
    text = replace_once(
        text, "?pct(out.value/e.value('Input sheet!B22')-1)+' vs. reference.'",
        "?pct(out.value/e.value('Input sheet!B22')-1)+' DCF gap to reference (DCF / price − 1).'",
    )
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                         separators=(',', ':')).replace('</', '<\\/')
    text = replace_region(text, 'VALUATION',
                          f'const BUNDLED_VALUATION={encoded};',
                          'class FormulaError extends Error')
    text = replace_region(text, 'VALUATION-CSS',
                          (WEB / 'valuation.css').read_text(), '</style>')
    text = replace_region(text, 'VALUATION-JS',
                          (WEB / 'valuation.js').read_text(),
                          'async function init(){')
    return text


def reverse_grids(inputs: dict) -> list[dict]:
    grids = []
    definitions = [
        ('Flat WACC and terminal ROIC', 'Terminal ROIC', 'Flat WACC',
         [.06, .07, .08, .09, .10], [.08, .15, .20, .25, .30],
         lambda x, y: {'waccInitial': x, 'waccTerminal': x,
                       'terminalExcessReturns': True, 'terminalRoic': y}),
        ('Growth and adjusted EBIT margin', 'Target adjusted EBIT margin',
         'Years 2–5 growth', [.03, .05, .07, .09, .11],
         [.15, inputs['margin1'], .20, .22, .25],
         lambda x, y: {'growth2to5': x, 'targetMargin': y}),
    ]
    for label, row_label, col_label, columns, rows, change in definitions:
        grid = {'label': label, 'rowLabel': row_label,
                'columnLabel': col_label, 'columns': columns, 'rows': []}
        for row in rows:
            values = []
            for col in columns:
                try:
                    values.append(evaluate_dcf({**inputs,
                                                **change(col, row)})['value'])
                except ValueError:
                    values.append(None)
            grid['rows'].append({'input': row, 'values': values})
        grids.append(grid)
    return grids


def build(skip_xlsx: bool = False) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(['node', '--check', str(WEB / 'valuation.js')],
                   check=True, cwd=ROOT, capture_output=True, text=True)
    index = ROOT / 'index.html'
    inputs = load_original_inputs(index)
    scenarios = build_scenarios(inputs)
    methods = get_methods(inputs, scenarios)
    questions = read_json(ROOT / 'models/questions/wd40_questions.json', {})
    measurement = read_json(OUT / 'measurement.json')
    if measurement is None:
        raise ValueError('Run node models/measure.mjs before building.')
    model_hash = source_model_hash(index)
    if measurement.get('sourceModelHash') != model_hash:
        raise ValueError('Workbook or engine changed. Rerun node models/measure.mjs.')
    case = embedded_json(index, 'BUNDLED_CASE')
    measured_proposals = [{
        'id': p['id'], 'cell': p['cell'], 'value': p['value'],
        'operation': p.get('operation', 'override'),
        'sourceIds': p.get('sourceIds', []),
    } for p in case['proposals']]
    if measurement.get('proposals') != measured_proposals:
        raise ValueError('Original proposals changed. Rerun node models/measure.mjs.')
    if abs(scenarios[0]['value'] - measurement['original']['value']) > 1e-8:
        raise ValueError('Python original DCF differs from measured engine.')
    research = read_json(ROOT / 'models/data/research.json', {})
    source_registry = read_json(ROOT / 'models/data/sources.json', {})
    market = read_json(ROOT / 'models/data/market.json', {})
    sources = source_registry.get('sources', []) + research.get('sources', [])
    fingerprint_files = [
        *sorted((ROOT / 'models').glob('*.py')),
        *sorted((ROOT / 'models').glob('*.mjs')),
        *sorted((ROOT / 'models/data').glob('*.json')),
        ROOT / 'models/questions/wd40_questions.json',
        *sorted(WEB.glob('*')),
    ]
    fingerprint = stable_hash({
        'sourceModelHash': model_hash,
        'case': case,
        'measurement': measurement,
        'files': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in fingerprint_files if p.exists()},
    })
    export_path = OUT / 'export-report.json'
    previous = read_json(export_path, {})
    workbook_path = OUT / 'wd40_valuation.xlsx'
    if not skip_xlsx:
        workbook_hash = hashlib.sha256(workbook_path.read_bytes()).hexdigest() \
            if workbook_path.exists() else None
        if (previous.get('buildFingerprint') == fingerprint
                and previous.get('workbookSha256') == workbook_hash
                and workbook_hash is not None):
            export = previous
        else:
            from .export import build_workbook
            export = build_workbook(scenarios, methods, questions, workbook_path)
            export['buildFingerprint'] = fingerprint
            export['workbookSha256'] = hashlib.sha256(
                workbook_path.read_bytes(),
            ).hexdigest()
            export_path.write_text(json.dumps(export, indent=2,
                                               allow_nan=False) + '\n')
    else:
        export = previous if previous.get('buildFingerprint') == fingerprint else {}
    verification = read_json(OUT / 'verification.json', {})
    verified = (verification.get('buildFingerprint') == fingerprint
                and verification.get('status') == 'passed')
    workbook_current = (
        export.get('buildFingerprint') == fingerprint
        and workbook_path.exists()
        and export.get('workbookSha256') == hashlib.sha256(
            workbook_path.read_bytes(),
        ).hexdigest()
    )
    original = scenarios[0]
    payload = {
        'schemaVersion': '1.0', 'buildFingerprint': fingerprint,
        'reference': {**measurement['reference'],
                      **market.get('reference', {}),
                      'price': measurement['reference']['price'],
                      'priceAsOf': measurement['reference']['priceAsOf']},
        'original': original, 'scenarios': scenarios, 'methods': methods,
        'measurement': measurement, 'reverseGrids': reverse_grids(inputs),
        'sources': sources, 'questions': questions, 'research': research,
        'markers': market.get('markers', []),
        'books': export.get('books', []),
        'workbookBase64': base64.b64encode(workbook_path.read_bytes()).decode()
        if workbook_current else None,
        'checks': {
            'pythonOriginal': original['value'],
            'originalEngine': measurement['original']['value'],
            'evaMinusDcf': original['evaMinusDcf'],
            'browserFormulaStatus': 'verified' if verified else 'pending',
            'workbookCurrent': workbook_current,
            'excelStatus': ('Python and browser formula checks pass. '
                            'Fresh Microsoft Excel recalculation has not been performed.'
                            if verified else
                            'Fresh Microsoft Excel recalculation has not been performed.'),
        },
    }
    # This is the same definition graph that is embedded in the browser.
    (OUT / 'valuation.json').write_text(json.dumps(
        payload, indent=2, ensure_ascii=False, allow_nan=False,
    ) + '\n', encoding='utf-8')
    patched = patch_page(index.read_text(encoding='utf-8'), payload)
    if patched != index.read_text(encoding='utf-8'):
        temporary = index.with_suffix('.html.tmp')
        temporary.write_text(patched, encoding='utf-8')
        temporary.replace(index)
    subprocess.run(['node', str(ROOT / 'models/football_field.mjs')],
                   check=True, cwd=ROOT, capture_output=True, text=True)
    preview = ROOT / 'dist'
    preview.mkdir(exist_ok=True)
    (preview / 'index.html').write_text(patched, encoding='utf-8')
    if workbook_current:
        download = preview / 'models/out'
        download.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(workbook_path, download / workbook_path.name)
    elif (preview / 'models/out/wd40_valuation.xlsx').exists():
        (preview / 'models/out/wd40_valuation.xlsx').unlink()
    return {
        'original': original['value'],
        'scenarios': {s['id']: s['value'] for s in scenarios},
        'methods': {m['id']: m['status'] for m in methods},
        'questionCount': len(questions.get('questions', [])),
        'pageBooks': len(payload['books']),
        'workbook': str(workbook_path) if workbook_path.exists() else None,
        'buildFingerprint': fingerprint,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-xlsx', action='store_true')
    options = parser.parse_args()
    print(json.dumps(build(options.skip_xlsx), indent=2))

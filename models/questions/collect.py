'''Download inert public benchmark files and record their content hashes.'''

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'data' / 'benchmarks'
SOURCES = {
    'financebench': {
        'title': 'FinanceBench public annotated sample',
        'revision': 'cc39aeb4afdf33909ee1412188bf89035950c2eb',
        'url': ('https://raw.githubusercontent.com/patronus-ai/financebench/'
                'cc39aeb4afdf33909ee1412188bf89035950c2eb/'
                'data/financebench_open_source.jsonl'),
        'page': 'https://github.com/patronus-ai/financebench',
        'filename': 'financebench.jsonl',
        'format': 'jsonl',
    },
    'finlfqa': {
        'title': 'FinLFQA development / validation set',
        'revision': '22900e97366d0b977b6f37863486bc9828e5bdc0',
        'url': ('https://huggingface.co/datasets/Dragongon/FinLFQA/resolve/'
                '22900e97366d0b977b6f37863486bc9828e5bdc0/'
                'data/validation.json'),
        'page': 'https://huggingface.co/datasets/Dragongon/FinLFQA',
        'filename': 'finlfqa_validation.json',
        'format': 'json',
    },
    'pe-bench': {
        'title': 'PE Bench public Voltaic tasks and rubrics',
        'revision': '4e596185e3d64af6223a158e3fae66a4eb901421',
        'url': ('https://raw.githubusercontent.com/GetCompoundAI/pe-bench/'
                '4e596185e3d64af6223a158e3fae66a4eb901421/'
                'tasks/voltaic.jsonl'),
        'page': 'https://github.com/GetCompoundAI/pe-bench',
        'filename': 'pe_bench_voltaic.jsonl',
        'format': 'jsonl',
    },
    'fincausal': {
        'title': 'FinCausal 2020 Task 2 practice cause-effect spans',
        'revision': '33a933f1bebd3317ab67edcf447c1a333fe879f5',
        'url': ('https://raw.githubusercontent.com/yseop/YseopLab/'
                '33a933f1bebd3317ab67edcf447c1a333fe879f5/'
                'FNP_2020_FinCausal/data/practice/'
                'fnp2020-fincausal2-task2.csv'),
        'page': ('https://github.com/yseop/YseopLab/tree/develop/'
                 'FNP_2020_FinCausal'),
        'filename': 'fincausal_2020_practice.csv',
        'format': 'csv',
    },
    'fintextqa': {
        'title': 'FinTextQA publicly released policy / regulation QA',
        'revision': '51aa9851114adb5972ac9b6adfa662c21c6483dd',
        'url': ('https://raw.githubusercontent.com/AlexJJJChen/FinTextQA/'
                '51aa9851114adb5972ac9b6adfa662c21c6483dd/'
                'manual-qa-regulation%20policy.xlsx'),
        'page': 'https://github.com/AlexJJJChen/FinTextQA',
        'filename': 'fintextqa_policy.xlsx',
        'format': 'xlsx',
    },
}


def download(item, output_dir, refresh=False):
    '''Fetch bytes only; downloaded code and code fields are never executed.'''
    name, source = item
    path = output_dir / source['filename']
    result = {'id': name, **source, 'licenseKnown': False}
    try:
        if path.exists() and not refresh:
            payload = path.read_bytes()
        else:
            request = urllib.request.Request(
                source['url'], headers={'User-Agent': 'Sunesis-benchmark-snapshot/1.0'}
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read()
            path.write_bytes(payload)
        result.update({
            'status': 'available',
            'sha256': hashlib.sha256(payload).hexdigest(),
            'sizeBytes': len(payload),
            'localFile': source['filename'],
        })
    except (OSError, urllib.error.URLError) as error:
        result.update({'status': 'unavailable', 'error': str(error)})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=DATA_DIR)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--only', nargs='+', choices=list(SOURCES))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    selected = [(key, value) for key, value in SOURCES.items()
                if not args.only or key in args.only]
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(
            lambda item: download(item, args.output_dir, args.refresh), selected
        ))
    manifest_path = args.output_dir / 'manifest.json'
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    by_id = {item['id']: item for item in previous.get('sources', [])}
    by_id.update({item['id']: item for item in results})
    manifest = {
        'schemaVersion': '1.0',
        'retrievedAt': datetime.now(timezone.utc).isoformat(),
        'sources': list(by_id.values()),
        'note': (
            'Source snapshots are inert data. Availability does not establish '
            'reuse rights.'
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps([{key: item.get(key) for key in
                       ('id', 'status', 'sizeBytes', 'sha256', 'error')}
                      for item in results], indent=2))


if __name__ == '__main__':
    main()

'''Normalize downloaded benchmark records without executing their contents.'''

import argparse
import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / 'data' / 'benchmarks'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def xlsx_questions(path):
    '''Read only cell values from the released policy workbook using OOXML.'''
    with ZipFile(path) as archive:
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            tree = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            shared = [''.join(item.itertext()) for item in tree]
        for member in sorted(archive.namelist()):
            if (not member.startswith('xl/worksheets/sheet')
                    or not member.endswith('.xml')):
                continue
            tree = ET.fromstring(archive.read(member))
            headers = None
            for row in tree.findall('.//s:sheetData/s:row', NS):
                values = {}
                for cell in row.findall('s:c', NS):
                    address = cell.attrib.get('r', '')
                    column = ''.join(c for c in address if c.isalpha())
                    value = cell.find('s:v', NS)
                    text = value.text if value is not None else ''
                    if cell.attrib.get('t') == 's':
                        text = shared[int(text)]
                    elif cell.attrib.get('t') == 'inlineStr':
                        text = ''.join(cell.find('s:is', NS).itertext())
                    values[column] = text
                if 'question' in values.values():
                    headers = {column: str(value) for column, value in values.items()}
                    continue
                if headers:
                    record = {headers.get(column, column): value
                              for column, value in values.items()}
                    if record.get('question'):
                        yield {
                            'recordId': member + '!row-' + row.attrib['r'],
                            'originalQuestion': record['question'],
                            'company': None,
                            'questionType': 'policy_regulation_qa',
                            'document': record.get('document'),
                            'institute': record.get('institute'),
                        }


def records_for(source, path):
    source_id = source['id']
    if source_id in ('financebench', 'pe-bench'):
        records = [json.loads(line) for line in path.read_text().splitlines() if line]
        for record in records:
            if source_id == 'financebench':
                yield {
                    'recordId': record['financebench_id'],
                    'originalQuestion': record['question'],
                    'company': record['company'],
                    'questionType': record['question_type'],
                    'reasoning': record.get('question_reasoning'),
                    'domainQuestionId': record.get('domain_question_num'),
                }
            else:
                yield {
                    'recordId': record['task_id'],
                    'originalQuestion': record['prompt'],
                    'company': 'Ironvale Digital Infrastructure (fictional)',
                    'questionType': 'deal_work_task',
                    'deliverable': record.get('deliverable'),
                }
    elif source_id == 'finlfqa':
        for record in json.loads(path.read_text()):
            yield {
                'recordId': str(record['id']),
                'originalQuestion': record['question'],
                'questionType': 'long_form_qa',
                'company': None,
                'topic': record.get('topic'),
            }
    elif source_id == 'fincausal':
        with path.open(newline='') as stream:
            reader = csv.DictReader(stream, delimiter=';', skipinitialspace=True)
            for raw in reader:
                record = {key.strip(): value.strip() for key, value in raw.items()
                          if key is not None and value is not None}
                yield {
                    'recordId': record['Index'],
                    'originalQuestion': None,
                    'originalText': record['Text'],
                    'cause': record['Cause'],
                    'effect': record['Effect'],
                    'company': None,
                    'questionType': 'cause_effect_spans',
                }
    elif source_id == 'fintextqa':
        yield from xlsx_questions(path)


def extract(data_dir):
    manifest = json.loads((data_dir / 'manifest.json').read_text())
    merged = []
    counts = {}
    for source in manifest['sources']:
        if source['status'] != 'available':
            counts[source['id']] = 0
            continue
        path = data_dir / source['localFile']
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != source['sha256']:
            source_id = source['id']
            raise ValueError(f'Content hash mismatch for {source_id}')
        rows = list(records_for(source, path))
        counts[source['id']] = len(rows)
        merged.extend({
            'source': source['id'],
            'sourceUrl': source['url'],
            'sourceHash': source['sha256'],
            'licenseKnown': source['licenseKnown'],
            **row,
        } for row in rows)
    return merged, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=DEFAULT_DATA)
    parser.add_argument('--output', type=Path,
                        default=DEFAULT_DATA / 'questions_merged.jsonl')
    args = parser.parse_args()
    records, counts = extract(args.data_dir)
    args.output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                   for row in records))
    print(json.dumps({'counts': counts, 'total': len(records)}, indent=2))


if __name__ == '__main__':
    main()

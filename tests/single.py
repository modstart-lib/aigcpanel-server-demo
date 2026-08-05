# -*- coding: utf-8 -*-
"""
Non-queue (single-shot) mode test.

Starts `run.py` via subprocess with a task config named `*.example.json`.
The SDK treats such configs as test entries: the server processes the first
task and then exits instead of polling the queue (single-shot mode).

Run from the project root:  python tests/single.py
"""

import base64
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(ROOT, '_temp')

RESULT_LINE_RE = re.compile(r'AigcPanelRunResult\[([^\]]+)\]\[([A-Za-z0-9+/=]+)\]')


def main():
    os.makedirs(TEMP_DIR, exist_ok=True)

    # `.example.json` suffix -> single-shot mode (process one task then exit)
    configPath = os.path.join(TEMP_DIR, 'single.example.json')
    taskConfig = {
        'id': 'SingleTts',
        'mode': 'local',
        'modelConfig': {
            'type': 'soundTts',
            'text': '你好，这是一次非队列模式的单次运行。',
            'param': {},
        },
        'setting': {},
    }
    with open(configPath, 'w', encoding='utf-8') as f:
        json.dump(taskConfig, f, ensure_ascii=False, indent=2)

    print('[TEST] run: python -u run.py', configPath)
    result = subprocess.run(
        [sys.executable, '-u', 'run.py', configPath],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=30,
    )
    print(result.stdout)

    assert result.returncode == 0, \
        'single mode should exit cleanly, code={}'.format(result.returncode)
    # Collect every AigcPanelRunResult (device info + task result) and pick
    # the one carrying the generated file url.
    results = []
    for match in RESULT_LINE_RE.finditer(result.stdout):
        try:
            results.append(json.loads(base64.b64decode(match.group(2)).decode('utf-8')))
        except Exception:
            continue
    assert results, 'no AigcPanelRunResult found in output'
    urlResult = next((d for d in results if isinstance(d, dict) and 'url' in d), None)
    assert urlResult, 'no result with url: {}'.format(results)
    assert os.path.isfile(urlResult['url']), 'result file missing: {}'.format(urlResult['url'])
    print('[TEST] PASS: single mode result ->', urlResult)

    os.remove(configPath)


if __name__ == '__main__':
    main()

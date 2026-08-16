# -*- coding: utf-8 -*-
"""
Queue (watch) mode test.

Starts `run.py` via subprocess: the server processes the argv config first,
then keeps polling `aigcpanel-queue/` for new `*.queue.json` tasks. The test
submits several tasks while the server is running, then verifies every task
produced an `AigcPanelRunResult` line and its result file actually exists.

Run from the project root:  python tests/queue.py
"""

import base64
import json
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_DIR = os.path.join(ROOT, 'aigcpanel-queue')
TEMP_DIR = os.path.join(ROOT, '_temp')
EXAMPLE_FILE_DIR = os.path.join(ROOT, 'example-file')

RESULT_LINE_RE = re.compile(r'AigcPanelRunResult\[([^\]]+)\]\[([A-Za-z0-9+/=]+)\]')


def taskConfig(taskId, taskType, **extra):
    modelConfig = {'type': taskType, 'param': {}}
    modelConfig.update(extra)
    return {'id': taskId, 'mode': 'local', 'modelConfig': modelConfig, 'setting': {}}


def submit(name, config):
    """Write a task into the queue directory (consumed by the server)."""
    with open(os.path.join(QUEUE_DIR, name), 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print('[TEST] queued:', name)


def main():
    # ---- seed config: the first task, passed on argv ----
    os.makedirs(TEMP_DIR, exist_ok=True)
    seedPath = os.path.join(TEMP_DIR, 'queue-seed.json')
    seedConfig = taskConfig('QueueSeed', 'soundTts', text='你好，队列模式种子任务。')
    with open(seedPath, 'w', encoding='utf-8') as f:
        json.dump(seedConfig, f, ensure_ascii=False, indent=2)

    # ---- queue tasks (submitted AFTER the server is running) ----
    os.makedirs(QUEUE_DIR, exist_ok=True)
    queuedTasks = [
        ('001_textToImage.queue.json', taskConfig(
            'QueueT2I', 'textToImage', text='A fantasy landscape')),
        ('002_soundClone.queue.json', taskConfig(
            'QueueClone', 'soundClone',
            text='你好',
            promptAudio=os.path.join(EXAMPLE_FILE_DIR, 'nihao.wav'),
            promptText='参考音频提示文字')),
        ('003_asr.queue.json', taskConfig(
            'QueueAsr', 'asr', audio=os.path.join(EXAMPLE_FILE_DIR, 'nihao.wav'))),
        ('004_general.queue.json', taskConfig(
            'QueueGeneral', 'generalImage',
            param={'prompt': '通用模型测试', 'count': 3})),
    ]
    expectedIds = ['QueueSeed'] + [c['id'] for _, c in queuedTasks]

    # ---- start the server via subprocess ----
    print('[TEST] start: python -u run.py', seedPath)
    proc = subprocess.Popen(
        [sys.executable, '-u', 'run.py', seedPath],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
    )

    # Drain stdout in a background thread
    lines = []

    def _reader():
        for line in proc.stdout:
            lines.append(line.rstrip('\n'))

    threading.Thread(target=_reader, daemon=True).start()

    # Give the server a moment to process the seed task and enter polling,
    # then submit the queued tasks.
    time.sleep(2)
    for name, config in queuedTasks:
        submit(name, config)

    found = {}
    urlPaths = set()
    start = time.time()
    timeout = 60
    try:
        while time.time() - start < timeout:
            for line in lines:
                match = RESULT_LINE_RE.search(line)
                if not match:
                    continue
                try:
                    data = json.loads(base64.b64decode(match.group(2)).decode('utf-8'))
                except Exception:
                    continue
                if match.group(1) not in found:
                    # 仅记录业务结果（url/images/files/text/records 等），
                    # 忽略 resultEnv 输出的 Device 设备信息
                    if isinstance(data, dict) and any(
                        k in data
                        for k in ('url', 'images', 'files', 'text', 'records', 'error', 'msg')
                    ):
                        found[match.group(1)] = data
                        print('[TEST] result:', match.group(1), '->', data)
                # 收集结果中的全部文件路径：url（单文件）/ images（图片数组）/ files（文件数组）
                if isinstance(data, dict):
                    for urlKey in ('url',):
                        if data.get(urlKey):
                            urlPaths.add(data[urlKey])
                    for urlKey in ('images', 'files'):
                        urls = data.get(urlKey) or []
                        if isinstance(urls, list):
                            for u in urls:
                                if u:
                                    urlPaths.add(u)
            if set(found) >= set(expectedIds):
                break
            if proc.poll() is not None:
                print('[TEST] server exited early; missing:', set(expectedIds) - set(found))
                break
            time.sleep(0.2)

        missing = set(expectedIds) - set(found)
        assert not missing, 'missing results: {}'.format(missing)
        assert urlPaths, 'no result url found in output'
        for urlPath in urlPaths:
            assert os.path.isfile(urlPath), 'result file missing: {}'.format(urlPath)
            print('[TEST] result file exists:', urlPath)
        # 通用模型结果校验：images（多张）+ text（文字）+ files（附加文件）
        generalResult = found.get('QueueGeneral') or {}
        assert generalResult.get('images'), 'general result missing images'
        assert len(generalResult['images']) == 3, 'general images count mismatch'
        assert generalResult.get('text'), 'general result missing text'
        assert generalResult.get('files'), 'general result missing files'
        print('[TEST] general result OK: {} images, text={!r}, files={}'.format(
            len(generalResult['images']), generalResult.get('text'), len(generalResult['files'])))
        print('[TEST] PASS: {} tasks processed'.format(len(expectedIds)))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        print('[TEST] server stopped')

    # ---- cleanup ----
    for name in os.listdir(QUEUE_DIR):
        os.remove(os.path.join(QUEUE_DIR, name))
    os.remove(seedPath)
    print('[TEST] queue directory cleaned')


if __name__ == '__main__':
    main()

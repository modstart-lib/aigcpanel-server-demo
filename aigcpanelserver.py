# -*- coding: utf-8 -*-
"""
A lightweight, self-contained SDK for AIGCPanel model server integration.

A minimal re-implementation of the official `_aigcpanel.lib` module, built
ONLY from Python standard library + `requests`. The function names/signatures
mirror the official SDK, so `run.py` can be ported to a real project (which
ships the full `_aigcpanel` package) without any changes.

Only the parts needed by the queue (`watchNext`) pattern are kept:
- `appPrepare(name)` : read argv[1] task config, init global state
- `watchNext()`      : first call returns the argv config; when
                       `mode.type == 'watch'` in config.json, keep polling
                       `aigcpanel-queue/*.queue.json` for new tasks
                       (idle window = `mode.watchDelay` seconds)
- `result()`         : emit `AigcPanelRunResult[id][base64json]` to stdout,
                       which is what the launcher / UI parses
- `end()`            : cleanup + exit
"""

import base64
import hashlib
import json
import math
import os
import re
import shutil
import sys
import time
from datetime import datetime

import requests

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

globalConfig = None            # current task config (updated on every watchNext)
globalServerConfig = None      # server config loaded once from config.json
globalWatchNextIsFirst = True  # first watchNext() returns the argv config
fileCleanList = []             # temp files to delete after each task


def root():
    """Project root directory (the directory containing this module)."""
    return os.path.dirname(os.path.abspath(__file__))


def rootPath(path):
    return os.path.join(root(), path)


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(level, msg, *args):
    if not args:
        log_message = '[{}] {} - {}'.format(level, now(), msg)
    else:
        formatted_args = ' '.join(
            jsonStringifyUnicode(arg) if isinstance(arg, dict) else str(arg)
            for arg in args
        )
        log_message = '[{}] {} - {} - {}'.format(level, now(), msg, formatted_args)
    print(log_message, flush=True)


def logInfo(msg, *args):
    log('I', msg, *args)


def logDebug(msg, *args):
    if isDebug():
        log('D', msg, *args)


def isDebug():
    return getEnvBool('AIGCPANEL_SERVER_DEBUG', False)


# ---------------------------------------------------------------------------
# JSON / env helpers
# ---------------------------------------------------------------------------

def jsonStringify(data):
    return json.dumps(data)


def jsonStringifyUnicode(data, indent=None):
    return json.dumps(data, ensure_ascii=False, indent=indent, separators=(',', ':'))


def setEnv(key, value):
    os.environ[key] = value


def getEnv(key, defaultValue=''):
    return os.environ.get(key, defaultValue)


def getEnvBool(key, defaultValue=False):
    value = getEnv(key, defaultValue)
    if isinstance(value, str):
        value = value.lower()
        if value in ['true', '1', 'yes']:
            return True
        if value in ['false', '0', 'no']:
            return False
    return bool(value)


# ---------------------------------------------------------------------------
# File / cache helpers
# ---------------------------------------------------------------------------

def fileEnsureFileDir(pathname):
    pathnameDir = os.path.dirname(pathname)
    if pathnameDir and not os.path.exists(pathnameDir):
        os.makedirs(pathnameDir)
    return pathnameDir


def fileWrite(path, content):
    fileEnsureFileDir(path)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def fileDeleteSafely(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)
    except BaseException:
        pass


def fileExt(pathOrUrl, defaultValue=''):
    pathOrUrl = pathOrUrl.split('?')[0] if '?' in pathOrUrl else pathOrUrl
    parts = os.path.splitext(pathOrUrl)
    return parts[1][1:] if len(parts) >= 2 else defaultValue


def fileCleanAdd(path):
    if not path:
        return
    if isinstance(path, list):
        for p in path:
            fileCleanAdd(p)
        return
    fileCleanList.append(path)


def fileCleanRun():
    global fileCleanList
    for path in fileCleanList:
        if os.path.exists(path):
            fileDeleteSafely(path)
    fileCleanList = []


def contentJson(pathOrUrl):
    with open(pathOrUrl, 'r', encoding='utf-8') as f:
        return json.load(f)


def getCacheRoot(dir='_file'):
    cacheRoot = rootPath('_cache/' + dir)
    os.makedirs(cacheRoot, exist_ok=True)
    return cacheRoot


def localCacheRandomPath(ext='bin'):
    md5 = hashlib.md5(str(time.time()).encode('utf-8')).hexdigest()
    return os.path.join(getCacheRoot(), '{}.{}'.format(md5, ext))


def downloadFileDirect(url, path):
    headers = {'User-Agent': 'AigcPanelServer', 'Referer': url}
    logInfo('LIB.DownloadFileDirect', {'url': url, 'path': path})
    response = requests.get(url, headers=headers, stream=True, timeout=3600)
    response.raise_for_status()
    fileEnsureFileDir(path)
    with open(path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return path


def localCache(pathOrUrl):
    """Return a local copy of pathOrUrl.

    Remote URLs are downloaded into `_cache/_file/` (keyed by md5); local
    paths are returned as-is.
    """
    if not pathOrUrl.startswith('http'):
        return pathOrUrl
    md5 = hashlib.md5(pathOrUrl.encode('utf-8')).hexdigest()
    cachePath = os.path.join(getCacheRoot(), '{}.{}'.format(md5, fileExt(pathOrUrl)))
    if not os.path.exists(cachePath):
        downloadFileDirect(pathOrUrl, cachePath)
    else:
        os.utime(cachePath, (time.time(), time.time()))
    return cachePath


# ---------------------------------------------------------------------------
# Device info (torch optional - falls back to cpu gracefully)
# ---------------------------------------------------------------------------

def platformName():
    return {'darwin': 'osx', 'win32': 'win', 'linux': 'linux'}.get(sys.platform, 'unknown')


def platformIsWin():
    return platformName() == 'win'


def platformIsLinux():
    return platformName() == 'linux'


def platformIsOsx():
    return platformName() == 'osx'


def getDevice():
    try:
        import torch
        if torch.cuda.is_available():
            return 'cuda'
        if torch.backends.mps.is_available():
            return 'mps'
    except Exception:
        pass
    return 'cpu'


def getDeviceName():
    if platformIsOsx():
        return 'MPS'
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_properties(0).name
    except Exception:
        pass
    return 'CPU'


def getDeviceMemorySize():
    if platformIsOsx():
        return math.ceil(int(os.popen('sysctl -n hw.memsize').read()) / (1024 ** 3))
    try:
        import torch
        if torch.cuda.is_available():
            return math.ceil(torch.cuda.get_device_properties(0).total_memory / (1024 ** 3))
    except Exception:
        pass
    return 0


def getCudaVersion():
    if platformIsOsx():
        return None
    try:
        match = re.search(r'CUDA Version: (\d+\.\d+)', os.popen('nvidia-smi').read())
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def getInfo():
    envs = {
        'Device': getDevice(),
        'DeviceName': getDeviceName(),
        'DeviceMemorySize': getDeviceMemorySize(),
    }
    if platformIsWin() or platformIsOsx():
        envs['CudaVersion'] = getCudaVersion()
    return envs


# ---------------------------------------------------------------------------
# Config handling
# ---------------------------------------------------------------------------

def normalConfig(config):
    if 'id' not in config:
        logInfo('LIB.Error', 'Config.id not found')
        exit(-1)
    if 'mode' not in config:
        config['mode'] = 'local'
    if 'setting' not in config:
        config['setting'] = {}
    if 'modelConfig' not in config:
        config['modelConfig'] = {}
    if 'param' not in config['modelConfig']:
        config['modelConfig']['param'] = {}
    logInfo('LIB.Config', config)
    gpu = config['setting'].get('gpu', '')
    if gpu and getDevice() == 'cuda':
        setEnv('CUDA_VISIBLE_DEVICES', str(gpu))
    return config


def setConfig(config):
    global globalConfig
    globalConfig = config
    fileWrite(rootPath('config-last.json'), jsonStringifyUnicode(config, indent=2))


def getServerConfig(key, defaultValue=None):
    global globalServerConfig
    if globalServerConfig is None:
        configFile = rootPath('config.json')
        if not os.path.exists(configFile):
            logInfo('LIB.GetConfig.Error', 'ConfigNotFound', configFile)
            exit(-1)
        globalServerConfig = contentJson(configFile)
    return globalServerConfig.get(key, defaultValue)


def appPrepare(name):
    """Read argv[1] task config, init global state and return (config, ROOT_DIR).

    Must be called exactly once, before the `while watchNext()` loop.
    """
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Usage: python run.py <config.json>')
        exit(-1)
    logInfo('LIB.Start')
    logInfo('LIB.AigcPanelServer', {
        'name': name,
        'version': getServerConfig('version'),
        'mode': getServerConfig('mode'),
        'root': root(),
    })
    config = normalConfig(contentJson(sys.argv[1]))
    setConfig(config)
    logInfo('LIB.Info', getInfo())
    return (config, root())


# ---------------------------------------------------------------------------
# Result output (parsed by the launcher / UI)
# ---------------------------------------------------------------------------

def result(data):
    global globalConfig
    if globalConfig is None:
        raise ValueError('globalConfig is None, cannot log result')
    logInfo('Result[{}][{}]'.format(globalConfig['id'], jsonStringifyUnicode(data)))
    base64Data = base64.b64encode(jsonStringify(data).encode('utf-8')).decode('utf-8')
    logInfo('AigcPanelRunResult[{}][{}]'.format(globalConfig['id'], base64Data))


def resultValue(key, value):
    result({key: value})


def resultEnd():
    fileCleanRun()
    result({'End': True})


def resultEnv():
    result(getInfo())


def urlForResult(url):
    """Prepare a result file path for the launcher.

    - launcher API mode: copy into `launcher-data/` so the launcher's
      embedded API server can serve it
    - schedule mode: prefix with `urlForResult://`
    """
    if getEnvBool('AIGCPANEL_LAUNCHER_API_MODE', False) and os.path.exists(url):
        launcherDataRoot = os.path.abspath('launcher-data')
        os.makedirs(launcherDataRoot, exist_ok=True)
        newPath = os.path.join(launcherDataRoot, '{}.{}'.format(int(time.time() * 1000), url.split('.')[-1]))
        shutil.copy(url, newPath)
        return newPath
    if globalConfig and globalConfig.get('mode') == 'schedule':
        return 'urlForResult://' + url
    return url


# ---------------------------------------------------------------------------
# Text filter
# ---------------------------------------------------------------------------

def filterText(text, filters=['emoji', 'invisible']):
    import unicodedata
    newText = text
    if 'emoji' in filters:
        emoji_pattern = re.compile(
            "[" "\U0001F600-\U0001F64F" "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF" "\U0001F1E0-\U0001F1FF"
            "\U00002700-\U000027BF" "\U0001F900-\U0001F9FF"
            "\U00002600-\U000026FF" "\U00002B50-\U00002B55" "]+",
            flags=re.UNICODE)
        newText = emoji_pattern.sub(r'', newText)
    if 'invisible' in filters:
        newText = ''.join(
            ch for ch in newText
            if unicodedata.category(ch)[0] not in ('C', 'Z') or ch in (' ', '\n', '\t'))
    if newText != text:
        logInfo('LIB.FilterText.Changed', {'from': text, 'to': newText})
    return newText


# ---------------------------------------------------------------------------
# Queue mode (the core of the "continuous queue" pattern)
# ---------------------------------------------------------------------------

def _isExampleConfigEntry():
    """Test convenience: configs named `*.example.json` run once and exit."""
    return len(sys.argv) > 1 and '.example.json' in os.path.basename(sys.argv[1])


def watchNext():
    """Yield the next task config, or None when the loop should stop.

    - The FIRST call returns the config passed on argv[1].
    - When `mode.type == 'watch'` in config.json, subsequent calls poll the
      `aigcpanel-queue/` directory for `*.queue.json` files for up to
      `mode.watchDelay` seconds; the first queued file is consumed, removed
      and returned as the next task.
    - Otherwise (or after the watch window expires) returns None, ending the
      while loop so the process can exit via `end()`.
    """
    global globalWatchNextIsFirst
    if globalWatchNextIsFirst:
        globalWatchNextIsFirst = False
        return globalConfig
    # In test mode (example config path in argv), skip polling and exit.
    if _isExampleConfigEntry():
        return None
    mode = getServerConfig('mode')
    if not mode or mode.get('type', 'once') != 'watch':
        return None
    watchDelay = mode.get('watchDelay', 10)
    start = time.time()
    watchQueueDir = rootPath('aigcpanel-queue')
    os.makedirs(watchQueueDir, exist_ok=True)
    while time.time() - start < watchDelay:
        queueFiles = sorted(f for f in os.listdir(watchQueueDir) if f.endswith('.queue.json'))
        if not queueFiles:
            time.sleep(1)
            continue
        watchConfigFile = os.path.join(watchQueueDir, queueFiles[0])
        time.sleep(0.1)  # avoid reading a half-written file
        config = normalConfig(contentJson(watchConfigFile))
        setConfig(config)
        logInfo('LIB.WatchNext', config)
        try:
            os.remove(watchConfigFile)
        except BaseException as e:
            logInfo('LIB.WatchNext.RemoveError', {'file': watchConfigFile, 'error': str(e)})
            return None
        return config
    return None


def end(killChildren=False):
    fileCleanRun()
    logInfo('LIB.End')
    exit(0)

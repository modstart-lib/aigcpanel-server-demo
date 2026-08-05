# -*- coding: utf-8 -*-
"""
Queue-based model server demo.

Entry: python -u run.py <config.json>    (or: python -u -m run <config.json>)

This module demonstrates the "continuous queue" pattern used by real
AIGCPanel model integrations:

    config, ROOT_DIR = aigcpanelserver.appPrepare(name)
    while config := aigcpanelserver.watchNext():
        ... process one task ...
    aigcpanelserver.end()

Flow:
1. `appPrepare()` loads the initial task config from argv[1] and sets up
   the global environment.
2. The `while watchNext()` loop processes the initial task, then keeps
   polling the `aigcpanel-queue/` directory for new `*.queue.json` files
   (keep-alive window = `mode.watchDelay` seconds in config.json).
   The process stays alive between tasks, so a heavy model is loaded once
   and reused across all queued tasks.
3. When no new task arrives within `watchDelay`, `watchNext()` returns
   None, the loop exits and `end()` cleans up.

The lightweight SDK lives in `aigcpanelserver.py` (a self-contained
re-implementation of the official `_aigcpanel.lib` module).
"""

import os
import shutil
import time

import aigcpanelserver


def run():
    config, ROOT_DIR = aigcpanelserver.appPrepare('server-demo')
    modelConfig = config['modelConfig']

    # Demo assets used to mock real model inference results
    exampleFileDir = os.path.join(ROOT_DIR, 'example-file')
    soundFile = os.path.join(exampleFileDir, 'nihao.wav')
    videoFile = os.path.join(exampleFileDir, 'short.mp4')
    imageFile = os.path.join(exampleFileDir, '1.png')

    # NOTE: In a real project, load the (heavy) model HERE once and reuse it
    # across all queued tasks. That is exactly why the queue mode exists:
    # the process stays alive so the model is not reloaded for every task.

    while config := aigcpanelserver.watchNext():
        modelConfig = config['modelConfig']
        # Report device info (device type/name/memory) for every task
        aigcpanelserver.resultEnv()

        # Normalize optional params
        if 'param' not in modelConfig:
            modelConfig['param'] = {}
        if 'seed' not in modelConfig['param']:
            modelConfig['param']['seed'] = 0

        aigcpanelserver.logInfo('TaskBegin', {
            'id': config['id'],
            'type': modelConfig.get('type'),
        })

        ########### 语音合成 soundTts ###########
        # See ./example-config/soundTts.json
        if modelConfig.get('type') == 'soundTts':
            text = aigcpanelserver.filterText(modelConfig['text'])
            time.sleep(1)  # mock inference time
            resultPath = aigcpanelserver.localCacheRandomPath('wav')
            shutil.copy(soundFile, resultPath)
            aigcpanelserver.result({'url': aigcpanelserver.urlForResult(resultPath)})
            aigcpanelserver.resultEnd()
            continue

        ########### 语音克隆 soundClone ###########
        # See ./example-config/soundClone.json
        if modelConfig.get('type') == 'soundClone':
            text = aigcpanelserver.filterText(modelConfig['text'])
            # Download/cache the prompt audio when it is a remote URL
            promptAudio = aigcpanelserver.localCache(modelConfig['promptAudio'])
            time.sleep(1)  # mock inference time
            resultPath = aigcpanelserver.localCacheRandomPath('wav')
            shutil.copy(soundFile, resultPath)
            aigcpanelserver.result({'url': aigcpanelserver.urlForResult(resultPath)})
            aigcpanelserver.resultEnd()
            continue

        ########### 视频合成 videoGen ###########
        # See ./example-config/videoGen.json
        if modelConfig.get('type') == 'videoGen':
            aigcpanelserver.localCache(modelConfig['video'])
            aigcpanelserver.localCache(modelConfig['audio'])
            time.sleep(1)  # mock inference time
            resultPath = aigcpanelserver.localCacheRandomPath('mp4')
            shutil.copy(videoFile, resultPath)
            aigcpanelserver.result({
                'url': aigcpanelserver.urlForResult(resultPath),
                'Duration': 1.0,
            })
            aigcpanelserver.resultEnd()
            continue

        ########### 语音识别 asr ###########
        # See ./example-config/asr.json
        if modelConfig.get('type') == 'asr':
            aigcpanelserver.localCache(modelConfig['audio'])
            time.sleep(1)  # mock inference time
            records = [
                {'start': 0.0, 'end': 3.0, 'text': '你好，欢迎使用 AIGCPanel。'},
                {'start': 3.0, 'end': 6.0, 'text': '这是第二句识别内容。'},
            ]
            aigcpanelserver.result({'records': records})
            aigcpanelserver.resultEnd()
            continue

        ########### 文生图 textToImage ###########
        # See ./example-config/textToImage.json
        if modelConfig.get('type') == 'textToImage':
            time.sleep(1)  # mock inference time
            resultPath = aigcpanelserver.localCacheRandomPath('png')
            shutil.copy(imageFile, resultPath)
            aigcpanelserver.result({'url': aigcpanelserver.urlForResult(resultPath)})
            aigcpanelserver.resultEnd()
            continue

        ########### 图生图 imageToImage ###########
        # See ./example-config/imageToImage.json
        if modelConfig.get('type') == 'imageToImage':
            aigcpanelserver.localCache(modelConfig['image'])
            time.sleep(1)  # mock inference time
            resultPath = aigcpanelserver.localCacheRandomPath('png')
            shutil.copy(imageFile, resultPath)
            aigcpanelserver.result({'url': aigcpanelserver.urlForResult(resultPath)})
            aigcpanelserver.resultEnd()
            continue

        ########### 文生视频 textToVideo ###########
        # See ./example-config/textToVideo.json
        if modelConfig.get('type') == 'textToVideo':
            time.sleep(1)  # mock inference time
            resultPath = aigcpanelserver.localCacheRandomPath('mp4')
            shutil.copy(videoFile, resultPath)
            aigcpanelserver.result({'url': aigcpanelserver.urlForResult(resultPath)})
            aigcpanelserver.resultEnd()
            continue

        ########### 图生视频 imageToVideo ###########
        # See ./example-config/imageToVideo.json
        if modelConfig.get('type') == 'imageToVideo':
            images = modelConfig.get('images', [])
            for image in images:
                aigcpanelserver.localCache(image)
            time.sleep(1)  # mock inference time
            resultPath = aigcpanelserver.localCacheRandomPath('mp4')
            shutil.copy(videoFile, resultPath)
            aigcpanelserver.result({'url': aigcpanelserver.urlForResult(resultPath)})
            aigcpanelserver.resultEnd()
            continue

        raise Exception('未知的模型类型: {}'.format(modelConfig.get('type')))

    aigcpanelserver.end()


if __name__ == '__main__':
    run()

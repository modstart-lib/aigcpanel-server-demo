import json
import base64
import shutil
import sys
import time
import os

# 解析输入配置文件
config = json.loads(open(sys.argv[1], 'r').read())
# 保存文件到临时文件，方便调试
with open('config-last.json', 'w') as f:
    f.write(json.dumps(config, indent=4, ensure_ascii=False))

def cacheRandom(ext):
    cacheRoot = os.path.abspath('_cache')
    if not os.path.exists(cacheRoot):
        os.makedirs(cacheRoot)
    return os.path.join(cacheRoot, str(time.time()) + '.' + ext)

def printResult(key, value):
    global config
    print('AigcPanelRunResult', {key: value})
    print(f'AigcPanelRunResult[{config["id"]}][' + base64.b64encode(json.dumps({key: value}).encode()).decode() + ']')

# 公共输出
## 检测是否支持 Cuda 输出给前端
printResult('UseCuda', True)

########### 语音合成 ###########
## config = { "id": "SoundTts_999", "mode": "local", "modelConfig": { "type": "soundTts", "param": {}, "text": "你好" }, "setting": {} }
if config['modelConfig']['type'] == 'soundTts':
    print('正在合成', 'config=', config)
    time.sleep(30)
    resultPath = cacheRandom('wav')
    shutil.copy('./example/nihao.wav', resultPath)
    print('合成完成', resultPath)
    ## 语音合成输出结果
    printResult('url', resultPath)
########### 语音合成 ###########

########### 语音克隆 ###########
## config = { "id": "SoundClone_999", "mode": "local", "modelConfig": { "type": "soundClone", "param": {}, "text": "你好", "promptAudio": "/path/to/audio/xxxxx.wav", "promptText": "参考音频提示文字" }, "setting": {} }
if config['modelConfig']['type'] == 'soundClone':
    print('正在克隆', 'config=', config)
    time.sleep(3)
    resultPath = cacheRandom('wav')
    shutil.copy('./example/nihao.wav', resultPath)
    print('克隆完成', resultPath)
    ## 语音克隆输出结果
    printResult('url', resultPath)
########### 语音克隆 ###########

########### 视频合成 ###########
## config = { "id": "VideoGen_999", "mode": "local", "modelConfig": { "type": "videoGen", "param": {}, "video": "/path/to/video/xxxxx.mp4", "audio": "/path/to/audio/xxxxx.wav" }, "setting": {} }
if config['modelConfig']['type'] == 'videoGen':
    print('正在生成', 'config=', config)
    time.sleep(3)
    resultPath = cacheRandom('mp4')
    shutil.copy('./example/short.mp4', resultPath)
    print('生成完成', resultPath)
    ## 视频合成输出结果
    printResult('url', resultPath)
########### 视频合成 ###########

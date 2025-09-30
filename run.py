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
## 输出基本信息
## 设备类型 cpu / gpu
printResult('Device', 'cpu')
## 设备名称
printResult('DeviceName', 'Nvidia GeForce RTX 4090')
## 设备内存大小，单位 GB
printResult('DeviceMemorySize', 24)
## CUDA 版本
printResult('CudaVersion', '12.8')

########### 语音合成 ###########
## 参考 ./_example/soundTts.json
print('正在合成', 'config=', config)
time.sleep(30)
resultPath = cacheRandom('wav')
shutil.copy('./example/nihao.wav', resultPath)
print('合成完成', resultPath)
## 语音合成输出结果
printResult('url', resultPath)
########### 语音合成 ###########

########### 语音克隆 ###########
## 参考 ./_example/soundClone.json
print('正在克隆', 'config=', config)
time.sleep(3)
resultPath = cacheRandom('wav')
shutil.copy('./example/nihao.wav', resultPath)
print('克隆完成', resultPath)
## 语音克隆输出结果
printResult('url', resultPath)
########### 语音克隆 ###########

########### 视频合成 ###########
## 参考 ./_example/videoGen.json
print('正在生成', 'config=', config)
time.sleep(3)
resultPath = cacheRandom('mp4')
shutil.copy('./example/short.mp4', resultPath)
print('生成完成', resultPath)
## 视频合成输出结果
printResult('url', resultPath)
########### 视频合成 ###########

########### 语音识别 ###########
## 参考 ./_example/soundAsr.json
print('正在识别', 'config=', config)
time.sleep(3)
resultText = '你好，欢迎使用AIGC面板。'
print('识别完成', resultText)
## 语音识别输出结果
printResult('text', resultText)
########### 语音识别 ###########

########### 文生图 ###########
## 参考 ./_example/textToImage.json
print('正在生成', 'config=', config)
time.sleep(3)
resultPath = cacheRandom('png')
shutil.copy('./example/1.png', resultPath)
## 文生图输出结果
printResult('url', resultPath)
########### 文生图 ###########

########### 图生图 ###########
## 参考 ./_example/imageToImage.json
print('正在生成', 'config=', config)
time.sleep(3)
resultPath = cacheRandom('png')
shutil.copy('./example/1.png', resultPath)
## 图生图输出结果
printResult('url', resultPath)
########### 图生图 ###########


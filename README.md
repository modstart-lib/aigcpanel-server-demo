# aigcpanel 示例

## osx

```shell
eval "$(conda shell.bash hook)"
conda create --prefix ./_aienv -y python=3.10
conda activate ./_aienv
```

## linux

```shell
eval "$(conda shell.bash hook)"
conda create --prefix ./_aienv -y python=3.10
conda activate ./_aienv
```

## windows

```shell
conda 'shell.powershell' 'hook' | Out-String | Invoke-Expression
conda create --prefix ./_aienv -y python=3.10
conda activate ./_aienv
```
# 基于MinerU的解析API
- MinerU的CPU版本
- 基于FastAPI的PDF、图片解析接口
- 利用Redis实现队列机制
## 安装
使用conda安装:
```bash
conda create -n mineru-api python=3.10
conda activate mineru-api
pip install -r requirements.txt
```
## 启动
```bash
bash start.sh
```
> 本项目依赖Redis实现队列管理、工作优先度，修改`app.py`和`worker.py`中的`Redis`连接信息适配你的`Redis`服务。
# 自定义 YOLO / SAM 的 Nuclio 适配入口

官方 YOLO11n 检测已在本机 GTX 1660 Ti 上通过真实部署验收：
CVAT 调用推理、保存 5 个检测框、重新读取核对成功，记录位于 `utils/lan/verification.json`。
这是单个模型的实测结果；其它版本、分割任务及自定义权重仍需逐个验证。

## 接入范围

| 模型 | engine | task | 条件 |
| --- | --- | --- | --- |
| 原版 YOLOv5 v7.0 | yolov5 | detect / segment | 独立 YOLOv5 运行环境；修改网络结构的分支需额外依赖 |
| YOLOv8、YOLO11、YOLO12、YOLO26 | ultralytics | detect / segment | 权重须可由指定版本的 Ultralytics 加载 |
| SAM、SAM2、SAM3 | sam | interactive | 权重须符合 Ultralytics SAM 加载器的格式和文件命名 |

不是根据 `.pt` 后缀就能保证兼容。原版 YOLOv5 与 YOLOv5u 格式不同；
自定义层、不同训练分支和导出文件要另做验证。当前入口仅接受 `.pt/.pth`。
YOLO12 分割架构可训练，但官方没有发布对应预训练分割权重，需要提供训练好的 checkpoint。

SAM 入口实现点击/框提示的单图交互分割，输出 CVAT 掩膜。
未接入 SAM3 文本概念提示和 SAM2/SAM3 视频记忆跟踪。
SAM/SAM2/SAM3 的权重文件名要保留加载器识别信息，如 `sam_b.pt`、`sam2.1_b.pt`、`sam3.pt`；
原生 Meta 权重不保证可直接使用。SAM3 权重下载可能需要事先申请访问权限。

## 准备和部署

原始文件按模型名集中管理，目录结构和新增操作见[本地模型管理说明](../../utils/lan/models/README.zh-CN.md)。
下文使用仓库内独立模型目录；权重也可以放在其它位置并传入其真实路径。

以下在 **Ubuntu / WSL 终端**执行。先按 [局域网说明](../../utils/lan/README.zh-CN.md)启动 CVAT。
确认 Ubuntu 中 `docker info` 可用。安装与本仓库 Nuclio dashboard 一致的 **nuctl 1.16.3**，
参考 [Nuclio release](https://github.com/nuclio/nuclio/releases/tag/1.16.3)
与 [CVAT 官方步骤](https://docs.cvat.ai/docs/administration/community/advanced/installation_automatic_annotation/)。
启用 GPU 前必须确认 Docker Desktop / WSL 能在容器里使用 NVIDIA GPU。

准备真实的 `labels.json`，内容例如 `["person", "car"]`，顺序严格对应模型类别 ID。
运行时会与 checkpoint 类别名称核对，不一致会拒绝加载，避免静默错标。

例如部署 YOLO11 分割（路径替换为你自己的）：

```bash
cd /mnt/e/workspace/annotation/cvat
python3 serverless/custom-models/prepare.py \
  --name my-yolo11-seg --engine ultralytics --task segment \
  --weights utils/lan/models/my-yolo11-seg/weights/best.pt \
  --labels utils/lan/models/my-yolo11-seg/labels.json --gpu
```

脚本只生成部署目录并复制权重，不会下载依赖或启动模型。
接着执行脚本输出的 `nuctl create project` / `nuctl deploy` 命令。
同名目录已存在会拒绝覆盖。换模型时使用不同 `--name`。
构建过程中会从网络下载 Python 包，首次耗时和空间占用取决于网络与依赖。

YOLOv8/11/12/26 检测用 `--task detect`；分割用 `--task segment`。
原版 YOLOv5 改为 `--engine yolov5`，使用对应检测/分割权重。
如需匹配训练环境，可以指定 `--ultralytics-version X.Y.Z`；默认 8.4.184，
是查询时已发布的版本，不代表所有自定义训练版本都兼容。
默认固定 PyTorch 2.5.1 / torchvision 0.20.1，GPU 使用 CUDA 11.8 wheels，以保留本机 Turing 显卡支持。
若模型训练依赖更新版本的 PyTorch（尤其 SAM3 或自定义层），需为该模型调整独立构建环境并重新验证。

部署 SAM2 示例，SAM / SAM3 使用相同入口并换成对应权重：

```bash
python3 serverless/custom-models/prepare.py \
  --name my-sam2 --engine sam --task interactive \
  --weights utils/lan/models/my-sam2/weights/sam2.1_b.pt --gpu
```

CPU 运行省略 `--gpu`。每个函数一个 worker；多个 GPU 函数仍会各自常驻显存。
6GB 显存建议逐个验证，勿将全部模型同时装载。若要卸载某个函数：

```bash
nuctl delete function my-sam2 --platform local
```

权重会复制进生成目录并打包进本机模型镜像，部署后保留原始权重备份。

## 网页验收

1. `nuctl get functions --platform local` 显示 `ready`。
2. CVAT 的 Models 页面列出对应模型。
3. YOLO：创建匹配标签的测试任务，执行自动标注、核对标签映射和置信度阈值。
4. 分割：检查原图边缘、非正方形图片、孔洞及多个实例，保存后重新打开核对掩膜。
5. SAM：在任务的 AI 交互工具中选择模型，测试正点、负点和框提示。
6. 用另一台电脑的独立账号验证访问和 Job 权限。

当前已完成 YOLO11n 检测的上述验收，分割和 SAM 验收尚未执行。
出现加载错误需提供训练仓库版本与依赖，
而不是反复更换文件扩展名。基础协议测试可在本机直接执行：

```powershell
python serverless/custom-models/test_adapter.py
```

接口参考：[Ultralytics 模型矩阵](https://docs.ultralytics.com/models/)、
[YOLOv5 推理](https://github.com/ultralytics/yolov5/tree/v7.0/segment)、
[SAM API](https://docs.ultralytics.com/reference/models/sam/model/)、
[SAM3](https://docs.ultralytics.com/models/sam-3/)。

# 按模型管理本地文件

每个部署模型使用一个独立目录，目录名建议与 CVAT 中的模型名（`--name`）一致。
同一架构的不同训练版本、检测与分割权重也应分开命名，避免覆盖已有模型。

```text
utils/lan/models/
├── README.zh-CN.md
├── yolo11n-demo/                  # 已部署的官方检测示例
│   ├── weights/yolo11n.pt
│   ├── labels.json
│   ├── coco.yaml
│   └── samples/bus.jpg
├── sam-vit-b/                    # 已部署，原版 SAM，CPU
│   ├── weights/sam_b.pt
│   └── source.json
├── mobile-sam/                   # 已部署，轻量 SAM，GPU
│   ├── weights/mobile_sam.pt
│   └── source.json
├── sam2-1-tiny/                  # 已部署，SAM2.1 Tiny，GPU
│   ├── weights/sam2.1_t.pt
│   └── source.json
├── factory-yolo11-det-v1/         # 自己训练的检测模型（示意）
│   ├── weights/best.pt
│   ├── labels.json
│   └── samples/test.jpg
├── factory-yolo11-seg-v1/         # 分割模型（示意）
│   ├── weights/best.pt
│   ├── labels.json
│   └── samples/test.jpg
└── sam2-interactive/              # 交互分割模型（示意）
    ├── weights/sam2.1_b.pt
    └── samples/test.jpg
```

目前实际存在的模型是 `yolo11n-demo`、`sam-vit-b`、`mobile-sam`、`sam2-1-tiny`；
其余目录是命名示例，按需创建。三款 SAM 的使用和部署见 [SAM 使用说明](../SAM使用说明.md)。
`labels.json` 是类别名称数组，例如 `["person", "car"]`，顺序必须与训练类别 ID 一致。
SAM 不需要类别表，权重文件名应保留加载器需要的命名；YOLO 权重可以叫 `best.pt`。
可另存一份模型说明，记录训练版本、用途和类别定义。

## 添加自己的 YOLO 模型

1. 在 Windows 创建 `utils\lan\models\factory-yolo11-det-v1\weights`，将权重放为 `best.pt`。
2. 在该模型目录中放入正确的 `labels.json`，可在 `samples` 中存放测试图片。
3. 打开 Ubuntu / WSL，在仓库根目录生成独立的部署目录：

```bash
cd /mnt/e/workspace/annotation/cvat
python3 serverless/custom-models/prepare.py \
  --name factory-yolo11-det-v1 --engine ultralytics --task detect \
  --weights utils/lan/models/factory-yolo11-det-v1/weights/best.pt \
  --labels utils/lan/models/factory-yolo11-det-v1/labels.json --gpu
```

4. 在同一个 WSL 终端部署。以下使用已安装的本地 nuctl 和部署示例建立的 Docker 客户端配置：

```bash
export DOCKER_CONFIG="$PWD/utils/lan/docker-client"
export DOCKER_HOST=unix:///var/run/docker.sock
utils/lan/bin/nuctl get project cvat --platform local >/dev/null 2>&1 || \
  utils/lan/bin/nuctl create project cvat --platform local
utils/lan/bin/nuctl deploy --project-name cvat --platform local \
  --path serverless/custom-models/generated/factory-yolo11-det-v1 \
  --file serverless/custom-models/generated/factory-yolo11-det-v1/function.yaml
```

5. 模型 ready 后在 CVAT 的 Models 页面确认，并在独立测试任务中验证类别和标注结果。

分割模型将 `--task` 改为 `segment` 并使用分割权重；原版 YOLOv5 使用 `--engine yolov5`。
SAM 使用 `--engine sam --task interactive`，省略 `--labels`。
完整的依赖条件、SAM 示例与验收步骤见[模型接入说明](../../../serverless/custom-models/README.zh-CN.md)。

**只放入文件夹不会让 CVAT 自动识别模型，仍需生成部署目录并部署。**
添加新版本时换一个目录名与 `--name`；生成器会拒绝覆盖已经存在的同名部署目录。
现有 6GB 显存应逐个部署和验收，多个 GPU 模型同时运行会分别占用显存。

## 本地文件、部署副本与 Git

- 此处保存原始权重、类别和测试素材，用于备份和再次部署。
- `serverless/custom-models/generated/<模型名>/` 是生成的部署副本；已经按模型分目录。
- 运行中的模型使用容器镜像内的权重。移动本地原始文件不会更新运行中的模型；换权重需要重新生成和部署。
- 本目录仅这份说明提交到 Git；所有模型子目录均被忽略。请单独备份权重和类别表。

旧版平铺目录升级时，将 `yolo11n.pt` 移到 `yolo11n-demo/weights/`，
`labels.json` 与 `coco.yaml` 移到 `yolo11n-demo/`，`bus.jpg` 移到 `yolo11n-demo/samples/`。
已有的部署目录、模型容器和 CVAT 任务无需更名。

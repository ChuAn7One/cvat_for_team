# SAM / SAM2 交互分割

## 当前已部署的模型

| CVAT 中的模型名 | 权重目录 | 运行设备 | 本机公交车样例耗时 |
| --- | --- | --- | --- |
| `sam-vit-b` | `models/sam-vit-b/weights/sam_b.pt` | CPU | 约 7～8 秒/次 |
| `mobile-sam` | `models/mobile-sam/weights/mobile_sam.pt` | GPU | 约 0.3～0.5 秒/次 |
| `sam2-1-tiny` | `models/sam2-1-tiny/weights/sam2.1_t.pt` | GPU | 约 0.4～0.5 秒/次 |

耗时是单人、单张公交车图片的 API 实测，首次调用可能更慢；多人使用时需要排队。
默认建议先用 `sam2-1-tiny`，再用 `mobile-sam` 或 `sam-vit-b` 对比边界。
SAM ViT-B 使用 CPU，为现有 YOLO 和两款轻量分割模型留出显存。

三款模型均通过 CVAT API 的正点、正负点、框提示测试，9 个掩膜保存并重新读取核对通过。
现成测试任务：[SAM 公交车分割测试](http://192.168.110.92:8080/tasks/2)。
测试掩膜会相互重叠，分别对应各模型和提示方式，不是九个不同物体。
浏览器中实际点击的效果和你的业务图片仍需人工检查。

## 在网页中使用

1. 使用桌面版 Chrome/Edge，进入自己的 Job。
2. 点击左侧魔法棒 **AI assistance**，切换到 **Prompting** 页签。
3. **Model** 选择 `sam2-1-tiny`，**Label** 选择物体类别。
4. 点击 **Add visual prompts**。
5. 在物体内部用鼠标左键添加正点，等待分割预览。
6. 如果把背景也选进来了，用右键在不需要的区域添加负点；可继续添加正点修正漏选。
7. 轮廓满意后点击上方 **Done**，或按 **N** 完成当前物体。确认 Objects 中出现新对象。
8. 点击 Save 或按 Ctrl+S，等待保存完成。

也可以先打开 **Start with a bounding box**，再点击 **Add visual prompts**，
框住目标后等待分割；框提示可以单独使用，不强制要求额外点击正点。
如需多边形，打开 **Convert masks to polygons**，并检查转换后的轮廓精度。
新任务的标签建议使用 `Any` 或 `Mask`；选择明确的业务类别，例如“零件”“裂纹”。
Worker 账号需要加入组织并被分配对应的 Job。

SAM 根据你给出的点或框分割当前物体，不会自动判断业务类别。
整批检测框预标注继续使用 YOLO 的 **Automatic annotation / Auto-labeling**。
当前 SAM 接口处理单图，不包含 SAM2 视频记忆跟踪或文本提示。

## 重新部署与验收

以下在 Ubuntu / WSL 中执行，先启动 Docker Desktop 和 CVAT：

```bash
cd /mnt/e/workspace/annotation/cvat
bash utils/lan/deploy-sam.sh
python3 utils/lan/verify-sam.py
```

也可以只部署一款：

```bash
bash utils/lan/deploy-sam.sh sam2-1-tiny
python3 utils/lan/verify-sam.py --models sam2-1-tiny
```

`prepare-sam.py` 从 Ultralytics 官方 v8.4.0 权重发布下载文件，核对文件大小与 SHA256，
保存到各自的模型目录，再生成独立 Nuclio 部署目录。
已有权重会先校验再复用；不覆盖校验失败的文件。
已有生成目录会核对配置与权重后复用，源码变化时需要更新对应生成目录中的适配代码再重新部署。
模型文件与运行报告不进入 Git，仓库只保存脚本、权重清单与文档。

验收脚本会创建或复用专门的 `SAM interactive deployment check - bus` 任务，
**替换该测试任务中的标注**，不要把这个任务用于正式工作。
本机记录在 `utils/lan/sam-verification.json`，任务 ID 记录在 `.sam-state.json`。
新电脑的任务 ID 可能不同，以脚本输出为准。

已部署的模型会随 Docker 容器重启恢复，无需每次开机重新下载和部署。
若显存不足，先减少同时调用的人数或停止闲置模型容器，不要再一次性添加大号 GPU 模型。

来源：[SAM](https://docs.ultralytics.com/models/sam/)、
[MobileSAM](https://docs.ultralytics.com/models/mobile-sam/)、
[SAM2](https://docs.ultralytics.com/models/sam-2/)、
[官方权重发布](https://github.com/ultralytics/assets/releases/tag/v8.4.0)。

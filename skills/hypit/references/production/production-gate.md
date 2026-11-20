# 生成前只检查真实输入

原全量门禁和独立审查链已移除；不再创建preproduction/workflow/allocation/review冻结包，不为每个镜头运行开发测试。

默认runninghub_h3.py submit只核对真实request/prompt、选镜、图片/音频绑定与上传回执、4–15秒时长、default实例和空视频槽，然后发送检查过的确切字节。production_gate.py仅兼容旧命令，内部调用同一轻量检查，不导入审查/五文档/工作流检查器，也不调用模型或测试。

内容保留直接在完整目标分镜和实际采用/剪辑里核对；生成成功不代表画风、表演或节奏合格。单镜/邻镜/整场到最终出口仍检查实际声画、当前Agent音频观察、后期和残留问题。方法见[生产简表](short-drama-production.md)。

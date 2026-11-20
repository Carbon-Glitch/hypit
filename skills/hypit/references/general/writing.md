# 通用Agent创作

当前Agent直接完成口播、播客、街访、榜单、讲解、屏幕演示和MG设计。按[通用索引](index.md)读命中的格式与手艺，保留用户目标、事实和已有素材，直接写现有Brief/Treatment、文案、场景或工程文件；不套短剧源表和26列分镜。

图像与视听判断使用Agent中当前可用的能力。无法听取声音时，用[波形与本地测量](../production/gemini-audio-review.md)推进粗定位；词义、音色和听感尚不能确认的内容注明即可，不另接外部模型。

旧批次若需要自动收集输入，仍可在原请求设置 `creative_mode:"general"` 和 `format`，运行 `write_drama_documents.py run` 导出当前Agent上下文；该命令不再调用服务。无需这一步的任务直接创作。

媒体生成继续使用既定H3与内置imagegen；格式、构图、节奏与声音由当前Agent主动决定。

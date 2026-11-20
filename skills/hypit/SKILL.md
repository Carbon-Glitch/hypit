---
name: hypit
description: Direct, recreate and produce videos from briefs, references or supplied media; use for 短剧、口播/UGC、双人播客、街访、榜单比较、产品与屏幕演示、旁白讲解、MG动效、字幕声音后期，以及Hypit原生工程。按需路由并保留本地创作与生产定制。
---

# Hypit · 按作品需要组织创作

**观众体验与有表现力的视听优先。** 从当前材料和委托出发，大胆选择表演、机位、构图、运镜、图形、声音与剪辑。先判断作品由人物行动、直接表达、对话、旁白、屏幕证据还是图形变化推动；只加载当前需要的格式与手艺，同一作品可以组合多种形态。

## 先到当前任务的入口

| 当前任务 | 读取与继续 |
| --- | --- |
| 短剧/漫剧、剧情复刻改编、续集 | [本地短剧工作流](references/creation/local-drama-workflow.md)，沿用源表、分镜、资产、H3和EDIT |
| UGC、单人口播、创作者直面镜头 | [口播](references/general/references/playbooks/formats/talking-head.md) |
| 双人播客、对谈、访谈反应 | [双人播客](references/general/references/playbooks/formats/two-person-podcast.md) |
| 街访、偶遇式采访 | [街访](references/general/references/playbooks/formats/street-interview.md) |
| 榜单、排序、清单、比较板 | [榜单比较](references/general/references/playbooks/formats/ranking-listicle.md) |
| 主讲人配演示、图解或动态图形 | [视觉讲解](references/general/references/playbooks/formats/presenter-led-explainer.md) |
| 旁白配产品、手部、B-roll或屏幕 | [旁白主导](references/general/references/playbooks/formats/narration-led-demo.md) |
| 网站/软件/终端操作、录屏与教程 | [屏幕演示](references/general/references/playbooks/craft/screen-demonstrations.md)与[捕获](references/general/references/production/browser-capture.md) |
| MG、标题、图表、卡片或纯视觉动画 | [图形构图](references/general/references/playbooks/craft/graphic-compositions.md)、[动效](references/general/references/playbooks/craft/motion-graphics.md) |
| 独立图片编辑、字体、字幕、声音、剪辑或素材操作 | [通用任务索引](references/general/index.md)，直接完成该项 |
| SVML/SVS/SVRun、组件、Runtime、Studio或原生工程 | [新版原生生产](references/general/references/production/index.md)；已有旧工程沿其当前版本继续 |

非短剧任务直接进入对应入口，不先补短剧源表或26列分镜。混合形式各读命中的页；没有现成格式时，按该作品的观看关系组织，不必硬归类。参考解读、创作、素材、合成与反馈可按实际依赖交错推进。

## 本地定制继续生效

创作、拉片判断、分镜、提示词、审查与后期决定都由[当前Agent直接完成](references/creation/document-writing.md)，使用Agent内可用的模型能力，不再要求外部写作、听审或转写模型。听不了就用[波形、能量、静音与响度](references/production/gemini-audio-review.md)辅助粗定位，注明未听取并继续制作。

需要生成视频时仍沿用 RunningHub MiniMax H3、default实例、目标图片/按需音频参考，视频槽保持空；资产生成优先用内置imagegen，媒体生成备用沿现有选择。已有素材剪辑、录屏和MG按其实际工具完成。

前期节奏、情绪与关键反应接到真实源窗；[剪辑接口](references/production/editing-and-finishing.md)、[音乐](references/production/music-selection.md)、[字幕](references/production/caption-direction.md)、缓存和恢复继续复用。上游Kit、Provider和Studio是按需能力，不自动替换当前服务、安装运行时或迁移旧工程，细节见[本地执行约定](references/general/local-overrides.md)。

写作优先描述具体要出现和发生的内容。普通创作与技术选择主动完成；真正改变目标、既定体验或已授权范围时再提出选择。实际结果与计划分开，项目事实留在已有所有者，避免平行副本。

# H3写法：把当前镜头写成可见、可听的过程

日常写作使用本页；特殊格式查[官方Ref2VA](h3-prompts/ref-en.md)或[官方Base](h3-prompts/base-en.md)。原文保留供查证，按任务选读。运行中的MiniMax H3采用实际绑定的目标图片/按需音频，default实例；视频槽保持空。

## Ref2VA六段

字段名及顺序固定，英文写导演说明，台词/歌词/画内文字保留原语言。

| 字段 | 只负责这一件事 |
| --- | --- |
| `subject_definitions` | 定义本块实际引用的人、地、物及素材职责。`<Subject N>`可以来自多图；只为提供身份的图在主体定义中引用，作为具体画面锚点的图才另列`<Picture N>`。音频标明声线/复用职责及对应说话人。 |
| `summary` | 一小段任务和主要关系，前缀按真实用途用`[reference generation]`，确有画面锚点/音频时组合`keyframe completion`、`audio reference`或`audio reuse`。 |
| `retention_analysis` | 每项参考的适用镜次、保留内容与强度。视觉用`fully_preserved / partially_preserved / attribute_transfer / weak_reference`；音频用`fully_copy / partially_copy / reference / weak_reference`。声线参考用`reference`；`fully_copy`指整段音频作为完整最终音轨。 |
| `detailed_description` | 开头用一两句定本块画风与必要光态；随后按播放顺序写构图、行动/接触、听者、揭示、声音和退出。 |
| `overall_soundscape` | 持续环境、物理声音与非语言人声；事件同步的声音在正文发生处写，完整对白只在正文出现一次。全片明确静音时用`N/A`。 |
| `non_diegetic_music` | 生成画面中实际需要的观众配乐：配器、节奏与动态；独立配乐由后期完成时写`N/A`。 |

标签按真实输入顺序编号，图片/音频各自从1开始。`<Subject N>`代表可复用内容，`<Picture N>`代表图或画面锚点。先给静态事实一个明确载体，再集中描述本镜变化。

## 镜头、对白与时间

第一镜写`[Shot 1]`；后续切镜写`[Shot N] At MM:SS.mmm, ...`，切点递增且在本次时长内。说话者按首次实际发声顺序使用稳定`(S1)`等ID，合说可用`(S1,S2)`；人物表演/声线在标签外，逐字台词写`<d>[Chinese] 原句</d>`等。音频参考绑定沿用该说话人ID；retention只写参考职责。

台词跨切时两端使用`<scenetrans>`并说明声音延续；实际设计在片尾截断的话使用`<cutoff>`。VO使用`says in an off-screen voiceover`，对应画内人物在该段嘴唇保持闭合。画内可见文字用英文双引号包原文。完整句子、串行动作、必要反应共同决定负载。

时间戳是生成计划，动作内优先写“接触后、松手时、看见后”等因果触发；实际返回后依据真实发声和动作定切点。Ref2VA生成任务中，官方通常建议 **detailed_description这一段为350–500英文词**，不含另外五段；单镜不自动构成缩短理由。对白密集时优先容纳完整发声时间线，编辑任务随复杂度调整；这不是所有模式、每切或每个短镜的硬性词数门槛。先展开有效导演决定，再删重复，不用身份绑定篇幅代替过程。详见[调度展开](h3-dense-direction.md)。

## 摄影、光照和质感

**运镜写起终画面。** 起始取景→触发→相机行为→观众看见的变化→停点。Push/Pull是机位前后移动，Zoom是变焦；Pan/Tilt是转动，Truck/Pedestal是平移/升降；Arc、Tracking、Static、Shake、POV、Roll按实际用途写成句子。幅度/速度只在影响本镜时补充。固定镜头明确稳定构图，人物按戏正常表演。

需要推轨视差时写出相机经过的近景与背景关系；转焦写“先清楚谁→由什么触发→谁转清楚、谁变虚”。给移动留足起始取景空间，终点保住脸、手或证物。积极组合推拉、横移、升降、环绕、变焦和焦点，写清触发、路径、速度变化及构图落点，让运动产生情绪和感官体验。

**光照写结果。** 实际光源/世界方向→软硬与明暗关系→脸或关键物件的受光→动作中的变化。已接受场景图提供基础光时只交代本镜差异。反打继承同一世界光源，画面左右随机位改变。角色身份板的棚拍光与现场光分别处理。

**质感跟已选画风。** 相机、镜头和胶片词可作为风格线索，同时展开可见特征，例如细颗粒、柔和高光过渡、轻微光晕或阴影色调；全片统一颗粒/调色可交后期。器材名是弱风格提示，具体取景/焦点/光照仍写明。

## 每句话占用注意力都应有作用

默认只写要出现、要发生和实际需要保持的内容。省略泛化防御清单、重复质量口号，以及工具已保证的限制。只有当前参考图确有冲突、故事有隐藏/首次揭示边界，或某种错误已在本镜发生且会破坏结果时，才用一条具体、限定范围的排除句；同一条件放在所属段一次。参考选择的`deny`可以为空。

身份/服装等已绑定事实保留必要识别句；summary负责概括，正文负责新过程。来源论证、内部验收和工具操作留在工程。写完顺读一次，直接修冲突和重复。

## 诊断时按症状处理

运镜偏弱先查实际输入与起终取景，再看场景板是否把视点/构图约束得过紧；按本镜地理需要调整参考职责或选图。精确接触/复杂动作失败时先简化一次生成承担的动作链或补覆盖。已有可用表演尽量由剪辑解决时长与衔接。

## 其他模式

Base/T2VA、I2VA、FL2VA、L2VA使用三段：`integrated_multimodal_description`、`overall_soundscape`、`non_diegetic_music`。I2VA/FL2VA/L2VA的首/尾帧对齐首行及有效时长按[官方Base](h3-prompts/base-en.md)原样使用；具体输入模式取决于当前已验证接口。Ref2VA构图参考按软约束判断，首帧像素是否锁定由实际模式决定。

## 方法依据

[MiniMax官方Skill](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)规定格式与基本摄影语言；本页压缩执行信息，官方副本留供查证。
[Loop Forge摄影实验](https://loopforge.cc/projects/h3-camera-shots/)及[器材词对照](https://raw.githubusercontent.com/loopforge0/minimaxh3-shots-skills/main/.claude/skills/h3-camera-shots/references/gear.md)支持优先描述画面结果；其量化/采样设置与本机路线有差异，病例用于定位风险。
本机short-drama的lighting-craft、camera-audio-continuity和performance-action-timing提供光位+受光结果、运镜动机和按景别选择表演的写法。公开病例及证据边界见[方法记录](../../creation/drama-method-sources.md)。

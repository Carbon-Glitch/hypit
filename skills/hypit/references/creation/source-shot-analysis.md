# 原片逐镜分析：25列主表

源事实写入SOURCE_SHOTS.csv与SOURCE_CONTEXT.json。按实际切镜建稳定ID，全范围建立因果、知情与铺垫兑现关系；关键动作、听者和揭示再局部密读。原片时长由入点、出点计算。

使用[25列模板](../../assets/source-shots-template.csv)。有内容才填；无关的可选列留空，尚未查明的内容写`UNKNOWN:原因`，已知不适用也可写`N/A:原因`。观察用`OBS:`、解释用`INF:`；共同事实引用`@SC01.look`等已有记录，当前变化在行内展开。

## 列的职责

| 列 | 写到能指导复刻的程度 |
| --- | --- |
| 镜头ID | 稳定镜号，切镜/插入镜依实际画面登记 |
| 场次段落与EX | 场次及实际依赖的跨镜体验单元 |
| 入点 / 出点 | 源时钟的半开区间[start,end)，覆盖委托范围 |
| 叙事任务与知情变化 | 本镜推进什么、观众和人物何时得知什么 |
| 时空与在场关系 | 实际地点/时间、谁在场、谁对谁行动 |
| 起终状态与连续性 | 入镜→出镜，持续造型、伤势、持物和后果 |
| 景别机位与透视 | 起终取景、视点/高度/角度、可见空间观感 |
| 构图景层与焦点 | 注意中心、遮挡、景深/转焦如何变化 |
| 运镜与注意路径 | 相机何时怎样动、让观众依次看到什么 |
| 空间轴线与视线 | 世界锚点、相对关系、视线/运动方向 |
| 行动接触与物理过程 | 刺激→行动→接触/转移→后果；关键中间状态 |
| 表演与同步反应 | 主体起峰收与听者/旁观者同期行为 |
| 角色策略与关系变化 | 如何争取/回避/试探，权力或亲疏怎样改变 |
| 逐字台词与文字依据 | 完整源台词、说话人及听证/字幕依据 |
| 声音表演 | 语气/重音/呼吸/节奏；稳定声线引用公共记录 |
| 同期声与环境声 | 接触声与持续声床，远近/混响/左右声场 |
| 音乐与有意义静默 | 本段进入/发展/退出、对白让位与静默职责 |
| 声桥与声画同步 | 声音跨切、动作/揭示触发及未完句 |
| 画面文字与特效过程 | 文字原文及出现/可读/退出、可见特效过程 |
| 光色材质与气氛 | 光源/受光、曝光变化、实际颜色/材质/气氛 |
| 转场切点与节奏 | 边界事实、为何此刻切、匹配/停顿的作用 |
| 导演作用与体验机制 | 哪些具体过程产生期待/反差/兑现，删弱会损失什么；解释与证据对应 |
| 制作贡献索引 | 稳定detail/obligation ID及真实字段指针，由工具取得正文 |
| 证据未知与复查 | 实际媒体/区间/查看方式、未决点和下一次具体回查 |

填表时把同一事实放在其主要职责列，其余引用即可。多镜共享音乐段、人物声线、空间和EX放在SOURCE_CONTEXT；本镜音乐只写阶段变化。音乐可与对白、动作声同时存在。

## 阅读与交接

先验证镜头边界，再看实际运动、前后镜和声音。联系表与[source_review](source-review.md)帮助定位；疑点加密抽帧。听音按[实际音频分析](../production/gemini-audio-review.md)逐场完成，返回事件时间换回源时钟。

细节精度取决于观看作用。例如“递盒后收回”应分清对方是否已接触、谁仍持有、听者反应何时发生；稳定背景只引用。低信息的静帧或音频统计用于定位，完整声画观察支持对应结论。

目标设计通过源SH/义务ID承接。本次变换、可拍动作与后期选择写入目标STORYBOARD，当前H3只接选镜及其依赖。

## 制作贡献索引与上下文

同一行的`制作贡献索引`保留现有JSON结构，`fields`指向上表真实列名。例如以下局部结构：

```json
{"details":[{"id":"SH01.D1","dimension":"interaction","importance":"critical","temporal":true,"requires_generation":true,"fields":["行动接触与物理过程","表演与同步反应"],"obligations":[{"id":"SH01.O1","fields":["行动接触与物理过程"],"checks":["visual","motion"]},{"id":"SH01.O2","fields":["表演与同步反应"],"checks":["visual","motion"]}]}],"inventories":[{"id":"SH01.X1","family":"audience_experience","details":["SH01.D1"],"fields":["表演与同步反应"]}],"context_fields":{}}
```

每条实际贡献有可检验的义务；details与五类inventories沿用plot/dialogue/shot_language/director_intent/audience_experience。dialogue另有准确text/speaker/language，text来自台词列。ID全局稳定。普通共享背景可在context_fields说明归属；戏剧变化指向obligations。空白、UNKNOWN和N/A不制造虚构贡献。

SOURCE_CONTEXT：`version=1`；`media/review`引用实际文件和sha256；`source_interval`为委托范围；`records`保存公共/E/EX/卖点/声线/音乐；`dependencies`为必要文本引用；实际缺席的inventory类别在`observed_absence`引用已有观察依据。

`source_shots.py`机械生成source v3，写作器从表和context读实际正文。独立导出：

```text
python <skill>/scripts/source_shots.py SOURCE_SHOTS.csv SOURCE_CONTEXT.json --output source.json
```

## 旧表与迁移

读取器兼容旧49列源表、44列目标表。新表以25/26列为默认；旧文件修订沿原表头，显式迁移另存：

```text
python <skill>/scripts/shot_tables.py migrate source SOURCE_SHOTS.csv --output SOURCE_SHOTS.v2.csv
python <skill>/scripts/shot_tables.py migrate target STORYBOARD.csv --output STORYBOARD.v2.csv
```

迁移先检查旧源时长，再将同组原文原样放入带`[[旧字段]]`标记的单元格，旧贡献指针继续解析到对应原文。这个标记用于旧资料保真，新写作直接写紧凑的新列内容。采用新路径后重建执行包/引用哈希，已有任务回执和素材继续保留。

# 源贡献到实际成片：现有字段映射

只在追查漏项、旧工程恢复或执行包编译时读。事实链是：SOURCE_SHOTS/SOURCE_CONTEXT → STORYBOARD → SHOT_PACKET/REFERENCE_PLAN → 实际H3请求/EDIT → 采用区间/最终出口。中间无需手写allocation、transfer、content-review或workflow冻结包。

## 源侧

源表`制作贡献索引`指向本行真实字段与SOURCE_CONTEXT公共/E/EX记录。`source_shots.py`机械生成source v3：details、obligations、plot/dialogue/shot_language/director_intent/audience_experience五类inventories及原文件版本。写作/执行包从这些指针取得实际原文。结构详见[源表](../creation/source-shot-analysis.md)。

观察、解释、未知分开。未听不是无声；无某类贡献需有实际读取依据。源目录来自原片，不从改编计划反推。源内容只在证据更正时更新。

## 目标侧

26列STORYBOARD直接记录源镜号/义务、具体目标行动、完整台词、导演/观众作用、起终状态、声音及model/post职责。拆并镜可以，必要贡献和发生顺序仍能找到；新增单独标明，不抵扣丢失项。普通复刻无需再写目标剧本或五类target inventory。

H3正文和实际绑定承载本块应生成的作用；精确图形/音乐等由可执行EDIT承载。静态图不能代替动作全过程，提示词有一句话不能证明素材已演出来。最终检查真实采用区间和出口，见[接受证据](acceptance-evidence.md)。

## 旧项目

旧allocation/transfer/source v2留作读取线索，不再补齐其字段或升级版本来解锁生产。恢复时找到原始源表/主稿、实际任务和采用媒体，迁入当前队列所需的真实输入；缺源证据则补相应范围。当前`source_contract`仍核对源v3机械投影，提交由[轻量生产检查](production-gate.md)核对真实请求与输入。它们不能替代源义理解或艺术验收。

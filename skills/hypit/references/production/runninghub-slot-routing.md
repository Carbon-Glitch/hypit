# RunningHub H3：图片/音频与默认实例

当前制作固定instanceType=default，视频参考停用；应用schema里仍可有VIDEO节点，实际请求全部清空。原片/已生成片段只用于本地分析和对照，承接用实际采用出口的单帧。用户实测视频参考造成原画风迁入，因此不能以“只迁移动作”的文字重新启用它。

## 准备

    python <skill>/scripts/runninghub_h3.py discover --host <已授权站点> --app-id <应用ID> --output route.json

已有当前schema可传schema选项，复用已授权账户。物理槽按schema枚举；只选择实际需要的图片/音频，不要求填满。典型应用有6图、3音频和1个停用视频槽。角色四宫格负责身份/当前造型，场景总览/按需机位图负责空间与基础光线，当前状态图负责实际动作后果，单张镜头图负责当前构图/接触/道具状态。格图不是硬首帧。

音频按声线参考或明确的原信号复用分配，不能把混合轨称为分轨。单片2–15秒，音频合计最多15秒；按需提取：

    python <skill>/scripts/runninghub_h3.py clip source.mp4 --start 12 --end 16 --kind audio --output voice.wav

视频裁切命令仅供本地取证/剪辑，不能绑定生成。原片的动作、表演、摄影、切镜节奏在详细分镜和H3正文中具体重建；新画风以目标资产与色卡为准。

## 计划、提示词与绑定

    python <skill>/scripts/runninghub_h3.py plan reference-selection.json --output REFERENCE_PLAN.json

selection含route、packet和media职责选择；每项id/slot/roles/accepted/asset/review和control.allow/deny来自实际资料。计划机械编号Picture/Audio，作者接同一计划与选中图写官方六段提示词，不另抄绑定清单。默认实例；视频项在规划和上传前拒绝。

    python <skill>/scripts/runninghub_h3.py prepare execution-selection.json --job jobs/SH01-v1

execution-selection可只给version、reference_plan、prompt、duration、reference_quotes和必要controls，继承原资产分配。没有计划时沿用完整media结构。四至十五秒输出，镜头/对白/反应须装入实际块时钟。上传按站点+内容hash缓存，回执一天到期则重传，不能制造资源值；原请求/回执保存供恢复。参考检查不证明生成已符合预期。

## 默认提交

    python <skill>/scripts/runninghub_h3.py submit --job jobs/SH01-v1 --route route.json
    python <skill>/scripts/runninghub_h3.py query --job jobs/SH01-v1 --route route.json

submit只检查prepared/request/作者prompt、绑定与上传回执、实际时长/选镜、default实例和空视频槽，不要求独立review或五文档/全量冻结包。检查后的确切bytes进入transport，旧PLUS/ULTRA或视频输入也会被拒绝。旧package/review参数仅兼容已有命令，不触发全量门禁。

已有task直接恢复查询，submit-started状态不明不重复付费。SUCCESS下载并ffprobe实际输出；返回素材仍需单镜→镜对→整场采用，风格必须与资产对照，后期及最终出口检查照常。具体生产原则见[简表](short-drama-production.md)，声音实听及离线恢复见[当前Agent](gemini-audio-review.md)。

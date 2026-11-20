# 复用执行、按状态调度与增量后期

普通制作使用现有25列源表、26列目标分镜、必要设计/资产和EDIT。机器选择、执行包和队列从这些资料派生，不新增创作或审批环节。先复用本项目已验证的账户/route、声线、色卡、素材和工具；只补当前集真正变化的内容。

## 默认执行入口

`episode_runner.py`复用当前H3适配器，承担机械准备、批量提示词请求装配、实际提交/恢复、共享上传缓存和并发补位。它不会替代实际看图、采用表演或声画验收；下载完成只是素材返回，动态后继仍由真实观察状态解锁。

```text
python <skill>/scripts/episode_runner.py stage EPISODE.json
python <skill>/scripts/episode_runner.py writing EPISODE.json --blocks B01,B02 --batch scene-01 --output writing-request.json
python <skill>/scripts/write_drama_documents.py run writing-request.json
python <skill>/scripts/episode_runner.py run EPISODE.json --watch 600
python <skill>/scripts/episode_runner.py finish EPISODE.json
```

当前Agent直接写入并回读目标提示词，无需外部作者或逐项授权。可选的writer run只整理上下文；旧成功批次可恢复原结果。同场景/共同依赖的若干块可一起写，完整正文仍逐块输出；每个单元的图片/音频编号和状态独立。超长场景按实际输出容量拆批，不强制全集一次写完。

EPISODE.json是从现有选择机械派生的队列视图；最小形状如下，示例并发数须换成本次账号已知值，未知默认1：

```json
{
  "version":1,"route":"../route/adapter-route.json","concurrency":2,
  "blocks":[{
    "id":"B01","job":"jobs/B01","duration":10,
    "packet":{
      "scope":"当前场景的完整选镜","storyboard":"STORYBOARD.csv",
      "source_table":"SOURCE_SHOTS.csv","source_context":"SOURCE_CONTEXT.json",
      "selected_shots":["SH01"],"owners":["DESIGN.md"]
    },
    "media":[{
      "id":"character","slot":"image-1","asset":"assets/character.png",
      "review":"assets/character.review.json","accepted":true,"roles":["identity_reference"],
      "control":{"allow":["identity"],"deny":["sheet background","fixed pose"]}
    }],
    "task":"按已定分镜与实际参考职责写本块完整六段提示词"
  }]
}
```

路径相对该队列文件；file/sha256记录也可直接使用。packet沿用原selection字段，支持owners、owner_slices、adoptions、shared_state和必要依赖。`media`沿用现有reference-selection；不为运行器重新造资产登记。原创在顶层与packet写source_kind=original，省去源表。`writing_inputs`可携带当前场景的必要完整原文；输出预算可用writing_max_output_tokens指定。

已有prepared作业只需列id/job；运行器验证原请求后恢复/提交，不重建。新块先stage生成SHOT_PACKET/REFERENCE_PLAN，再由指定作者写prompt；prepare只机械补入精确参考控制与缺失状态短语到官方retention_analysis，保留原始prompt与编译回执，不改台词或故事。新作业共享本集上传缓存，实际输入检查、default实例和空视频槽保持有效。

`after:["B01"]`表示等待该任务下载；`requires:["states/SH01.json"]`表示等待实际采用/其他输入。真正动态交接还须在packet.adoptions写相应观察记录，路径可先声明、文件回来后再冻结哈希。目录/占位文件本身不证明状态成立，packet仍核对真实来源。稳定事实按下节处理，不能用一个冗长after链代替状态判断。

## 队列推进与恢复

运行器在`.hypit-run/state.json`保留任务位置与状态，循环查询已提交任务、下载结果并补空位；轮询休眠最多30秒，可在生成期间继续其他已授权工作。`--watch`是本次持续运行的时间范围，到期保存状态退出，下次同命令恢复。缺prompt、缺观察或需修输入时返回具体位置，由执行者继续相应制作，不制造人工审批。

同一任务有receipt/taskId就查询原任务；提交状态不明时保留并占用相应槽位，不重复付费。明确421队列满且没有taskId的拒绝会归档后退避重试；804/813、未知状态、网络异常或超时不冒充失败。账号之外的排队/并发无法从本队列推断，不升级实例、不取消未知任务。已失败任务要改方法/输入并建明确修复版本，不循环重抽。

完成采用和导演精剪后，队列的finishing:[{edit:"EDIT.json",output:"delivery/final-v1.mp4"}]引用既有EDIT；finish调用原finish_drama，保留渲染/对白回执，导出编译后时钟的SRT和本地outputs索引。字幕/无字等已定版本可列多项并共享同目录渲染缓存；不猜测哪些图层应删。实际声画回查与具体残留仍进入既有DELIVERY，不把outputs索引当艺术通过。

所用独立音乐有真实asset/许可侧车时，finish同时汇总本作.music-credits.txt与来源索引；音乐文件/hash不对应时不冒用该记录。真实曲库的检索/下载/试听接入见[音乐资源](music-resources.md)。

## 只把会改变的事实变成等待边

天气、服装、既有伤势或固定布局等确实不变的事实，可用已有图像review复用。目标行可标stable_keys，selection.shared_state按场景/键指向实际已接受review；编译器核对图像字节、实际state_facts和完整前后目标跨度。跨度内有该键的changes、reset或未分类镜头时，仍等待真实前镜；实际采用已存在且矛盾时不允许用稳定事实遮盖。

门/书开闭、道具数量、持物/落点、起身/坐下和关键后果等实际变化继续承接已采用结果。导演准备与普通提示词可提前做；会受结果影响的构图/绑定在真实状态返回后完成。未知保留，不把planned_exit当已观察事实。详细字段见[空间交接](spatial-continuity.md)。

## 一份事实只送一次

writer会机械去掉REFERENCE_PLAN与SHOT_PACKET完全相等的continuity正文副本，明确引用本请求内已提供的完整正文，保留原文件/hash追溯。批量execution_units对相同文件/版本去重，完整源25列、目标26列、EX依赖、准确台词、未知与实际图片控制不删。相似但不同的内容不会合并。

稳定规则与必要原文切片复用，动态状态放后；服务端缓存只看真实usage，不为缓存添加无用长文。已付费返回、本地转录、实际图/音频观察和渲染片段按源字节/区间/参数恢复，不用路径相同冒充内容没变。

## 粗剪提前，修复选对方法

素材陆续返回就形成当前场景可播放粗剪；一次场景导演回合同时决定表演、反应、节奏、音乐/停乐和关键效果，不等所有局部修完再给整体分配时间。适合目标氛围的音乐获取/试听与生成并行，真实文件、乐句/交接和尾音落入同一EDIT；识别原曲不在默认关键路径上。

微缩、多物体交互或精确文字等高风险点在分镜/构图阶段选可控表达，先检查必要同框与尺度。修复时比较现成后期、局部H3覆盖和有依据的镜头改组；没有已验证方案时，不默认现场开发逐帧抠像/跟踪器。两次针对性修复无改善就换方法，在已授权预算内保留最好结果。核心体验、关键反应和连戏义务不因此删掉。

优先渲染相关范围/代理与必要图层，沿用finish_drama缓存；采用稳定后输出最终版本。只改声查相应声段，只改图查相应画段，切点/速度/整体混音改变时回查相关声画及邻接；未变部分复用同版本有效证据。最终编码文件的完整对白、关键状态、累计节奏和声画观察仍完成；技术成功不当审美通过。

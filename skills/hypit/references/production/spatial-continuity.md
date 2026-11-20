# 空间、持物与实际状态交接

跨镜地点、反打、持物/转交或动作后果影响下一镜时读。先锁共同空间，再承接当前状态，再确定本机位；最后看实际镜对。仅RunningHub H3 default、图片/按需音频、空视频槽。方法用于执行，不新增独立审查或多份创作文档。

## 空间依据与三种左右

跨镜地点默认一张[3/4总览](../creation/drama-reference-sheets.md)，只补实际机位/状态图，九宫格按需。简单平面图负责推理；复杂遮挡/多人交叉反复失败时才用3D白模导出静态机位图。720图是环视背景，不等于完整可平移几何；要互动的椅子/门/杯不要只烘焙在背景里。规划图先派生干净的目标画风图，不把箭头、白模和格线当成最终画面。

人物解剖左右手、世界位置/地标和屏幕左右分别记录。世界事实/持物手持续；正反打的屏幕投影按camera推导。不要把screen_side等投影键写进持久facts；有意跨轴、时间跳跃可以成立，但目标必须说明其可读作用。

## 在现有分镜保存一个小交接

25列源表继续完整解构，26列目标表不加列、不缩过程。指定作者在有实际依赖的“跨镜依赖与补拍风险”单元里加入以下紧凑JSON，note保留本镜风险正文。普通无依赖镜头不填空模板。

```text
@continuity {"scene":"ROOM","camera":{"id":"CAM-B","view":"From the doorway facing the table","screen_positions":{"father":"frame-left"}},"predecessor":"SH01","entry":{"cup.hand":"anatomical left hand","chair.pose":"overturned"},"visible_keys":["cup.hand","chair.pose"],"changes":{},"note":"关键物件不得随反打换手或复原"}
```

entry是本镜必要预期；changes是动作将改变的键；未改变事实从前镜继承，画外对象不清零。visible_keys可只列本镜可见关键事实，省略时视为全部；未知事实重新入画前补清楚证据。camera.view与事实值采用可直接入H3的简短英文表达，作者在真实提示词对应段保留这些短语，不能只传私有ID。没有前镜的新场从已接受设计/图像建立初始状态。
CSV中的JSON单元格须正确转义逗号和双引号；初始镜头直接省略predecessor，不填NONE。
位置本身影响后镜时，同时记chair.location、cup.relative_to等稳定地标关系，例如“on the floor beside the doorway side of the table”；只写椅子倒地不能保证落点不漂移。按当前剧情需要选键，不为全部摆件建坐标库。

同一请求内后镜可引用前一目标镜号，机械承接planned_exit，标为within_request_planned_transition；这是规划，不是已生成事实。跨请求引用前镜必须有实际观察。明确省略/新场可加reset:{kind:time_jump/new_scene/authorized_transition,reason:实际原因}，不为物件穿帮伪造时间跳跃。

若依赖仅为已经接受且在完整跨度内不变的事实，可在该目标行标stable_keys:["street.weather","qiu.costume"]，packet-selection用shared_state:{"STREET":{"street.weather":{file,sha256},"qiu.costume":{file,sha256}}}指向原有图像review。review需accepted:true、observer、实际asset及对应state_facts。编译器查看逻辑前镜到当前镜的完整目标行：有相关changes、不同entry、reset或未分类行便不允许复用。全部必要entry/visible事实已覆盖时可先准备/并行，不必等相邻镜；实际已采用状态存在且冲突时仍拒绝。持物、倒地、开闭、数量等有后果变化继续等实际结果，不为加速把动态事实改写为稳定。

旧表可在原packet-selection的continuity:{镜号:同结构}做一次机械投影，并附basis为实际目标行的原文引用；同一镜不得同时有行内和外置两份权威。新创作优先行内写，不另造连戏剧本。

## 实际采用与观察

```text
python <skill>/scripts/scene_continuity.py capture candidate.mp4 --start 0.2 --end 5.8 --times 0.3,3.5,5.5 --output evidence/SH01
```

只提取实际采用区间的帧；整段生成末帧、废弃尾巴不能冒充出口。结果物件不可见时，补动作完成后的最近清楚帧，结合仍有效状态，不凭脸部特写猜椅子位置。打开这些实际图后，在原采用/观察记录中写所见，先观察再比目标，不能复制“应该倒地”成事实。机器输入示例（file/hash均机械取真实值）：

```json
{"scene":"ROOM","shot":"SH01","manifest":{"file":"evidence/SH01/frames.json","sha256":"<真实哈希>"},"observed_facts":{"cup.hand":"anatomical left hand","chair.pose":"overturned"},"evidence":{"cup.hand":["F3"],"chair.pose":["F3"]},"observer":"当前代理对实际帧的观察","unknown_keys":[]}
```

```text
python <skill>/scripts/scene_continuity.py observe actual-observation.json --output adopted-state.json
```

这两份JSON是现有作业的观察输入/派生状态，不是新增创作文档或额外审查。已有review JSON也可使用continuity段；参考图review可用下文同名围栏。observe可加previous:{file,sha256}继承未变化/暂未可见事实；每项新事实必须有实际帧ID，来源与输入哈希留存。unknown_keys不是复原许可。可选packet:{file,sha256}将实际观察与当前镜planned_exit比较，变化键未观察到就保留unknown/需修复。

原packet-selection增加adoptions:{"SH01":{file,sha256}}，指向实际前镜记录。SHOT_PACKET自动携带当前事实、当前机位、预期变化、来源和依赖；当前Agent收到实际正文，不能靠远端会话记忆。若实际结果与后镜entry冲突，先修前镜或在委托内正式修订后镜；不能改观察值骗过检查。改变采用区间/出口画面/相关事实时更新受影响记录，静态独立镜头继续并行。

## 输入图的可见状态与冲突

在已存在的图像review JSON内记录asset:{file,sha256}、state_facts:{键:实际所见值}；Markdown review可追加一个continuity围栏保存同一对象，不另写评审链。例如：

```continuity
{"asset":{"file":"current-room.png","sha256":"<真实哈希>"},"state_facts":{"chair.pose":"overturned"},"unseen_keys":["cup.hand"],"observer":"当前代理实际看图"}
```

composition_reference/first_frame/last_frame用于有continuity的镜头时，需要在该既有review覆盖可见关键键；确实不在画面里的键放unseen_keys，不知道/看不清则先补清楚图，不能默默省略。纯身份图无需为未承载的布局造事实；若图里可见矛盾持物/道具，同样必须记录并处理。

图片状态默认作用于当前请求第一个有continuity的镜头；必要时media项加continuity_shots:[具体镜号]表示内部后镜的状态图。初始图可以承担同一请求的动作起点，不能错误拿它约束动作后的后镜；位置/状态作用范围同时写清在H3参考说明里。

旧图可见“椅子摆正”而当前要求“已倒地”时，reference plan/prepare在上传前拒绝已声明冲突，先最小修图、裁去冲突或撤下旧图。只写否定词不算处理像素。新机位从原始共同空间＋有效状态派生，避免连续重画累积漂移。能从实际采用结果抽帧时不调用生图。

## 真实写作、提交与排程

状态事实进入官方六段中的相关正文，不加Seedance顶层字段。reference_plan把当前状态和实际选图送给指定作者；prepare和submit核对新旧依据、已观察图像事实、实际请求中状态/机位短语。submit也重查当前packet，过期状态不能仅靠刷新request哈希继续使用。

这些是声明、来源与文本载体检查，不会认证像素、语法否定或物理正确；真实请求反读仍要确认谁在哪、哪只手、允许变化和最终结果。条件只对有关状态镜头生效，旧普通镜头不补全量冻结包。

同一状态内无依赖镜头可并行；递交、踢倒、起身、损坏等动态后继先等真实采用结果。同请求内可完成“作用→后果→反应”时不硬拆成互不相知的请求，仍须观察内部切镜是否复原。反复失败只修错误层，按需加强构图/白模，不无限重生、不升级实例或恢复视频槽。

## 采用镜对、状态回查与精剪

对照实际采用出口→后镜入口，以及对象再次入画时：身份/手、数量、落点、开闭/破损/倒地、视线、背景投影和光源。屏幕位置变化可能来自合理机位，不要求所有角度像素相同。关键动作中段需要密读/实际镜对观看，静帧与清单不能证明完整动作成立。
后镜若开头又重演前镜已完成的落地/转交，不因尾帧正确就采用整条。只在后段有足够正确覆盖、未丢必要对白/反应/新动作时裁去重复段，并从新采用区间重取状态依据；覆盖不足则局部修镜。静态状态图和明确提示仍可能被模型重演动作，不能把它当作自动锁定。

```text
python <skill>/scripts/scene_continuity.py compare adopted-state.json expected-facts.json --output continuity-result.json
```

expected-facts可由当前packet的planned_exit机械导出，不新增模型写作。匹配只说明已观察声明符合目标，artistic_accepted始终不由脚本授予；错误/未知保留needs_continuity_repair，实际可修问题先修再继续。导出层仍按[场次验收](scene-acceptance.md)和[对白保护](dialogue-preservation.md)处理。

实际剪辑里不可缺的状态转移，放已有anchors:[{id,start,end,kind:state_change,required:true}]。retime_finish会先恢复被跳过的区间，再重映射字幕/声cue。技术建立段只在有需要且小样有收益时启用，不全片固定加/删一秒；有必要台词、接触或因果的实际片段不能被当技术头尾裁掉。

## 方法依据与边界

2026-10-16核查：Hell Grind官方Project Brief与下载的CINEDANCE V4强调3/4场景、地标、机位、手部和物件状态；小云雀官方导演台手册将截图作为构图参考、全景作为背景；Runway官方References介绍草图/框线控制物件位置；H3官方指南要求逐镜位置与状态变化。来源见[方法记录](../creation/drama-method-sources.md)。这些方法不保证H3严格服从三维坐标，源码检查和测试不冒充实际作品通过。

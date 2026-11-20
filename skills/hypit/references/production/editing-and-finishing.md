# 实际素材到精剪与后期执行

完整目标分镜拥有故事/准确台词，原EDIT配置拥有采用和后期决定。不另写剪辑文学稿或恢复独立审查。当前Agent依据实际素材/粗剪作决定，直接编译、执行并修正具体问题。视频生成仍用H3 default、空视频槽。

## 粗剪后的导演回合

先用采用素材形成可播放粗剪。按场/交流读取真实声画、既有分镜/源义务和已有字词时钟或波形数据，按[紧凑短剧选镜与切点](drama-editing.md)选择表演、组织注意力/反应和动作接续，再收紧无效等待与局部速度。该方法随storyboard/post请求自动进入作者上下文，决定落回现有EDIT；无需额外创作回合。整体体验机制需展开时读[注意力与节奏](../creation/attention-and-rhythm.md)。

`review_drama.py`从实际媒体准备1×带声音的较小代理与该区间本地声音测量，生成的evidence只是现有检查资料。`write_drama_documents.py`现在支持videos，把真正MP4及其源依据附给当前Agent；未知不能变成观察。粗代理用于整体判断，动作/接触/剪点和文字回原文件密读；当前Agent估秒不能压过本地字词时钟。

```text
python <skill>/scripts/review_drama.py rough.mp4 --output checks/scene-v1 --context current-edit-context.json --writing-request post-request.json --project <project> --edit-file EDIT.json --batch scene-post-v1
python <skill>/scripts/write_drama_documents.py run post-request.json
python <skill>/scripts/finish_drama.py EDIT.json final-v2.mp4
```

参考任务在post-request沿用source_shot_table/source_shot_context或所选execution_packet，承接当前完整相关行与EX依赖；不重抄全片，不假定服务记忆。角色post也可读取所选执行包。实际媒体变化只重做受影响区间，已付费返回先恢复，不重复投递结果不明的请求。

可在review_drama直接传--source-shot-table、--source-shot-context或--execution-packet（相对project的既有路径），自动标记reference；原创任务才省略。后期请求默认autonomous_finish=true：未决项保留到回执而不要求人工批准；需要显式保存带发现的post/sound/copy返回时用adopt post-request.json --retain-findings。采用文档不等于艺术通过，后续仍执行可行修复和实际出口检查。

## 可执行EDIT接口

下面是参数示例，不是每片必须照填的模板；路径均为实际文件。大段普通素材不必先转HTML工程。复杂图形只渲染所需图层/效果段，再进入同一时间线。

```json
{
  "version":1,
  "canvas":{"width":1280,"height":720,"fps":24},
  "clips":[
    {"id":"A","file":"speaker.mp4","segments":[{"start":0,"end":2.5,"speed":1.0}],"native_audio":false,"grade":{"exposure":0.1,"contrast":1.03}},
    {"id":"B","file":"listener.mp4","start":0,"end":3,"native_audio":false}
  ],
  "audio":[
    {"id":"A-voice","bus":"dialogue","file":"speaker.mp4","start":0,"end":3,"at":0,"gain_db":0},
    {"id":"M1","bus":"music","file":"accepted-score.wav","start":12,"end":17.5,"at":0,"gain_db":-18,"fade_in":0.3,"fade_out":0.8}
  ],
  "captions":[{"audio_id":"A-voice","start":0.4,"end":2.9,"text":"当前已定台词"}],
  "music_map":[{"id":"SOURCE-M1","match":"replacement","audio_ids":["M1"],"basis":"实际试听后保留原片压迫感与退出位置"}],
  "master":{"duck_music":true},
  "expected_lines":[{"id":"line-A","text":"当前已定台词"}],
  "pacing":{"decision":"保留说话声到3秒，2.5秒先切听者反应"}
}
```

这里只表达L-cut的时间关系；实际素材必须确有这些台词/反应，口型可见时保持同步。无对应听者、动作或原生近景时补对应H3覆盖，不用低清裁切、冻结或后期文字替代必要表演。

### 画面、切点与速度

- clips是剪辑单元，不等于一个H3任务。每单元一个file（或job目录）及有序segments，未列区间被裁掉；多个来源拆为多个剪辑单元。不要求每个生成块都留在成片。
- 旧clips[].audio_segments不能直接交给新执行器；先将真实来源、源窗及成片位置迁入audio[]，明确native_audio，避免丢声或双声。新执行器遇到此旧字段会明确报错；旧check-edit仍可用于检查原项目。
- segments每项start/end为本源秒，speed是有理由的局部速度。默认带原声native_audio=true；编译器先做实际对白和required动作保护，再以当前帧率换算真实时钟。requested_speed保留意向，实际speed包含最多约半帧的时长对齐。
- 不需要固定24fps或某个画幅；canvas省略时从素材继承。明确画幅转换不得切掉关键物件/听者。只给有实际需要的clip写grade/effects。
- 一般硬切。确有用途时给后镜transition_in:{type:fade/wipeleft/wiperight/slideleft/slideright/dissolve/smoothleft/smoothright/fadeblack/fadewhite,duration:秒}；重叠会减少总时长，所有锚点按实际重算，不能把转场时长重复加回。
- anchors可沿用[{start,end,kind:state_change/action/reaction/reveal,required:true}]保护不可缺动作/反应/揭示。跨镜位置与实际状态仍按[连戏交接](spatial-continuity.md)。
- 音频独立时置native_audio=false，audio里明确选原轨/对白；完整目标台词必须出现在expected_lines，最终依据当前Agent可用声音能力、已有时间戳和技术数据核对，不能用完整字幕掩盖缺词。
- 速度精修每次实际判断。确实偏慢时主动试温和加速，如1.05/1.10/1.15，按有效结果采用；可覆盖整场再保留必要停顿。它们是候选不是固定标准，避免统一1.2的提醒不等于默认保留全部原速。先剪无效等待，再保调调整，最后重排独立BGM。

### 同一时间线的声音与事件锚点

audio每项包含id、实际file、源start/end、at、bus（dialogue/native/music/ambience/sfx），可选speed、gain_db、fade_in/out、pan(-1左到1右)、volume:[{time,db}]。time是本音频事件内秒；也可写事件锚点。

at/until支持成片秒数，或{clip:镜号,source_time:该源秒,offset:可正负偏移}，或{clip:镜号,edge:start/end,offset:偏移}。until需要的素材比源段长时，明确选loop:true或改乐句/增加片段；不悄悄拉伸、循环或截断对白。BGM默认speed=1，切后按乐句/重拍/静默重组，不随全片再次变速。

字幕用audio_id定位独立声音源，或clip定位同源声画；无这些字段时start/end为成片时钟。必须保留完整发声区间。改速后脚本换算，不能直接沿用源片/旧粗剪秒数。

fx支持highpass/lowpass(hz)、eq(hz,q,db)、denoise(noise_floor)、compressor(threshold,ratio,attack_ms,release_ms)、delay(ms,decay)。简单delay不是任意真实房间的混响。需要真实卷积、跟踪/复杂合成时调用已配置专门工具并带回真实文件；不用未执行的效果名称代替成片。

master.duck_music可为true或{threshold,ratio}，threshold为线性幅度（如0.035）；也可显式写{threshold_db:-29,ratio:4}，由当前前景控制配乐让位。master.lufs与true_peak_db控制实际两遍响度处理；按发行目的选择，不设通用平台标准。export_stems:true导出native/dialogue/music/ambience/sfx五类混音前音轨，空bus可以静音。H3原声混合轨仍是native，不假称独立对白stem；原声已有BGM时先分清层，防止双配乐。clip.native_music写present/absent/unknown，必须据实际听证，不凭H3提示词。

### 真实音乐与原片BGM承接

配乐默认以目标氛围、情绪发展、连贯和自然收尾为准。原曲是参考；先取得适配的真实音乐，不把识曲/找同版/分离原曲变成前置。原曲明确被指定时才按该范围处理。按[配乐方法与曲库](music-selection.md)在生成期间选曲，真实粗剪上定位乐句、转折、停乐与尾音。

现有source_music_cues保存源观察，music_map保存目标采用，可用id、match(original/recovered/replacement/silence/unresolved)、audio_ids、basis。replacement是正常选配；silence需有目标留白职责，可带at/until，不把未知原曲当无音乐。原曲身份未知可留在source记录，实际选配完成就用对应音频ID，不让目标配乐继续空着。

独立audio[] bus=music跨镜连续，按乐句选择start/end、at/until、音量/淡变；以当前剪辑重定位，避免每块重新开始或随视频再拉伸BGM。可记录ending=cadence/ring_out/intentional_cut及ending_basis。编译器会提示超出片尾被截的音乐或未处理的退出；提示不是听感通过。实际试听乐句与尾音比单纯填写fade_out更重要。

```text
python <skill>/scripts/music_assets.py extract source.mp4 --start <音乐清楚处> --end <结束> --output music-cue.wav
python <skill>/scripts/music_assets.py recognize music-cue.wav --output recognition.json
python <skill>/scripts/music_assets.py queries observed-music-cue.json --output search-queries.json
python <skill>/scripts/music_assets.py acquire <实际音频HTTPS直链> --page <来源页> --title <实际曲名或描述> --kind original_track --output assets/score.mp3
```

queries读取title/artist，或实际听到的mood/instruments/rhythm/development；用web搜索执行查询，默认按情绪/配器/发展/结尾找可用曲库并试听；cue.mode=source_match仅用于明确要求原曲的任务。不要编造识曲成功。recognize使用可用shazamio（支持私密工具环境~/.hypit/tools/music-recognition）；没有/失败就走其他识曲、清楚片段或检索，不把查不到解释为无BGM。

music_assets separate可调用已配置audio-separator及明确模型；模型/权重不是每片前置。输出是未听审候选，检查吞字、漏音乐/音效和新伪影后采用。已有media-use/音乐SFX工具时优先复用；缺少某曲库账号不强制新订阅。

### 图形、艺术字与调色

overlays使用实际image/video/color或text。字段at、duration或until、x/y、width/height、opacity、fade_in/out；透明WebM由alpha解码器读取。image/video可用reveal:wipeleft与reveal_duration。text必须指定font_file和准确文字，可调size、color、border；普通淡入文字不是所有艺术片名的等价方案。

复杂片名沿用[片名设计](title-design.md)与[后期设计](post-design.md)的已接受字形/材质/遮罩过程，使用现有HyperFrames工程或其他实际合成器渲染短透明层，再作为video/image叠加；不是让H3生成最终精确艺术字。只在本作需要时加，不默认新增片名或花式转场。

clip.grade支持exposure(档)、brightness、contrast、saturation、gamma、red/green/blue中间调平衡、lut(真实cube路径/引用)。先参考同场主图/代表镜头匹配相邻曝光与白平衡，再做创意look。元数据retag不能代替颜色变换；SDR素材不凭空套相机Log转换。

clip.effects可选blur(sigma)、vignette(angle)、zoom(amount,x,y)与shake(pixels,hz)，只实现已定导演过程。速度变化用segments，颜色用grade，不把grade_notes当已处理的画面。未支持的复杂效果先渲染成具体图层，不能静默忽略。

### 允许删除已确认的多余原声

default对白保护仍有效。需要删模型多说、重复句或确认ASR误识别时，discarded_speech:[{start,end,reason,review:{file,sha256}}]指向该原轨字节的实际听证。review包含input:{file,sha256}、observer、discarded_speech:[{start,end,kind:duplicate/unwanted/asr_false_positive,basis}]。不能凭静音/目标文本推测来解除保护。

finish_drama会在保留画面的采用区间内静音这些已确认范围，或不把其恢复进被精剪区间；原混音同一时刻的环境/动作声也可能被影响，需要补必要床/拟音。需要分离的先分离。保留已有转录与时间戳，最终仍核对完整目标台词。retime_finish用于声画同剪，不适合保动作而只删重复对白的情形。

## 输出与回改

finish_drama输出实际MP4、.post.json、可复用中间片段/混音与编译时钟。已存在结果只有同输入同参数同执行版本才恢复，改变采用区间只重算相关消费者。最终报告保留未实现cue、原音乐未解/替换、保护区损失、未听审和对白疑点，机器始终不授予艺术通过。

编译结果的`editorial_metrics`自动汇总当前采用源秒数、声画变速实际节省量、有效平均速度、独立音乐覆盖与空档所在镜头；`pacing.source_duration`可填当前比较范围的真实源片秒数，得到总时长差。它不统计未提供的早期预变速、不把重叠转场算为变速，也不把native混轨中的音乐判为空白。无需另写检查文档或新增门禁；将这些现成数字带进当前Agent后期回合，解释并修正无职责增长、无意断乐和仅局部试速却整体仍拖慢的问题。

最终声画观察必须明确评论整集节奏和音乐承托/发展/退出，不能只逐字复述剧情。模型估秒超过实际附件时长、出现大跨度空洞或与本地字钟矛盾时，该时刻不能作剪点或完整覆盖证明；只复查相关范围并保留未知，已有有效局部证据继续复用。

以真实终片再次走实际声画回查；按定位的问题修改原EDIT中的受影响部分再渲染，完成可做的修复。目标仍未达到时明确具体残留，不把生成、ASR匹配、编译或渲染成功当作节奏/美感通过。

# Directing a dramatic voice

Read before choosing or changing a character's voice. [Sound direction](../../creation/sound-direction.md) owns the scene's audience experience and hearing perspective; DESIGN/existing character facts own vocal identity; the current story owner (full STORYBOARD for ordinary recreation, literary body when used) owns words and key vocal actions. STORYBOARD owns performed timing and actual input duties.

## Cast the person through the sound

Choose a voice that embodies this character's social world, relationships and contradictions. Describe audible language/accent, pitch range, resonance/weight, grain/breath, articulation and rhythm where they matter. A demographic label or “pleasant” voice cannot establish identity. A commanding person may speak softly to control a listener; a bright voice may make a threat more unsettling. Avoid prescribing beauty, youth, authority or restraint as universal qualities.

Compare relevant cast voices by listening. They should be distinguishable for this drama without all becoming caricatures. Keep each current accepted profile and actual sample/version in CHARACTERS/ASSETS, linked from Treatment. A changed look does not automatically change a person's voice; an intentional voice/body transformation has an explicit scope and story reason.

## 特殊语音：源听审到角色表演

方言、口音、特殊音区和戏剧化腔调可能是人物辨识与卖点载体。第一次真实听审顺带分析，不给每句再开专项调用：

| 特征 | 记录的可听事实与边界 |
| --- | --- |
| 方言/口音 | 语言、发音/用词/语气词例证、浓淡和变换；短句或遮蔽不足以定地域时未知，不根据字幕/身份猜；保留实际方言词，不自动普通话化 |
| 特殊音区/质地 | 相对高/中/低或超低的听感、厚薄、明暗、沙哑/气声/鼻腔色彩与共鸣；音区不等于音量，未经测量不编Hz |
| 表演腔调 | 先写尖细、假声、咬字、拖腔、收尾和节奏等特征，再解释“太监腔”等戏剧标签；不由声音推定职业、身份或生理状态，不把所有高音写为同一种腔调 |
| 标志性声音行为 | 笑声、叹气、口癖、特殊断句与重复方式，发生触发和所承担的幽默、威压、反差或余韵；无作用的呼吸不强造卖点 |
| 表演与声音处理 | 区分稳定声线、本句策略及疑似降调/低频增强/失真/混响；仅听混轨不能确认制作技术或干净stem时明确未知 |

当前Agent沿现有events.auditory_detail、shots.delivery、summary.observations/unknowns记录实际证据；GPT据此把跨镜稳定特征汇入`SOURCE_CONTEXT.records.voice_profiles`，关联角色/匿名说话者、媒体版本、听审区间和未知。profile只保留可辨声音要点与出处，不复制逐句转录或整份听审报告；源表`声音表演`列引用其ID并写本镜变化。声音参与卖点的部分进入原有保真义务。没有实际听证的特征不填为源事实。

目标DESIGN人物声音段/已有角色档案选择保留或有依据转译；26列目标表的完整台词、语气重音停顿呼吸、导演意图和成功条件承接具体发声，不加列。H3正文用可执行声音描述并绑定实际支持的参考样本；样本存在不等于已上传/已生效。特殊声线保持可辨，但讨好、惊恐、愤怒或低语应有不同表演。

生成后在实际candidate/邻镜/成片听审中比较口音、音区、腔调、笑声及功能是否存活，检查跨镜漂移和变速/降噪/混音损失。错误表演优先局部H3修复，不靠EQ、随意升降调冒充方言或重新表演。换语言/声线时明确保住何种体验，不承诺精确克隆。旧报告未覆盖的重要特征按[专项补听](../../production/gemini-audio-review.md)只查有关短段，不另写人物声音文档或新增审批。

## Compress the voice into a vivid direction

State stable vocal identity separately from the passage's tactic. “A low, slightly rough voice with unhurried phrasing” is identity; “he tries to make her stay without admitting he needs her” is playable strategy. Specify only consequential stress, hesitation, breaths, volume/distance changes and the release after a line. Mood adjectives alone cannot carry a reversal or the listener's understanding.

For example, fictional scene direction:

```text
Identity: a clear mid-low voice, slight dry grain, conversational English and measured phrasing.
Action: he tries to sound casual while asking her to stay; the first word comes too quickly,
he briefly regains composure, and the last phrase softens as he waits for her answer.
The same voice persists when he becomes relieved; do not replace it with a different sweet timbre.
```

Another character's quick, crisp delivery might mask fear rather than indicate confidence. Write what the person is trying to achieve with their listener, and which audible change exposes that effort. No gesture, gasp or sob quota applies.

## Let the sample carry the character

Prefer accepted material in the performed language when available. A sample contains accent/prosody as well as timbre; cross-language resemblance is not proof of target-language delivery. Choose material with clear identity and the intended character, excluding accidental score/other speakers/heavy echo unless that relationship is deliberately being referenced.

Reuse an accepted sample, extract a suitable passage from already accepted H3 audio, or create a sample through a configured, authorized voice service or H3 audition. Voice Design/Clone are options only when actually available and needed, not automatically installed requirements. Draft samples and provisional auditions remain labeled until heard and accepted for their duty. Check key emotional delivery in the relevant scene; a neutral sample does not accept every future performance.

Follow [voice/performance](voice-and-performance.md#carry-one-accepted-voice-into-varied-acting) and [real audio inputs](../../production/request-controls.md#carry-audio-intent-into-actual-inputs). Bind actual uploaded bytes to the named speaker when the selected RunningHub operation supports it. A sample file, prose label or serialized `None` does not transfer the sound to the model. Timbre reference, signal reuse and exact speech drive require separate capability evidence.

## Let one voice express different thoughts

Vocal identity stays recognizable while the character questions, conceals, provokes, reassures or loses control. Timing comes from read/performance and actual aligned media, with time for listening and action. Do not flatten a whispered secret, an interruption or broad comedic delivery merely to make generation easier; choose feasible H3 blocks/coverage preserving the essential response.

[Video direction](video-direction.md#direct-the-reason-for-an-action) relates voice to gaze, posture and interaction; [script measurement](../../creation/script-and-time.md#measure-before-choosing-durations) sizes the passage; [sound/mix](sound-mix.md) retains space, cues and quiet through the final scene. Actual listening settles cast continuity and expressive delivery.

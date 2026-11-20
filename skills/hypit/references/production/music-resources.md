# 音乐资源库与取得方式

核对日期：2026-10-20。用于缺曲检索，配乐决定与衔接方法见[情绪选曲](music-selection.md)。



**已实现并实测自动检索、下载和试听输入：Incompetech、Scott Buckley。**前者使用作者为代理公布的JSON目录，后者使用音乐库页面声明的公开WordPress目录接口；无需新账号。其他来源仍按表中网页/API入口使用，不冒称已配置。选定素材的来源、取得依据与署名自动留在既有资产侧车记录，不新增审批表。

## 默认可执行路线

先复用本地已选乐段，缺口再在线查曲。保存/检索沿用当前选曲JSON，不要求另写素材报告：

```text
python <skill>/scripts/music_assets.py remember selected-music.json
python <skill>/scripts/music_assets.py recall "主角 反击 上升" --limit 3 --output selected-music.json
```

remember记录tracks里实际file/start/end、可选theme/variant/function/ending/tags/basis/review及原资产侧车引用；review可引用已有实际听审文件。索引默认~/.hypit/music-libraries/segments.json，--index可改为系列专用路径。音频留在原位置，不打包或复制；recall校验当前字节，失效来源跳过并报告，结果可直接交attach。收藏与旧观察不自动代表新场景适配或新许可，空结果继续search/fetch，不为建库补作历史听审。

```text
python <skill>/scripts/music_assets.py search "dark strings tension" --limit 6 --output music-candidates.json
python <skill>/scripts/music_assets.py fetch music-candidates.json --id <返回的实际ID> --output assets/music/score.mp3
python <skill>/scripts/music_assets.py audition assets/music/score.mp3 --start 0 --end 18 --output checks/music-head.mp4
```

search默认并行查询两个已实现来源，按关键词返回少量候选，支持常用中文情绪词；结果含实际来源、metadata匹配依据和未试听状态。它不按标题自动决定艺术适配。目录缓存位于~/.hypit/music-libraries，默认一天复用；--offline只查缓存，--refresh明确更新，--providers可选择单库。一库失败保留其他真实结果，离线旧目录明确标记，不伪造成功或绕过站点限制。

fetch只取选定ID的完整MP3，不镜像整个音频库；自动保存实际时长、hash、来源/许可页面和credits.txt。已取得且字节相同的文件直接复用。选曲和实际用途仍遵守来源条件；这两个已实现来源的免费路线要求署名。

要接到现有导演回合，准备一个机器选择，例如：

```json
{"intent":"当前场景的克制紧张与自然收尾","tracks":[
  {"id":"候选ID","file":"assets/music/score.mp3","start":10,"end":28,"label":"实际音乐中段，非剧情画面","theme":"主角","variant":"反击","function":"上升","tags":["悬疑","低密度"]},
  {"id":"候选ID-ending","file":"assets/music/score.mp3","start":160,"end":178,"label":"已核实范围内的实际结尾"}
]}
```

start/end以已下载文件实际时长为准；示例秒数不是默认采用区间。每次选1–4个有用片段，按需包含中段/尾音，不反复传整曲。

```text
python <skill>/scripts/music_assets.py attach post-request.json selected-music.json --output checks/music-v1
python <skill>/scripts/write_drama_documents.py run checks/music-v1/writing-with-music.json
```

attach支持既有design/treatment/director/screenplay/storyboard/sound/post/观察请求：前期可把真实候选与主题/变奏/功能交同一当前Agent回合，写回已有DESIGN/目标分镜；后期写回同一EDIT。它把真实音频编为小MP4并保留原分镜/EX/对白上下文，自动携带配乐方法，不自行发付费请求或声称已听过。纯色画面只是当前Agent试听容器，不进入H3视频参考槽。只有音乐片段没有实际场景时，结论只是候选听感，不是整片接受。

采用后audio[] bus=music引用实际文件/乐段；episode_runner finish会从所用音乐的真实asset侧车汇总.music-credits.txt和输出索引，方便在本作交付/发布描述使用。没有相关记录的旧素材不被假冒成这两个库的已验证资产。

## 来源与接入边界

| 来源 | 适合的使用方式 | 关键边界 |
| --- | --- | --- |
| [Mixkit Music](https://mixkit.co/free-stock-music/) | 免费、按情绪/风格下载，先建常用短剧素材库 | [音乐许可](https://mixkit.co/license/modal/musicFree/)覆盖相应网络用途，排除TV/广播/游戏并限制remix/music-only等方式；不能默认所有曲库都允许同样的结构重编 |
| [Pixabay Music](https://pixabay.com/music/) | 大量情绪/类型候选，网页下载后试听 | 保存下载凭证；部分曲有Content ID。官方[API](https://pixabay.com/api/docs/)未列可核实音乐接口，不假造音乐搜索端点 |
| [YouTube Audio Library](https://studio.youtube.com/) | YouTube发布、背景和主题素材 | [官方说明](https://support.google.com/youtube/answer/3376882)区分标准许可/CC署名；不要把YouTube内的保证推广到任意平台 |
| [Incompetech](https://incompetech.com/agent-section/) | **已接入**：作者目录、情绪/配器检索、完整MP3及署名记录 | 免费CC BY 4.0路线署名；选定页再次核对，收费WAV等不自动取得 |
| [Scott Buckley](https://www.scottbuckley.com.au/library/) | **已接入**：电影/幻想/情绪配乐，公开目录检索、完整MP3与实际试听 | 只导入单曲页面明确CC BY 4.0的记录，保留作者要求的署名文本；网页无此声明不伪认 |
| [Freesound](https://freesound.org/) | **音效补充，未接API**：优先寻找接触、空间、环境、转场和设计声；[API文档](https://freesound.org/docs/api/overview.html)按实际账户/token使用 | [官方FAQ](https://freesound.org/help/faq/)区分CC0、CC BY、BY-NC；不能把全站当CC0。拿到实际适用文件后可acquire/audition/remember，不宣称已配置自动下载 |
| [小森平](https://taira-komori.net/) | **网页音效补充**：日常、环境与动作声，取得实际文件后复用现有资产工具 | [作者条款](https://taira-komori.net/welcome.html)允许商业作品使用，限制原音再分发、转售与冒名；不把原素材打包随Skill发布 |
| [ZapSplat](https://www.zapsplat.com/) | **网页候选**：确有音效缺口时按账户取得 | 本轮标准许可页读取失败，不采纳“免费一律免署名”概括；按实际账户与选定音效条款使用 |
| [Epidemic Sound](https://www.epidemicsound.com/) | 电影感曲库、可用stems/版本；自动化优先考虑官方[MCP](https://developers.epidemicsound.com/docs/mcp/) | MCP为Beta、需本人账户/key和相应订阅；Partner API开发测试许可与用户订阅/MCP分开核对，编辑版目前不是edited stems |
| [Artlist](https://artlist.io/) | 商业短剧/客户项目的人工选曲和版本下载 | [计划说明](https://help.artlist.io/hc/en-us/articles/29559573229725-Artlist-s-Music-and-SFX-plans-explained)：Social与Pro用途不同，不能用个人频道计划默认覆盖客户/广告 |
| [Uppbeat](https://uppbeat.io/) | 易检索的背景/情绪素材 | 按当前[用途与计划](https://uppbeat.io/blog/royalty-free-and-copyright-free-music/what-marketing-teams-should-check-in-stock-media-licenses)核对个人、专业客户或团队使用 |
| [Soundstripe](https://www.soundstripe.com/) | 曲库及正式[Music API](https://www.soundstripe.com/blogs/music-api-for-video-editing-platforms)集成 | 预览/评估key不等于生产商用权限；正式下载与发布依对应账户/API协议 |

免费/低门槛默认路线：recall本地已选真实段落→缺口用Incompetech/Scott Buckley检索与选定下载→所需片段试听；音效先保H3有效原声，缺口再用适用本地/Freesound/小森平素材。FreePD旧官网公告关闭，不列为默认活跃来源。Pixabay不按“全站CC0、无任何限制”推定；中文聚合站/剪辑软件中的下载免费也不自动代表本次用途。取得依据与署名仍用已有侧车，不新增审批表。自动化升级复用现有账户；其他来源需实际文件/账号才执行，不把网页入口冒充自动接入。


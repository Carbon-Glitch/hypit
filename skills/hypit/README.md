# Hypit — Carbon-Glitch 定制 Skill

基于 [hypit-ai/hypit](https://github.com/hypit-ai/hypit) 的本地定制版本，支持短剧、口播/UGC、播客、街访、榜单、讲解、屏幕演示、MG及字幕声音后期，按任务加载相应方法。

## 安装

```bash
npx skills add Carbon-Glitch/hypit --skill hypit -g
```

也可以将本目录放入 Agent 的 skills 目录，然后调用 `$hypit`。从已有定制版本升级时先保留自己的改动。

## 当前定制

- 创作、参考分析、分镜、提示词和后期判断由当前 Agent 完成，不额外调用写作或听审模型，也不自动启动 ASR。
- Agent 无法听取音频时，使用本地波形、能量、静音及响度数据辅助；未知的词义和听感不当作已经核实。
- 图片优先使用 Agent 的内置 imagegen；视频沿既定 RunningHub MiniMax H3 路线，账号与配置由使用者提供。
- 保留源表、镜头连续性、分轨剪辑、音乐与字幕、时间轴换算、缓存及恢复。通用形式不强套短剧模板。
- 字幕排版 helper 已随包提供，单独安装本 Skill 不需要另一份 short-drama-edit。

Python 辅助脚本需要本机 Python 与 FFmpeg/ffprobe；原生 Hypit 工程、浏览器渲染或媒体生成按任务使用其实际运行环境。安装 Skill 不会自动开通账户、安装模型或生成媒体。

## 来源

完整上游参考快照及本地调整见 `references/general/source.json`、`references/general/local-overrides.md`。根仓库仍保留上游 Runtime 和示例；本次定制集中在 `skills/hypit/`。

保留仓库根目录 LICENSE、[通用参考库的上游许可](references/general/LICENSE)与各方法文件中的来源说明。此 fork 不代表上游官方版本。

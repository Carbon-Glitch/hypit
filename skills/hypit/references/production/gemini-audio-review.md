# Agent声音观察与波形辅助

能用当前Agent能力听取音频时，直接观察实际文件。听不了时，先看波形、声能变化、静音区间、时长与响度，结合画面和已有字幕作近似定位，继续剪辑；不再调用外部听审、转写或理解模型。

```text
python <skill>/scripts/audio_signal.py source.mp4 --output checks/audio
python <skill>/scripts/inspect_finishing.py source.mp4 --output checks/technical.json
```

第一条生成 `signal.json` 与 `waveform.svg`：每50ms的能量/峰值和静音候选，使用所选源区间内秒数。需要片段时加 `--start` / `--end`。第二条按实际文件做解码、响度和其他技术测量；具体参数以帮助为准。

波形适合看声音起止、停顿、突变、接缝与配乐能量发展。能量峰值可能来自对白、音乐或音效，不能据此认出某个词、说话人、口音或声音好不好听。记录“波形推测/未听取”，不写成真实听审通过。

已有可靠字幕/词时间可继续使用。若提供 `<媒体文件名>.speech.json`，填当前媒体sha256、duration、status=ok及segments（start/end/text，可含words）；工具只读取这些现成时间，不启动识别模型。没有词时间时保留Agent选定源窗并提示边界未核实，不自动恢复整段或卡住交付。

`analyze_audio.py analyze ... --stage ...` 旧入口也已转为本地波形测量。旧模型回执仅用于历史恢复，不产生新调用。此页保留原文件名以兼容已有链接。

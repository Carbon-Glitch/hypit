# 选镜执行包

编译、修复某个H3块时使用。`shot_packet.py`从当前主表机械提取完整选镜、相关源行、公共/E/EX和声明的邻镜依赖。新表25/26列，旧49/44列按原样读。

稳定DESIGN/ASSETS用实际文件及必要owner_slices，状态用实际adoptions或经验证的shared_state。包中的故事、准确对白、动作/听者、揭示、摄影/声音和model/post职责都沿用当前所有者。

```text
python <skill>/scripts/shot_packet.py build selection.json --output SHOT_PACKET.json
python <skill>/scripts/shot_packet.py check SHOT_PACKET.json
```

selection含version=1、scope、storyboard文件记录、selected_shots有序ID；复刻加source_table/source_context，原创用source_kind=original。owners/dependencies引用所需实际文件；owner_slices用artifact、start_line、end_line。

包将声明依赖带入局部写作；调用者按剧情补齐场外伏笔或未在文字中显式引用的条件。任何上游字节变化后重新build。执行的prompt、REFERENCE_PLAN、request与回执沿当前job保存，详见[队列](efficient-execution.md)。

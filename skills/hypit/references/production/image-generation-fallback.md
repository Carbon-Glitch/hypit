# 生图备用路线：内置imagegen失败后继续

资产生图默认使用Codex内置imagegen。用户已指定：工具报错、不可用、超时或未得到可用图片时，由Codex接着调用OpenRouter `google/gemini-nano-banana-2.1`；这项备用属于已授权制作，不再次询问是否切换。该脚本不接管内置工具，通过Skill中的执行指令衔接实际失败结果。安全拒绝不能靠换供应商绕过。

## 保住同一资产意图

复用当前Agent作者的原提示词、已有目标身份/造型/空间/色卡参考和各图职责。修图必须附实际待改图片；不要把参考编辑降成纯文字重画，也不换角色、画风、构图和剧情。已有可用图直接复用。外观合格度仍按[资产规范](../creation/drama-reference-sheets.md)检查，不因备用生成成功自动接受。

备用固定Nano Banana 2.1，默认2K、每次一张；四/九宫格、人物和场景按同一资产职责执行。输入最多14图，但只传必要图。细节确实不足才对受影响图用4K，不默认全资产4K。色卡绘制、裁格、提取视频承接帧不需要生成服务。透明图必须检查真实alpha；无alpha保留候选并补实际去底，不把棋盘格或纯色背景当透明。

## 本地调用

复用听审/写作的私有OpenRouter凭据：环境变量OPENROUTER_API_KEY或当前用户.hypit/openrouter-audio/config.json所引用的DPAPI密钥。不复制密钥进项目或Skill，不修改写作/听审模型。模型与凭据首次或出现路由问题时检查一次，不对每张图重复doctor：

    python <skill>/scripts/generate_image_fallback.py doctor

将当前生图任务的原提示词保存到项目，按原资产记录生成请求JSON即可，不另写审查文档：

```json
{
  "version": 1,
  "project_root": "<实际项目绝对路径>",
  "asset_id": "CHR-01-look-v1",
  "builtin_failure": {"kind": "tool_error", "detail": "<实际内置工具错误；非虚构测试>"},
  "prompt_file": "assets/prompts/CHR-01-fourview.txt",
  "references": [{"file": "assets/CHR-01-anchor.png", "role": "同一角色的已接受身份与服装锚点"}],
  "output": "assets/CHR-01-fourview-v2.png",
  "resolution": "2K",
  "aspect_ratio": "1:1",
  "transparent_background": false
}
```

builtin_failure.kind为tool_error/unavailable/timeout/invalid_output，detail记录真实失败；新资产无参考时references为空。保持原定画幅。每次请求沿用同一资产ID和文件，不为重跑随意换ID制造重复收费。

    python <skill>/scripts/generate_image_fallback.py inspect image-request.json
    python <skill>/scripts/generate_image_fallback.py run image-request.json
    python <skill>/scripts/generate_image_fallback.py recover image-request.json

inspect只读检查。run使用官方POST /api/v1/images，resolution/aspect_ratio/n和input_references传实际图像字节；每个输入带用途说明。输出PNG、原始API响应、实际generation_id/usage（API提供时）及回执保存在项目.hypit-images，不在控制台输出base64。实际费用以回执及账户账单为准，不把每token报价误当每张价格。

同一输入已有响应时离线恢复；超时/提交状态不明时保留回执，不自动再次扣费，不转第三个供应商。图片尺寸/画幅/alpha异常保留候选供局部修复，技术有效仍需看身份、各格、空间、画风及文字。已接受/并发修改文件不覆盖；输出使用新版本路径。备用仍失败时继续不依赖该资产的工作，汇总实际缺口，不无限循环。

--smoke仅用于明确的接口集成测试，回执标为integration_smoke_test，不虚构内置失败，也不作为短剧资产验收。开发测试不加入每次制作流程。

## 选型依据

2026-10-15核对官方[模型页](https://openrouter.ai/google/gemini-nano-banana-2.1)、[图片API](https://openrouter.ai/docs/guides/overview/multimodal/image-generation)、[生图模型目录](https://openrouter.ai/api/v1/images/models)及[当前端点](https://openrouter.ai/api/v1/images/models/google/gemini-nano-banana-2.1/endpoints)。Nano Banana 2.1于2026-10-06进入目录，支持1K/2K/4K、单次1图、最多14张参考；官方模型说明强调多视图物体一致性、人物一致性、编辑和密集文字，适合作为本作资产备用，这是选型判断，不是实测排名保证。

当日图片输出报价$30/百万image tokens；模型说明2K约1680图像token，即约$0.0504/张的图片输出部分，其他适用计费另计，实际看usage/账单。价格与可用端点变化时用doctor重新核对，不自动换模型。此集成不改变RunningHub H3 default和空视频槽规则。

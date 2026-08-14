---
name: ip-visuals
description: "使用 IP Studio 锁定的角色包制作、修订和归档头像、主页横幅、资料卡、封面、说明图、正文插图及整篇文章配图组。Use when the user wants static bitmap visuals featuring an existing locked IP character. Do not use for character identity design, generic visuals without an IP character, animation, pets, video, or 3D."
---

# IP Visuals

使用 `$ip-studio` 已锁定的角色包制作和无损归档静态位图：头像、主页横幅、资料卡、文章封面、说明图、单张正文插图、整篇文章配图组，以及这些成品的后续修订。角色档案和主参考图只负责身份一致性；本 Skill 不创建或改写角色身份，也不处理没有 IP 角色参与的一般视觉、动画、桌宠、视频或 3D。

## 输入与创作边界

先取得明确的锁定角色包。用户用名称或英文标识点名角色时，调用兄弟 Skill 的正式解析入口：

```text
python <ip-studio-skill>/scripts/character_kit.py resolve-character <name-or-id>
```

读取返回的角色档案和当前主参考图，再完整读取 `references/visual-production.md`。用户提供完整提示词时原样写入 `prompt_text`；没有完整提示词时，只根据目标、完整材料、参考图职责、必要比例和用户硬要求写一条简洁准确的提示词，不替图像 AI 预选视觉中心、构图、场景、动作、物件、文字层级、配色、光影、材质或装饰。角色档案的维护字段、传播分析、方案理由、失败归因和归档数据不进入生图提示词。

本 Skill 不自动开启或关闭 Plan 模式。默认模式直接根据现有材料完成；用户主动开启 Plan 模式时，先读完材料并完成当前权限内的必要调查，再每轮只问一个必须由用户回答的审美、情绪或表达取舍问题，不重复已经出现的原话和边界。

第一次准备生图前完整读取 `$imagegen`。任何新图、编辑或重试都先展示脚本输出的完整提示词和有序图片输入并停止；用户下一轮确认后才原样交给图像入口。输入变化必须重新确认，多项未改变的任务可以整批确认。第一张正常生成结果就是本次成品，不因 Agent 自己的审美判断自动换图；用户明确要求检查、修改或另做一版时，再建立新的提示词和修订。

## 制作和归档

所有脚本都用当前 Skill 目录中的 `scripts/visual_kit.py`。先建立简报：

```text
python <ip-visuals-skill>/scripts/visual_kit.py schema
python <ip-visuals-skill>/scripts/visual_kit.py draft <brief> --kind <kind> --visual-id <slug> --language <language>
python <ip-visuals-skill>/scripts/visual_kit.py prompt <character-kit> --brief <brief>
```

`kind` 支持 `avatar`、`profile-banner`、`profile-card`、`cover`、`explainer` 和 `article-illustration`。每个结果共享角色版本，但分别建立简报、生成和归档。整篇文章配图先用 `plan-schema`、`plan-draft` 和 `materialize-plan` 找出互不重复的认知锚点及正文插入位置，数量由文章内容决定，不套固定张数。

用户明确选择极简手绘、OKX Editorial 或 Binance Editorial 时，按 reference 读取当前 Skill 内对应的正式风格资料和必要参考；普通提示词只写用户选择的风格名称，不复制维护侧 JSON，也不自动加入精确 Logo。只有用户明确要求精确标记时，才把相应 Logo 当作当前图片素材输入。

生成第一张结果后直接归档并校验：

```text
python <ip-visuals-skill>/scripts/visual_kit.py finalize <character-kit> --brief <brief> --image <generated-image>
python <ip-visuals-skill>/scripts/visual_kit.py check <visual-folder> --kit <character-kit>
```

正式结果进入角色包的 `derivatives/<kind>/<visual-id>/revisions/rNNN/`，旧版本不覆盖。修订时使用 `revision-prompt` 和 `revise`，以上一版成图作为正式输入；文章配图组全部完成后用 `finalize-set` 和 `check-set` 记录正文顺序与精确 revision。

## 完成状态

交付时先展示最终图片，再说明角色版本、视觉 revision 和绝对路径。只有真实图像已经归档、记录中的提示词与图片输入可读且 `check` 通过，才声称完成。没有生图能力时交付简报、完整提示词和有序参考；没有独立看图能力时不声称视觉验收通过。满足当前静态视觉请求后停止，不自动增加其它比例、配图、表情包或平台版本。

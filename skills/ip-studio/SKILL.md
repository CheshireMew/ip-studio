---
name: ip-studio
description: "创建、导入、修改并锁定可跨会话复用的个人或品牌 IP 角色包，维护唯一角色档案、主参考图和无损版本历史。Use when a user wants to establish or revise a stable stylized character identity. Do not use for static derivative visuals, animation assets, Codex pets, video, Live2D, or 3D."
---

# IP Studio

把身份线索或已有角色图变成可跨会话复用的角色包。`character-profile.json` 与当前版本登记的单张主参考图是唯一身份真源；测试图、衍生图和动态素材只消费它们，不反向改写角色。

本 Skill 只负责从零创建、导入已有形象、修改和升版、锁定与校验角色身份。头像、横幅、资料卡、封面和文章插图由 `$ip-visuals` 完成；有限状态的 2D 动作素材由 `$motion-studio` 完成；Codex v2 桌宠由 `$hatch-pet` 完成。普通品牌策划、照片级数字分身、视频、Live2D、骨骼动画和 3D 不属于本 Skill。

## 输入、权限与创作方式

依次使用当前请求、当前对话、用户提供或明确指向的图片、文档和既有角色包。只有缺失信息会改变轮廓、脸部、主配色、标志物或身份含义时才提出一个具体取舍；其它不改变身份的结构可以补全并在档案中标记为 Agent 推断。导入已有形象时分开记录用户有意保留的特征、稳定重复特征和当前图片的偶然细节。

本 Skill 不自动开启或关闭 Plan 模式。默认模式按现有材料直接完成；用户主动开启 Plan 模式时，先读完现有材料并完成当前权限内的必要调查，再每轮只问一个必须由用户本人回答的审美、情绪或身份取舍问题，保留用户自然原话，不套问卷。

当前环境需要生成或编辑位图时，第一次准备生图前完整读取 `$imagegen`。每个新图、编辑或重试任务都先展示实际将发送的完整提示词和有序图片输入并停止；用户下一轮明确确认后，才把完全相同的输入交给图像入口。任何输入变化都重新展示并等待确认，多项未改变的任务可以一次整批确认。没有生图能力时交付角色档案与完整提示词；没有独立看图能力时不声称视觉检查通过。

## 建立和锁定角色

完整读取 `references/character-system.md`。所有脚本都用当前 Skill 目录中的 `scripts/character_kit.py`，不要根据终端当前目录拼路径。

先取得由脚本自身位置确定的工作区：

```text
python <ip-studio-skill>/scripts/character_kit.py workspace --character-id <slug>
python <ip-studio-skill>/scripts/character_kit.py schema
python <ip-studio-skill>/scripts/character_kit.py draft <draft-profile> --character-id <slug> --display-name <name> --language <language>
```

新角色方向不清时，从同一份暂定档案建立三张真实不同的方向稿并实际打开检查；已有形象已获认可且只需建档时跳过方向稿。缩略图中先认出主轮廓和记忆点，缺肢、断裂、无关文字或细节堆积不通过。技术错误或违反已确认特征的结果从档案重生，不从失败图继续编辑；会改变身份锚点的分歧交给用户。

正式主图提示词由档案唯一派生：

```text
python <ip-studio-skill>/scripts/character_kit.py prompt <draft-profile> --purpose master
```

主参考图使用单角色、全身、正面或轻微三分之四视角、中性姿态和干净背景，使固定特征清楚可见。生成后按档案实际看图；同一复杂部件连续失败两次时才建立绑定当前角色版本的辅助校准板。主图获批后，用不同姿势、表情和简单背景做一次复用测试：

```text
python <ip-studio-skill>/scripts/character_kit.py prompt <draft-profile> --purpose consistency --reference <approved-master> --task <reuse-task>
```

测试失败时修正档案或主参考图。改变已锁定的轮廓、脸部、核心配色、标志物或含义必须升版，不覆盖旧版本。

## 无损归档与完成

使用 `workspace` 返回的绝对 `character_kit`：

```text
python <ip-studio-skill>/scripts/character_kit.py finalize <kit-folder> --profile <draft-profile> --master <master-image>
python <ip-studio-skill>/scripts/character_kit.py check <kit-folder>
```

`finalize` 把旧档案、说明和主图保存在历史中。完成前重新读取当前 `character-profile.json`、`character-guide.md` 和实际主图，并确认 `check` 通过。交付时先展示正式主图，再说明核心记忆点、当前版本和角色包绝对路径；没有真实主图、可读档案和通过的校验时，不声称角色已锁定。满足角色身份请求后停止，不自动扩展静态视觉、动作或平台版本。

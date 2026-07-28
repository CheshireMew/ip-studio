# IP Studio

`ip-studio` 是一个面向 Codex 与具备生图、看图能力的 AI Agent 的角色生产 Skill。它帮助用户从零建立可长期复用的个人或品牌 IP 角色，也能导入和修改已有形象，并让同一角色继续用于头像、主页视觉、文章配图和 Codex v2 桌宠。

设计目标是让 AI 负责整理资料、补全结构、生图、审图、重试、版本管理和文件校验，只把真正会改变角色身份或传播方向的选择交给用户。

## 主要能力

- 从零设计、导入或修改风格化人形、动物、拟人、物件和幻想生物。
- 用完整角色档案与单张主参考图维持跨会话一致性。
- 生成头像、主页横幅、资料卡、文章封面、说明图和正文插图。
- 制作包含九组应用状态与十六个注视方向的 Codex v2 桌宠。
- 自动维护角色版本、衍生视觉记录、桌宠运行记录和旧安装备份。
- 使用软遮罩和多背景检查处理桌宠透明边缘，减少幕布色残留。

照片级数字分身、Live2D、视频、普通动画和非 Codex 桌宠不属于当前能力范围。

## 安装

将仓库克隆到 Codex 的个人 Skills 目录：

```powershell
git clone https://github.com/CheshireMew/ip-studio.git "$env:USERPROFILE\.codex\skills\ip-studio"
```

重新打开 Codex 后，可以直接调用：

```text
$ip-studio 从零为我设计并定稿一个可以长期使用的个人 IP 角色。
```

制作 Codex 桌宠时需要工作区 Python 环境提供 Pillow 和 NumPy。角色档案及普通衍生视觉脚本只使用 Python 标准库。

## 仓库结构

```text
ip-studio/
├─ SKILL.md
├─ agents/openai.yaml
├─ references/
│  ├─ character-system.md
│  ├─ visual-production.md
│  └─ pet-production.md
└─ scripts/
   ├─ character_kit.py
   ├─ visual_kit.py
   ├─ pet_kit.py
   └─ pet/
```

`character-profile.json` 是角色身份的唯一真源。衍生图片和桌宠读取当前角色档案及其中登记的单张主参考图，不会反向修改角色身份。

## 隐私

Skill 默认只读取当前请求、当前对话、用户明确提供的材料，以及用户明确指向的角色文件夹。生成的角色包、图片、QA 文件和桌宠运行记录保存在本地输出目录，不属于本仓库，也不会被默认提交。

公开问题或贡献代码前，请自行确认提交中不包含角色私有素材、文章草稿、品牌资料、绝对路径、访问令牌或生成记录。

## 许可

本项目采用 [Apache License 2.0](LICENSE)。

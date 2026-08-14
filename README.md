# IP Studio Skill Suite

这个仓库现在包含三个职责独立、共享同一角色包协议的 Skill。角色身份、静态内容视觉和运行时动作素材分别有自己的入口，不再由一个大而全的 Skill 同时判断和执行。

| Skill | 负责交付的最终结果 |
| --- | --- |
| `ip-studio` | 创建、导入、修改、升版并锁定可长期复用的角色身份包。 |
| `ip-visuals` | 使用已锁定角色制作并归档头像、横幅、资料卡、封面、说明图、正文插图和整篇文章配图组。 |
| `motion-studio` | 根据真实运行时合同制作静态姿势、方向、循环、单次动作、过渡、透明帧、图集和 manifest。 |

Codex v2 桌宠不再由本仓库维护第二套实现。需要把已锁定角色制作成桌宠时，使用专门的 `hatch-pet` Skill，并把 IP Studio 当前主参考图交给它。

## 效果预览

三个 Skill 共享同一份角色身份真源。下面的角色主参考图由 `ip-studio` 锁定，后续内容视觉由 `ip-visuals` 消费，衍生结果不会反向改写角色身份。

<p align="center">
  <img src="docs/images/lantern-fox-master.webp" alt="灯笼狐正式主参考图示例" width="280">
</p>
<p align="center"><sub>正式主参考图：固定角色身份，不固定后续场景与动作。</sub></p>

<p align="center">
  <img src="docs/images/lantern-fox-banner.webp" alt="灯笼狐个人主页横幅示例" width="100%">
</p>
<p align="center"><sub>主页横幅：角色亲自承担画面中的信息关系。</sub></p>

<p align="center">
  <img src="docs/images/lantern-fox-explainer.webp" alt="同一 IP 驱动内容视觉的说明图示例" width="620">
</p>
<p align="center"><sub>说明图：身份保持稳定，表达方式由当前内容决定。</sub></p>

<p align="center">
  <img src="docs/images/lantern-fox-illustration.webp" alt="正文插图示例" width="100%">
</p>
<p align="center"><sub>正文插图：只解释当前段落最值得图像化的一项内容。</sub></p>

## 安装

先查看仓库中的三个 Skill：

```powershell
npx skills add CheshireMew/ip-studio --list
```

安装完整套件：

```powershell
npx skills add CheshireMew/ip-studio --skill '*' -g -a codex -y
```

如果只需要建立和维护角色身份，可以只安装 `ip-studio`：

```powershell
npx skills add CheshireMew/ip-studio --skill ip-studio -g -a codex -y
```

`ip-visuals` 和 `motion-studio` 会调用兄弟目录中 `ip-studio` 提供的正式角色包接口，因此使用静态视觉或动态素材时应安装整个套件。

## 使用

建立或修改角色身份：

```text
$ip-studio 从零为我设计并锁定一个可以长期复用的个人 IP 角色。
$ip-studio 把这张已经确认的角色图导入为角色包。
$ip-studio 读取 E:\path\to\character-kit，把斗篷改成墨蓝色，其它固定特征不变并升版。
```

制作静态内容视觉：

```text
$ip-visuals 使用“夜希”为下面这段正文制作一张 16:9 横版插图：……
$ip-visuals 使用 E:\path\to\character-kit，为这篇文章制作一组不重复的正文配图：……
```

制作运行时 2D 动作素材：

```text
$motion-studio 使用 E:\path\to\character-kit，读取这个 Godot 项目的真实状态机，只制作实际会触发的四方向站立、行走和工具动作。
$motion-studio 把这个角色做成前向应用助手，只需要待机、倾听、处理和完成状态，不要虚构方向动画。
```

制作 Codex v2 桌宠：

```text
$hatch-pet 使用 E:\path\to\character-kit 中的当前主参考图制作 Codex v2 桌宠。
```

## 共享角色包

从源码仓库运行时，`ip-studio` 把角色写入 Git 已忽略的 `ip-studio-output/<character-id>/`。从其它项目目录调用脚本不会把角色资料写进调用者项目。已安装的独立 Skill 则把本地工作区锚定在自身目录。

角色包中的 `character-profile.json` 和当前版本登记的单张主参考图是唯一身份真源。`ip-visuals` 与 `motion-studio` 只读取它们，并记录自己消费的准确角色 revision；静态图、动作帧、失败图和当前场景不会反向进入角色身份。

已有本地角色包不需要迁移，拆分前后的 `ip-studio-output/` 位置保持不变。

## 提示词与确认规则

用户已经提供完整提示词时，静态视觉流程原样传递，不追加构图、场景、动作、物件、配色、材质或装饰。没有完整提示词时，只写目标、原始材料、参考图职责、必要输出形式、固定机器协议和用户硬要求，不把维护字段、分析过程或方案理由塞进提示词。

任何新图、编辑或重试都先展示实际将发送的完整提示词和有序图片输入并停止。用户确认后，才把完全相同的输入交给图像入口；输入变化就重新确认。动态素材属于批量重活，还会在开始生成前同时展示运行时依据、任务数量、输出目录、项目改动范围和验收方式。

## 仓库结构

```text
skills/
  ip-studio/
    SKILL.md
    agents/openai.yaml
    references/character-system.md
    scripts/character_kit.py
  ip-visuals/
    SKILL.md
    agents/openai.yaml
    references/visual-production.md
    scripts/visual_kit.py
    assets/visual-languages/
  motion-studio/
    SKILL.md
    agents/openai.yaml
    references/dynamic-character-production.md
    scripts/motion_kit.py
    scripts/motion/
tests/
archive/
ip-studio-output/   # 本地角色与生产数据，Git 忽略
```

拆分前的单体入口位于 `archive/legacy-monolith/`，原 IP Studio 桌宠适配器位于 `archive/legacy-ip-studio-pet/`。两者只保留历史，不会被 Skill 安装器识别为活跃入口。原来的仓库根目录 `SKILL.md` 已迁移到 `skills/ip-studio/SKILL.md`。

## 验证

```powershell
python -m pytest tests -q
python ../meta-skills/scripts/quick_validate.py skills/ip-studio
python ../meta-skills/scripts/quick_validate.py skills/ip-visuals
python ../meta-skills/scripts/quick_validate.py skills/motion-studio
npx skills add . --list
```

`quick_validate.py` 来自同级的 `meta-skills` 仓库；普通使用者不需要它。三套脚本均按自身文件位置寻找资源，验证时还应从仓库外目录用绝对路径调用各自的 `schema` 命令。

## 隐私与许可

角色包、图片、QA 文件和动态运行记录保存在 Git 已忽略的本地工作区，不应提交到公开仓库。公开问题或贡献代码前，请确认提交中不包含角色私有素材、文章草稿、品牌资料、绝对路径、访问令牌或生成记录。

原创代码和 Skill 指令默认采用 [Apache License 2.0](LICENSE)。角色图片、生成媒体、视觉示例、Logo、商标和品牌素材按 [ASSET-LICENSE.md](ASSET-LICENSE.md) 及更近位置的来源或许可证说明处理。

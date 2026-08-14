---
name: pet-studio
description: "把已锁定的 2D IP 角色制作成桌面助手、应用宠物或其它运行环境可直接消费的离散状态宠物包，维护身份追溯、逐任务确认、方向动画 QA、无损运行历史和平台适配器；当前内置 Codex v2 适配器。Use when the user wants a locked IP character turned into a runtime-ready raster pet or wants a pet adapter produced, checked, packaged, installed, or revised. Do not use for character identity design, ordinary static visuals, general game or app character motion without pet behavior, video, Live2D, skeletal animation, or 3D."
---

# Pet Studio

把 `$ip-studio` 锁定的角色制作成由真实运行环境消费的离散状态式 2D 宠物，并维护角色来源、生产运行、方向动画检查、平台打包和安全安装。桌面助手、应用宠物和其它有限状态式宠物都属于本 Skill；Codex v2 是当前内置的平台适配器，不是本 Skill 的职责边界。

如果当前请求还没有锁定角色包，先用 `$ip-studio` 从用户提供的角色图或身份要求建立并锁定角色，然后继续完成同一请求，不让用户重新发起宠物任务。普通角色动作素材由 `$motion-studio` 完成；当用户最终要的是宠物语义、宠物包、平台适配或安装结果时，由本 Skill 负责并按需调用其共享动作合同。

## 输入、路由与权限

先取得锁定角色包，再读取真实目标运行时的状态生产者、方向来源、素材消费者、固定协议、包结构、安装位置和用户可见结果。目标已有内置适配器时使用该适配器；没有时，完整读取 `references/pet-production.md` 和兄弟 Skill 的 `../motion-studio/references/dynamic-character-production.md`，依据真实运行时建立动作合同、素材包与接入结果，不把 Codex 的九状态、十六方向或 8×11 图集套给其它平台。新增或修改平台适配器属于重大变更，按下面的确认边界执行。

本 Skill 不自动开启或关闭 Plan 模式。默认模式根据现有材料直接完成；用户主动开启 Plan 模式时，先读完现有材料并完成当前权限内的必要调查，再每轮只问一个必须由用户本人回答的宠物性格、动作感受或使用体验取舍问题。

宠物生产通常包含批量生图、大量产物、平台接入或安装。真正开始前先展示目标运行时、角色版本、状态与方向合同、任务数量、每个任务实际发送的完整提示词和有序图片输入、运行目录、项目或安装改动范围、成本影响和真实验收方式，然后停止。用户确认后才执行；提示词、图片输入、平台、文件范围、安装目标或验收方式变化时重新确认。

第一次准备生图前完整读取 `$imagegen`。每个新图、编辑、修复或重试任务都先展示唯一的实际提示词和有序图片输入，下一轮确认后原样交给图像入口。用户提供完整提示词时原样使用；没有时只加入目标、角色与其它原始材料、参考图职责、必要输出形式、平台固定协议和用户硬要求。方向分析和 QA 标准留在生成后检查，不扩写进生图提示词。

## 通用宠物生产

完整读取 `references/pet-production.md`。方向输入会连续改变宠物朝向或注视时，再读取 `references/direction-animation-qa.md`；没有连续方向输入时不虚构十六方向或方向盲审。

角色档案和当前主参考图是身份真源。每次运行记录角色 ID、revision、档案与主图哈希、宠物合同、提示词、图片输入、正式产物和检查结果。运行目录归档在角色包的 `derivatives/pets/` 下；旧运行、旧包和被替换任务进入历史，不被覆盖或删除。

没有专用适配器时，使用 `$motion-studio` 的正式合同和确定性生产入口完成目标运行时真正消费的状态、方向、透明帧、图集、manifest 与预览。本 Skill 继续负责宠物行为语义、角色适配、方向 QA、宠物包记录和用户要求的接入；只要求素材包时不修改目标项目，明确要求接入时才改真实消费者。

## Codex v2 内置适配器

用户目标是 Codex 桌宠时完整读取 `references/adapters/codex-v2.md`。所有命令都用当前 Skill 目录中的 `scripts/pet_kit.py`，它只实现 Codex v2 适配器；通用职责不由这个首个适配器反向定义。

```text
python <pet-studio-skill>/scripts/pet_kit.py schema
python <pet-studio-skill>/scripts/pet_kit.py prepare <character-kit> --adapter codex-v2
python <pet-studio-skill>/scripts/pet_kit.py ready <run-folder>
python <pet-studio-skill>/scripts/pet_kit.py check <run-folder> --stage prepared
```

`ready` 只返回依赖已经满足的任务。逐项展示登记的完整提示词和有序图片输入并取得确认后，才生成并实际打开结果；通过后运行：

```text
python <pet-studio-skill>/scripts/pet_kit.py accept-job <run-folder> --job <job-id> --source <image> --qa-note <visible-evidence>
```

全部状态、方向、透明处理和真实看图证据通过后才能运行 `finalize`。用户明确要求安装或可直接使用时，先 `check --stage final`，再运行 `install`；同名不同内容必须取得替换确认，安装器先备份旧目录并在失败时恢复。

## 完成状态

交付时展示最终总览和至少一个真实动作预览，再说明目标运行时、角色 revision、状态与方向、包路径、接入或安装状态。只有同一份真实产物通过正式生成、确定性检查和正常显示尺寸下的看图检查，并由真实消费者读取时，才声称宠物素材完成；项目接入还必须看到用户可观察的运行结果。没有独立看图能力时由用户检查总览与方向图，不伪造看图或盲审结论。

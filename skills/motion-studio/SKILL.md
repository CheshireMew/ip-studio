---
name: motion-studio
description: "把已锁定的 2D 角色转成由真实运行环境消费的静态姿势、方向、循环、单次动作、过渡、透明帧、图集和 manifest，并在明确要求时接入目标项目；只有角色图而没有角色包时先锁定身份再继续原请求。Use when a game, app, web interface, or assistant needs finite-state raster character motion. Do not use when the final requested result is a pet package or pet-platform installation, or for static content visuals, video, Live2D, skeletal animation, or 3D."
---

# Motion Studio

把 `$ip-studio` 锁定的 2D 角色转成真实运行环境会消费的静态姿势、方向、循环、单次动作、过渡、透明帧、图集和 manifest。它面向有限状态和逐帧位图驱动的游戏角色、应用助手、网页角色与状态式吉祥物；不创建角色身份，不制作普通静态内容视觉，也不处理视频、Live2D、骨骼动画或 3D。最终结果是桌面助手、应用宠物、宠物平台包或安装结果时由 `$pet-studio` 负责，本 Skill 只提供它需要的通用动作合同和确定性生产能力。

## 从真实运行时建立合同

先取得锁定角色包；只有角色图或身份要求而没有角色包时，先用 `$ip-studio` 锁定身份，再继续当前动作请求。完整读取 `references/dynamic-character-production.md`。目标项目存在时，读取真实的状态生产者、方向选择、动作结果发生位置、图片消费者、锚点、图集导入和最终可见结果；只有正式协议而没有代码时依据协议。不要从常见动画清单倒推动作：日程 NPC 可以只有四方向静态图，前向助手没有方向输入时不生成四向，转向只有在运行时存在独立过渡时才成为动画。

所有脚本都用当前 Skill 目录中的 `scripts/motion_kit.py`：

```text
python <motion-studio-skill>/scripts/motion_kit.py schema
python <motion-studio-skill>/scripts/motion_kit.py draft --motion-id <slug> --display-name <name> --output <contract>
python <motion-studio-skill>/scripts/motion_kit.py prepare <character-kit> --contract <contract>
python <motion-studio-skill>/scripts/motion_kit.py check <run-folder> --stage prepared
```

合同逐项记录目标表面、角色职责、镜头、状态与方向生产者、运行时消费者、用户可见结果、画布、脚底锚点，以及每个 `static`、`loop`、`oneshot` 或 `transition` clip 的方向、帧时长和效果发生帧。每个正式帧只能来自一个完整动作表格子，所有 clip 帧必须被映射，消费端不临时猜素材。

这是批量生图和大量产物工作。真正生成前先展示具体目标、角色版本、运行时依据、动作与方向清单、任务数量、完整提示词、有序图片输入、输出目录、项目改动范围和实际验收方式，并停止；用户确认后才开始。提示词或图片输入变化时重新确认，多个未改变的任务可以整批确认。第一次生图前完整读取 `$imagegen`，没有生图能力时停在已准备的合同、运行目录和完整任务输入。

## 整表生产与确定性处理

运行 `ready <run-folder>`，只处理返回的 `ready_jobs`。每个动作组在一张图片中生成全部方向与帧；网格只控制位置，成图不出现格线、标签或文字。不要按单帧分别生成再拼接，也不要把其它图片的人脸、头发、服装或肢体贴进完整帧。确定性处理只允许整人刚性位移、统一缩放、脚底对齐、软抠图和切格，不替换人物内部像素。

实际打开整表检查角色身份、完整身体、方向、动作顺序、帧数、尺度、基线、工具连接和背景后接受任务：

```text
python <motion-studio-skill>/scripts/motion_kit.py accept-sheet <run-folder> --job <group-id> --source <sheet> --qa-note <visible-evidence>
```

脚本输出透明图集、每个 clip 的透明 PNG 帧、APNG、无损 WebP 和处理报告。APNG 或无损 WebP承担颜色和循环验收；GIF 只在用户明确要求临时分享时生成。错误整帧或整组重新生成；被否决的已接受结果使用 `--replace-complete` 进入历史，不混入新包。

## 打包、接入与完成

全部动作组通过后运行：

```text
python <motion-studio-skill>/scripts/motion_kit.py finalize <run-folder>
python <motion-studio-skill>/scripts/motion_kit.py check <run-folder> --stage final
```

正式包包含 `motion-contract.json`、`motion-manifest.json`、透明图集和逐帧 PNG，预览与生成证据留在运行目录。只要求素材包时不修改目标项目；请求明确包含接入时，才让真实状态生产者选择 manifest 中的 clip，让方向输入切换方向，并让效果事件在登记帧通知玩法系统。

交付时展示动作表总览和实际 clip 预览，再说明角色版本、合同依据、动作与方向、效果事件和成品绝对路径。只有正式生产者输出存在、最终素材实际打开检查、`check` 通过且真实消费者已经读取，才声称素材完成；项目接入还必须看到用户可观察的运行结果。满足当前运行时结果后停止，不自动扩展动作、平台或桌宠版本。

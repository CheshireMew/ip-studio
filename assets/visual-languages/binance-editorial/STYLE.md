# Binance Editorial 视觉语言

`style-profile.json` 是日常生成唯一读取的视觉真源。它保存从五张来源案例中提炼出的两种画布模式、配色职责、字体层级、构图、场景家族、角色融合、Logo 使用边界、内容边界和成片检查；本文件不维护第二份参数。

正常请求把视觉简报的 `visual_language` 设为 `binance-editorial`，再由 `visual_kit.py` 读取 JSON 并编译进唯一提示词。五张案例不会在这一步打开或作为图片输入。默认 `image_references` 只有锁定角色主图和当前任务实际提供的资料。

`examples/` 保存本次提炼的来源证据。`logos/binance-mark-yellow.png` 与 `logos/binance-mark-black.png` 保存从来源案例中分离出的两种透明标记，用于适配深色或黄色背景。只有用户明确要求精确 Binance 标记时，才把其中一张作为当前品牌素材加入；它们不承担风格参考职责。来源和使用边界见 `SOURCE.md`。

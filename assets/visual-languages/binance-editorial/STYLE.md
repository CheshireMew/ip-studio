# Binance Editorial 视觉语言

`style-profile.json` 是日常生成唯一读取的视觉真源。顶层 `generation_text` 是真正送进图像模型的简短风格文字；详细的画布模式、配色职责、字体层级、构图、场景家族、角色融合、Logo 使用边界、内容边界和成片检查留在维护与归档侧，不整包倾倒进提示词。

正常请求把视觉简报的 `visual_language` 设为 `binance-editorial`，再由 `visual_kit.py` 把 `generation_text` 编译进唯一提示词。五张案例不会在这一步打开或作为图片输入。默认 `image_references` 依次包含锁定角色主图、黄色和黑色 Binance 标记，再接当前任务实际提供的资料。

`examples/` 保存本次提炼的来源证据。`logos/binance-mark-yellow.png` 与 `logos/binance-mark-black.png` 保存两种透明标记，用于适配深色或黄色／浅色背景。两张默认同时作为品牌素材提供，由图像模型根据自己最终选择的底色二选一使用；它们不承担风格参考职责。来源和使用边界见 `SOURCE.md`。

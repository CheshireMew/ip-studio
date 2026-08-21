# OKX Editorial 视觉语言

`style-profile.json` 是日常生成唯一读取的视觉真源。顶层 `generation_text` 是真正送进图像模型的简短风格文字；详细的配色职责、字体层级、构图、场景模式、角色融合、Logo 使用边界、内容边界和成片检查留在维护与归档侧，不整包倾倒进提示词。

正常请求把视觉简报的 `visual_language` 设为 `okx-editorial`，再由 `visual_kit.py` 把 `generation_text` 编译进唯一提示词。七张案例不会在这一步打开或作为图片输入。默认 `image_references` 依次包含锁定角色主图、白色 OKX 标记，再接当前任务实际提供的资料。

`examples/` 保存最初提炼这套视觉语言的来源证据，`logos/okx-mark-white.png` 保存精确品牌素材并在 OKX 风格请求中默认加入；它不承担风格参考职责。来源和使用边界见 `SOURCE.md`。

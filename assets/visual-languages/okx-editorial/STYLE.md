# OKX Editorial 视觉语言

`style-profile.json` 是日常生成唯一读取的视觉真源。它完整保存配色职责、字体层级、构图、场景模式、角色融合、Logo 使用边界、内容边界和成片检查；本文件不维护第二份参数。

正常请求把视觉简报的 `visual_language` 设为 `okx-editorial`，再由 `visual_kit.py` 读取 JSON 并编译进唯一提示词。七张案例不会在这一步打开或作为图片输入。默认 `image_references` 只有锁定角色主图和当前任务实际提供的资料。

`examples/` 保存最初提炼这套视觉语言的来源证据，`logos/okx-mark-white.png` 保存可选的精确品牌素材。用户明确要求精确 OKX Logo 时，可以把后者作为当前品牌素材加入；它不承担风格参考职责。来源和使用边界见 `SOURCE.md`。

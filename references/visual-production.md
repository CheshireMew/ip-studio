# IP 衍生视觉生产方法

在 `SKILL.md` 已确认用户要用现有 IP 角色制作头像、主页横幅、资料卡、文章封面、说明图或正文插图后读取本文件。它负责视觉简报、生图、检查和归档；一次性结果可以直接使用用户提供的角色图，可长期复用的结果仍由 `character-profile.json` 与其中登记的单张主参考图决定身份。

## 1. 先建立干净的视觉简报

运行 `python scripts/visual_kit.py schema` 读取当前合同，需要文件草稿时运行：

```text
python scripts/visual_kit.py draft <brief-path> --kind <kind> --visual-id <slug> --language <language>
```

Agent 从当前请求和用户资料建立草稿，用户不需要编辑 JSON。`prompt_text` 是实际准备交给图像模型的完整提示词：用户已经提供完整提示词时原样保存；没有完整提示词时，只写目标、完整内容材料、实际参考图职责、必要输出比例、逐字文字或 logo 等用户硬要求。开放的视觉中心、构图、场景、动作、物件、排版、配色、光影、材质和装饰由下游图像 AI 决定，不因为 Agent 能够分析内容就提前填满。

未选择其它视觉语言的默认文章封面没有完整提示词时不由 Agent 另写提示词，保持 `prompt_text` 为空，把文章全文原样写入 `content.source_text`。`scripts/visual_kit.py` 会读取由主入口路由的唯一活动封面模板，只代入用户比例、实际图片职责和完整正文；标题、核心对象、关键变化、品牌层级、角色动作与视觉叙事都由收到这份完整输入的图像模型在同一次生成中决定。

现有 `message`、`composition`、`character_action` 和 `decisions` 字段只为读取旧归档保留。新视觉可以保持为空或默认值；脚本不会把它们编译进生图提示词。图片资料仍分别登记身份、logo、界面、物品或风格参考的真实职责，参考图不得向当前内容补充事实。

## 2. 角色与资料怎样进入生图

使用已锁定角色包时运行：

```text
python scripts/visual_kit.py prompt <character-kit> --brief <brief-path>
```

只有一张已认可角色图并且只做当前一次结果时运行：

```text
python scripts/visual_kit.py prompt-once <approved-character-image> --brief <brief-path>
```

两条命令都会先验证视觉简报。输出的 `image_references` 按顺序列出角色参考图和其它资料；用户提供完整 `prompt_text` 时原样输出，默认文章封面读取正式封面模板，其它旧简报没有 `prompt_text` 时才由完整内容、必要比例、结果类型和图片职责形成简短兼容提示词。普通衍生图不再附加完整角色档案。`prompt-once` 不创建角色包或正式衍生归档。

角色身份和当前画面职责分别处理：

- 主参考图决定轮廓、比例、脸部、颜色落点、服装连接、材质和标志物；档案留在维护与归档侧。
- 用户提示词和硬要求决定必须固定的动作、场景、画幅、文字或其它内容；未固定部分由图像 AI 决定。
- 当前图片中偶然出现的衣饰、纹样和配件不写回角色档案。
- 衍生图不会成为新的角色参考图。用户明确要改变身份特征时返回角色修改流程，升版后再重新生成衍生图。

每张图片输入只承担一种明确职责：角色主参考图负责身份，用户当前提供的 logo 负责准确品牌标记，构图或界面资料负责当前页面关系。内置视觉语言可以提供用户明确选择的风格名称或实际参考图，但完整 JSON、维护说明、分析过程、备选方向、QA 检查表和通用负面词清单都不进入提示词。

### 极简手绘内容视觉

“极简手绘 IP”是封面、说明图和正文插图可选的内容视觉语言，不是头像、主页视觉或所有角色的全局默认值。用户明确选择，或当前任务确实需要低信息密度、强隐喻和高频复用时再采用。已有角色仍保留主轮廓、脸部锚点、主配色落点和标志物；若极简化会改变这些固定身份特征，先返回角色修改流程建立新版本，不能在衍生图里偷偷改画法。

选择后只把“极简手绘 IP”作为用户确认的风格目标，并把正式案例作为图片参考。具体隐喻、物件、动作、空间关系、留白和颜色组织由图像 AI 根据当前内容决定；Agent 不把案例拆成新的构图规格，也不把这一节改写成长串限制。

启用时先运行：

```text
python scripts/visual_kit.py style-references minimal-handdrawn
```

把命令输出的 `brief_references` 原样写入视觉简报的 `references`。这些绝对路径由脚本从内置资源清单生成，避免简报位于其它目录时解析到错误位置。案例只作为实际风格图片输入，不提供当前内容的事实或构图；来源与许可见命令输出的 `source_notice`。

### OKX Editorial 品牌编辑视觉

用户要求 OKX 风格，并且作品使用已锁定 IP 角色时，运行：

```text
python scripts/visual_kit.py style-profile okx-editorial
```

把视觉简报的 `visual_language` 设为 `okx-editorial`。命令返回 `style-profile.json` 的已验证内容、绝对路径和 SHA-256；脚本在生成提示词时读取同一文件，并在归档时保存本次 JSON 快照与哈希。七张来源案例和透明 Logo 留在资源目录中用于追溯提炼依据，不参与默认生成。

正常 OKX 风格生成的 `image_references` 只有角色主图和当前任务确实需要的资料。用户明确要求精确 OKX Logo 时，再把已保存的透明 Logo 作为当前品牌素材加入简报；普通风格请求不自动加载它。JSON 留在维护侧用于说明来源，不整体复制进提示词；提示词只保留用户选择的“OKX Editorial”风格名称。

### Binance Editorial 品牌编辑视觉

用户要求币安或 Binance 风格，并且作品使用已锁定 IP 角色时，运行：

```text
python scripts/visual_kit.py style-profile binance-editorial
```

把视觉简报的 `visual_language` 设为 `binance-editorial`。它与 OKX Editorial 使用同一套 prompt-profile 合同：命令返回已验证的 JSON、绝对路径和 SHA-256；生成时读取同一文件，归档时保存当次快照与哈希。五张来源案例只保留为提炼依据，不参与日常生成，也不向当前内容补充旧活动文案、奖励、人物、界面、商品、二维码或构图。

默认图片输入只有角色主图和当前任务资料；用户明确要求精确 Binance 标记时，才按底色加入资源目录中的黄色或黑色透明标记。JSON 留在维护侧用于说明来源，不整体复制进提示词；提示词只保留用户选择的“Binance Editorial”风格名称，具体画布和场景由图像 AI 决定。

## 3. 头像、主页横幅和资料卡

所有衍生视觉都接受任意合法的正整数 `宽:高` 比例。以下比例只在用户没有指定时作为默认值，不构成白名单。

### 头像

默认输出一张可用于圆形和方形裁切的 `1:1` 头像源图。提示词只固定角色参考、平台裁切要求和用户明确内容；人物姿态、背景、色彩和表现方式由图像 AI 决定。用户明确要求多个独立头像版本时再分别建立任务。

### 主页横幅

未指定平台时使用 `3:1` 通用主页横幅。用户指定平台且提供页面截图或尺寸时，以资料中的实际裁切、头像和按钮位置为准；其它构图和角色表现由图像 AI 决定。

需要平台当前规格且用户没有提供资料时，先查询该平台的官方尺寸与安全区。规格只影响当前视觉简报，不写入角色档案。

### 资料卡

默认使用 `4:5` 手机端比例。名称、定位、标签或其它逐字内容只有用户明确要求时才进入提示词，版式、动作和背景由图像 AI 决定。

完整角色档案只用于保持身份，不把三视图、配色表、结构清单或生图说明画进资料卡。

用户说“主页套图”时，默认交付一张头像和一张主页横幅；明确要求资料卡时再加入资料卡。三张图分别建立简报、生成和归档，共享同一角色版本和品牌线索。

## 4. 文章封面

用户没有指定比例时默认使用 `5:2` 横版；用户指定其它比例时原样采用。默认封面提示词直接使用主入口路由的正式模板，输入只有完整正文、实际图片职责和比例。Agent 不先提炼标题、核心对象、关键变化、品牌层级、角色动作或构图；模板把这些判断与最终成图留在同一次图像生成中完成。

## 5. 说明图

默认使用 `4:5`；方形社交卡使用 `1:1`；纵向内容可用 `3:4`；横向内容可用 `16:9`。提示词只固定完整信息、准确文字、实际资料、用途和用户指定比例；图解结构、模块数量、角色动作、连线、配色和阅读顺序由图像 AI 决定。

## 6. 正文插图

用户没有指定比例时默认使用 `16:9` 横版。提示词交付当前段落或章节的完整内容、角色参考、用户明确的文字和用途；具体选择隐喻、流程、结构、对比或场景，以及角色怎样参与，都由图像 AI 决定。

## 7. 整篇文章配图组

用户要求给整篇文章配图时，先规划全组，不按段落机械出图，也不先假定四张或八张。运行：

```text
python scripts/visual_kit.py plan-schema
python scripts/visual_kit.py plan-draft <plan-path> --set-id <slug> --language <language>
```

阅读全文，找出只有图像化后才会明显降低理解成本的认知锚点。每项必须记录互不重复的核心关系、应该插在哪段之后，以及能在原文中按顺序找到的 `source_excerpt`；数量由真实锚点决定。相邻图片不能重复解释同一结论，纯装饰、换句话说和没有角色作用空间的段落不进入计划。

根据关系选择结构：变化过程或步骤用 `process`，前后差异用 `comparison`，对象间依赖用 `structural-relation`，抽象判断用 `conceptual-metaphor`，具体情境用 `local-scene`。物件、动作和空间关系必须从当前文章重新创造，不从风格案例复制固定物件池。

完成计划后运行：

```text
python scripts/visual_kit.py materialize-plan <plan-path> --output <ordered-brief-directory>
```

脚本验证原文片段与顺序，为每个锚点生成现有 `article-illustration` 简报。按返回顺序逐张运行 `prompt`，先把本批所有完整提示词和图片输入展示给用户；用户确认后下一轮才逐张原样生图并 `finalize`。每张只生成一版并遵守同一单图合同，不建立第二套文章插图提示格式。全部归档后运行：

```text
python scripts/visual_kit.py finalize-set <character-kit> --plan <plan-path>
python scripts/visual_kit.py check-set <article-set-folder> --kit <character-kit>
```

文章配图组记录正文顺序、插入位置、原文锚点和它实际消费的每一个 visual revision。任何单图缺失、未归档，或者与计划登记的 `visual_id` 不一致时，整组不能归档完成。

## 8. 第一版交付与用户要求的修订

衍生视觉默认只生成一版。生图前先展示实际完整提示词和图片输入，等待用户确认；确认后不得改写。图片正常生成后直接归档并交给用户，不先进行审美筛选，不因为 Agent 发现文字、构图、角色动作或细节问题而修改简报、自动重生、生成多个候选或替用户选择。用户明确要求检查、修正、比较或授权 Agent 代选时，新的提示词仍须先展示并重新确认。

用户明确要求检查、修正、比较或授权 Agent 代选后，才实际打开当前成图，只对照原始提示词、输入图片、内容真源和用户点名的问题说明具体差异。用户确认需要修改后，按实际问题选择第 9 节的修订范围；不把一次成品瑕疵升级成以后每张图都要经过的自动检查和重试。需要改变事实、叙事重点或角色固定特征时，返回 `SKILL.md` 的主流程处理取舍。

## 9. 已归档视觉的无损修订

用户要求“删标题，其它不变”“改错字”“调整动作”或“换重点”时，先读取 visual 根目录的 `current.json`、当前 revision 的 `visual-record.json`、视觉简报和最终图片，再选择唯一修订范围：

- `local-rendering`：删除或替换局部文字、修明显渲染错误、轻调局部位置；上一版成图是编辑底图，未点名内容保持不变。
- `content-structure`：核心重点、动作因果、构图结构或文字层级发生变化；从内容真源和角色真源按新简报重做，上一版只校准连续性。
- `character-revision`：固定角色特征已正式升版；新主参考图是身份真源，旧成图只保留当前视觉的用途和节奏。

先修改同一个 visual-id 的简报，再运行：

```text
python scripts/visual_kit.py revision-prompt <character-kit> --visual <visual-folder> --brief <revised-brief> --change-scope <scope> --note <exact-change>
```

先把返回的完整 `prompt` 和有序 `image_references` 展示给用户并停止；确认后下一轮才原样编辑或重生，其中第二张输入固定为上一版成图。检查通过后运行：

```text
python scripts/visual_kit.py revise <character-kit> --visual <visual-folder> --brief <revised-brief> --image <approved-image> --change-scope <scope> --note <exact-change>
python scripts/visual_kit.py check <visual-folder> --kit <character-kit>
```

每次修订创建 `r002`、`r003` 等新目录，旧 revision 与生成输入继续保留。不要覆盖旧图，也不要另建一个失去父版本关系的新 visual-id。角色未升版时不能使用 `character-revision`，角色已经改变时也不能把它伪装成局部修图。

旧版平铺目录不属于正常运行合同。发现 `<visual-folder>/visual-record.json` 而没有 `current.json` 时，只能显式运行一次：

```text
python scripts/visual_kit.py migrate-visual <visual-folder> --kit <character-kit>
```

迁移把旧结果变成 `r001`，并把原平铺目录移动到同级 `.ip-studio-legacy-archives/` 保留。迁移完成后，`prompt`、`revise`、`check` 和文章配图组只消费版本化结构，不维护两套读取逻辑。

## 10. 归档与停止

第一张结果生成后直接运行：

```text
python scripts/visual_kit.py finalize <character-kit> --brief <brief-path> --image <approved-image>
python scripts/visual_kit.py check <visual-folder> --kit <character-kit>
```

正式产物写入：

```text
<character-kit>/derivatives/<kind>/<visual-id>/
├── current.json
└── revisions/
    ├── r001/
    └── r002/
```

每个 revision 保存最终图片、视觉简报、当次角色档案快照、完整生图输入、输入资料副本、父版本与变更范围；`current.json` 只指向当前 revision。角色包当前身份文件及历史版本保持不变。只有用户明确要求另做、检查或修订时才产生新的候选或 revision。

归档后重新读取当前 revision 的 `visual-record.json`，把登记的最终图片直接展示给用户，再说明它表达的核心关系、visual revision、角色版本和绝对保存路径；文章配图组按正文顺序展示。满足当前请求后停止，不自动检查、重生、扩展成其它比例或其它媒体。

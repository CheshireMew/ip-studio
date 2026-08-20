---
name: ip-studio
description: "创建、锁定并长期复用个人或品牌 IP 角色，并用同一角色实际制作头像、主页横幅、资料卡、文章视觉、离散状态式 2D 动态角色素材和 Codex v2 桌宠；环境没有生图能力时才回退为完整提示词包。Use when a user wants to turn identity cues or existing art into a stable stylized character kit; use that locked character in social or content visuals; produce runtime-grounded static poses, directional clips, state loops, one-shot actions, transitions, sprite atlases, or interface-character motion; or build a Codex-compatible v2 pet as one fixed platform adapter. Do not use for generic visuals without an IP character, photorealistic digital doubles, general motion graphics, skeletal animation, Live2D, video, or 3D."
---

# IP Studio
把身份线索或已有角色图变成可跨会话复用的角色包，再用同一身份制作社交视觉、内容视觉和离散状态式 2D 动态角色。角色档案与其中登记的单张主参考图是身份真源；衍生图和动态素材只消费它们，不反向改变角色。

## 路由与边界
先按用户要得到的独立结果选择路径：

- **一次性角色图**：用户只要求生成或修改当前这一张角色图，没有明确要求建立、锁定、导入、升级或长期复用角色身份。即使用户点名 `$ip-studio`，也直接把当前图片任务交给图像入口；不得创建工作区、角色档案、角色包、版本、历史或一致性测试，也不得运行 `workspace`、`schema`、`draft`、`prompt --purpose master` 或 `finalize`。图片生成、检查并交付后停止。用户说明图片以后可能用于某个项目，不等于要求现在建立角色包。
- **一次性衍生视觉**：用户提供一张已经认可的角色图，只要求当前这一张头像、横幅、资料卡、封面、说明图或正文插图，并且没有要求长期复用角色身份。直接使用该图片和对应衍生视觉模板，不先导入或锁定角色包，也不创建角色版本、历史或正式衍生归档。
- **角色身份**：从零创建、导入已有形象，或修改已锁定角色。
- **可长期复用的衍生视觉**：头像、主页横幅、资料卡、文章封面、说明图、单张正文插图、整篇文章配图组或既有衍生图修订。用户要求以后继续复用同一身份、保存版本或归档衍生图时，只有图片而没有角色包先导入并锁定；没有角色时先完成角色身份路径。
- **动态角色素材**：从真实运行环境反推静态姿势、方向、循环、单次动作、过渡、命中事件、锚点与导出格式，再用已锁定角色制作完整动作表、透明帧、图集和无损预览。游戏小人、应用助手、网页角色和状态式吉祥物走此路径。
- **Codex 桌宠**：动态角色素材的固定平台适配器。它继续输出九组应用状态、十六个注视方向和 Codex v2 8×11 图集，并在用户要求可用或安装时写入本机 Codex。

当前请求明确同时包含长期角色身份和其它结果时，先锁定角色，再分别完成点名的结果；不能根据此前项目背景或图片未来可能的用途自行增加建档。普通个人品牌策划、没有 IP 角色参与的一般视觉、照片级数字分身、一般动效、骨骼动画、Live2D、视频和 3D 不属于本 Skill。其它桌宠或角色平台只有在能由离散状态、方向和逐帧 2D 素材完整表达时才进入动态角色路径；安装协议另行确认。用户只点名 `$ip-studio` 而没有说明要得到什么时，询问本次结果，不默认创建角色。

## 通用决策与权限
信息依次取自当前请求、当前对话、用户提供或明确指向的图片、文档、链接和角色目录。材料足够时由 Agent 直接发展一个完整方向，不自动生成多个候选；只有缺失信息会改变身份、事实、品牌方向、核心叙事或既有安装时，才提出一个具体取舍。只有用户明确要求比较时才提供多个方向。角色基于已有品牌、作品或公共形象时，先从用户提供的说明与素材中确认已经形成的美术锚点；只有名称而没有视觉材料时，查看官方标志、官方主色和已经稳定重复的公共二创形象，再开始设计。公开材料只用于找出观众已经能够识别的共同线索，不替用户决定尚未形成共识的细节。本 Skill 不自动开启或关闭 Plan 模式。默认模式根据现有材料直接完成单一路线；用户主动开启 Plan 模式时，先读完已有材料并完成当前权限内必要的调查、联网补充或外部材料发现，再使用 `request_user_input` 每轮只追问一个只有用户能够回答的审美、情绪或取舍问题。用户自然、有辨识度的原话、矛盾和边界进入后续角色设计，不重复询问；访谈不替代图像输入确认、外部写入或其它既有授权。

调用本 Skill 已授权查看用户提供的图片、项目中与角色状态生产和消费直接相关的代码与素材合同，并使用现有生图与看图能力；只有当前请求明确进入角色身份、衍生视觉、动态角色或桌宠路径时，才授权在本 Skill 仓库自己的本地工作区创建相应目录和档案。请求“可用的 Codex 桌宠”包含写入本机 Codex 宠物目录；不同内容占用同一标识时，先保留旧目录并请求替换决定。其它运行时接入、安装、上传、发送或发布必须由请求明确包含。本流程不删除既有角色版本、正式衍生图、动态运行记录或旧安装。角色创建或升版、整篇配图组、动态角色素材、Codex 桌宠、批量结果、项目接入或安装开始前，先完成确定范围所需的只读检查，再向用户展示具体目标、锁定输入、预计任务量、主要动作、产物与影响位置、耗时或付费及安装影响、真实验收方式，并停止等待确认。确认后才创建本次正式运行目录或开始生产；范围、输入、成本、权限或验收变化时重新确认。一次性角色图、单张衍生视觉和低成本、易恢复的小任务不增加这道总确认，仍遵守后续提示词确认。

回复语言跟随用户。内部档案使用固定英文键名，用户不需要编辑 JSON、提示词、文件名、编号或分支。

### 图像能力分流
当前路径需要位图成品时只选择一次图像入口。Codex 环境存在 `$imagegen` 时在第一次准备生图前完整读取它，其它 Agent 使用自身原生生图或编辑能力。实际交给图像入口的文字只有一份：用户已经给出完整图片要求时保持原意直接使用，只做图片顺序等必要指代澄清；要求尚不完整时，只补齐目标、参考图职责、必要输出形式和用户硬要求。有参考图时由图片承担已经可见的角色外观，不把头脸、发型、身体、服装、配色、材质、标志物或视角结构重新翻译成文字，也不加入角色档案、设计理由、精确色值、负面清单、验收标准和维护记录。

任何新图、编辑、重试或新动作任务都先把实际将发送的完整提示词和有序图片输入直接展示给用户并停止；用户只需要看到这两项，脚本返回的路径、角色编号、Schema、状态、字符数、哈希和其它校验记录留在内部。只有用户明确确认后，下一轮才把完全相同的提示词和图片输入交给图像入口。提示词或图片输入发生任何变化时重新展示并等待确认。多个已经准备好的任务可以一次展示并整批确认，确认只覆盖这批未改变的输入。具有生图能力时，确认后继续到实际生成和当前请求明确包含的归档；一次性角色图不归档为角色包。没有确认或环境没有生图能力时停在提示词与图片输入。后续角色、衍生视觉、动态角色和桌宠路径都遵守这个共同确认边界，不各自重新判断 provider。

有生图但没有独立看图能力时可以交付候选，不能声称视觉检查或最终定稿通过；有看图能力时必须实际打开生产者输出，不用文字描述或消费端假数据代替图片。

## 一次性衍生视觉路径
本路径直接消费用户提供的已认可角色图，不建立长期角色包。完整读取 `references/visual-production.md`；默认文章封面还要完整读取 `references/cover-prompt.md`。用户已有完整提示词时原样写入 `prompt_text`；否则只保留本次成品需要的内容材料、图片职责和用户比例，比例不按类型设白名单。默认文章封面没有完整提示词时保持 `prompt_text` 为空，把本次封面需要的内容原文写入 `content.source_text`；Agent 不预填标题、核心对象、角色动作或构图。依次运行 `python scripts/visual_kit.py schema`、`python scripts/visual_kit.py draft <brief-path> --kind <kind> --visual-id <slug> --language <language>` 和 `python scripts/visual_kit.py prompt-once <approved-character-image> --brief <brief-path>`。把输出的 `prompt` 和 `image_references` 完整展示并等待确认；确认后原样生图。一次性结果不运行 `finalize`，不写入角色包。

## 角色身份主路径
先完整读取 `references/character-system.md`。它负责单一路线角色发展、可选的极简手绘 IP 方向、正常比例动漫形象图、档案结构、生图、看图检查、复杂部件和一致性方法。

开始创建或导入角色前先运行：

```text
python scripts/character_kit.py workspace --character-id <slug>
```

脚本根据 `ip-studio` 仓库自身位置返回绝对的 `output_root`、`character_kit` 和 `work_area`，不读取当前终端目录。新角色的草稿、候选图和检查文件放入 `work_area`，正式角色包写入 `character_kit`；后续衍生视觉、动态素材和桌宠继续归档在这个角色包内。不得用调用方项目的当前目录自行拼出 `ip-studio-output`。只有用户明确提供了另一个既有角色包路径时，才直接使用该路径。

### 1. 先得到可判断的角色形象
先区分从零创建、导入和修改。从零创建时不要先创建或填写 `character-profile.json`，也不要运行 `prompt --purpose master`。第一张图的唯一创作输入只包含用户原始目标、用户提供的材料、已经确认的美术锚点、正常比例全身动漫形象这一必要输出形式，以及用户明确提出的硬边界。美术锚点是来源已经占据公众记忆的稳定识别组合，例如主色系、角色原型、动物或物件拟人特征和反复出现的标志形态；它们是必须继承的认知资产，不因常见而被当成俗套删掉。没有被用户、材料或公共共识确定的脸、发型、服装细节、表情、姿势和构图由图像模型在锚点之内共同决定。Agent 先把实际将发送的这份简洁提示词和图片输入完整展示给用户，获确认后原样生成一张。

第一张图必须是单角色、正常比例、完整全身并具有鲜明动作张力的动漫角色形象，不先做方向卡、候选组、Q 版、黑色剪影、中性站桩、设定表或多视图。拟人角色默认使用自然、亲和且容易被不同画师复现的人体基型；动物或物件身份优先通过已有美术锚点进入耳、角、尾、发型、配色、纹样、服装轮廓或随身标志。除非来源本身如此或用户明确要求，不为了显得原创而改变四肢、器官和人体连接方式，也不额外发明需要设定说明才能理解的异常结构。生成后实际打开图片，只根据用户已经确认的要求、美术锚点和图片中真实可见的结果判断；此时没有角色档案可供反向判定。用户否定设计时，根据其具体反馈修改同一份创作输入并重新提交一张，不自动扩成三个候选。任何新提示词仍按图像确认边界先展示。只有用户明确要求比较时，才建立互不继承的多个方向。

导入已有形象时，用户已经认可的图片直接作为待建档主参考候选，不重新设计。修改已锁定角色时读取现有 `character-profile.json` 与主参考图；不改变身份锚点的任务不返回本路径，重新设计轮廓、脸部、核心配色或标志物时先产生并确认新的角色形象，获批后再升版。

### 2. 从获批图片建立身份真源
只有用户认可第一张形象或明确提供了已认可形象后，才运行当前 schema 并由 Agent 创建档案：

```text
python scripts/character_kit.py schema
python scripts/character_kit.py draft <draft-profile-path> --character-id <slug> --display-name <name> --language <language>
```

以获批图片和用户已经确认的要求为输入，分开记录来源美术锚点、图片中稳定可见的角色化表达，以及当前姿势、光线或背景造成的偶然细节。美术锚点和用户确认的固定形象进入一致性边界；发型、服装或表情中没有承担来源识别的部分仍可按用户选择保持灵活。逐项补全到另一位 Agent 无需发明身份关键细节就能重建正面、侧面和背面；图片未显示但不会改变轮廓、脸部、主配色、标志物或含义的背面、接缝和连接由 Agent 采用最简洁结构补全，并标记 `agent_inferred`。会改变这些身份锚点的分歧才交给用户。

从这一步起，`character-profile.json` 与获批主参考图共同构成身份真源。档案负责可复原结构，主参考图负责实际视觉身份；不再维护另一份平行身份提示词。姿势、动作、场景、画幅和镜头只进入当次任务。

### 3. 一致性测试与无损锁定
使用刚建立的档案和获批图片运行：

```text
python scripts/character_kit.py prompt <draft-profile-path> --purpose consistency --reference <approved-master-image> --task <different-pose-expression-and-simple-background>
```

把输出的 `prompt` 与 `master_reference` 展示给用户；确认后才一起生图。测试图必须保留形体、脸部、颜色落点、服装连接、材质和标志物，只用于检查，不成为长期参考。失败时修正档案或主参考图；新提示词重新确认，仍需放弃已批准特征时再交给用户决定。

`prompt --purpose master` 只用于角色外观已经由获批资料完整确定、但确实需要按现有档案重建主图的恢复或重绘任务；它不是从零设计入口。正常从零流程直接把用户认可的第一张形象作为主参考图，不再根据后来建立的档案重画一次。

一致性测试通过后，使用 `workspace` 命令返回的绝对 `character_kit`：

```text
python scripts/character_kit.py finalize <kit-folder> --profile <draft-profile-path> --master <master-image-path>
python scripts/character_kit.py check <kit-folder>
```

`finalize` 写入新版本并把旧档案、说明和主图保存在历史中。成功后重新读取 `character-profile.json`、`character-guide.md` 和实际主图，再运行一次：

```text
python scripts/character_kit.py prompt <kit-folder> --purpose scene --task <simple-reuse-task>
```

只有当前档案、说明、主图、历史和派生提示词均可读取且 `check` 通过，角色才算锁定。

## 衍生视觉主路径
本路径只消费锁定角色。完整读取 `references/visual-production.md`，再按用户点名建立一个或多个独立结果：`avatar`、`profile-banner`、`profile-card`、`cover`、`explainer`、单张 `article-illustration`、有序文章配图组或既有 visual 的新修订。主页套图默认含头像和主页横幅，明确要求时再加入资料卡；每个结果共享角色版本，但分别建立简报、生成和归档。

用户用名称或英文名点名已有角色时，先运行：

```text
python scripts/character_kit.py resolve-character <name-or-id>
```

直接使用返回的 `character_kit`、`work_area`、角色档案和主参考图。角色档案中的 `display_name` 与 `character_id` 共同承担稳定寻址，不另建第二份注册表，不根据读音猜英文 ID，也不遍历其它目录寻找角色。找不到或同名时由命令明确报错。

### 1. 建立简报并选择视觉语言
```text
python scripts/visual_kit.py schema
python scripts/visual_kit.py draft <brief-path> --kind <kind> --visual-id <slug> --language <language>
```

视觉简报保留用户原始要求、本次成品需要的内容材料、必要输出格式和实际图片资料。用户已经给出完整提示词时，把它原样写入 `prompt_text`；没有完整提示词时，Agent 只根据目标、本次成品需要的内容材料、参考图职责、必要比例与用户硬要求写一条简洁准确的 `prompt_text`，不替下游图像 AI 预选视觉中心、构图、场景、动作、物件、文字层级、配色、光影、材质或装饰方法。未选择其它视觉语言的默认文章封面是唯一例外：`prompt_text` 保持为空，由正式封面模板直接消费这些内容材料、图片职责和比例，在同一次生图中完成标题与视觉叙事。角色主参考图负责身份；完整角色档案、传播分析、方案理由、失败归因和归档字段不进入普通衍生图提示词。

整篇文章配图不逐段盲目出图。先运行 `plan-schema` 和 `plan-draft`，从全文找出互不重复的认知锚点，为每项记录正文插入位置与原文片段，再用 `materialize-plan` 生成按正文顺序排列的现有 `article-illustration` 简报。数量由锚点决定，不套固定张数。完整命令和结构选择见 reference。

封面、说明图和正文插图可选择 reference 中的“极简手绘 IP”内容视觉；选中后先运行 `python scripts/visual_kit.py style-references minimal-handdrawn`，再把脚本返回的完整案例清单写入 `references`，使视觉语言和实际参考图共同进入生图链。它不是全局默认，也不能借衍生图改写已锁定角色的身份画法。

用户要求“OKX 风格”且当前结果包含已锁定 IP 角色时，把简报的 `visual_language` 设为 `okx-editorial`。它适用于主页横幅、资料卡、封面、说明图和正文插图；运行 `python scripts/visual_kit.py style-profile okx-editorial` 可以查看维护侧的 JSON 风格资料。普通生图提示词只写用户选择的风格名称，不复制完整 JSON；`image_references` 默认只有角色主图和当前任务确实需要的界面或素材。透明 OKX 标记也不自动加载，只有用户明确要求精确 Logo 时才把 `assets/visual-languages/okx-editorial/logos/okx-mark-white.png` 作为当前品牌素材加入。

用户要求“币安风格”或“Binance 风格”且当前结果包含已锁定 IP 角色时，把简报的 `visual_language` 设为 `binance-editorial`。它支持与 OKX 同样的五类衍生视觉；运行 `python scripts/visual_kit.py style-profile binance-editorial` 查看维护侧的 JSON 风格资料。普通生图提示词只写用户选择的风格名称，不复制完整 JSON 或预选场景家族。只有用户明确要求精确 Binance 标记时，才根据底色把 `assets/visual-languages/binance-editorial/logos/binance-mark-yellow.png` 或 `binance-mark-black.png` 作为当前品牌素材加入。

### 2. 生成和归档
```text
python scripts/visual_kit.py prompt <kit-folder> --brief <brief-path>
```

命令输出的 `prompt` 是本次唯一生图文字输入，`image_references` 是有序图片输入。先把两者完整展示给用户并停止；用户确认后下一轮才原样执行，不另写、扩写或改写提示词。第一张正常生成的结果就是本次成品；不以内部看图、文字瑕疵或审美判断为由修改简报、自动重生或换一张代替它。用户之后明确要求检查、修正或另做一版时，先产生新的完整提示词和图片输入，再重新等待确认。

第一张结果生成后直接运行：

```text
python scripts/visual_kit.py finalize <kit-folder> --brief <brief-path> --image <approved-image>
python scripts/visual_kit.py check <visual-folder> --kit <kit-folder>
```

正式结果进入 `<kit-folder>/derivatives/<kind>/<visual-id>/revisions/rNNN/`，visual 根目录的 `current.json` 指向当前版本。重新读取当前 revision 的 `visual-record.json`，确认角色版本、简报、完整生图输入、输入资料和校验值都可读取，然后把登记图片交给用户。默认不会出现由 Agent 自动生成的候选图或重试图。

修订时先按 reference 判定 `local-rendering`、`content-structure` 或 `character-revision`，运行 `revision-prompt` 并把上一版成图作为正式输入，再用 `revise` 创建下一 revision；不覆盖旧图，也不换一个失去来源关系的新 visual-id。旧的平铺衍生目录只能显式运行一次 `migrate-visual`，迁移后正常路径不再读取旧结构。文章全部单图通过后运行 `finalize-set` 与 `check-set`，归档其正文顺序和所消费的精确 visual revisions。

## 动态角色素材主路径
本路径只消费锁定角色。完整读取 `references/dynamic-character-production.md`；它负责从目标运行环境确定动作合同、整表生图、透明处理、逐帧检查、图集、无损预览和真实消费验证。动态只表示角色由有限状态、方向和逐帧图片驱动，不把视频、Live2D、骨骼或 3D 工作流带进来。

### 1. 先确定运行时真正会消费什么

目标项目存在时，读取角色状态的生产者、方向选择、动作结果发生位置、图片消费者、锚点、图集导入和最终可见结果。目标平台只有说明而没有代码时，依据正式协议建立同一合同。不要从常见动画清单倒推动作：日程 NPC 可以只要四方向静态图；玩家角色只生产当前控制器能触发的移动和工具动作；前向应用助手没有方向输入时不生成四方向；转向只有在运行时存在独立过渡时才是动画。

用 Agent 根据真实证据完成合同，用户不需要编辑 JSON：

```text
python scripts/motion_kit.py schema
python scripts/motion_kit.py draft --motion-id <slug> --display-name <name> --output <contract-path>
python scripts/motion_kit.py prepare <kit-folder> --contract <contract-path>
python scripts/motion_kit.py check <run-folder> --stage prepared
```

合同逐项记录目标表面、角色职责、镜头、状态与方向生产者、运行时消费者、用户可见结果、画布与脚底锚点，以及每个 `static`、`loop`、`oneshot` 或 `transition` clip 的方向、帧时长和效果发生帧。每帧只能由一个完整动作表格子产生；所有 clip 帧都必须被映射，不能留下消费端临时猜测的素材。

### 2. 整张生成并接受动作组

运行 `motion_kit.py ready <run-folder>`，只处理返回的 `ready_jobs`。读取每个 job 的完整提示词和图片输入，先展示给用户并等待确认；获确认后才在一张图片中生成该动作组的全部方向与帧。网格只控制位置，成图不能出现格线、标签或文字。不要按方向或单帧分别生图再拼接，也不要把另一张图的脸、眼睛、头发、服装或肢体贴进完整帧。直生图的轻微内部晃动可以保留；确定性处理只允许整人刚性位移、统一缩放、脚底对齐、软抠图和切格，不替换人物内部像素。

实际打开整表，确认同一角色、完整身体、方向、动作顺序、帧数、尺度、基线、工具连接和背景后运行：

```text
python scripts/motion_kit.py accept-sheet <run-folder> --job <group-id> --source <generated-sheet> --qa-note <visible-evidence>
```

脚本输出透明 PNG 图集、每个 clip 的透明 PNG 帧、APNG、无损 WebP 和处理报告。APNG 或无损 WebP承担颜色与循环验收；GIF 只有用户明确要临时分享时另行转换，不进入正式包，不承担颜色判断。错误整帧或整组重生；已接受结果后来被否决时增加 `--replace-complete`，旧组进入历史，不混入新包。

### 3. 打包并验证真实消费

全部动作组通过后运行：

```text
python scripts/motion_kit.py finalize <run-folder>
python scripts/motion_kit.py check <run-folder> --stage final
```

正式包包含 `motion-contract.json`、`motion-manifest.json`、透明图集和逐帧 PNG；预览与生成证据留在运行目录。若请求包含项目接入，继续让真实状态生产者选择 manifest 中的 clip，让方向输入切换对应方向，并让效果事件在登记帧通知玩法系统；再在实际目标尺寸中查看最终角色。只有生产者确实发出状态、正式素材被导入、消费者确实读取、动作效果与画面同步且用户能看见，才说运行时接入完成。只要求素材包时不擅自修改项目。

## Codex 桌宠适配路径

本路径只消费锁定角色。先读取 `references/dynamic-character-production.md` 的共同身份、整表生成、预览和修正规则，再完整读取 `references/pet-production.md`；后者只负责 Codex v2 的固定九状态、十六方向、8×11 布局、盲审、成品和安装。先建立“准备运行目录 → 桌宠主形象 → 动作与方向 → 拼装验证和安装”四步可见进度，只有真实文件或决定出现后才推进。

先加载工作区依赖并始终使用其返回的 Python 绝对路径：

```text
"<workspace-python>" -B scripts/pet_kit.py schema
"<workspace-python>" -B scripts/pet_kit.py prepare <kit-folder>
"<workspace-python>" -B scripts/pet_kit.py check <run-folder> --stage prepared
```

使用通用分流已经选择的图像入口。运行 `pet_kit.py ready <run-folder>`，只处理 `ready_jobs`；每个任务先读取并展示 `imagegen-jobs.json` 登记的完整提示词和全部图片输入，等待用户确认后下一轮才原样执行。选中并实际检查结果后运行：

```text
"<workspace-python>" -B scripts/pet_kit.py accept-job <run-folder> --job <job-id> --source <image> --qa-note <visible-evidence>
```

按 reference 完成桌宠主形象、九组动作、四向锚点、两条八格方向行、8×11 精灵表、GIF、连续性检查和隔离盲审。后续检查发现已接受任务失败时，用同一命令增加 `--replace-complete`，让脚本归档失效产物并从最早失败点重建；不手改状态或混用旧图集。

全部确定性与看图证据通过后运行：

```text
"<workspace-python>" -B scripts/pet_kit.py finalize <run-folder>
"<workspace-python>" -B scripts/pet_kit.py check <run-folder> --stage final
"<workspace-python>" -B scripts/pet_kit.py install <run-folder>
```

`finalize` 只在角色快照、十三个视觉任务、九组动作、十六方向、透明与 v2 几何均通过后生成 `pet.json` 和 `spritesheet.webp`。仅当请求包含可用或安装时执行 `install`；相同内容不重复写入，不同内容占用标识时回到通用权限边界。Agent 不代替用户重启应用或点击设置。

## 能力缺失

没有生图能力时仍完成当前路径的结构化生产输入：角色路径交付完整档案和 master prompt；衍生路径交付视觉简报或文章配图计划、有序参考和 prompt；动态路径完成真实动作合同与 `prepare`，交付运行目录、任务图和完整动作表提示；桌宠同样完成平台合同与准备目录。明确说明哪些图片、透明处理、运行时包、归档或安装尚未完成。

没有独立看图能力时，不声称角色一致性、视觉成片、动态连续性或桌宠盲审通过；只交付已有确定性检查和需要用户查看的总览。没有可写工作区时，聊天图片不冒充可携带角色包、可验证衍生目录或运行时动作包。

## 交付与停止

先说明当前结果是否真正完成。角色完成时展示正式主图并给出核心记忆点、版本和角色包绝对路径；衍生视觉先展示最终图片，再说明核心关系、角色版本和绝对路径；一般动态角色展示整表总览和实际 clip 预览，再说明角色版本、合同依据、动作与方向、效果事件和成品路径；桌宠展示最终总览和至少一个动作预览，再说明安装状态、角色版本、九组状态、十六方向、成品与安装路径。

只有真实生产者输出已生成、下游已读取、最终图片或动态素材已实际检查，且对应 `check` 通过，才能声称素材完成；项目接入还必须看到真实运行时消费者产生可观察结果。满足用户当前请求后停止，不自动扩展其它比例、媒体、动作、表情包或平台版本。

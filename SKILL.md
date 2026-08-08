---
name: ip-studio
description: "创建、锁定并长期复用个人或品牌 IP 角色，并用同一角色实际制作头像、主页横幅、资料卡、文章封面、说明图、整篇文章配图和 Codex v2 桌宠；环境没有生图能力时才回退为完整提示词包。Use when a user wants to turn identity cues or existing art into a stable stylized human, animal, anthropomorphic, object, or fantasy character; import or revise a portable character kit; use that locked character in social-profile and content visuals; plan and produce an ordered article illustration set; revise a derivative without overwriting history; or build a Codex-compatible 8x11 animated pet with nine app states and sixteen look directions. Do not use for general personal-brand strategy, generic visuals without an IP character, photorealistic digital doubles, general animation, Live2D, video, or non-Codex desktop-pet applications."
---

# IP Studio

把身份线索或已有角色图变成可跨会话复用的角色包，再用同一身份制作社交视觉、内容视觉和 Codex v2 桌宠。角色档案与其中登记的单张主参考图是身份真源；衍生图和桌宠只消费它们，不反向改变角色。

## 路由与边界

先按用户要得到的独立结果选择路径：

- **角色身份**：从零创建、导入已有形象，或修改已锁定角色。
- **衍生视觉**：头像、主页横幅、资料卡、文章封面、说明图、单张正文插图、整篇文章配图组或既有衍生图修订。只有图片而没有角色包时，先导入并锁定；没有角色时，先完成角色身份路径。
- **Codex 桌宠**：用已锁定角色制作、检查和安装 v2 桌宠。只有图片或还没有角色时，同样先完成角色身份路径。

同一请求包含多个结果时，先锁定角色，再分别完成点名的结果。普通个人品牌策划、没有 IP 角色参与的一般视觉、照片级数字分身、Live2D、视频、通用动画、Windows 独立桌宠和其它桌宠平台不属于本 Skill。用户只点名 `$ip-studio` 时，按从零创建角色处理。

## 通用决策与权限

信息依次取自当前请求、当前对话、用户提供或明确指向的图片、文档、链接和角色目录。材料足够时直接继续；只有缺失信息会改变身份、事实、品牌方向、核心叙事或既有安装时，才提出一个具体取舍。角色方向不清时给三张完整方向卡，不发问卷；用户把决定交给 Agent 时选择最符合用途的一张并说明原因。除非用户明确要求为只有品牌名的请求补充公开线索，否则不主动研究品牌。

调用本 Skill 已授权查看用户提供的图片、使用现有生图与看图能力，并在可写工作区创建角色包、衍生视觉和桌宠运行目录。请求“可用的 Codex 桌宠”包含写入本机 Codex 宠物目录；不同内容占用同一标识时，先保留旧目录并请求替换决定。其它安装、上传、发送或发布必须另行获得授权。本流程不删除既有角色版本、正式衍生图、桌宠运行记录或旧安装。

回复语言跟随用户。内部档案使用固定英文键名，用户不需要编辑 JSON、提示词、文件名、编号或分支。

### 图像能力分流

当前路径需要位图成品时只选择一次图像入口。用户明确只要方案或提示词时按其要求停止；否则，Codex 环境存在 `$imagegen` 时在第一次生图前完整读取并直接调用它，其它 Agent 使用自身原生生图或编辑能力。具有生图能力就必须继续到实际生成、看图、必要重试和归档，不能把提示词当成成品；只有环境确实没有生图能力时才交付脚本生成的完整提示词和有序图片输入。后续角色、衍生视觉和桌宠路径都消费这个已选择的入口，不各自重新判断 provider。

有生图但没有独立看图能力时可以交付候选，不能声称视觉检查或最终定稿通过；有看图能力时必须实际打开生产者输出，不用文字描述或消费端假数据代替图片。

## 角色身份主路径

先完整读取 `references/character-system.md`。它负责方向卡、可选的极简手绘 IP 方向、Q 版诊断、档案结构、生图、看图检查、复杂部件和一致性方法。

### 1. 建立身份真源

先区分从零创建、导入和修改。导入时分开记录用户有意保留的身份特征、稳定重复特征和当前图片的偶然细节；修改已锁定角色时读取 `character-profile.json` 及其主参考图，改变固定特征必须升版。

运行当前 schema；需要草稿时由 Agent 创建：

```text
python scripts/character_kit.py schema
python scripts/character_kit.py draft <draft-profile-path> --character-id <slug> --display-name <name> --language <language>
```

Q 版方向尚未确定时允许相关字段暂空；正式生图前必须按 reference 补全到另一位 Agent 无需猜身份关键细节就能重建正面、侧面和背面。不会改变轮廓、脸部、主配色、标志物或含义的结构由 Agent 补全并标记 `agent_inferred`；会改变这些身份锚点的分歧才交给用户。

`character-profile.json` 是唯一身份描述。所有生图提示词由脚本从档案派生，不维护平行的手写身份提示词；姿势、动作、场景、画幅和镜头只进入当次任务。

### 2. 诊断并选择设计

从同一份暂定档案独立建立三张真实不同的方向稿，按 reference 生成并实际打开检查。缩略图中必须先认出主轮廓和主要记忆点；缺肢、断裂、无关文字和细节堆积不通过。技术错误或违反已确认特征的结果从原档案重生，不从失败图继续编辑；结构成立但改变未确认细节的结果保留为明确分支。向用户展示通过的方向及取舍，除非用户已授权 Agent 代选。

已有形象已获认可且只需建档时跳过 Q 版。修改角色时，只有重新设计轮廓、脸部、核心配色或标志物才返回方向诊断。

### 3. 正式主图与复用测试

运行：

```text
python scripts/character_kit.py prompt <draft-profile-path> --purpose master
```

用已选择的图像入口实际执行输出的 `prompt`。正式主参考图使用单角色、全身、正面或轻微三分之四视角、中性姿态和干净背景，使所有固定特征可见；Q 版图不进入正式角色包。生成后按档案逐项看图，先修缺失的生产者字段，再处理渲染错误，每阶段最多自动重试两次。同一复杂部件连续失败两次时，按 reference 先锁定部件结构，再重生整张图；同类角度、动作、手部或配件漂移连续失败两次时，才按 reference 建立绑定当前角色版本的辅助校准板。它不是第二身份真源，角色升版后自动失效。

用户批准正式图或已授权 Agent 定稿后运行：

```text
python scripts/character_kit.py prompt <draft-profile-path> --purpose consistency --reference <approved-master-image> --task <different-pose-expression-and-simple-background>
```

把输出的 `prompt` 与 `master_reference` 一起生图。测试图必须保留形体、脸部、颜色落点、服装连接、材质和标志物，只用于检查，不成为长期参考。失败时修正档案或主参考图；仍需放弃已批准特征时再交给用户决定。

### 4. 无损锁定

在可写工作区使用 `ip-studio-output/<character-slug>/`：

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

本路径只消费锁定角色。完整读取 `references/visual-production.md`，再按用户点名建立一个或多个独立结果：`avatar`、`profile-banner`、`profile-card`、`cover`、`explainer`、单张 `article-illustration`、有序文章配图组或既有 visual 的新修订。主页套图默认含头像和主页横幅，明确要求时再加入资料卡；每个结果共享角色版本，但分别建立简报、生成、检查和归档。

### 1. 建立简报并选择视觉语言

```text
python scripts/visual_kit.py schema
python scripts/visual_kit.py draft <brief-path> --kind <kind> --visual-id <slug> --language <language>
```

Agent 根据内容真源完成内容提炼、传播判断、视觉构思和提示词生产：填写核心对象、理解缺口、机制或变化、看后结论与品牌角色，选择唯一视觉中心、主要结构、场景层次、角色动作、文字、配色和图片资料。用户不需要另行调用提示词流程。角色必须亲自作用于核心对象并产生可见结果；图片输入的身份、logo、风格、构图或界面职责必须分开记录，参考图不得向当前内容补充事实。

整篇文章配图不逐段盲目出图。先运行 `plan-schema` 和 `plan-draft`，从全文找出互不重复的认知锚点，为每项记录正文插入位置与原文片段，再用 `materialize-plan` 生成按正文顺序排列的现有 `article-illustration` 简报。数量由锚点决定，不套固定张数。完整命令和结构选择见 reference。

封面、说明图和正文插图可选择 reference 中的“极简手绘 IP”内容视觉；选中后先运行 `python scripts/visual_kit.py style-references minimal-handdrawn`，再把脚本返回的完整案例清单写入 `references`，使视觉语言和实际参考图共同进入生图链。它不是全局默认，也不能借衍生图改写已锁定角色的身份画法。

用户要求“OKX 风格”且当前结果包含已锁定 IP 角色时，把简报的 `visual_language` 设为 `okx-editorial`。它适用于主页横幅、资料卡、封面、说明图和正文插图；运行 `python scripts/visual_kit.py style-profile okx-editorial` 可以直接查看脚本实际读取的 JSON 风格真源。正常生成只把这份 JSON 编译进提示词，不打开或传入七张来源案例；`image_references` 默认只有角色主图和当前任务确实需要的界面或素材。透明 OKX 标记也不自动加载，只有用户明确要求精确 Logo 时才把 `assets/visual-languages/okx-editorial/logos/okx-mark-white.png` 作为当前品牌素材加入。

### 2. 生成、看图和归档

```text
python scripts/visual_kit.py prompt <kit-folder> --brief <brief-path>
```

用已选择的图像入口实际执行命令输出的 `prompt` 和有序 `image_references`，不另写平行的角色或内容提示词。提示词按“图片职责、主体与动作、环境、构图、光色与材质、准确文字和 logo、最少必要限制”的顺序由脚本一次生成，内部分析和检查表不写进生图输入。实际打开结果，先看缩略图的信息层级，再以 100% 尺寸检查角色一致性、内容事实、动作因果、唯一结构、文字与 logo、接触遮挡、共同光线、边缘和技术完整性。失败时修正最早出错的简报判断，从原始档案、内容和参考图重生；每张结果最多自动重试两次。需要改变事实、叙事重点或固定特征时只询问这一项。

用户批准或已授权 Agent 定稿后运行：

```text
python scripts/visual_kit.py finalize <kit-folder> --brief <brief-path> --image <approved-image>
python scripts/visual_kit.py check <visual-folder> --kit <kit-folder>
```

正式结果进入 `<kit-folder>/derivatives/<kind>/<visual-id>/revisions/rNNN/`，visual 根目录的 `current.json` 指向当前版本。重新读取当前 revision 的 `visual-record.json`，实际打开登记图片，并确认角色版本、简报、完整生图输入、输入资料和校验值都可读取。候选图和重试图不进入正式目录。

修订时先按 reference 判定 `local-rendering`、`content-structure` 或 `character-revision`，运行 `revision-prompt` 并把上一版成图作为正式输入，再用 `revise` 创建下一 revision；不覆盖旧图，也不换一个失去来源关系的新 visual-id。旧的平铺衍生目录只能显式运行一次 `migrate-visual`，迁移后正常路径不再读取旧结构。文章全部单图通过后运行 `finalize-set` 与 `check-set`，归档其正文顺序和所消费的精确 visual revisions。

## Codex 桌宠主路径

本路径只消费锁定角色。完整读取 `references/pet-production.md`；它是 v2 精灵表合同、九组状态、十六方向、逐行生图、确定性拼装、盲审、预览、成品和安装的执行真源。先建立“准备运行目录 → 桌宠主形象 → 动作与方向 → 拼装验证和安装”四步可见进度，只有真实文件或决定出现后才推进。

先加载工作区依赖并始终使用其返回的 Python 绝对路径：

```text
"<workspace-python>" -B scripts/pet_kit.py schema
"<workspace-python>" -B scripts/pet_kit.py prepare <kit-folder>
"<workspace-python>" -B scripts/pet_kit.py check <run-folder> --stage prepared
```

使用通用分流已经选择的图像入口。运行 `pet_kit.py ready <run-folder>`，只处理 `ready_jobs`；每个任务使用 `imagegen-jobs.json` 登记的提示词和全部图片输入。选中并实际检查结果后运行：

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

没有生图能力时仍完成当前路径的结构化生产输入：角色路径交付完整档案和 master prompt；衍生路径交付视觉简报或文章配图计划、有序参考和 prompt；桌宠路径完成 `prepare` 并交付运行目录、任务图和第一条基础图提示。明确说明哪些图片、修订、配图组、归档或安装尚未完成。

没有独立看图能力时，不声称角色一致性、视觉成片或桌宠盲审通过；只交付已有确定性检查和需要用户查看的总览。没有可写工作区时，聊天图片不冒充可携带角色包或可验证衍生目录。

## 交付与停止

先说明当前结果是否真正完成。角色完成时展示正式主图并给出核心记忆点、版本和角色包绝对路径；衍生视觉先展示最终图片，再说明核心关系、角色版本和绝对路径；桌宠展示最终总览和至少一个动作预览，再说明安装状态、角色版本、九组状态、十六方向、成品与安装路径。

只有真实生产者输出已生成、下游已读取、最终图片或桌宠已实际检查，且对应 `check` 通过，才能声称完成。满足用户当前请求后停止，不自动扩展其它比例、媒体、表情包、动画或平台版本。

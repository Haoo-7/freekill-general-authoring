---
name: "freekill-general-authoring"
description: "新月杀（FreeKill）自制武将拓展：把自然语言描述或卡面图落成可加载、可实测的 Lua 武将包，覆盖拆解技能规则、查本机源码样板、写技能与翻译、处理原画语音、登记拓展管理、静态验收与游戏内验证。用户要自制武将、做个技能、改原画或语音、做扩展包时使用。不用于：修改 FreeKill 本体或官方包源码；无名杀等其他三国杀引擎的拓展；只问规则不写代码的咨询；联机故障排查。"
metadata:
  version: "2.0.0"
---

# 新月杀自制武将

目标是把自然语言武将描述落成可加载的 FreeKill 拓展。全程区分三种状态：文件已写入、静态验收通过、游戏内实测通过。只有用户回报游戏内通过后，才称“已生效”。

## 开始前

先看 [本机环境](references/local-environment.md)。它是一份模板：还没填就先把 FreeKill 根目录、当前工作版本和测试入口填进去，填不出来就问用户。

按需要读的参考资料：

| 阶段 | 参考资料 |
| --- | --- |
| 建目录、写骨架 | [拓展骨架](references/package-template.md) |
| 查 API 与样板文件 | [API 与样板](references/core-api-samples.md) |
| 写技能效果的形态与坑 | [技能形态](references/skill-mechanics.md) |
| 写视为技、从隐藏区用牌、废除区域 | [视图技与区域废除](references/viewas-and-areas.md) |
| 写翻译、技能文案、放素材 | [翻译与素材](references/text-and-assets.md) |
| 改了没生效、静默失败 | [排查](references/troubleshooting.md) |
| 跑静态验收 | `scripts/check_package.py` |

## 1. 确认版本和项目根目录

读取 `<root>\fk_ver`，确认 `<root>\packages` 存在。只修改用户指定或当前确认的那一份安装，不要把新旧两份安装混用。

根目录不明确时先问用户，不要把文件写进另一份安装。

完成标准：记录实际版本号、根目录和目标 `packages` 目录。

## 2. 先拆规则，再写代码

用户给的是卡面图片时，先用图像工具放大裁切，逐字确认技能名、势力徽章、体力、称号和技能原文。

形近字（如 悬／谏、沈／沉、奖励／樊励）和繁体极易误读，势力徽章也是重灾区；拿不准的当面问用户。

把描述拆成这份清单：

- 触发时机：`fk.TurnStart`、`fk.TargetConfirmed`、`fk.AfterCardsMove`、`fk.RoundEnd` 等
- 技能类型：主动、触发、锁定、视为、禁止、手牌上限、目标选择、失效
- 参与者与目标的强制／可选关系
- 牌名限制、次数限制、回合／轮次持续时间
- 标记的进入、离开、清除时机
- 伤害、无效、技能失效、移动牌的先后顺序
- 区域废除对象与恢复时机
- 空城、死亡、无人参与、无结果、多目标等边界

把“其”“你”“其他角色”绑定到具体对象。规则仍有歧义时问一个最小澄清问题，不要在代码里默默决定关键规则。

卡面里“获得／失去／喝掉技能”这类状态机，先问清两件事：状态用什么承载（隐藏玩家标记还是技能所有权），状态变化显示在哪里（详情弹窗／头像按钮／战报）。

“武将牌上未获得的技能”做成宿主技能的相关技能（`related_skills`，开局不授予）；随对局状态显隐要加客户端钩子，见 [技能形态](references/skill-mechanics.md)。

完成标准：每个技能都有触发、成本、效果、持续时间和边界行为。

## 3. 查本机源码样板

先在 `<root>\packages` 里搜中文翻译或技能内部名，再读同名 Lua。优先复用本机 API，不凭旧文档猜接口。任何方法调用前先在本机源码确认存在。

搜索命令按 [本机环境](references/local-environment.md) 里的写法用 `findstr`，不要去扫整个 `packages`。

按需读 [API 与样板](references/core-api-samples.md)：可靠样板文件索引、常用 API 清单和实踩过的坑。

完成标准：每个复杂效果都有本机样板，或明确记录没有现成实现。

## 4. 创建拓展结构

套用 [拓展骨架](references/package-template.md) 的三文件骨架：`init.lua` / 子包 `init.lua` / 技能文件；素材目录按第 8 节放置。

规则：

- 入口必须 `return { ... }`；只写 `return 包对象` 时包不注册、武将不出现
- 子包设置 `extension.extensionName`，它必须等于 `packages/` 下的文件夹名
- 子包调用 `loadSkillSkelsByPath` 加载技能目录
- 代码名必须全局唯一；`__` 前是角标前缀，后半段是真名
- 一个子包建议不超过 40 名武将，避免 Lua 单文件局部变量限制

自定义势力、角标、技能显示顺序的处理见 [技能形态](references/skill-mechanics.md) 末节。

完成标准：入口、子包、技能目录和 `General:new` 均存在，技能名与文件中的 `name` 一致。

## 5. 登记 packages.db

Lua 加载和游戏内“拓展包管理”是两套机制：

- `packages/<包名>/init.lua` 存在就能被 `ModManager:loadPackages()` 加载，武将一览可见
- 拓展管理页只读 `<root>\packages\packages.db` 的 `packages` 表（列 `name, url, hash, enabled`）
- 禁用后的包名会进 `GetDisabledPacks()`，`loadPackages()` 遇到这些目录名就跳过

只写 Lua 不登记时：武将能用，但管理页认不到，也无法禁用后加入对方服务器。建包后必须：

1. 备份 `packages.db`
2. `INSERT INTO packages(name,url,hash,enabled) VALUES ('<包名>','local://packages/<包名>','<40 位 hash>',1)`
3. 在包目录初始化 git 并提交，把 `git rev-parse HEAD` 写回 `hash`
4. 用 `SELECT name FROM packages WHERE name='<包名>'` 确认行存在

hash 必须是当前 HEAD，每次改完都要同步。提交失败多为仓库没配 identity，用 `git -c user.name="local" -c user.email="local@local" commit -m "..."`；不要用不存在的 `--allow-empty-on-error`。

`enabled=0` 会让整包从加载列表静默消失，日志只少一个包名、没有报错。改完代码要同时确认 `enabled=1`。

启用一个包前先查重名：同一武将代码名或技能名已存在于另一个 `enabled=1` 的包里时，`loadPackages()` 会直接 `error` 中断，新武将根本进不了游戏。

不要用 git 命令替代数据库登记，也不要在房间里靠“武将一览”绕开整包禁用。

完成标准：`packages.db` 行的 hash 等于 `git rev-parse HEAD`，`enabled=1`。静态验收脚本会核对这两项。

## 6. 写 Lua

直接在确认的根目录写文件。写之前确定：目标版本与绝对路径、精确新增文件列表、武将属性与技能原文、已解决的规则解释、本机参考文件。

写法约束：

- 不改官方包，不创建无关文件，不经用户要求不删除或覆盖已有拓展
- UTF-8 无 BOM、2 空格缩进、LF 结尾
- 已有扩展时在包内追加武将，不重复建空包
- 写完查磁盘再读文件，不接受口头“完成”

默认把代码实现派给隔离执行者，自己只拆规则和验收。派单任务里写死目标文件绝对路径、已拍板的规则口径、必须自查的本机 API，以及“不要 git commit、不要动 packages.db”。

子代理只交报告。回来后自己 `git diff` 逐行看，把每条结论落到源码 file:line；再跑第 9 节的验收。“子代理说已通过”不算验收。

效果怎么写、哪个钩子用错会静默失效，见 [技能形态](references/skill-mechanics.md)；视为技与隐藏区用牌见 [视图技与区域废除](references/viewas-and-areas.md)。

完成标准：新增文件实际存在，路径与目标一致。

## 7. 客户端和服务端分界

技能回调要按“谁会调用它”区分，不能只按函数名猜。

客户端会执行：`can_use`、`enabled_at_play`、`enabled_at_response`、`interaction`、`card_filter`、`view_as`。这些用于按钮、选牌和可用性刷新。

客户端路径里不能访问 `player.room`、`room.draw_pile`、`room:getOtherPlayers()` 这类服务端专有状态，改用 `Fk:currentRoom()`、`Fk:currentRoom():getCurrent()`、`Fk:currentRoom().alive_players` 和玩家公开属性。

服务端执行：主动技 `on_use(room, effect)`、触发技 `on_cost` / `on_use`、视为技 `before_use` / `after_use`。这里的 `player` 是 `ServerPlayer`，可以用 `player.room`、`room.draw_pile`、`room:getOtherPlayers()`、`room:moveCardTo()`。

两条时机语义容易踩：

- `ViewAsSkill:enabledAtPlay` 的引擎注释是“空闲时间点内是否可以使用转化技”。它不只管出牌阶段按钮，开局和回合外的空闲时间也走它；只许出牌阶段用的效果必须加 `player.phase == Player.Play`
- `enabled_at_response(self, player, cardResponsing)` 第三参为 true 表示“打出”型询问（问闪／杀）；濒死自救这类“使用”型询问是 false

主动技的 `can_use` 属于客户端按钮合法性路径，会由 `skillButtonValidity` 等请求刷新流程调用，不是只在服务端执行。在 `can_use` 里访问 `player.room` 会报 `attempt to index a nil value (local 'room')`。

隐藏牌堆和服务端牌面条件留给服务端 `on_use`、`can_trigger` 或 `on_cost` 做最终检查；客户端只检查同步可见状态。堆栈若落在客户端请求处理链，先修边界，不要先改牌堆搜索逻辑。

完成标准：逐个检查两侧回调，确认客户端路径里没有服务端专有状态；限出牌阶段的效果有 phase 判断。

## 8. 翻译、描述与素材

翻译表必须覆盖武将名、称号、设计者／配音／画师、阵亡台词、技能名、技能描述和所有 prompt。技能名 ≤2 字，称号 ≤7 字；锁定技提示不要手动加粗。

原画放 `packages/<包名>/image/generals/<代码名>.jpg`，官方将面 250×292；从整卡图裁原画时把体力图标、势力徽章、技能文案区裁掉，否则会重影。技能音放 `audio/skill/`，阵亡音放 `audio/death/`。

不改官方素材；需要覆盖时用 `resource_pak/<名字>/` 按原相对路径同名覆盖。

动态描述、显示标记、技能转手后的措辞、交换显示名的做法、规则改动后回核描述的检查点，见 [翻译与素材](references/text-and-assets.md)。

完成标准：素材路径、文件名、尺寸、编码已检查，没误放进另一份安装。

## 9. 静态验收

先跑脚本，它只检查程序能确认的问题：

```text
python scripts/check_package.py <root>/packages/<包名> --fk-root <root>
```

脚本核对编码与换行、入口与子包结构、`extensionName` 与目录名、技能 `return skill`、`addSkills` 引用、翻译键、已知不存在的 API、客户端／服务端可疑调用，以及 `packages.db` 的 `enabled` 与 hash。

再加语法解析：本机没有 `lua` / `luac`，先在工作目录 `npm install luaparse --no-save`，然后加 `--lua-parse <node_modules/luaparse 目录>`。解析器带行号，修完重跑直到通过。语法合法不等于运行正确。

脚本不覆盖的部分自己过一遍：状态持续时间（`-turn`、`-phase`、`-round`、`-inhand`）、虚拟牌与实体子卡、`nullified` / `nullifiedTargets`、伤害修改、牌移动顺序、`General:addSkills` 顺序与显示名对应。

要写自测时按 [拓展骨架](references/package-template.md) 的 `addTest` 写法，按 key 筛 `effect_spec_list`；跑测试用 `& '.\FreeKill.exe' --testskills <skill_name>`。

有报错以最新堆栈为准，读报错行前后代码和对应官方样板，不只修第一处表面错误。修完重新提交并把新 hash 写回 `packages.db`。

完成标准：脚本无错误，语法解析通过；做不到时把具体剩余风险列给用户，不要声称已通过运行测试。

## 10. 游戏内验证

改完必须完整退出并重新启动正确版本的 `FreeKill.exe`。只关弹窗或回大厅不会重载 Lua 与 `packages` 缓存。用单机启动、开自由选将、右键强制选将；开发测试最好用独立客户端。

至少验证：

- 拓展管理能看到包名并禁用／启用
- 武将一览能加载拓展和原画
- 每个技能从正确时机触发
- 强制／可选参与者符合技能文本
- 空城、死亡、无人参与、多目标、无结果、轮次边界不报错
- 视为使用／打出时牌移动位置正确
- 牌名次数、伤害增幅、无效、非锁定技失效的持续时间正确
- 有相关技能动态显隐时，开玩家详情弹窗确认条目的消失与恢复

表现不对时按 [排查](references/troubleshooting.md) 的顺序走：先核对日志里的加载列表，再怀疑 hash 不同步或客户端条件。

完成标准：只在用户实际回报游戏内通过后才称“已生效”；否则称“文件已写入／静态验收通过”。

## 11. 交付与发布

交付时只报文件路径、主要能力、脚本与测试结果、实际验证到哪一步、剩余风险。

用户要求发布或提 PR 时：

1. 先看现场：`git remote -v`、`git branch -vv`、`git log --oneline origin/main..HEAD`
2. 无副作用地验权限：`$env:GIT_TERMINAL_PROMPT="0"; git push --dry-run origin <分支>`。报 `could not read Username` 就是本机没有凭据，不要反复重试，也不要向用户索要密码或令牌
3. 用户默认要 PR 不直推主干：推 `feat/<主题>`，给出 `feat/...` → 主干的 PR 链接；没有推送权限时 fork 后从自己的分支开 PR
4. 仓库公开时，头像、真实姓名、邮箱这类个人信息要单独确认；提交作者信息不确定时先问用户

未授权或没权限时明确说“卡在授权”，不把本地提交当成已上传。

完成标准：`git push` 成功且 `git ls-remote --heads origin` 能看到新分支，或给出 PR 链接。

## 注意

- 不混用旧版本安装
- 未经用户要求不删除或覆盖已有拓展
- 同一武将或技能不要在两个启用的包里各注册一份
- 静态验收通过不等于游戏内生效，两者分开报告

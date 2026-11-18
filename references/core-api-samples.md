# 常用 API 与本机样板索引

回链：[SKILL.md §3 查本机源码样板](../SKILL.md)。以下结论在 0.5.25 实测，每条都有本机样板。**API 与旧三国杀文档不同，任何方法调用前先在本机源码确认存在。**

卡牌／玩家的方法定义在 `packages\freekill-core\ltk\core\card.lua`、`player.lua` 和 `lua\fk_ex.lua`。例如卡牌点数是 `.number` 属性，没有 `getNumber()`（实踩过的坑）。

0.5.25 新核心的官方包位于 `packages/freekill-core/`；自己的拓展仍使用 `packages.<包名>`，不要把 `packages.freekill-core` 当作自己的前缀。

## 目录

- [可靠样板](#可靠样板)
- [效果类型的回调名](#效果类型的回调名)
- [常用 API](#常用-api)
- [相关技能与客户端钩子的引擎细节](#相关技能与客户端钩子的引擎细节)

## 可靠样板

- `packages\freekill-core\standard\pkg\skills\yingzi.lua`：最小触发技
- `packages\freekill-core\standard\pkg\skills\jieyin.lua`：选牌、选目标、主动技
- `packages\freekill-core\standard\pkg\skills\jianxiong.lua`：带 `can_trigger` 的触发技
- `packages\freekill-core\standard\pkg\skills\kongcheng.lua`、`qianxun.lua`：`is_prohibited` 目标限制
- `packages\shzl\pkg\mountain\skills\xiangle.lua`：`TargetConfirmed` 后令牌无效
- `packages\jsrg\pkg\beginning\skills\chaozheng.lua`、`shelun.lua`、`fayi.lua`：议事
- `packages\offline_new\pkg\zhencang\skills\queying.lua`：获得【影】并视为牌
- `packages\utility\utility.lua`：`U.Discussion`、`U.getShade`、`U.askForChooseCardNames`
- `packages\ol\pkg\menfa\skills\lieshi.lua`、`packages\overseas\pkg\overseas_sp\skills\juezhu.lua`：废除判定区
- `packages\lunar\pkg\lunar_xsg\skills\duanan.lua`：废除手牌区（全库唯一用例，自补标记与回合结束恢复）
- `packages\jsrg\pkg\transition\skills\manjuan.lua`：官方【漫卷】`js__manjuan`
- `packages\freekill-core\standard\aux_skills_dir\uncompulsory_invalidity.lua`：非锁定技失效
- `packages\hegemony\pkg\lord_ex\skills\aocai.lua`：响应型 viewas
- `packages\tenyear_mini\pkg\tenyear_mini_xinghuo\skills\shouxi.lua`：`askForChooseCardNames` 选牌名

## 效果类型的回调名

以本机基类为准：`packages\freekill-core\ltk\core\skill_type\*.lua`（`button.lua`=主动技、`trigger.lua`=触发技、`view_as.lua`=视为技、`prohibit.lua`=禁止）。

`addEffect` 的 spec 键是 snake_case，由 `skill_skeleton.lua` 映射到 camelCase 方法（`prohibit_use` → `prohibitUse`）。两种写法都不能凭直觉猜：先读基类确认这个方法存在，再确认它的参数顺序和调用点。

## 常用 API

- 蓄力技：`tags = { Skill.Charge }`，`local U = require "packages.utility.utility"` 后用 `U.skillCharged(player, 数值, 上限)` 改蓄力，变化事件 `U.SkillChargeChanged`，获得／失去技能用 `addAcquireEffect` / `addLoseEffect` 设初值。样板 `offline_new\pkg\piracy_e\skills\tuntian.lua`
- 无效化：单目标在 `TargetConfirmed` 里 `data.nullified = true`（`xiangle.lua`）；整卡所有目标用 `data:setNullified()` 或往 `data.use.nullifiedTargets` 插目标（`gamemode\pkg\jiange_generals\skills\bashi.lua`）；一张牌只询问一次可在 `data.use` 上挂自定义 Lua 字段做去重
- 强制用牌：`room:useVirtualCard(牌名, 子卡, from, to, skillName, 不计次数)`（第 5 参写入 `card.skillName`，不做距离校验，样板 `ol\pkg\menfa\skills\fenjian.lua`）；`room:useCard{ from=, tos=, card= }`（`lijian.lua`）
- 无距离限制：`addEffect("targetmod", { bypass_distances = ... })`（`qicai.lua`）；攻击范围判断 `player:inMyAttackRange(p)`
- 濒死与翻面：`fk.EnterDying`、`fk.AfterDying`（`wansha.lua`、`juejing.lua`）；翻面事件 `fk.TurnedOver`
- 牌上标记：`room:setCardMark(Fk:getCardById(id), 标记名, 值)`，读 `card:getMark(标记名)`，跨区域持久（`brainhole_new\pkg\brainhole\skills\nuha.lua`）；玩家表标记 `room:addTableMark` / `player:getTableMark`
- table 扩展：FreeKill 用 `table.simpleClone`（`util.lua`），**没有 `table.copy`**；`table.filter/map/contains/insertIfNeed` 都存在
- 失去体力不想立刻进濒死结算（如“同时失去体力”后再统一结算）：在 `fk.BeforeHpChanged` 触发里把 `data.preventDying = true`（样板 `shzl\pkg\wind\skills\buqu.lua`），濒死判定在 `BeforeHpChanged` 之后才执行
- 询问 API：`askToSkillInvoke`、`askToChoice`（`fanjian.lua`）、`askToChoosePlayers`（`tuxi.lua`）、`askToChooseCardsAndPlayers`（`yiji.lua`）、`askToDiscard`
- 常用结算：`room:loseHp(p, n, 技能名)`（`kurou.lua`）、`room:recover{ who=, num=, recoverBy=, skillName= }`（`rende.lua`）、`room:throwCard(牌, 技能名, who)`、`room:moveCardTo(牌, Player.Hand, 目标, fk.ReasonGive, 技能名, nil, false, player)`
- 伤害来源：`data.skillName`，虚拟牌再查 `data.card.skillName`（`zhuque.lua`、`kuixiang.lua`）；**改牌技能（朱雀羽扇 `data:changeCard` 等）会覆写 `card.skillName`，但会继承 `skillNames` 列表并追加新名**——判断“牌来自某技能”用 `table.contains(card.skillNames, 技能名)` 最稳；在 `fk.DamageCaused` 里 `data:changeDamage(n)`（`luoyi.lua`）
- 弃置统计：`fk.AfterCardsMove` 里 `move.from == player and move.moveReason == fk.ReasonDiscard`（`offline_new\pkg\bgmdiy\skills\hantong.lua`）
- 技能交互下拉：`interaction = function(self, player) return UI.CardNameBox{ choices = {...} } end`，`on_use` 里 `self.interaction.data` 取值（`baihu.lua`）；另有 `UI.ComboBox`、`UI.OptionBox`
- 自定义势力：翻译表加 `["内部名"] = "显示名"` 即可（`brainhole_new\pkg\brainhole\init.lua` 的 `n_pigeon`／“鸽”）；独立势力的映射与势力图见 [技能形态](skill-mechanics.md)
- 胜利结算：`room:gameOver(winners)`（`server\room.lua:3670`），winners 传玩家表或身份串；单人 `{player}`，阵营 `player:getFriends(true, true)`（`server\events\misc.lua:43` 先例）
- `fk.CardUseFinished` = 一整次使用（含全部目标）结算完毕，`data.from` / `data.tos` / `data.card.suit`（`Card.Heart == 3`）；响应／打出走 `CardRespondFinished`，不算“使用”
- `fk.GameStart` 触发样板：`ol\pkg\ol_ex\skills\xueyi.lua`（在 `attachSkillToPlayers` 之后触发，`can_trigger` 里可判 `player:hasSkill`）

## 相关技能与客户端钩子的引擎细节

- 声明：`fk.CreateSkill{ related_skills = { "xxx" } }`（skeleton 字段，注释原文“如〖志继〗的〖观星〗”）。开局授予走 `getSkillNameList(true)`（**不含** related，`gamelogic.lua` 的 `attachSkillToPlayers`），所以相关技能开局天然“未获得”
- 详情显示：对局内玩家详情弹窗 `LunarLtk\Pages\InfoPopups\PlayerDetail.qml` 读 `Ltk.getPlayerSkills(id)`（`client\util.lua:402`）= 运行时已拥有技能 + **每个已拥有技能骨架的 `related_skills`**（相关色渲染，`skillNames.includes` 去重）；大厅武将详情 `GeneralDetailPage.qml` / `getGeneralDetail(general)` 读静态 `general.all_skills` + 骨架 related。**两处都是骨架静态数据，授予／移除技能不会让相关条目消失**
- 动态显隐：客户端钩子文件 `require("packages.<包>.xxx_client")(Client or Fk.Base.ClientBase)`，劫持 `base.handleSetPlayerMark`（标记同步全走这里，含无 `@` 标记）按状态改 `Fk.skill_skels[宿主].related_skills`，并在 `base.notifyUI` 里拦 `GameOver` / `PropertyUpdate(general)` 还原，防止状态泄漏进大厅。样板在你本机 `packages` 下搜 `handleSetPlayerMark` 就能找到实际写法
- 状态承载：无 `@` 前缀玩家标记不显示在头像区但同步到客户端、客户端回调可读（`ol\pkg\ol_ex\skills\jijiang.lua` 读 `jijiang_failed-phase`）；`@` 前缀标记才会显示。`-turn` / `-phase` / `-round` 后缀标记自动在回合／阶段／轮次结束清除（`mark_enum.lua` 的 `MarkEnum.TempMarkSuffix`，样板 `tuqi.lua`）
- `room:handleAddLoseSkills(player, "skill|-skill", source, sendlog, no_trigger)`（`server\events\skill.lua:206`）：幂等、广播 AddSkill／LoseSkill、发战报，授予／移除真实技能用它；但详情弹窗不反映运行时授予

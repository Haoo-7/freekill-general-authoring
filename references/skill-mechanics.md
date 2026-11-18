# 技能形态与本机实测坑

回链：[SKILL.md §6 写 Lua](../SKILL.md)。写具体技能效果时读这一份。以下结论在 0.5.25 实测，每条都在本机有样板；调用前仍要在源码确认方法存在。

## 目录

- [触发技与主动技](#触发技与主动技)
- [禁止类钩子的两个粒度](#禁止类钩子的两个粒度)
- [主动技按钮出不来](#主动技按钮出不来)
- [回合外发动](#回合外发动)
- [active 与 viewas 不能同挂](#active-与-viewas-不能同挂)
- [让玩家声明牌名](#让玩家声明牌名)
- [牌堆与顶牌操作](#牌堆与顶牌操作)
- [给牌与只选指定的牌](#给牌与只选指定的牌)
- [观看或挑选对方手牌](#观看或挑选对方手牌)
- [状态标记与动态描述](#状态标记与动态描述)
- [技能转手后的措辞](#技能转手后的措辞)
- [把状态记在别人身上](#把状态记在别人身上)
- [借用技能时封锁牌](#借用技能时封锁牌)
- [事件统计口径](#事件统计口径)
- [失效技](#失效技)
- [结算时这张牌在哪](#结算时这张牌在哪)
- [翻牌比大小](#翻牌比大小)
- [相关技能与动态显隐](#相关技能与动态显隐)
- [无实体牌视为技与酒](#无实体牌视为技与酒)
- [自定义势力与角标](#自定义势力与角标)

## 触发技与主动技

- 触发技的成本数据用 `event:setCostData` / `event:getCostData`
- 主动技用 `addEffect("active", ...)`，注意 `on_use(room, effect)` 与触发技签名不同；`max_phase_use_time` 控制次数

选牌数要“任意张”时只写 `min_card_num` / `max_card_num`（都可以是函数）。一旦写了 `card_num` 就完全覆盖这两个值（`ButtonSkill:getMinCardNum` / `getMaxCardNum` 优先取 `card_num`），`card_num = 0` 表示不选牌。

带 `tags = { Skill.Compulsory }` 的技能照样能有主动技按钮（`client/util.lua` 的 `getSkillData` 只看是不是 `ActiveSkill` 来定 `freq = "active"`，`Skill.Compulsory` 只影响 `frequency` 显示）。不要为“按钮不出来”去摘锁定技标签。

`loadSkillSkelsByPath` 逐个加载文件并把单个返回值登记为 skeleton；默认一文件一 skill 并 `return skill`。要多技能时先确认 loader 支持返回表，不要凭经验写 `return { ... }`。

## 禁止类钩子的两个粒度

`addEffect("prohibit", ...)` 有两个粒度不同的钩子，选错那个不会报错、`freekill.server.log` 也无 traceback，只是那句限制永远不生效：

- `prohibit_use(self, player, card)`：限制“该角色自己不能用这张牌”（映射见 `skill_skeleton.lua:389`，调用点 `Player:prohibitUse`）
- `is_prohibited(self, from, to, card)`：限制“这张牌不能指定 `to` 为目标”（样板 `freekill-core\standard\pkg\skills\kongcheng.lua`、`qianxun.lua`）

“你不能使用某类牌”用前者，“别人不能对你用某类牌”用后者。

## 主动技按钮出不来

主动技默认只在出牌阶段出现按钮。按钮不亮时先怀疑客户端条件，不要先改结算逻辑。需要“回合外也能发动”时先问清时机，见下一节。

## 回合外发动

若是“你于回合外需要使用或打出牌时”，改成响应型 viewas 技：`card_filter = Util.FalseFunc`、`view_as = Util.DummyFunc`、`feasible = Util.TrueFunc`。

在自定义 `on_use(self, room, cardUseEvent, _, params)` 里跑完整流程并返回 use spec（`{ from = player, tos = {}, card = card }`）；本牌用不上时 `return 技能名` 禁掉本次询问。样板 `packages\hegemony\pkg\lord_ex\skills\aocai.lua`（【傲才】）。

判断是否处于响应窗口用 `local pattern = (params and params.pattern) or Fk.currentResponsePattern`。不要只看 `params.is_response`：部分调用链里它为空，会误判成出牌阶段并弹出牌名框。

`enabled_at_response` 只在设计明确“仅回合外”时才判 `Fk:currentRoom():getCurrent() ~= player`；要能在自己回合内响应【无懈可击】等就不要加这条限制，只判失效标记。不要用 `fk.EventPhaseStart` 轮询别人的出牌阶段来充当“回合外”，也不要在 `can_use` 里放行阶段。

## active 与 viewas 不能同挂

同一技能不能同时挂 `addEffect("active")` 和 `addEffect("viewas")`（全库无此例）。

需要“主动声明 + 之后把牌当手牌用”时拆成两个技能：主动技负责声明、校验和打标记，再 `room:handleAddLoseSkills(player, "<辅助技能>", nil, false, true)` 动态发给玩家。辅助技能名用 `#` 前缀（`SkillSkeleton.visible = false`，不出现在技能列表），并在 `room.logic:getMostRecentEvent(GameEvent.Turn):addExitFunc` 里收回。

## 让玩家声明牌名

不要用 `askToChoice` 堆上百个牌名。用 `U.askForChooseCardNames(room, player, 可选名表, min, max, 技能名, prompt, all_names, true)`（`packages\utility\utility.lua`，QML 选择框，`utility` 已是本包依赖）。样板 `packages\tenyear_mini\pkg\tenyear_mini_xinghuo\skills\shouxi.lua`。

## 牌堆与顶牌操作

置牌于牌堆顶用 `room:moveCardTo(ids, Card.DrawPile, ...)`（`drawPilePosition` 为空即置顶）。“依次置顶 X 张”要逐张调用，批量移动会丢掉先后顺序。

亮出顶牌用 `room:turnOverCardsFromDrawPile`（移到 Processing），放回牌堆用 `room:returnCardsToDrawPile`（默认 top）。

`room:getNCards(n)` 只返回 id、**不会把牌从 `draw_pile` 里拿掉**（删除逻辑在源码里已注释掉），必须紧跟 `room:moveCards{ ids = ids, toArea = Card.Processing, moveReason = fk.ReasonJustMove, skillName = ... }`；不移就再取一次会拿到同一张。

## 给牌与只选指定的牌

“交给别人”用 `room:moveCardTo(cards, Player.Hand, target, fk.ReasonGive, 技能名, nil, false, player)`（样板 `freekill-core\standard\pkg\skills\rende.lua`）。`room:moveCards{ ids, to, toArea = Card.PlayerHand, ... }` 看着等价，实测不交付也不报错。

只让玩家从指定的那组牌里选 N 张，用 `room:askToChooseCards{ target = player, flag = { card_data = { {"$Hand", ids} }, visible_data = {} }, min = n, max = n, cancelable = false }`；`askToCards` 只能在整手牌里选。

要把牌作为实体子卡使用则参考 `addFakeSubcards` 与 `before_use`，别把实体牌误送弃牌堆。

## 观看或挑选对方手牌

不要用 `flag = "h"`：字符串 flag 会让客户端按 `cardVisible` 把未知牌写成 `visible_data[id] = false`，玩家只看到牌背（`ltk/client/client.lua` 的 `askForCardChosen`）。

改传表形 `flag = { card_data = { { "$Hand", target:getCardIds("h") } } }`。表形 flag 原样下发给 UI，不写 `visible_data` 就是全明牌；限定候选牌也用同一写法。

## 状态标记与动态描述

技能文本要在局内变化用 `dynamic_desc = function(self, player, lang) return "技能_变体" end`，返回不带冒号的翻译键（引擎补 `:` 查表），原 `:技能` 键保留。

这类“文本被删／规则改写”的全局状态必须用 `room:setPlayerMark` 给每个玩家打标记（包括之后接手该技能的人）。纯 Lua 变量客户端读不到，描述和 `hasSkill` 会停在旧状态。

要把计数／债务／标记值显示在武将牌旁，标记名必须带 `@` 前缀并补翻译 `["@标记"] = "显示名"`，客户端才会渲染「显示名 + 数值」（`@@` 为隐藏附加数据，`@!` 为图片标记，样板 `standard/pkg/skills/lord_designating_heir.lua`）。只写普通名字的标记只存在于代码，玩家看不到。带回合范围的显示标记照旧加 `-turn` / `-phase` 后缀，`Room:clearHistory` 按后缀自动清。

## 技能转手后的措辞

技能能交到别人手上时，描述里的“你”会随技能转移变成当前持有者。需要原持有者执行的句子（收回、结算、回收债务）直接写武将名，例如“每轮结束后，霖收回此技能”。写成“你收回”会被读成接管者自己收回。

## 把状态记在别人身上

记在其他角色身上（欠债、保护、代管）时，收取方不能写 `player:getTableMark(...)`：触发／刷新回调里的 `player` 恒为技能持有者本人，记在别人身上的账永远读不到。

改成遍历 `room.players` 找出带该标记且 `owner` 指向自己的角色，逐个结算。先把所有角色的欠账减完并写回 mark，再执行任何 `moveCardTo` / `recover`，否则第一次交付引发的嵌套事件会重复扣账。

## 借用技能时封锁牌

如果本技能把某张实体牌移入弃牌堆，再临时借用另一个技能（如 `js__manjuan`）处理它，不能只限制本技能的 `can_use`：借用技能可能绕过原技能直接使用／打出该实体牌。

给这张牌加仅在目标区域生效的 `-inarea` 标记，并在 `prohibit_use` 与 `prohibit_response` 中同时拦截；牌离开该区域后由移动系统清除标记。只封锁本技能产生的牌，不要全局禁用同名牌；用真实实体牌 ID 做测试。

若限制规则按角色当前状态生效，而非仅针对本技能生成的那张牌（例如 `drank > 0` 时，漫卷不能使用弃牌堆中的任何【酒】），单张 `-inarea` 标记不够：弃牌堆可能在技能发动前就已有同名牌。此时禁止 hook 应同时检查状态、借用技能、牌的 `trueName` 和实体牌当前区域。

实体牌区域查询先查 `CardManager:getCardArea(id)`；客户端要用同步可用的 `Fk:currentRoom():getCardArea(id)`，禁止 hook 不要访问 `player.room`。若卡牌可能是虚拟牌，遍历其实体子牌再逐张查区域。

## 事件统计口径

事件统计既要排除自己制造的移动，也要识别借来的视为技。漫卷 `js__manjuan` 产生的牌可能在 `move.skillName` 上带技能名，也可能在使用／响应结束时只保留外层 `UseCard` / `RespondCard` 事件的 `attachedSkillAndUser.skillName`；统计 `fk.AfterCardsMove` 时同时检查这两层。

统计“因技能获得牌”不能只看 `move.skillName` 非空：卡牌效果也带 skillName（顺手牵羊 `snatch.lua` 传 `snatch_skill`，是 `cardskill` 生成的 `CardSkill`），会把【顺手牵羊】当成技能。判定写成 `Fk.skills[name]` 存在、`not sk:isInstanceOf(CardSkill)`、且 `type(sk:getSkeleton().attached_equip) ~= "string"`（麒麟弓这类装备触发技不是 CardSkill，只排 CardSkill 会漏）。不要改判 `moveReason`，因为技能偷牌同样用 `fk.ReasonPrey`。

同一份统计逻辑在 `can_trigger`、`on_cost`、`on_use` 里各写一遍很容易走偏（改一处漏两处），抽成一个局部函数三处共用。

临时获得已有官方技能时，先记录角色原本是否已有，只对本次新增的登记清理。把清理函数挂到当前回合事件的退出回调，比在 `fk.TurnEnd` 里判断标记可靠（`TurnEnd` 的触发时机和 target 匹配不可靠，标记清不掉就变成永久技能）：

```lua
room:handleAddLoseSkills(player, "js__manjuan", nil, false, true)
local turn = room.logic:getMostRecentEvent(GameEvent.Turn)
if turn then
  turn:addExitFunc(function()
    if player:hasSkill("js__manjuan", true) then
      room:handleAddLoseSkills(player, "-js__manjuan", nil, false, true)
    end
  end)
end
```

`GameLogic:getMostRecentEvent(eventType)` 在当前事件继承链里找最近事件，`GameEvent:addExitFunc` 的回调在事件退出时执行（`packages/freekill-core/lua/server/gameevent.lua`）。借用时用官方原名（如 `js__manjuan` 而非 `manjuan`），先在 `packages` 里搜确认实际技能名。

## 失效技

写“你的其余技能无效”这类失效技用 `addEffect("invalidity", { global = true, invalidity_func = function(self, from, skill) ... end })`。

- 判断持有者必须写 `from:hasSkill(技能名, true)`：`hasSkill` 会回调 `isEffectable` → 本函数，第二参不传 `true` 就无限递归
- 判断是不是自己的技能树用 `skill:getSkeleton().name`：派生效果是独立隐藏技能（`#技能_1_invalidity`），比 `skill.name` 会把自己的子技能一起无效掉
- 持恒技是 `Skill.Permanent`（`skill.lua:36`），标记只能加在共享的 `skeleton.tags` 上；运行期加上后要在 `fk.GameStart` 用 `can_refresh` / `on_refresh` 清掉，否则跨局残留
- 这类“只改共享状态、玩家看不到结果”的内部清理一律走 refresh（`trigger_event.lua` 的 `exec` 先跑 refresh、不生成 SkillEffect）；写成 `can_trigger` / `on_use` 会在开局亮将并弹一次空技能
- 失效范围要排除装备技能（`skill:isEquipmentSkill(from)`，底层看 `skeleton.attached_equip`），否则“你的其余技能无效”会连带把装备区的牌一起废掉
- 已有失效逻辑可直接复用官方 `UncompulsoryInvalidity`

## 结算时这张牌在哪

结算 `fk.CardUseFinished` / `fk.CardRespondFinished` 时，“此牌”不一定还在处理区：装备牌在此之前已置入使用者的 `Card.PlayerEquip`，只有普通牌留在 `Card.Processing`，而 `UseCard:clear()` 事后只清理处理区。

依托“使用／打出的这张牌”的效果按 `room:getCardArea(id)` 同时接受 `Card.Processing` 和本人 `Card.PlayerEquip`（用 `room:getCardOwner(id) == player` 认主人）。只判处理区的写法会在装备牌上静默空发。

## 翻牌比大小

从牌堆顶翻牌比大小，`room:getNCards(n)` 只返回 id 不移动（见上文）。两边都要亮的比大小写成：各自 `getNCards(1)` + 移到 Processing，比完再一起 `room:cleanProcessingArea({ a, b })`，中途洗牌才不会把第一张再翻回来。

## 相关技能与动态显隐

“未获得的技能”一律做成宿主技能的相关技能：`related_skills = { ... }` 声明，不写入 `addSkills`。开局不授予，详情弹窗以相关技能色（紫／粉）显示。

相关技能的显示是骨架静态数据（`PlayerDetail.qml` 读 `Ltk.getPlayerSkills`、大厅读 `general.all_skills`），授予／移除技能不会让条目增减。要随对局状态显隐，必须加客户端钩子文件：`require("packages.<包>.xxx_client")(Client or Fk.Base.ClientBase)`，劫持 `handleSetPlayerMark` / `notifyUI` 动态改 `Fk.skill_skels[宿主].related_skills`；对局结束要还原，防止状态泄漏进大厅。样板在你本机 `packages` 下搜 `handleSetPlayerMark` 就能找到。

状态本体用无 `@` 前缀的隐藏玩家标记承载（客户端可读、不显示）。引擎细节见 [API 与样板](core-api-samples.md)。

## 无实体牌视为技与酒

无实体牌的视为技用 `card_num = 0` + `card_filter = Util.FalseFunc` + `view_as(self, player)`，样板【穷途】。消耗写在服务端 `before_use(self, player, use)`，返回字符串会拒绝本次使用。

视为【酒】的限次沿用官方语义：出牌阶段增益判 `player:usedCardTimes("analeptic", Player.HistoryTurn) == 0`，濒死自救不限次也不计次（引擎置 `extraUse`）。

从隐藏区（牌堆、他人手牌）用牌的完整分支、`drank` 的无反馈特性、区域废除见 [视图技与区域废除](viewas-and-areas.md)。

## 自定义势力与角标

势力别顺手写 `god`：`packages/standard/init.lua` 用 `Fk:appendKingdomMap("god", {"wei","shu","wu","qun"})` 把神将映射成四国，开局 `Room:askToChooseKingdom` 只给这张映射表里的选项，界面上永远没有“神”。

要独立的“神”势力，用自定义 kingdom id（如 `"hshen"`）并在翻译表加 `["hshen"] = "神"`。该势力不进映射表、也没有 `subkingdom` 时，开局不会再弹选势力询问，势力固定为该值。

要让它开局可选势力（神 + 魏／蜀／吴／群），把自定义势力映射到这几个 id 再交给 postLoad：`Fk:addPostLoadFunc(function() Fk:appendKingdomMap("hshen", { "god", "wei", "shu", "wu", "qun" }) end)`。`getKingdomMap` 只保留 `Fk.kingdoms` 里已注册的势力，直接写在文件顶层会因加载顺序被过滤成空表。

自定义势力要把势力图写进拓展包本身，否则只有本机能显示：`packages/<包名>/image/kingdom/<id>.png`（势力图标）、`<id>-magatama.png`（勾玉）、`<id>-back.png`（将面底图）。内容从本机 `image/card/general/<id>.png`、`<id>-magatama.png`、`image/photo/back/<id>.png` 复制。游戏根目录 `image/` 下的文件不进仓库，别人装包后势力图标与将面底图缺图（客户端日志 `Cannot open: ...general/undefined<id>`）。`SkinBank.getGeneralCardDir` 先查根目录，缺失时回落到包内 `image/kingdom/`。

武将卡角标是 `general.prefix`（默认取代码名 `__` 前那段），要显示称号就 `g.prefix = "称号"`。扩展包名是另一处，改 `Fk:loadTranslationTable { ["<包名>"] = ... }`，两者别混。

调整武将技能显示顺序时，按目标顺序重排 `General:new(...):addSkills { ... }` 中的内部技能名，并核对每个内部名对应的翻译；不要通过重命名 Lua 文件或交换实现代码来改变显示顺序。

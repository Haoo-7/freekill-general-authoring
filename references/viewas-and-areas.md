# 视图技（视为技）与区域废除

回链：[SKILL.md §6 写 Lua](../SKILL.md)。写“视为使用某牌”“从牌堆／隐藏区用牌”“不能持有手牌”“不能放判定牌”这类效果时读这一份。

核心 API 以本机 0.5.25 源码为准：`ltk/core/skill_type/view_as.lua`、`ltk/core/skill_skeleton.lua`、`ltk/core/card.lua`、`ltk/server/events/movecard.lua`、`ltk/server/room.lua`（`abortPlayerArea`）。

## 目录

- [视图技的最小骨架](#视图技的最小骨架)
- [五个容易踩的点](#五个容易踩的点)
- [从隐藏区用牌](#从隐藏区用牌不要让玩家选改由服务端定位)
- [区域废除](#区域废除)

## 视图技的最小骨架

```lua
skill:addEffect("viewas", {
  anim_type = "support",
  pattern = "analeptic",
  prompt = "#技能",
  card_num = 0,
  card_filter = Util.FalseFunc,
  filter_pattern = {          -- 必须有，见下
    min_num = 0,
    max_num = 0,
    pattern = "",
  },
  view_as = function(self, player, cards)
    local card = Fk:cloneCard("analeptic")
    card.skillName = self.name
    return card
  end,
  before_use = function(self, player, use)
    ...
  end,
  enabled_at_play = function(self, player) ... end,
  enabled_at_response = function(self, player, response) ... end,
})
```

## 五个容易踩的点

### 1. `filter_pattern` 不能省

`ViewAsSkill:cardFilter` 里：

```lua
local filter_pattern = self:filterPattern(player, card and card.name, selected)
if filter_pattern then
  ...
  if #selected >= filter_pattern.max_num then return false end
  ...
end
return false              -- filter_pattern 为 nil 时直接到这里
```

`filterPattern` 的默认实现 `return nil`，于是不写 `filter_pattern` 的视图技返回 false，客户端一张牌都点不亮，技能表现为“点了没反应”。无消耗视图技写 `{ min_num = 0, max_num = 0, pattern = "" }`。官方样板 `packages/tenyear/pkg/tenyear_ex/skills/xiansi_viewas.lua` 就是这么写的。`filter_pattern` 在 `skill_skeleton.lua:695` 被转成返回常量表的函数。

### 2. 使用与响应入口分开判断

`enabled_at_response(player, response)` 的 `response` 表示“这是要求打出，不是要求使用”。酒、桃这类**使用**牌要写 `return not response and ...`；写成恒真会让求桃、求杀阶段也冒出酒按钮。参考 `xiansi_viewas.lua` 的 `enabled_at_response`。

### 3. 不要把实体子卡预先丢进弃牌堆

官方使用链 `UseCard:main` 会 `room:moveCardTo(useCardData.card, Card.Processing, nil, fk.ReasonUse)`，结算后再把处理区剩余实体牌送弃牌堆。实体牌已经在弃牌堆时，这条链静默失败：按钮能点、无弃牌、无效果。

`before_use` 若必须动实体牌，也只应挂子卡或做取消判断，不要抢先 `moveCardTo(DiscardPile)`。

```lua
before_use = function(self, player, use)
  local room = player.room
  local id = table.find(room.draw_pile, function(cardId)
    return Fk:getCardById(cardId, true).trueName == "analeptic"
  end)
  if not id then return self.name end   -- 返回技能名即取消本次使用
  use.card:addSubcard(id)
end,
```

`before_use` 返回字符串会取消本次使用（`ViewAsSkill:onUse` 直接 `return rejectSkillName`）。隐藏区用牌的可靠形态仍是下文的服务端主动技，不要把这段当主路径。

### 4. 拿不到隐藏区的牌时，先分清两个症状

同一个“没从牌堆取出【酒】”的反馈，可能来自完全不同的两层，先分清再改代码：

| 症状 | 层 | 查法 |
|---|---|---|
| 按钮根本不亮／点了没反应 | 客户端可用性 | 是否缺 `filter_pattern`、`enabled_*` 是否写反、`git status` 是否有未提交改动 |
| 按钮能点、技能提示出现，但没有牌进入弃牌堆 | 服务端结算链 | 是否抢先 `moveCardTo(DiscardPile)`；`on_use` 是否被 `player:canUse` 早退；牌堆实体酒 `useVirtualCard` 是否静默失败（改走 `obtainCard` + 拦截 + `drank`）；`table.find` 是否命中 |

“技能提示出现了但没效果”支持的是第二层，不要去动 `filter_pattern`。在 `on_use` 用 `print` 打出找到的 id、是否调用 `useVirtualCard`、返回值是否为 nil；`freekill.server.log` 无 traceback 却无效果，就是早退或使用链静默失败，加日志比继续推断快。

若两层都已排除、按钮就是不亮，问题在“客户端决定可用性”这个前提本身（见下一节）。实测结论：牌堆属于隐藏区，`viewas` 的可用性判断在客户端执行，客户端看不到牌堆内容，因此**任何依赖牌堆状态的视为技都无法可靠亮起**，这时应整体改成服务端主动技，而不是继续调 `filter_pattern` 或 `enabled_*`。

### 5. 排除自身产生的牌移动，也要排除借来的技能

统计 `fk.AfterCardsMove` 时除了检查 `move.skillName`，还要检查当前事件的外层 `UseCard` / `RespondCard` 元数据：官方漫卷 `js__manjuan` 的最终弃牌移动可能没有技能名，但外层 `attachedSkillAndUser.skillName` 仍然是 `js__manjuan`。普通梅花牌仍应触发；仅排除移牌字段会漏掉漫卷使用／响应后的情况。

同一回合内先 `abortPlayerArea` 再在同一阶段取牌时，注意 `Room:abortPlayerArea` 是**先 `moveCards` 清空区域、后写 `sealedSlots` 并广播**，顺序敏感的效果不要假设废除在清空之前已完成。

## 从隐藏区用牌：不要让玩家选，改由服务端定位

牌堆不是可见区。证据在客户端选牌入口 `ltk\client\client.lua` 的 `Client:askForCardChosen`：它只拼接 `target.player_cards[Player.Hand]`、`[Player.Equip]`、`[Player.Judge]` 三个区域，**没有牌堆**。由此两条路都堵死：

- 主动技 + `room:askToChooseCard{ flag = { card_data = { { "pile_draw", ids } } } }`：`expand_pile` / `card_data` 的展开机制只服务私人牌堆（`player:getPile(name)`）和装备区
- 视图技 + `before_use`：造牌那一步没问题，但**可用性判断在客户端**，客户端不知道牌堆里有没有那张牌，按钮要么不亮要么恒亮

正确骨架是“服务端定位 + 客户端零输入”的主动技。**如何结算那张实体牌**按效果类型分支，不要默认 `useVirtualCard`：

```lua
local function findDeckCard(room)              -- 从上往下扫，取最靠上的一张
  for _, cardId in ipairs(room.draw_pile) do
    if Fk:getCardById(cardId, true).trueName == "analeptic" then
      return cardId
    end
  end
end

skill:addEffect("active", {
  prompt = "#<前缀>__<技能名>",
  card_num = 0,
  target_num = 0,
  card_filter = Util.FalseFunc,
  target_filter = Util.FalseFunc,
  can_use = function(self, player)              -- 客户端和服务端都会执行，只检查公开前置条件
    return player:hasSkill(skill.name) and player:isHandAreaSealed()
  end,
  on_use = function(self, room, effect)
    local player = effect.from
    local id = findDeckCard(room)
    if not id then return end
    -- 按效果类型结算，见下表；不要默认 useVirtualCard
  end,
})
```

要点：

- `card_num = 0` + `target_num = 0` + 两个 `Util.FalseFunc` ⇒ 玩家只点确认，不产生任何选择请求
- 牌堆没有目标牌时按钮仍可能亮（客户端看不到牌堆）；`on_use` 找不到 id 则直接返回，满足“无牌则无效”
- “最靠上” = `room.draw_pile` 顺序的第一个元素，直接 `ipairs` 遍历取首个命中项，不要排序
- 不要自己 `cloneCard` + `player:canUse` + `moveCardTo(DiscardPile)` + `room:useCard`：前置 `canUse` 常因虚拟牌次数／区域判 false 而早退；预先弃牌会让官方处理区移动静默失败

### 结算那张实体牌

| 目标效果 | 做法 | 不要做 |
|---|---|---|
| 需要完整“使用一张【酒】”结算（计入使用、濒死求酒、动画） | 官方封装 `room:useVirtualCard("analeptic", { id }, player, player, skill.name, true)`。样板 `packages/brainhole_new/pkg/brainhole/skills/yaoyin.lua` 用的是无子卡虚拟酒 | 先 `moveCardTo(DiscardPile)` 再使用 |
| 只要“酒进弃牌堆 + 获得酒状态”，且角色手牌区已废除 | `room:obtainCard(player, id, true, fk.ReasonPrey, player, skill.name)`，核心 `moveInfoTranslate` 会自动把它改送到弃牌堆，再单独 `player.drank = player.drank + 1; room:broadcastProperty(player, "drank")`（对齐 `analeptic.lua` 非濒死 `on_effect`） | 继续调 `useCard` / `useVirtualCard`。0.5.25 上对牌堆实体酒多次静默失败：按钮能点、无弃牌、无 drank |

`obtainCard` 路径**不是**正式使用一张酒：不占本回合使用酒次数，也不走濒死求酒。用户只要状态效果时用这条，要完整使用结算时才走 `useVirtualCard`。手牌区是否拦截由核心按 `isHandAreaSealed()` 自动判定。

`drank` 在界面上几乎没有反馈（`LunarLtk/Components/Photo.qml` 里 `// visible: root.dataModel.drank > 0` 是注释掉的，只剩 `0.4 + log(drank)*0.12` 的头像泛红）。验收改问：出【杀】时伤害是否 +1（`analeptic_skill` 的 `fk.PreCardUse` 消费 `drank`），并向用户说明“这个效果没有图标”。

## 区域废除

```lua
room:abortPlayerArea(player, Player.JudgeSlot)   -- 服务端
room:resumePlayerArea(player, Player.JudgeSlot)  -- 复原
```

状态存在 `player.sealedSlots`，客户端读 `player:isJudgeAreaSealed()` / `player:isHandAreaSealed()`，事件 `fk.AreaAborted` / `fk.AreaResumed`。废除瞬间该区域内的牌进弃牌堆。

**判定区和手牌区支持程度完全不同，别照同一套写：**

| | 判定区 | 手牌区 |
|---|---|---|
| 核心是否自动拦截 | 是，三处强制：`Player:isProhibited`、`Player:isProhibitedTarget`、`events/usecard.lua` 放入判定区前的检查 | 是，`moveInfoTranslate` 阶段就把移入的牌改判为置入弃牌堆 |
| 废除后延时锦囊 | 不能指定该角色、不能移入、结算时进弃牌堆 | 不适用 |
| “不能持有手牌” | — | 核心已覆盖，**不要**再写 `fk.BeforeCardsMove` 补偿 |

手牌区为什么不用补拦截（0.5.25 已追通全链）：`room:obtainCard` / `room:moveCardTo` 最终都走 `self:moveCards(...)`，而 `moveCards` 先调 `moveInfoTranslate`。后者在 `toArea == Card.PlayerHand` 且 `to:isHandAreaSealed()` 时把该 move 塞进 `abortMoveInfos` 并 `goto continue2` 跳过，随后单独产出一条落到 `Card.DiscardPile` / `fk.ReasonPutIntoDiscardPile` 的移动。

所以 `fk.BeforeCardsMove` 触发时 `move.toArea` **已经是** `Card.DiscardPile`，`move.toArea == Card.PlayerHand` 永远不成立——照旧写法补的那段拦截是死代码。只有需要改目的地、或改 `moveReason` / 带上自己的 `skillName` 时，才值得挂 `fk.BeforeCardsMove`。

官方客户端对废除区域没有专门美术表现，再加 `@<前缀>_sealed` 一类标记让客户端看得见状态。

游戏内表现不对时按 [排查顺序](troubleshooting.md) 走。

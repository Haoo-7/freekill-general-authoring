# 最小可用三文件骨架

回链：[SKILL.md §4 创建拓展结构](../SKILL.md)。把 `<包名>` / `<子包>` / `<前缀>` / 代码名替换成自己的。UTF-8 无 BOM、2 空格缩进、LF 换行、文件尾留空行。

## 1. `packages/<包名>/init.lua`

```lua
-- 拓展入口：只有 init.lua 会被自动加载
local prefix = "packages.<包名>.pkg."

local <子包> = require(prefix .. "<子包>")

Fk:loadTranslationTable {
  ["<包名>"] = "扩展显示名",
}

return {
  <子包>,
}
```

入口必须 `return { ... }`。写成 `return <子包>` 时包不注册、武将不出现，日志里也看不出原因。

## 2. `packages/<包名>/pkg/<子包>/init.lua`

```lua
local extension = Package:new("<子包>")
extension.extensionName = "<包名>" -- 必须是 packages/ 下的文件夹名

extension:loadSkillSkelsByPath("./packages/<包名>/pkg/<子包>/skills")

Fk:loadTranslationTable {
  ["<子包>"] = "武将一览里的分组名",
}

-- General:new(所属包, 代码名, 势力, 体力, [体力上限], [性别])
General:new(extension, "<前缀>__<真名>", "shu", 4):addSkills { "<前缀>__<技能名>" }

Fk:loadTranslationTable {
  ["<前缀>"] = "角标字",          -- 显示在将面右下角
  ["<前缀>__<真名>"] = "武将名",
  ["#<前缀>__<真名>"] = "称号",
  ["designer:<前缀>__<真名>"] = "设计者",
  ["cv:<前缀>__<真名>"] = "配音",
  ["illustrator:<前缀>__<真名>"] = "画师",
  ["~<前缀>__<真名>"] = "阵亡台词",
}

return extension
```

## 3. `packages/<包名>/pkg/<子包>/skills/<前缀>__<技能名>.lua`

```lua
local skill = fk.CreateSkill {
  name = "<前缀>__<技能名>",
  tags = { Skill.Compulsory }, -- 锁定技；普通触发技去掉这一行
}

skill:addEffect(fk.DrawNCards, { -- 摸牌阶段摸牌时
  anim_type = "drawcard",
  on_use = function(self, event, target, player, data)
    data.n = data.n + 1
  end,
})

Fk:loadTranslationTable {
  ["<前缀>__<技能名>"] = "技能名",        -- ≤2 字
  [":<前缀>__<技能名>"] = "锁定技，摸牌阶段，你多摸一张牌。",
  ["$<前缀>__<技能名>1"] = "技能语音文本",  -- 音频放 audio/skill/<前缀>__<技能名>1.mp3
}

return skill
```

## 换成主动技（签名与触发技不同）

```lua
skill:addEffect("active", {
  anim_type = "support",
  prompt = "#<前缀>__<技能名>-active", -- 必须补这条翻译，否则提示为空
  max_phase_use_time = 1,
  card_filter = Util.FalseFunc,        -- 无牌消耗时这样写
  target_filter = function(self, player, to_select, selected)
    return #selected == 0 and to_select ~= player
  end,
  target_num = 1,
  on_use = function(self, room, effect)
    local from = effect.from
    local target = effect.tos[1]
    from:drawCards(1, skill.name)      -- 效果写在这里
  end,
})

Fk:loadTranslationTable {
  ["#<前缀>__<技能名>-active"] = "你可以摸一张牌。",
}
```

要点：`card_filter(self, player, to_select, selected)`、`target_filter(self, player, to_select, selected)`、`on_use(self, room, effect)`，取 `effect.from` / `effect.tos` / `effect.cards`。触发技则是 `can_trigger(self, event, target, player, data)` + `on_use(self, event, target, player, data)`。真实样板：`packages/freekill-core/standard/pkg/skills/jieyin.lua`（选牌+选目标）、`kurou.lua`（无牌主动技）。

## 触发技加可选条件

```lua
skill:addEffect(fk.Damaged, {
  anim_type = "masochism",
  can_trigger = function(self, event, target, player, data)
    return target == player and player:hasSkill(skill.name)
  end,
  on_use = function(self, event, target, player, data)
    player.room:obtainCard(player, data.card, true, fk.ReasonJustMove, player, skill.name)
  end,
})
```

样板：`packages/freekill-core/standard/pkg/skills/jianxiong.lua`。

## 借用现成技能

```lua
General:new(extension, "<前缀>__<真名>", "god", 5):addSkills { "wushuang", "<前缀>__<技能名>" }
```

## 写自测（可选）

```lua
skill:addTest(function(room, me)
  FkTest.RunAddSkills(me, skill.name)
  local spec = table.find(skill.effect_spec_list, function(item)
    return item[1] == fk.DrawNCards
  end)
  lu.assertTrue(type(spec[3].on_use) == "function")
end)
```

`skill.effect_spec_list` 每项是 `{key, attribute, spec}`（`skill_skeleton.lua:154/156`）。**`[1]` 是第一个 `addEffect` 调用，不是想要的那个效果**：先 `prohibit` 后 `active` 的技能取 `effect_spec_list[1][3].can_use` 得到 `nil`，测试在 `nil` 上调用直接报错。按第一个元素（key）筛出目标效果，不要按序号硬取。`lu.assertTrue` / `lu.assertFalse` 可用（`standard_cards\pkg\skills\nioh_shield.lua`）。

跑测试：在游戏根目录 `& '.\FreeKill.exe' --testskills <skill_name>`。

# 排查：改了但没生效

回链：[SKILL.md §10 静态验收](../SKILL.md)、[§11 游戏内验证](../SKILL.md)。游戏内表现不对、日志里没有报错时读这一份，按顺序查。

## 第 0 步：核对加载列表

先看 `freekill.server.log` 里 `Loaded N extension(s):` 后面那串包名有没有你的包。没有就什么都别改，先解决整包没加载的问题；这一步比读代码快一个数量级，能直接排掉“整包没加载”这类假 bug。

## 包没加载的三种原因

- `packages/<包名>/init.lua` 缺失或没有 `return { ... }`（写成 `return package` 时包不注册、武将不出现）
- `packages.db` 里 `enabled=0`：整包从加载列表静默消失，日志只少一个包名，没有报错、没有 traceback，武将直接不存在
- 目录名被改过或包被移到别处，`loadPackages()` 按 `packages/` 下的目录名匹配

## 包在列表里，但技能不触发

没有 Lua traceback 说明代码是被跳过而不是报错。优先怀疑这三件事，不要先改结算逻辑：

1. 工作区有未提交改动：游戏加载的是已提交版本，改了没提交等于没改。先 `git status`
2. `packages.db` 的 `hash` 与 `git rev-parse HEAD` 不一致：见下节
3. 技能不可用：客户端 `cardFilter` 返回 false，按钮根本不亮

两次同样的“触发失败”反馈，先核对 `git status` 是否有未提交改动；工作区一直在 `M` 状态就是空转，不是新 bug。

## hash 与仓库脱节，管理器会冲掉文件

在拓展管理里禁用／启用一个包，管理器会按它记录的 hash 把包目录 `git checkout` 还原。管理器持旧 hash（或启动时缓存的旧值）会直接冲掉磁盘上的新文件，表现为“刚写好的代码不见了”。

提交对象不会丢：`git reflog` 找到提交后 `git reset --hard <hash>` 恢复，再把正确的 `git rev-parse HEAD` 写回 `packages.db` 的 `hash` 列。

## 症状对层

| 症状 | 先查哪一层 |
| --- | --- |
| 按钮不亮／点了没反应 | 未提交改动 → db hash → 客户端条件（缺 `filter_pattern`、`enabled_*` 写反） |
| 技能提示出现但没效果 | 服务端结算链：`canUse` 早退、预先 `moveCardTo(DiscardPile)`、牌堆实体牌 `useVirtualCard` 静默失败 |
| 武将不在武将一览 | 包未加载、代码名重名导致 `loadPackages` 中断 |
| 报错堆栈落在 `client.lua` | 客户端／服务端边界，见 [SKILL.md §7](../SKILL.md) |
| 势力显示不对、只有本机能看 | 自定义势力未映射或势力图没进包，见 [技能形态](skill-mechanics.md) 末节 |

## 重名会中断整包加载

同一武将代码名或技能名已存在于另一个 `enabled=1` 的包里时，`loadPackages()` 会直接 `error` 中断（`Duplicate general <名> detected[package exist A, new package B]`），新武将根本进不了游戏。

写入前先 `SELECT name FROM packages WHERE enabled=1` 看谁在跑，再在全包范围扫重名：`Set-Location "<root>\packages"; cmd /c "findstr /s /m /c:<代码名> *.lua"`。

## 两个包内容重叠

把某个自制包里的武将并入合包时，先复制其技能文件与原画到合包、把翻译和 `General:new` 搬进合包 `init.lua`，再把源包目录改名为 `<包名>.disabled`。

`ModManager:loadPackages()` 跳过任何名字含 `.disabled` 的目录，改名即停用且可逆，不要直接删源包。随后在 README 的安装说明里写明须停用并移出原包，并确认全库只剩一份注册。

## 技能发动但无效果

遇到“特效出现但没有弃牌或状态变化”，记录 `gameMode`、`#room.draw_pile`、目标牌是否找到和 `disabled_packs`，先确认资源确实存在，再判断结算代码。

牌包加载和牌堆组成是两件事：即使日志显示某个拓展已加载，当前房间仍可能把它列入 `disabled_packs`，导致身份局牌堆没有对应的牌。

`drank` 在界面上几乎没有反馈（`Photo.qml` 里对应那行是注释掉的，只剩头像泛红）。验收改问：出【杀】时伤害是否 +1。向用户解释时也要主动说明“这个效果没有图标”。

## 报错修复原则

有报错以最新堆栈为准，读报错行前后代码和对应官方样板，不只修第一处表面错误。修完 grep 全包确认没有同款误用，重新提交并把新 hash 写回 `packages.db`。

# freekill-general-authoring

新月杀（[FreeKill](https://github.com/Qsgs-Fans/FreeKill)）自制武将的 Agent Skill：让 Agent 把自然语言武将描述（或卡面图）落成**可加载、可实测**的 Lua 拓展，而不是只交出一堆“看起来能用”的文件。

## 它解决什么问题

自制武将真正的成本不在写 Lua，而在三件容易被跳过的事：规则拆不清、API 凭印象猜、验收停在“文件写完了”。

这个 Skill 把三件事都定死：

- **先拆规则再写码**：把描述拆成触发时机、成本、效果、持续时间和边界；“获得／失去技能”这类状态机先问清承载方式与显示位置
- **查本机样板再动手**：在 `packages/` 里定位真实样板与 API 用法，不引用旧文档里不存在的接口
- **区分三种完成状态**：文件已写入、静态验收通过、游戏内实测通过；只有用户回报实测通过才叫“已生效”

同时附带一个可执行的静态验收脚本，把“验收清单”从人肉记忆变成可重复运行的检查。

## 安装

把仓库地址交给 Agent，让它克隆到宿主的 skills 目录，例如：

```text
~/.zcode/skills/freekill-general-authoring/
```

或用 skills CLI：

```bash
npx skills add Haoo-7/freekill-general-authoring
```

## 使用

对 Agent 说这些就会触发：

- “帮我做个武将，技能是……”
- “把这张武将卡图做成可玩的武将”
- “给现有拓展加一个新武将 / 改原画语音”
- “帮我验收这个包，看看为什么技能没触发”

**不会**触发：修改 FreeKill 本体或官方包源码、无名杀等其他引擎的拓展、纯规则咨询、联机故障排查。

## 配置

没有 API Key、没有账号、不需要联网。

只有一处需要按机器填：`references/local-environment.md` 是一份模板，写下你的 FreeKill 根目录、当前工作版本、游戏内测试入口和本机工具情况。可以让 Agent 直接读 `fk_ver` 填，也可以口头告诉它根目录。

静态验收脚本只需要 Python 3.10+ 标准库：

```bash
python scripts/check_package.py <FreeKill根目录>/packages/<包名> --fk-root <FreeKill根目录>
python -m unittest discover -s tests
```

想让脚本顺带做 Lua 语法解析时，在工作目录 `npm install luaparse --no-save`，再加 `--lua-parse <luaparse 目录>`。

## 目录结构

```text
SKILL.md                            # 主流程：11 个步骤，每步有完成标准
references/package-template.md      # 三文件骨架：触发技/主动技/借用技能/自测
references/core-api-samples.md      # 0.5.25 实测的 API 索引与样板文件
references/skill-mechanics.md       # 技能形态与坑：钩子粒度、失效技、标记、统计口径
references/viewas-and-areas.md      # 视为技、从隐藏区用牌、区域废除
references/text-and-assets.md       # 翻译键、文案规则、原画与语音
references/troubleshooting.md       # 改了没生效时的排查顺序
references/local-environment.md     # 本机环境模板（首次使用需填写）
scripts/check_package.py            # 静态验收：结构、编码、翻译键、db hash
tests/test_check_package.py         # 脚本的回归测试
```

## 兼容与依赖

- 需要本机有可用的 FreeKill 安装；主流程版本无关，API 清单与骨架以 **0.5.25** 实测为准
- 平台以 Windows + PowerShell 验证；搜索命令用了 `findstr`，其他平台请替换成自己的搜索工具
- 验收脚本只要 Python 3 标准库；Lua 语法解析需要 Node.js + luaparse
- 游戏内验证必须在真实客户端里做，脚本不能替代

## 数据边界

- Skill 不联网、不采集任何项目内容
- 脚本只读本地文件，只有在你显式指定 `--db` 或 `--fk-root` 时才读取 `packages.db`，并且只做只读查询
- 修改 `packages.db` 前会先备份；静态校验通过不代表游戏内生效，以实测回报为准

## 致谢

结构按 [oil-skill-creator](https://github.com/oil-oil/oil-skill-creator) 的方法论整理与校验。
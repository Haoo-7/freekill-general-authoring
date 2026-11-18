# 本机环境

回链：[SKILL.md 开始前](../SKILL.md)。这份文件是模板：第一次使用本 Skill 时，把你的环境填进去；填不出来就在对话里问用户，不要猜。

## 需要填写

| 项 | 填什么 | 怎么确认 |
| --- | --- | --- |
| FreeKill 根目录 | 装着游戏的目录，里面有 `fk_ver` 和 `packages` | 列目录，读 `fk_ver` |
| 当前工作版本 | 上面读到的版本号 | 和用户确认改哪一份 |
| 旧版安装 | 其他安装目录，标清不要混写 | 同上 |
| 游戏内测试入口 | 在根目录启动游戏并带 `--testskills <技能名>` 的写法 | 根目录的可执行文件名 |
| Python | 能跑 `scripts/check_package.py` 的 3.10+ | `py -3 --version` 或 `python3 --version` |
| Node + luaparse | 只在需要 Lua 语法解析时准备 | `node -v`，`npm i luaparse --no-save` |

有多份安装时，在表里写清哪份是当前工作版本、哪份是旧版。只改用户指定的那一份。

## 项目现状

按当前项目填写，不要套用别人的：

- 哪些包已经启用、彼此有没有注册同一个武将代码名或技能名
- 新武将应该写进哪个包
- 势力、角标这套内部 id 该沿用哪个值

同一代码名出现在两个启用的包里会让 `loadPackages()` 直接中断，新武将进不了游戏。写入前先查重。

## 平台备忘

下面几条是 Windows + PowerShell 上踩过的；其他平台换成等价工具，规则不变。

- 搜索：没有 `rg` 时用 `findstr`，先 `Set-Location <目录>` 再 `cmd /c "findstr /s /m /c:关键词 *.lua"`。`/s` 递归、`/m` 只列文件名、`/n` 带行号；限制到具体子目录，全库扫描可能挂起
- `Get-ChildItem -Recurse | Select-String` 扫大目录会长时间不返回，别用来做全库搜索
- `Get-ChildItem -Include *.lua -Path <目录>` **静默返回空**（路径要以 `\*` 结尾），空输出不能当“没搜到”下结论
- `findstr` 无匹配的退出码是 1，`Command exited with code 1` 是“没搜到”，不是命令失败
- PowerShell 里 `cd /d` 会报错，先 `Set-Location` 再调 `cmd`
- 没有 `sqlite3` 命令行时，用 Python 的 `sqlite3` 模块读写 `packages.db`
- 没有 `lua` / `luac` 时，用 luaparse 做语法解析，参数见 [SKILL.md 第 9 步](../SKILL.md)
- 控制台按本地代码页输出时中文会变乱码；脚本里固定 UTF-8 输出，读管道前也统一成 UTF-8

## 工具限制

- 写文件的工具可能有沙箱目录限制，写不进目标盘时改用整文件写入或换工具
- 精确替换类工具要求原文唯一，多处重复要带上下文，唯一性失败时整文件重写
- 看图工具可能只读工作区目录，要看包内原画先复制过去

## 协作约定

- 代码实现默认派给隔离执行者：任务里写死目标文件绝对路径、已拍板的规则口径、必须自查的本机 API，以及“不要 git commit、不要动 packages.db”
- 子代理只交报告，回来后自己 `git diff` 逐行看，把每条结论落到源码 file:line
- “子代理说已通过”不算验收

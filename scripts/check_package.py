#!/usr/bin/env python3
"""FreeKill 拓展包静态验收：只检查程序能确认的问题，不证明游戏内生效。

用法：
    python check_package.py <包目录> [--fk-root <FreeKill 根目录>]
                            [--db <packages.db>] [--lua-parse <luaparse 目录>]
                            [--json]

退出码 0 表示没有错误（警告可以存在），1 表示有错误，2 表示用法错误。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Iterable, NamedTuple

SKILL_CALLBACK_HINTS = (
    "enabled_at_play",
    "enabled_at_response",
    "can_use",
    "card_filter",
    "target_filter",
    "view_as",
    "interaction",
)
SERVER_ONLY_TOKENS = ("player.room", "room.draw_pile", "room:getOtherPlayers()")
FORBIDDEN_TOKENS = (
    ("table.copy(", "FreeKill 没有 table.copy，用 table.simpleClone"),
    ("--allow-empty-on-error", "git commit 没有 --allow-empty-on-error 选项"),
    (":getNumber()", "卡牌点数用 card.number 属性，没有 getNumber()"),
)
CREATE_SKILL_RE = re.compile(r"fk\.CreateSkill\s*\{")
SKILL_NAME_RE = re.compile(r'name\s*=\s*"([^"]+)"')
GENERAL_RE = re.compile(r'General:new\s*\(\s*[^,]+,\s*"([^"]+)"')
ADD_SKILLS_RE = re.compile(r"addSkills\s*\{(.*?)\}", re.DOTALL)
QUOTED_RE = re.compile(r'"([^"]+)"')
EXTENSION_NAME_RE = re.compile(r'extension\.extensionName\s*=\s*"([^"]+)"')
LOAD_SKILLS_RE = re.compile(r"loadSkillSkelsByPath\s*\(\s*\"([^\"]+)\"")
RETURN_RE = re.compile(r"^return\s+(?:\{|[A-Za-z_][A-Za-z0-9_]*)\s*$", re.MULTILINE)
CALLBACK_LINE_RE = re.compile(r"^(\s*)([A-Za-z_]+)\s*=\s*function\b")


class Finding(NamedTuple):
    level: str
    code: str
    message: str
    file: str = ""
    line: int = 0


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _line_of(text: str, needle: str) -> int:
    index = text.find(needle)
    if index < 0:
        return 0
    return text.count("\n", 0, index) + 1


def check_text_files(package: Path) -> list[Finding]:
    """编码与换行：UTF-8 无 BOM、LF、无 Tab、文件尾留空行。"""
    findings: list[Finding] = []
    for path in sorted(package.rglob("*.lua")):
        raw = path.read_bytes()
        name = _rel(path, package)
        if raw.startswith(b"\xef\xbb\xbf"):
            findings.append(Finding("error", "text.bom", "文件带 UTF-8 BOM，游戏读取会出错", name, 1))
            raw = raw[3:]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            findings.append(Finding("error", "text.encoding", f"不是合法 UTF-8：{exc.reason}", name, exc.start))
            continue
        if b"\r\n" in raw:
            line = raw[: raw.find(b"\r\n")].count(b"\n") + 1
            findings.append(
                Finding(
                    "warning",
                    "text.crlf",
                    "使用 CRLF 换行，改为 LF；若是 git 自动换行所致，先查 core.autocrlf",
                    name,
                    line,
                )
            )
        if "\t" in text:
            line = text[: text.find("\t")].count("\n") + 1
            findings.append(Finding("warning", "text.tab", "出现 Tab 缩进，改为 2 空格", name, line))
        if text and not text.endswith("\n"):
            findings.append(Finding("warning", "text.final-newline", "文件末尾缺少换行", name, text.count("\n") + 1))
    return findings


def collect_skill_names(package: Path) -> dict[str, Path]:
    """只在 fk.CreateSkill 里写明文名字的技能（翻译检查用）。卡牌技能不显示名字，跳过。"""
    names: dict[str, Path] = {}
    for path in sorted(package.rglob("*.lua")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in CREATE_SKILL_RE.finditer(text):
            tail = text[match.end() : match.end() + 400]
            name_match = SKILL_NAME_RE.search(tail)
            if name_match and "cardskill" not in tail.lower():
                names.setdefault(name_match.group(1), path)
    return names


def known_skill_names(package: Path) -> set[str]:
    """名字来自常量时（如 name = A.xingye）静态拿不到，用同名文件补上。"""
    known = set(collect_skill_names(package))
    known.update(path.stem for path in package.rglob("*.lua"))
    return known


def check_structure(package: Path) -> list[Finding]:
    """入口、子包、技能目录与 return 语句。"""
    findings: list[Finding] = []
    entry = package / "init.lua"
    if not entry.is_file():
        findings.append(Finding("error", "layout.entry-missing", "缺少入口 init.lua", "init.lua"))
        return findings
    entry_text = entry.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"return\s*\{", entry_text):
        findings.append(
            Finding(
                "warning",
                "layout.entry-return",
                "入口没有 return 表：自制包写成 return 包对象时常见不注册（改成 return { 包 } 最稳）",
                "init.lua",
                _line_of(entry_text, "return"),
            )
        )
    subpackages = [path for path in package.rglob("*/init.lua") if path != entry]
    if not subpackages:
        findings.append(
            Finding(
                "warning",
                "layout.subpackage-missing",
                "没有子包 init.lua；试验角色可以只有入口，正式拓展建议建子包",
                "init.lua",
            )
        )
    for sub in subpackages:
        text = sub.read_text(encoding="utf-8", errors="replace")
        name = _rel(sub, package)
        if "Package:new" not in text:
            continue  # i18n 这类辅助 init 不是子包
        ext = EXTENSION_NAME_RE.search(text)
        if not ext:
            findings.append(
                Finding(
                    "warning",
                    "layout.extension-name",
                    "子包未设置 extension.extensionName；自制包必须设成 packages/ 下的文件夹名",
                    name,
                )
            )
        elif ext.group(1) != package.name:
            findings.append(
                Finding(
                    "error",
                    "layout.extension-name-mismatch",
                    f'extensionName 是 "{ext.group(1)}"，必须等于 packages/ 下的文件夹名 "{package.name}"',
                    name,
                    _line_of(text, "extensionName"),
                )
            )
        load = LOAD_SKILLS_RE.search(text)
        if not load:
            findings.append(Finding("warning", "layout.load-skills", "子包没有调用 loadSkillSkelsByPath", name))
        elif package.name not in load.group(1).replace("\\", "/") or not load.group(1).endswith("/skills"):
            findings.append(
                Finding(
                    "warning",
                    "layout.load-skills-path",
                    f'loadSkillSkelsByPath 路径是 "{load.group(1)}"，核对是否指向本包的 skills 目录',
                    name,
                    _line_of(text, "loadSkillSkelsByPath"),
                )
            )
    for path in sorted(package.rglob("*.lua")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if not CREATE_SKILL_RE.search(text):
            continue
        if not RETURN_RE.search(text):
            findings.append(
                Finding(
                    "error",
                    "skill.return-missing",
                    "技能文件没有 return 骨架变量，加载后拿不到 skill",
                    _rel(path, package),
                    text.count("\n") + 1,
                )
            )
    return findings


def check_generals_and_skills(package: Path) -> list[Finding]:
    """代码名前缀、技能名一致性、addSkills 引用。"""
    findings: list[Finding] = []
    defined = known_skill_names(package)
    for path in sorted(package.rglob("*.lua")):
        text = path.read_text(encoding="utf-8", errors="replace")
        name = _rel(path, package)
        for match in GENERAL_RE.finditer(text):
            code = match.group(1)
            if "__" not in code:
                findings.append(
                    Finding(
                        "warning",
                        "general.prefix",
                        f'武将代码名 "{code}" 没有 __ 前缀，与官方武将同名时会冲突',
                        name,
                        _line_of(text, code),
                    )
                )
            prefix = code.split("__")[0]
            for block in ADD_SKILLS_RE.finditer(text):
                for skill_name in QUOTED_RE.findall(block.group(1)):
                    if skill_name in defined:
                        continue
                    if skill_name.startswith(prefix + "__"):
                        findings.append(
                            Finding(
                                "warning",
                                "skill.undefined",
                                f'addSkills 引用了 "{skill_name}"，本包没有同名技能骨架',
                                name,
                                _line_of(text, skill_name),
                            )
                        )
    return findings


def referenced_skill_names(package: Path) -> set[str]:
    """被 General:addSkills 引用的技能才是显示在武将上的技能。"""
    names: set[str] = set()
    for path in sorted(package.rglob("*.lua")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for block in ADD_SKILLS_RE.finditer(text):
            names.update(QUOTED_RE.findall(block.group(1)))
    return names


def check_translations(package: Path) -> list[Finding]:
    """武将上的技能必须有翻译键；描述缺失只提醒（辅助技能常见）。"""
    findings: list[Finding] = []
    corpus = "\n".join(
        path.read_text(encoding="utf-8", errors="replace") for path in sorted(package.rglob("*.lua"))
    )
    displayed = referenced_skill_names(package)
    for skill_name, path in sorted(collect_skill_names(package).items()):
        # # 前缀是隐藏技能，卡牌技能和未上武将的技能不用翻译
        if skill_name.startswith("#") or skill_name not in displayed:
            continue
        if f'["{skill_name}"]' not in corpus:
            findings.append(
                Finding(
                    "error",
                    "translation.missing",
                    f'缺少技能名翻译键 ["{skill_name}"]',
                    _rel(path, package),
                )
            )
        if f'[":{skill_name}"]' not in corpus:
            findings.append(
                Finding(
                    "warning",
                    "translation.missing-desc",
                    f'缺少技能描述翻译键 [":{skill_name}"]；纯辅助技能可忽略',
                    _rel(path, package),
                )
            )
    return findings


def callback_blocks(text: str) -> list[tuple[str, int, list[str]]]:
    """按缩进切出客户端回调的函数体，判断服务端专有字段是否真落在客户端路径里。"""
    lines = text.splitlines()
    blocks: list[tuple[str, int, list[str]]] = []
    for index, line in enumerate(lines):
        match = CALLBACK_LINE_RE.match(line)
        if not match or match.group(2) not in SKILL_CALLBACK_HINTS:
            continue
        indent = len(match.group(1))
        body = [line]
        single_line = line.count("function") == line.count("end")
        if not single_line:
            for follow in lines[index + 1 :]:
                stripped = follow.strip()
                if stripped and len(follow) - len(follow.lstrip()) <= indent and stripped.startswith("end"):
                    break
                body.append(follow)
        blocks.append((match.group(2), index + 1, body))
    return blocks


def check_callbacks(package: Path) -> list[Finding]:
    """客户端/服务端分界与已知不存在的 API。"""
    findings: list[Finding] = []
    for path in sorted(package.rglob("*.lua")):
        text = path.read_text(encoding="utf-8", errors="replace")
        name = _rel(path, package)
        for token, message in FORBIDDEN_TOKENS:
            if token in text:
                findings.append(Finding("error", "api.forbidden", message, name, _line_of(text, token)))
        for key, start, body in callback_blocks(text):
            for token in SERVER_ONLY_TOKENS:
                offset = next((i for i, row in enumerate(body) if token in row), None)
                if offset is None:
                    continue
                findings.append(
                    Finding(
                        "warning",
                        "callback.boundary",
                        f"{key} 在客户端执行，里面出现了 {token}",
                        name,
                        start + offset,
                    )
                )
    return findings


def check_lua_syntax(package: Path, luaparse_dir: Path) -> list[Finding]:
    """用 luaparse 真解析每个 Lua 文件。"""
    findings: list[Finding] = []
    node = shutil.which("node")
    if node is None:
        return [Finding("warning", "lua.node-missing", "找不到 node，跳过语法解析")]
    script = (
        "const p=require(process.argv[1]);"
        "const fs=require('fs');"
        "try{p.parse(fs.readFileSync(process.argv[2],'utf8'));}"
        "catch(e){console.error(e.message);process.exit(1);}"
    )
    for path in sorted(package.rglob("*.lua")):
        result = subprocess.run(
            [node, "-e", script, str(luaparse_dir), str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            findings.append(
                Finding(
                    "error",
                    "lua.syntax",
                    f"语法解析失败：{result.stderr.strip().splitlines()[0] if result.stderr.strip() else '未知错误'}",
                    _rel(path, package),
                )
            )
    return findings


def check_database(package: Path, db_path: Path) -> list[Finding]:
    """packages.db 登记状态与 hash 同步。"""
    findings: list[Finding] = []
    if not db_path.is_file():
        return [Finding("error", "db.missing", f"找不到 packages.db：{db_path}", str(db_path))]
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = connection.execute(
            "SELECT name, hash, enabled FROM packages WHERE name = ?", (package.name,)
        ).fetchall()
        connection.close()
    except sqlite3.Error as exc:
        return [Finding("error", "db.read", f"读取 packages.db 失败：{exc}", str(db_path))]
    if not rows:
        return [
            Finding(
                "error",
                "db.row-missing",
                f'packages 表没有 "{package.name}" 行；拓展管理页认不到这个包',
                str(db_path),
            )
        ]
    _, recorded_hash, enabled = rows[0]
    if not enabled:
        findings.append(
            Finding(
                "error",
                "db.disabled",
                "enabled=0 会让整包从加载列表静默消失；改完代码必须置 1",
                str(db_path),
            )
        )
    head = subprocess.run(
        ["git", "-C", str(package), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if head.returncode == 0:
        head_hash = head.stdout.strip()
        if recorded_hash != head_hash:
            findings.append(
                Finding(
                    "error",
                    "db.hash-stale",
                    f"hash 与 HEAD 不一致（库中 {str(recorded_hash)[:8]}，HEAD {head_hash[:8]}）；"
                    "拓展管理按库中 hash 还原会冲掉新文件",
                    str(db_path),
                )
            )
    else:
        findings.append(
            Finding("warning", "db.git-missing", "包目录不是 git 仓库，无法核对 hash", str(package))
        )
    return findings


def run_checks(package: Path, db_path: Path | None, luaparse_dir: Path | None) -> list[Finding]:
    findings: list[Finding] = []
    findings += check_text_files(package)
    findings += check_structure(package)
    findings += check_generals_and_skills(package)
    findings += check_translations(package)
    findings += check_callbacks(package)
    if luaparse_dir is not None:
        findings += check_lua_syntax(package, luaparse_dir)
    if db_path is not None:
        findings += check_database(package, db_path)
    return findings


def format_findings(findings: Iterable[Finding]) -> str:
    lines = []
    for item in sorted(findings, key=lambda f: (f.level != "error", f.file, f.line)):
        location = f"{item.file}:{item.line}" if item.line else item.file
        lines.append(f"[{item.level.upper()}] {item.code} {location} — {item.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    # Windows 控制台默认用本地代码页写中文，管道读取会解码失败；固定 UTF-8 输出。
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="FreeKill 拓展包静态验收")
    parser.add_argument("package", help="拓展包目录，例如 <root>/packages/<包名>")
    parser.add_argument("--fk-root", help="FreeKill 根目录；给出时默认读取其中的 packages/packages.db")
    parser.add_argument("--db", help="packages.db 路径，覆盖 --fk-root 推断值")
    parser.add_argument("--lua-parse", help="luaparse 模块所在目录，给出时逐个文件解析语法")
    parser.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON")
    args = parser.parse_args(argv)

    package = Path(args.package).expanduser()
    if not package.is_dir():
        print(f"包目录不存在：{package}", file=sys.stderr)
        return 2

    db_path = Path(args.db).expanduser() if args.db else None
    if db_path is None and args.fk_root:
        candidate = Path(args.fk_root).expanduser() / "packages" / "packages.db"
        db_path = candidate if candidate.is_file() else None
    luaparse_dir = Path(args.lua_parse).expanduser() if args.lua_parse else None

    findings = run_checks(package, db_path, luaparse_dir)
    errors = [item for item in findings if item.level == "error"]
    warnings = [item for item in findings if item.level == "warning"]

    if args.as_json:
        print(
            json.dumps(
                {
                    "package": str(package),
                    "errors": len(errors),
                    "warnings": len(warnings),
                    "findings": [item._asdict() for item in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        text = format_findings(findings)
        if text:
            print(text)
        print(f"{'FAIL' if errors else 'PASS'}：{len(errors)} 个错误，{len(warnings)} 个警告")
        if not errors:
            print("静态验收只证明文件结构合法，不能证明游戏内生效；仍需重启游戏实测。")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

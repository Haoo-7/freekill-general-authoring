"""check_package.py 的回归测试：用完整调用链构造包目录，不单测正则。

运行：python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_package  # noqa: E402

GOOD_ENTRY = """local prefix = "packages.demo.pkg."

local main = require(prefix .. "main")

return {
  main,
}
"""

GOOD_SUB = """local extension = Package:new("main")
extension.extensionName = "demo"

extension:loadSkillSkelsByPath("./packages/demo/pkg/main/skills")

General:new(extension, "abc__hero", "shu", 4):addSkills { "abc__skill" }

return {
  extension,
}
"""

GOOD_SKILL = """local skill = fk.CreateSkill {
  name = "abc__skill",
}

skill:addEffect(fk.DrawNCards, {
  on_use = function(self, event, target, player, data)
    data.n = data.n + 1
  end,
})

Fk:loadTranslationTable {
  ["abc__skill"] = "摸牌",
  [":abc__skill"] = "锁定技，摸牌阶段，你多摸一张牌。",
}

return skill
"""


def write_package(root: Path, entry: str = GOOD_ENTRY, sub: str = GOOD_SUB, skill: str = GOOD_SKILL) -> Path:
    package = root / "demo"
    (package / "pkg" / "main" / "skills").mkdir(parents=True)
    (package / "init.lua").write_text(entry, encoding="utf-8", newline="\n")
    (package / "pkg" / "main" / "init.lua").write_text(sub, encoding="utf-8", newline="\n")
    (package / "pkg" / "main" / "skills" / "abc__skill.lua").write_text(skill, encoding="utf-8", newline="\n")
    return package


class CheckPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def codes(self, findings) -> set[str]:
        return {item.code for item in findings}

    def test_clean_package_passes(self) -> None:
        package = write_package(self.root)
        findings = check_package.run_checks(package, None, None)
        self.assertEqual([item for item in findings if item.level == "error"], [])

    def test_bom_and_crlf_are_flagged(self) -> None:
        package = write_package(self.root)
        target = package / "pkg" / "main" / "skills" / "abc__skill.lua"
        target.write_bytes(b"\xef\xbb\xbf" + GOOD_SKILL.replace("\n", "\r\n").encode("utf-8"))
        codes = self.codes(check_package.run_checks(package, None, None))
        self.assertIn("text.bom", codes)
        self.assertIn("text.crlf", codes)

    def test_entry_returning_bare_object_is_warning(self) -> None:
        package = write_package(self.root, entry="local main = require('x')\nreturn main\n")
        findings = check_package.run_checks(package, None, None)
        self.assertIn("layout.entry-return", {item.code for item in findings if item.level == "warning"})

    def test_extension_name_must_match_folder(self) -> None:
        package = write_package(self.root, sub=GOOD_SUB.replace('"demo"', '"other"'))
        codes = self.codes(check_package.run_checks(package, None, None))
        self.assertIn("layout.extension-name-mismatch", codes)

    def test_missing_return_skill_is_error(self) -> None:
        package = write_package(self.root, skill=GOOD_SKILL.replace("return skill\n", ""))
        codes = self.codes(check_package.run_checks(package, None, None))
        self.assertIn("skill.return-missing", codes)

    def test_missing_name_translation_is_error(self) -> None:
        package = write_package(self.root, skill=GOOD_SKILL.replace('  ["abc__skill"] = "摸牌",\n', ""))
        findings = check_package.run_checks(package, None, None)
        self.assertIn("translation.missing", {item.code for item in findings if item.level == "error"})

    def test_missing_description_translation_is_warning(self) -> None:
        package = write_package(
            self.root, skill=GOOD_SKILL.replace('  [":abc__skill"] = "锁定技，摸牌阶段，你多摸一张牌。",\n', "")
        )
        findings = check_package.run_checks(package, None, None)
        self.assertEqual([item for item in findings if item.level == "error"], [])
        self.assertIn("translation.missing-desc", {item.code for item in findings})

    def test_hidden_skill_needs_no_translation(self) -> None:
        package = write_package(
            self.root,
            skill=GOOD_SKILL.replace('name = "abc__skill"', 'name = "#abc__skill"').replace(
                '  ["abc__skill"] = "摸牌",\n  [":abc__skill"] = "锁定技，摸牌阶段，你多摸一张牌。",\n', ""
            ),
        )
        codes = self.codes(check_package.run_checks(package, None, None))
        self.assertNotIn("translation.missing", codes)

    def test_return_variable_name_can_differ(self) -> None:
        package = write_package(self.root, skill=GOOD_SKILL.replace("return skill\n", "return xiongbian\n"))
        codes = self.codes(check_package.run_checks(package, None, None))
        self.assertNotIn("skill.return-missing", codes)

    def test_forbidden_api_is_error(self) -> None:
        package = write_package(
            self.root,
            skill=GOOD_SKILL.replace("data.n = data.n + 1", "local n = Fk:getCardById(1):getNumber()"),
        )
        codes = self.codes(check_package.run_checks(package, None, None))
        self.assertIn("api.forbidden", codes)

    def test_client_boundary_is_flagged(self) -> None:
        package = write_package(
            self.root,
            skill=GOOD_SKILL.replace(
                "  on_use = function(self, event, target, player, data)\n    data.n = data.n + 1\n  end,",
                "  can_use = function(self, player)\n    return player.room.draw_pile ~= nil\n  end,",
            ),
        )
        codes = self.codes(check_package.run_checks(package, None, None))
        self.assertIn("callback.boundary", codes)

    def test_database_hash_and_enabled(self) -> None:
        package = write_package(self.root)
        subprocess.run(["git", "init", "-q"], cwd=package, check=True)
        for key, value in (("user.name", "t"), ("user.email", "t@example.com")):
            subprocess.run(["git", "config", key, value], cwd=package, check=True)
        subprocess.run(["git", "add", "."], cwd=package, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=package, check=True)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=package, capture_output=True, text=True, check=True
        ).stdout.strip()

        db_path = self.root / "packages.db"
        connection = sqlite3.connect(db_path)
        connection.execute("CREATE TABLE packages (name TEXT, url TEXT, hash TEXT, enabled INTEGER)")
        connection.execute(
            "INSERT INTO packages VALUES ('demo', 'local://packages/demo', ?, 1)", (head,)
        )
        connection.commit()
        connection.close()

        self.assertEqual(
            [item for item in check_package.run_checks(package, db_path, None) if item.level == "error"], []
        )

        connection = sqlite3.connect(db_path)
        connection.execute("UPDATE packages SET hash = 'deadbeef' WHERE name = 'demo'")
        connection.commit()
        connection.close()
        codes = self.codes(check_package.run_checks(package, db_path, None))
        self.assertIn("db.hash-stale", codes)

        connection = sqlite3.connect(db_path)
        connection.execute("UPDATE packages SET enabled = 0 WHERE name = 'demo'")
        connection.commit()
        connection.close()
        codes = self.codes(check_package.run_checks(package, db_path, None))
        self.assertIn("db.disabled", codes)

    def test_cli_json_output_and_exit_code(self) -> None:
        package = write_package(self.root)
        target = package / "pkg" / "main" / "skills" / "abc__skill.lua"
        target.write_bytes(b"\xef\xbb\xbf" + GOOD_SKILL.encode("utf-8"))
        result = subprocess.run(
            [sys.executable, str(Path(check_package.__file__)), str(package), "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertGreaterEqual(payload["errors"], 1)
        self.assertIn("text.bom", {item["code"] for item in payload["findings"]})


if __name__ == "__main__":
    unittest.main()

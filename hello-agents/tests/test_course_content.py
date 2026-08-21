from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CourseContentTests(unittest.TestCase):
    def test_all_sixteen_lessons_and_projects_exist(self):
        lessons = sorted((ROOT / "lessons").glob("[0-9][0-9]-*.md"))
        projects = sorted((ROOT / "projects").glob("[0-9][0-9]-*"))
        self.assertEqual(16, len(lessons))
        self.assertEqual(16, len(projects))
        for project in projects:
            self.assertTrue((project / "README.md").exists(), project)
            self.assertTrue((project / "main.py").exists(), project)

    def test_lessons_contain_mapping_and_practice_links(self):
        for lesson in sorted((ROOT / "lessons").glob("[0-9][0-9]-*.md")):
            content = lesson.read_text(encoding="utf-8")
            self.assertTrue("学习状态" in content or "当前状态" in content, lesson)
            self.assertTrue("实践项目" in content or "代码实践" in content, lesson)
            self.assertTrue("实验" in content or "完成标准" in content or "验收" in content, lesson)

    def test_no_hello_agents_code_imports_achieve(self):
        for path in (ROOT / "projects").rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("from achieve", content, path)
            self.assertNotIn("import achieve", content, path)


if __name__ == "__main__":
    unittest.main()

"""Tests: task parsing, edit blocks, batch selection, and the whole pipeline in a temp git repo with stub models (shell commands)."""
import json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
import escalator as E

BLOCK = "FILE: a.txt\n<<<<<<< SEARCH\nold\n=======\n%s\n>>>>>>> REPLACE\n"


def put(path, text):
    with open(path, "w") as f:
        f.write(text)


class Pure(unittest.TestCase):
    def test_parse_tasks(self):
        md = "| id | text | files | status |\n|---|---|---|---|\n| T1 | Do it | a.py, b.py | |\n| T2 | Old | | closed |\n- [ ] T3: Third (files: c.py)\n- [x] T4: Done\n"
        t = E.parse_tasks(md)
        self.assertEqual([x["id"] for x in t], ["T1", "T2", "T3", "T4"])
        self.assertEqual(t[0]["files"], ["a.py", "b.py"])
        self.assertEqual(E.pick_rows(t, set(), set()), ["T1", "T3"])
        j = E.parse_tasks('[{"id": "J1", "text": "x"}]')
        self.assertEqual(j[0]["id"], "J1")

    def test_edits(self):
        edits = E.parse_edits("<think>hm</think>\n" + BLOCK % "new")
        self.assertEqual(edits, [("a.txt", "old", "new")])
        files, err = E.apply_edits(lambda p: "x old y\n", edits)
        self.assertEqual((files["a.txt"], err), ("x new y\n", ""))
        _, err = E.apply_edits(lambda p: "old old\n", edits)
        self.assertIn("matched 2 times", err)
        _, err = E.apply_edits(lambda p: "", [("../x", "", "n")])
        self.assertIn("outside", err)

    def test_diff_gate_and_state(self):
        d = "diff --git a/tests/test_x.py b/tests/test_x.py\n+++ b/tests/test_x.py\n+x\n"
        self.assertFalse(E.diff_gate(d, ["tests/*"], 10)[0])
        self.assertTrue(E.diff_gate(d, [], 10)[0])
        tsv = "A\tt\t1\tred\t-\nA\tt\t1\tred\t-\nB\tt\t1\tgreen\tb\nC\tt\t1\tinfra\t-\n"
        self.assertEqual(E.tsv_state(tsv), {"A", "B"})


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.repo = os.path.join(t, "repo")
        os.makedirs(self.repo)
        def g(*a): subprocess.run(["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", *a], check=True, capture_output=True)
        g("init", "-q", "-b", "main")
        put(os.path.join(self.repo, "a.txt"), "old\n")
        g("add", "."); g("commit", "-q", "-m", "init")
        put(os.path.join(t, "tasks.md"), "| id | text | files |\n|---|---|---|\n| T1 | Change the word old to new | a.txt |\n")
        self.draft = os.path.join(t, "draft.sh")
        self.cfg = E.load_config(None)
        self.cfg.update(repo=self.repo, tasks=os.path.join(t, "tasks.md"), worktrees=os.path.join(t, "wt"), logs=os.path.join(t, "logs"),
                        gate_cmd="grep -q '^new$' a.txt", tries=2,
                        draft={"cmd": "cat >/dev/null; cat " + self.draft}, review={"cmd": "cat >/dev/null; echo OK"})

    def tearDown(self):
        self.tmp.cleanup()

    def write_reply(self, text):
        put(self.draft, text)

    def test_green_commit(self):
        self.write_reply(BLOCK % "new")
        r = E.run_task(self.cfg, "T1", say=lambda *a: None)
        self.assertEqual((r["final"], r["committed"], r["escalated"]), ("green", True, False))
        self.assertEqual(subprocess.run(["git", "-C", self.repo, "show", "esc/t1:a.txt"], capture_output=True, text=True).stdout, "new\n")

    def test_escalates_on_red(self):
        self.write_reply(BLOCK % "wrong")
        self.cfg["fix"] = {"cmd": "cat >/dev/null; printf 'new\\n' > a.txt"}
        r = E.run_task(self.cfg, "T1", say=lambda *a: None)
        self.assertEqual((r["final"], r["escalated"], r["tries"]), ("green", True, 2))

    def test_red_without_fixer(self):
        self.write_reply(BLOCK % "wrong")
        r = E.run_task(self.cfg, "T1", say=lambda *a: None)
        self.assertEqual((r["final"], r["committed"]), ("red", False))
        self.assertIn("tests red", r["reason"])


class Help(unittest.TestCase):
    def test_help(self):
        for s in ("escalate", "escalate-batch"):
            p = subprocess.run([sys.executable, os.path.join(ROOT, "bin", s), "--help"], capture_output=True, text=True, timeout=30)
            self.assertEqual(p.returncode, 0, p.stderr)


if __name__ == "__main__":
    unittest.main()

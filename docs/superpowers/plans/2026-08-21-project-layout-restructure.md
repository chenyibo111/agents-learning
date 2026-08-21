# Split Current Learning Workspace Into Two Projects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep the existing 00–32 course intact under `achieve/` and add an independent `hello-agents/` learning track in the same Git repository.

**Architecture:** Move the existing lessons, projects, tests, and project-level documentation together under `achieve/` so their internal relative paths remain stable. Add a separate `hello-agents/` tree with its own curriculum, mapping, progress, lessons, projects, tests, and dependency template; the two tracks share only the repository-level Git configuration and are not coupled by imports.

**Tech Stack:** Markdown, Python, unittest, Git.

---

### Task 1: Move the existing course into `achieve/`

**Files:**
- Move: `lessons/` → `achieve/lessons/`
- Move: `projects/` → `achieve/projects/`
- Move: `tests/` → `achieve/tests/`
- Move: `README.md`, `CURRICULUM.md`, `ROADMAP.md`, `requirements.txt`, `.env.example` → `achieve/`

- [ ] Preserve the existing file contents and use Git-aware moves.
- [ ] Keep the untracked `.env` secret out of Git operations.

### Task 2: Add the new Hello-Agents track

**Files:**
- Create: `hello-agents/README.md`
- Create: `hello-agents/CURRICULUM.md`
- Create: `hello-agents/COURSE_MAP.md`
- Create: `hello-agents/PROGRESS.md`
- Create: `hello-agents/requirements.txt`
- Create: `hello-agents/.env.example`
- Create: `hello-agents/lessons/README.md`
- Create: `hello-agents/projects/README.md`
- Create: `hello-agents/tests/README.md`

- [ ] Document the original Hello-Agents chapter sequence.
- [ ] Mark each chapter as already learned, partially learned, or new relative to `achieve`.
- [ ] State that the new track is code-independent from `achieve`.

### Task 3: Update workspace entry points and ignore rules

**Files:**
- Create/Modify: root `README.md`
- Modify: root `.gitignore`
- Modify: `achieve/README.md`

- [ ] Make the root README link to both projects.
- [ ] Keep runtime artifacts and `.env` files ignored in either project.
- [ ] Document the working-directory convention for running each project.

### Task 4: Verify the restructure

- [ ] Run `git diff --check`.
- [ ] Run `.venv311/bin/python -m unittest discover -s achieve/tests -p 'test_*.py' -v`.
- [ ] Run the lesson 32 offline evaluation from `achieve/`.
- [ ] Scan staged/candidate files for API keys and confirm no `.env` is tracked.
- [ ] Confirm `hello-agents/` has no imports into `achieve/`.

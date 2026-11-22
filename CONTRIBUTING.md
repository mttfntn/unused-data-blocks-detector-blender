# Contributing to Unused Data Blocks Detector

Thanks for helping! Bug reports, ideas and pull requests are all welcome.

## Reporting a bug or suggesting a feature

Open an [issue](https://github.com/mttfntn/unused-data-blocks-detector-blender/issues/new/choose) and pick a form:

- **Bug report:** say which Blender version and Unused Data Blocks Detector version you use, your operating system, and the steps to reproduce.
- **Feature request:** describe what you're trying to do, not only the solution you have in mind.

First, check whether someone has already opened an issue for the same thing. Security problems go through [SECURITY.md](SECURITY.md), not public issues.

## Changing the code

[HANDOVER.md](HANDOVER.md) explains how the extension is organised and the pitfalls already found. Read it before a larger change.

1. **Fork** the repository and create a branch for your change.
2. You need **Blender 5.3** (the only supported version) and Python 3.
3. Run the tests from the repo root. They run in a separate, headless Blender with a throwaway profile (or without Blender), so your own add-ons and preferences stay out of it:

   ```
   blender --background --factory-startup --python tests/test_blender.py
   ```

   HANDOVER.md ("How to run the tests") has the details and the expected result. Never run the tests inside the Blender session you work in.
4. **If you fix a bug,** add a test that fails without your fix.
5. **If you change behaviour on purpose,** compare with the previous version (HANDOVER.md explains how) and explain every difference in the pull request.
6. **Open a pull request.** The template has a short checklist, and CI runs the tests.

### Style

- Comments must say what the code does; check them when you change the code.
- Keep commits small, with messages that explain what changed and how you checked it.

## License

Unused Data Blocks Detector is GPL-3.0-or-later. By contributing, you agree that your contribution is released under the same license.

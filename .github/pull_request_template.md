## Description

<!-- What does this PR do? Why is it needed? -->

## Type of change

- [ ] `feat` — new feature
- [ ] `fix` — bug fix
- [ ] `refactor` — refactoring with no behavior change
- [ ] `test` — adding or fixing tests
- [ ] `docs` — documentation
- [ ] `build` — build / CI changes
- [ ] `chore` — maintenance

> The squash-merge PR title must follow Conventional Commits — it drives the
> SemVer bump on release: `feat!` / `BREAKING CHANGE` → major, `feat` → minor,
> everything else → patch.

## Security checklist

- [ ] No secrets (tokens, user ids) in code, tests or logs
- [ ] Allowlist / fail-closed behavior preserved
- [ ] User input that reaches the CSV stays sanitized
- [ ] Received media is still deleted after processing

## Checklist

- [ ] `pytest` passes locally (coverage ≥ 80%)
- [ ] `ruff check .` passes
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] New or changed bot replies exist in all languages (pt/en/es)

## Tests added / modified

<!-- List new or changed tests. -->

## Notes for the reviewer

<!-- Context, design decisions, known pitfalls. -->

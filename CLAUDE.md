# count-people

Telegram bot that counts people in photos and videos with MiVOLO (age group +
gender demographics), replies localized in pt/en/es, and keeps a CSV history of
aggregated numbers. Runs on macOS (Apple Silicon/MPS), CPU-only VPS or CUDA.

## Commands

```bash
# Setup (Python 3.12; the project path must not contain spaces)
python3.12 -m venv .venv && source .venv/bin/activate
PIP_CONSTRAINT=$PWD/constraints.txt pip install -r requirements.txt -r requirements-dev.txt

pytest                      # unit tests + coverage gate (>= 80%; keep it at 100%)
RUN_INTEGRATION=1 pytest    # adds real-model tests (slow; needs local weights + samples)
ruff check .                # lint / static analysis

set -a && source .env && set +a && python3 bot.py   # run the bot locally
```

## Architecture

- `bot.py` — Telegram handlers (long polling), allowlist, file-size limits
- `analysis.py` — MiVOLO inference: photo counting, video tracking (unique
  people), weight download + SHA256 verification
- `history.py` — CSV persistence and label sanitization
- `messages.py` — all user-facing texts in pt/en/es, resolved per sender's
  Telegram client language
- `count-people.ipynb` — standalone Google Colab alternative (same logic,
  duplicated on purpose; keep the CSV schema in sync with `history.py`)

## Conventions

- Squash-merge PRs with a Conventional Commit title; the release workflow
  computes SemVer from those titles (`feat!` → major, `feat` → minor,
  everything else → patch) and tags/releases automatically on every push to
  main. The `VERSION` file is bumped by the workflow — never edit it by hand.
- Update `CHANGELOG.md` under `[Unreleased]` in every PR.
- Every new or changed bot reply must exist in pt, en and es
  (`tests/test_messages.py` enforces completeness and placeholder consistency).

## Security invariants (do not regress)

- `ALLOWED_USER_IDS` is mandatory: the bot fails closed at startup and
  **silently ignores** unknown senders (no reply that confirms the bot exists).
- Model weights are pickle-loaded (`weights_only=False`), so the SHA256 pins in
  `analysis.py` are verified on every startup. Only update the pins for files
  from the official MiVOLO release.
- Captions are sanitized before reaching the CSV (control chars, leading
  formula chars, 64-char cap) — CSV/formula injection mitigation.
- The bot token must never appear in logs (the `httpx` logger stays at
  WARNING — it would print URLs containing the token) nor in git (`.env` is
  gitignored; media files and CSVs too).
- Received media is processed inside a `TemporaryDirectory` and deleted right
  after; only aggregated numbers persist.

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (60-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk go test             # Go test failures only (90%)
rtk jest                # Jest failures only (99.5%)
rtk vitest              # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk pytest              # Python test failures only (90%)
rtk rake test           # Ruby test failures only (90%)
rtk rspec               # RSpec test failures only (60%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%). Format flags (-c, -l, -L, -o, -Z) run raw.
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->

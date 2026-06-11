# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- GitHub Pages landing page (`docs/`) with live demos (sample photo/video),
  terminal walkthroughs for local and VPS setup, Telegram configuration guide
  and project metrics — responsive on any screen size

- Telegram bot that counts people in photos (single frame) and videos (unique
  people via tracking) using MiVOLO, with age group / gender demographics
- Replies localized in Portuguese, English and Spanish, picked from each
  sender's Telegram client language (fallback: English)
- CSV history of aggregated counts per event (`counts.csv`)
- Security hardening: mandatory user allowlist (fail closed, silent to
  strangers), SHA256-pinned model weights, caption sanitization against CSV
  injection, history file created with mode `600`, token-free logs
- Test suite: 101 unit tests at 100% coverage (80% gate in CI) plus opt-in
  real-model integration tests (`RUN_INTEGRATION=1`)
- Google Colab notebook alternative (`count-people.ipynb`)
- Bot logo (`assets/logo.png`) and its generator script (`assets/make_logo.py`)
- CI workflow (tests + coverage gate + ruff), SemVer release automation from
  conventional commits, Dependabot and PR template

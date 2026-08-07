# AGENTS.md

Instructions for AI coding agents (Claude Code, Codex, Cursor, etc.)
working in this repository. For architecture details, see `CLAUDE.md` —
this file is about process, specifically the release checklist below.

## Release checklist — do this for every user-facing change

A "user-facing change" is anything a user would notice or configure: new
or changed config flow fields, blueprint inputs, package entities/sensors,
notification content, dashboard cards, or any behavior documented in
`README.md`. For every such change, do **all** of the following as part
of finishing the change — do not wait to be asked separately for the
docs update or the release tag:

1. **Update `README.md`** wherever the change is user-visible: the
   Configuration table/steps, FAQ, Troubleshooting, Supported
   integrations, notification examples, Roadmap — whichever sections the
   change actually touches. A code change without a matching README
   update is not done.
2. **Bump the version**, consistently, in all four places (they must
   agree with each other):
   - `CHANGELOG.md` — new dated entry. Semver: patch = fix, minor =
     backward-compatible feature, major = breaking change.
   - `custom_components/smart_ev_charging/manifest.json`'s `"version"`
     (this is the one HACS actually reads for the Integration category).
   - `custom_components/smart_ev_charging/packages/smart_ev_charging.yaml`'s
     `sensor.ev_smart_charging_version` hardcoded state.
   - `README.md`'s version badge.
3. Validate before committing (see `CLAUDE.md` > "Validating changes"):
   YAML/JSON parse, Python `py_compile`, cross-file entity-reference grep
   if anything was renamed/removed.
4. Commit and push.
5. **Tag and release**: `git tag -a vX.Y.Z -m "..."`,
   `git push origin vX.Y.Z`, then
   `gh release create vX.Y.Z --title vX.Y.Z --notes "..."` (notes drawn
   from the CHANGELOG entry). Do this proactively, not only when the user
   explicitly asks — HACS installs from tags/releases, not raw commits,
   so a change the user can't yet install via HACS is effectively
   invisible to them until it's tagged.

Purely internal changes (refactor, comment-only, no user-visible effect)
don't need steps 1-2, but treat that as a judgment call to state
explicitly, not a default excuse to skip documentation.

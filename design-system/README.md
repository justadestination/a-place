# Design-system artifact (source of truth in git)

`design-system/project/` is the exact file tree of the published **NightCal Design System** artifact:

**https://claude.ai/artifact/DbbYzUsEryX4jx1246JpZN** (private to its owner until shared from the page's Share menu)

The artifact page comes from claude.ai's "Design System" artifact type. Its own content is only the files under `project/`, and this folder holds all of them. **If the artifact is ever lost, this folder recreates it.** If the repo copy and the artifact disagree, check whether someone edited the artifact on the page (token edits are possible there). If so, pull that copy back here first (see "Pull edits made on the page").

## What's in it

| File | Made by | Edit? |
|---|---|---|
| `project/design-system.json` | Hand-maintained index (`title`, `namespace`, `lastChange`) | Update `lastChange` when you republish. Keep `createdOnFiles` as it is. |
| `project/README.md` | Hand-written brand book (principles, voice, colour, type, components, theming, embeds) | Yes |
| `project/components/Cover/preview.html` | Hand-made cover (palette band + kind glyphs); the derivation is in its comment | Yes, when the palette or name changes |
| `project/tokens.json` | **Generated** by `web/tools/build_artifact.py` from `tokens/` | No |
| `project/components/bundle.css` | **Generated**: a copy of `web/css/nightcal.css` | No |
| `project/components/<Comp>/README.md` | **Generated**: copies of `web/components/<name>/README.md` | No (edit the source) |
| `project/components/<Comp>/preview.html` | **Generated** by `web/tools/artifact_previews.mjs`: a static render of `/embed/<name>/` | No |

## Keep it in sync

From `web/`:

```sh
npm run build                 # also rebuilds tokens.json, bundle.css and the component READMEs here
npm run artifact:previews     # re-captures previews (needs the dev server and API running, like npm run og)
npm test                      # fails if the generated files here are stale (build_artifact.py --check)
```

`node tools/artifact_previews.mjs --check` reports previews that differ from the live components without writing anything.

## Republish

The artifact is updated by publishing `project/` back to the same URL. From a Claude Code session in this repo, ask Claude to "republish design-system/ to the design-system artifact". The call it makes:

* `url`: the artifact link above
* `root`: `design-system`
* `file_path`: the absolute path of `design-system/project/design-system.json`
* `files`: every other changed file, mapped `"project/<path>": "project/<path>"`

Before publishing, read the live `project/design-system.json` and update its `lastChange` (`by`, `at`, `via`, `note`). Send only changed files. The index goes in the last call.

## Pull edits made on the page

People can edit tokens and README text directly on the artifact page. Before republishing from git, read the live files back (Artifact `read` with each `project/...` path) and diff them against this folder. If `project/tokens.json` changed on the page, carry the change into `tokens/` (the real source); otherwise the next build overwrites it here.

## If the artifact is lost

1. Create a new artifact from the Design System type, titled "NightCal Design System".
2. Publish this whole `project/` tree to it (as in "Republish", sending every file).
3. Put the new URL at the top of this file and in `web/README.md`.

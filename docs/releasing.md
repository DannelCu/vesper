# Releasing Vesper to PyPI

This is the maintainer's step-by-step for publishing `vesper-desktop` and its 13
plugins. Everything here that touches a package index (TestPyPI or PyPI) is a
**manual step you run yourself** — Code prepares metadata, builds, and verifies
locally, but never uploads anything. See the closing note at the bottom for exactly
what was and wasn't done on your behalf.

Distribution names (all currently free on PyPI, checked 2026-07-27):

| # | Distribution | Build backend | Depends on |
|---|---|---|---|
| 1 | `vesper-desktop` | setuptools | pywebview, packaging |
| 2 | `vesper-crash` | setuptools | `vesper-desktop>=0.1.0`, sentry-sdk |
| 3 | `vesper-db` | setuptools | `vesper-desktop>=0.1.0`, sqlalchemy |
| 4 | `vesper-http` | setuptools | `vesper-desktop>=0.1.0`, httpx |
| 5 | `vesper-keychain` | setuptools | `vesper-desktop>=0.1.0`, keyring |
| 6 | `vesper-mongodb` | setuptools | `vesper-desktop>=0.1.0`, pymongo |
| 7 | `vesper-notify` | setuptools | `vesper-desktop>=0.1.0`, desktop-notifier |
| 8 | `vesper-screenshot` | setuptools | `vesper-desktop>=0.1.0`, mss |
| 9 | `vesper-serial` | setuptools | `vesper-desktop>=0.1.0`, pyserial |
| 10 | `vesper-shortcuts` | setuptools | `vesper-desktop>=0.1.0`, pynput |
| 11 | `vesper-store` | **hatchling** | `vesper-desktop>=0.1.0` |
| 12 | `vesper-sysinfo` | setuptools | `vesper-desktop>=0.1.0`, psutil |
| 13 | `vesper-theme` | setuptools | `vesper-desktop>=0.1.0`, darkdetect |
| 14 | `vesper-watch` | setuptools | `vesper-desktop>=0.1.0`, watchdog |

**No plugin depends on another plugin** — every one of the 13 depends only on
`vesper-desktop`. This was verified by grepping every plugin `pyproject.toml` for a
`vesper-*` dependency other than `vesper-desktop`: there are none. That means the
only hard ordering constraint is **core before plugins**; the 13 plugins can be
uploaded in any order relative to each other.

---

## Prerequisites

- **Accounts**: one on [TestPyPI](https://test.pypi.org/account/register/) and one
  on [PyPI](https://pypi.org/account/register/) — they are separate accounts with
  separate logins, not the same account on two hosts.
- **API tokens**: generate a token on each site (start scoped to your account,
  narrow to per-project scope once the projects exist after the first upload).
  Store them in `~/.pypirc` or export as `TWINE_USERNAME=__token__` /
  `TWINE_PASSWORD=<token>` for the upload commands below. Never commit a token.
- **Toolchain, up to date.** The metadata uses PEP 639 SPDX license expressions
  (`License-Expression: MIT` instead of a `License ::` classifier), which older
  tooling does not understand. Verified locally against:
  - `setuptools` 78.1.1
  - `build` 1.5.0
  - `twine` 7.0.0
  - Python 3.14.4

  Minimum versions for PEP 639 support: `setuptools>=69.5`, `twine>=6.0`. If
  `python -m build` or `twine check` on your machine reports an error mentioning
  `License-Expression`, `Metadata-Version: 2.4`, or license classifiers, upgrade
  `pip install -U build twine setuptools` before continuing — do not work around it
  by adding a `License ::` classifier back (setuptools rejects that combination
  outright once `license` is an SPDX string; confirmed by testing it here).

---

## Step 1 — Build everything

From the repo root:

```bash
rm -rf dist build *.egg-info plugins/*/dist plugins/*/build plugins/*/*.egg-info

python -m build --outdir dist .
for p in plugins/*/; do
  python -m build --outdir dist "$p"
done

ls dist | wc -l   # expect 28: 14 packages × (sdist + wheel)
```

## Step 2 — Verify before uploading anything

```bash
pytest -q                 # must be green
twine check dist/*        # must be all PASSED, no warnings
```

If `twine check` reports a warning about the README not rendering, fix the
`readme`-referenced file before proceeding — a broken README renders as plain text
on the PyPI project page and cannot be fixed without a new version.

---

## Step 3 — Rehearsal on TestPyPI

Do this even if you're confident — TestPyPI is free, disposable, and catches
upload-order and dependency-resolution mistakes before they're permanent.

**3a. Upload, core first:**

```bash
twine upload -r testpypi dist/vesper_desktop-0.1.0*
```

**3b. Then the 13 plugins, any order:**

```bash
twine upload -r testpypi dist/vesper_{crash,db,http,keychain,mongodb,notify,screenshot,serial,shortcuts,store,sysinfo,theme,watch}-0.1.0*
```

If a plugin upload happens before the core is visible on TestPyPI's index, its own
upload still succeeds (uploading doesn't check dependencies) — but installing it
until the core appears will fail to resolve `vesper-desktop`. Uploading core first
avoids that race entirely.

**3c. Install from TestPyPI in a clean venv.** TestPyPI does not mirror PyPI, so
plain dependencies (`pywebview`, `sqlalchemy`, ...) must come from real PyPI while
`vesper-desktop`/`vesper-*` come from TestPyPI — that's what `--extra-index-url`
does:

```bash
python -m venv /tmp/testpypi-check
source /tmp/testpypi-check/bin/activate

pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            vesper-desktop
python -c "import vesper; print(vesper.__version__)"   # expect 0.1.0
vesper doctor                                            # expect "[OK] Vesper installed: 0.1.0"

pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            "vesper-desktop[db,http]"
python -c "import vesper_db, vesper_http"                # expect no ImportError

pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            vesper-store
python -c "
from vesper import App
from vesper_store import StorePlugin
app = App(plugins=[StorePlugin(app_name='testpypi-check')])
app.registry.get('store:get')   # raises CommandNotFoundError if not registered
print('plugin registered OK')
app.close()
"

deactivate
rm -rf /tmp/testpypi-check
```

Local wheel installs and a `pip install --dry-run` against local wheels were
already run during preparation (build + `twine check` + install test), so the
mechanics are known-good. What this TestPyPI step validates that a local check
cannot: that the **extras actually resolve against a real index** — a
`Requires-Dist: vesper-db>=0.1.0; extra == "db"` line only turns into an installed
package once both `vesper-desktop` and `vesper-db` exist on the same index the
resolver is searching. That's the one thing local `--find-links` testing cannot
prove, and it's the reason this rehearsal step exists at all.

If anything here fails, fix it, bump nothing (TestPyPI lets you delete a release, so
a broken rehearsal is not a versioning problem), rebuild, and re-upload to TestPyPI
until steps 3a–3c pass clean.

---

## Step 4 — Publish to PyPI (real, permanent)

**A version uploaded to PyPI cannot be deleted, replaced, or overwritten.** PyPI
allows "yanking" a release (marks it as not-recommended without removing it, so
existing pins that need it still resolve), but the files themselves and the version
number are permanent. If 0.1.0 has a problem discovered after publishing, the fix is
a new version — 0.1.1 — never a re-upload of 0.1.0. Rebuilding and re-uploading the
exact same version number is also rejected by PyPI outright.

**Name reservation**: until you run the uploads below, the names `vesper-desktop`
and each `vesper-<plugin>` are unclaimed and could in principle be taken by someone
else. Uploading the 0.1.0 release is what actually reserves each name — this is
the step that matters for that, not the packaging preparation.

Same order as the rehearsal, core first:

```bash
twine upload dist/vesper_desktop-0.1.0*
```

Wait for the [PyPI project page](https://pypi.org/project/vesper-desktop/) to show
0.1.0, then:

```bash
twine upload dist/vesper_{crash,db,http,keychain,mongodb,notify,screenshot,serial,shortcuts,store,sysinfo,theme,watch}-0.1.0*
```

---

## Step 5 — Post-publish

1. **Tag the release in git** (this is the point where the version becomes
   real, so this is on you, not Code):

   ```bash
   git tag -a v0.1.0 -m "vesper-desktop 0.1.0 — first PyPI release"
   git push origin v0.1.0
   ```

2. **Verify the PyPI project pages** for the core and at least a couple of
   plugins — check that the README renders (headings, code blocks, the
   comparison tables), that the classifiers/keywords show up in the sidebar, and
   that `Project-URL` links (Homepage, Repository, Documentation, Issues) work.

3. **Install from real PyPI** as the final sanity check, no `--extra-index-url`
   needed this time since everything is on the same index:

   ```bash
   python -m venv /tmp/pypi-check
   source /tmp/pypi-check/bin/activate
   pip install vesper-desktop
   python -c "import vesper; print(vesper.__version__)"
   vesper doctor
   pip install "vesper-desktop[all]"
   deactivate
   rm -rf /tmp/pypi-check
   ```

---

## Pre-flight checklist

Run through this immediately before Step 3. If anything is unchecked, stop and fix
it first — nothing after this point is reversible.

- [ ] `pytest -q` passes (1620 passed, 15 skipped as of this writing — an
      unexplained drop in that count is a reason to stop, not proceed)
- [ ] `version = "0.1.0"` in all 14 `pyproject.toml` files (core + 13 plugins)
- [ ] `twine check dist/*` reports PASSED for all 28 artifacts, zero warnings
- [ ] Distribution names confirmed unclaimed on PyPI — re-check the date, names can
      be taken between when this was last verified (2026-07-27) and when you
      actually publish
- [ ] `build`, `twine`, `setuptools` versions meet the PEP 639 minimums above
- [ ] `LICENSE` file content matches the declared `license = "MIT"` SPDX expression
      in every `pyproject.toml` (it does — MIT, copyright Dannel D. Ramos)
- [ ] `CHANGELOG.md` — `[0.1.0]` entry covers all 13 plugins and everything
      shipping in this release (done — see note below)
- [ ] TestPyPI rehearsal (Step 3) completed clean, this release cycle — a rehearsal
      from a previous attempt does not carry over if anything changed since

### CHANGELOG note

The `[0.1.0]` entry originally documented only 7 plugins; the other 6
(`vesper-watch`, `vesper-notify`, `vesper-crash`, `vesper-screenshot`,
`vesper-serial`, `vesper-sysinfo`) plus the packaging/metadata work, several bug
fixes, and three new example apps had accumulated under `[Unreleased]` since.
Since all 14 packages ship together as this first release, that content has been
folded into `[0.1.0]` (dated to when the merge happened) with the plugin/known-issue
counts corrected in a couple of stale bullets. `[Unreleased]` now holds only the
genuinely still-pending `### Planned` items. Update the `[0.1.0]` date to match the
day you actually publish if it differs from what's there.

---

## What Code did and did not do

Code built all 28 artifacts locally, ran `twine check` on all of them, installed
the core and a plugin from local wheels into a clean venv (`import vesper`,
`vesper doctor`, plugin command registration), and dry-ran extra resolution against
the local wheels. All `dist/`/`build/`/`*.egg-info` directories were deleted
afterward — nothing was left behind, and **nothing was uploaded to TestPyPI or
PyPI**. The `twine upload` commands in this document, the TestPyPI rehearsal, the
real PyPI publish, and the `git tag` in Step 5 are all steps you run yourself.

# CHANGELOG


## v0.1.0 (2026-02-10)

### Bug Fixes

- Add cluster config setup for CI tests
  ([`532159f`](https://github.com/ambient-code/mcp/commit/532159fb45d5e6a71300adcdc7f81364d0f3d86f))

Copy clusters.yaml.example to ~/.config/acp/clusters.yaml before tests to prevent FileNotFoundError
  in ACPClient initialization. This fixes 16 failing tests in test_security.py and related test
  failures.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Add environment to release workflow for trusted publishing
  ([`028ad6e`](https://github.com/ambient-code/mcp/commit/028ad6ea0c698d64fbc97476da65abfe69123ada))

Add 'environment: pypi' to the release workflow job to support PyPI trusted publishing. Some PyPI
  projects require an environment to be specified in the workflow for trusted publishing to work.

This should resolve the "Publisher with matching claims was not found" error.

Next steps: 1. Create a 'pypi' environment in GitHub repository settings 2. Configure trusted
  publisher on PyPI with environment name 'pypi'

Alternative: Use API token instead of trusted publishing by adding

PYPI_API_TOKEN secret and modifying the publish step.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Configure release workflow for Test PyPI
  ([`3b33274`](https://github.com/ambient-code/mcp/commit/3b3327497eafeb7fd607bf5dba9f3c4f49fcc08d))

Update release workflow to publish to Test PyPI first before production PyPI. This allows testing
  the release process safely.

Changes: - Changed environment from 'pypi' to 'test-pypi' - Added repository-url for Test PyPI:
  https://test.pypi.org/legacy/ - Updated comments to reflect Test PyPI usage

Next steps: 1. Create 'test-pypi' environment in GitHub settings (or reuse existing 'pypi'
  environment) 2. Configure trusted publisher on Test PyPI at
  https://test.pypi.org/manage/account/publishing/ 3. Test the release workflow 4. Once validated,
  switch back to production PyPI

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Correct test imports for formatter functions ([#15](https://github.com/ambient-code/mcp/pull/15),
  [`3b90d0a`](https://github.com/ambient-code/mcp/commit/3b90d0ad65b5b1c958cf05eac359df36fe7571a1))

Fix ImportError in test_server.py by updating imports to use the correct module and function names.
  Formatting functions were moved from server.py to formatters.py and don't have underscore
  prefixes.

Changes: - Import formatting functions from mcp_acp.formatters instead of mcp_acp.server - Remove
  underscore prefixes from function names (_format_* -> format_*) - Update all test method calls to
  use public function names

This resolves the CI import error: ImportError: cannot import name '_format_bulk_result' from
  'mcp_acp.server'

Co-authored-by: Claude Sonnet 4.5 <noreply@anthropic.com>

- Don't pass project arg to cluster-level tools ([#16](https://github.com/ambient-code/mcp/pull/16),
  [`8ff7616`](https://github.com/ambient-code/mcp/commit/8ff7616c94f150e60cd6531ee9c7e1c958bea2ad))

Tools like acp_list_clusters, acp_whoami, acp_login, acp_switch_cluster, acp_add_cluster, and
  acp_list_workflows don't accept a project parameter.

The call_tool() function was auto-filling project for ALL tools, causing these handlers to fail with
  'unexpected keyword argument project'.

Added TOOLS_WITHOUT_PROJECT set to exclude these tools from project auto-fill logic.

- Embed videos inline with HTML5 video tags ([#9](https://github.com/ambient-code/mcp/pull/9),
  [`b9cbb4a`](https://github.com/ambient-code/mcp/commit/b9cbb4a629f9d61f20aa2feb07efc3d304a01983))

Replace image links to .mp4 files with HTML5 <video> tags to enable inline playback on GitHub.
  Videos now play directly in the browser instead of redirecting to raw file download.

- Add poster images (thumbnails) to all 8 demos - Remove redundant "Watch Demo" links (video
  controls handle this) - Improves user experience and demo accessibility

Co-authored-by: Claude Sonnet 4.5 <noreply@anthropic.com>

- Remove pip cache from CI workflow (using uv not pip)
  ([`b518d4b`](https://github.com/ambient-code/mcp/commit/b518d4b3032b148742bf553f4a982715d1ca7f64))

The setup-python action was configured with cache: 'pip' but we use uv for package management. This
  caused CI failures with: "Cache folder path is retrieved for pip but doesn't exist on disk"

Caching is already handled by setup-uv action with enable-cache: true.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Remove pip cache from release workflow
  ([`2908dbe`](https://github.com/ambient-code/mcp/commit/2908dbeaf54e1e11a4aa41d0264c429411838a04))

Remove `cache: 'pip'` from Python setup since we're using uv, not pip. This eliminates the harmless
  but noisy cache warning: "Cache folder path is retrieved for pip but doesn't exist on disk"

We use uv for all package management, which has its own caching via the setup-uv action with
  enable-cache: true.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Reuse existing pypi environment for Test PyPI publishing
  ([`cc8d9cf`](https://github.com/ambient-code/mcp/commit/cc8d9cf3da3b8c1b01d05d6a9259a8b97d716ab2))

Change from 'test-pypi' to 'pypi' environment to reuse the existing environment configured for the
  ambient-code organization.

The environment name doesn't determine the publishing destination - that's controlled by the
  repository-url parameter. Using the existing 'pypi' environment simplifies setup and reuses
  infrastructure already in place.

Publishing destination: - repository-url: https://test.pypi.org/legacy/ → Test PyPI (current) - (no
  repository-url) → Production PyPI (future)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Show thumbnail images above video players ([#10](https://github.com/ambient-code/mcp/pull/10),
  [`aa4c4f5`](https://github.com/ambient-code/mcp/commit/aa4c4f521db1619e6da47501863e1f7cdb793b8e))

GitHub doesn't render the poster attribute on HTML5 video tags, so thumbnails weren't showing.
  Display image separately above each video player for visual preview before playing.

- Add <img> tag above each <video> tag - Remove poster attribute (not supported by GitHub) -
  Thumbnails now visible in demo gallery

Co-authored-by: Claude Sonnet 4.5 <noreply@anthropic.com>

- Update tests to match implementation and remove obsolete tests
  ([`d8c909a`](https://github.com/ambient-code/mcp/commit/d8c909a0c78d730d7c9527d7afa7b86f64657f62))

- Removed 3 obsolete config validation tests (tested non-existent _validate_config method) - Fixed
  test_delete_session_dry_run to expect correct response format - Fixed test_bulk_stop_sessions with
  proper mocking of _get_resource_json - Fixed server bulk operation wrappers to use proper async
  functions instead of lambdas - Updated test assertions to match actual formatter output - All 45
  tests now pass

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Use correct AgenticSession API version ([#21](https://github.com/ambient-code/mcp/pull/21),
  [`bafc2da`](https://github.com/ambient-code/mcp/commit/bafc2da2071ea55ad6e0203d3d7f101461552380))

Replace incorrect hardcoded apiVersion "agenticplatform.io/v1" with "vteam.ambient-code/v1alpha1" in
  clone_session and create_session_from_template manifests.

Fixes #19

Co-authored-by: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Use standard python build in semantic-release ([#18](https://github.com/ambient-code/mcp/pull/18),
  [`a0d09da`](https://github.com/ambient-code/mcp/commit/a0d09da5fceddc95cda4b01693dd82a33d017084))

The semantic-release action runs in its own container where uvx is not available. Use pip install
  build && python -m build instead.

- Use testpypi environment for Test PyPI publishing
  ([`6860e42`](https://github.com/ambient-code/mcp/commit/6860e420708e678a27d216d42320f658ce60f1df))

Update workflow to use the newly created 'testpypi' GitHub environment.

This provides clear separation between test and production publishing environments and follows best
  practices for environment management.

Next step: Configure Test PyPI trusted publisher at https://test.pypi.org/manage/account/publishing/
  with: - Owner: ambient-code - Repository: mcp - Workflow: release.yml - Environment: testpypi

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

### Documentation

- Fix version paths, convert examples to natural language, fix dead links
  ([#12](https://github.com/ambient-code/mcp/pull/12),
  [`ddb2fc3`](https://github.com/ambient-code/mcp/commit/ddb2fc30f3ea775e3b181c191924dcff1af8a661))

## Changes

### 1. Fixed Version Numbers (4 locations) - README.md lines 16, 124: Use dist/mcp_acp-*.whl pattern
  - QUICKSTART.md lines 47, 476: Use wildcard pattern instead of hardcoded version

### 2. Added OCP Login Note (2 locations) - README.md after line 186: Note about PR #558 frontend
  API - QUICKSTART.md after line 88: Same note

### 3. Converted Usage Examples to Natural Language (14 locations) - README.md lines 196-270: 12
  Python function calls → natural language - demos/README.md line 101: Function call → workflow
  description

Example conversion: - Before: acp_list_sessions(project="my-workspace", status="running") - After:
  List running sessions in my-workspace

### 4. Fixed Dead Links (10 locations in README.md) Replaced links to consolidated documentation
  files: - USAGE_GUIDE.md → QUICKSTART.md (5 occurrences) - ARCHITECTURE.md → CLAUDE.md (2
  occurrences) - DEVELOPMENT.md → CLAUDE.md (3 occurrences) - Removed CLEANROOM_SPEC.md reference

### 5. Updated First Command Example - Changed from "Use acp_whoami to check my authentication" -
  To: "List my ambient sessions that are older than a week"

Co-authored-by: Claude Sonnet 4.5 <noreply@anthropic.com>

### Features

- Add automatic semantic versioning with python-semantic-release
  ([#17](https://github.com/ambient-code/mcp/pull/17),
  [`bf11137`](https://github.com/ambient-code/mcp/commit/bf11137e0472491170da37c6bd104644534cd801))

- Configure python-semantic-release in pyproject.toml - Update release workflow to auto-bump version
  on push to main - Version bumps based on conventional commits: - fix: → patch (0.1.0 → 0.1.1) -
  feat: → minor (0.1.0 → 0.2.0) - BREAKING CHANGE: → major (0.1.0 → 1.0.0) - Auto-creates GitHub
  releases and publishes to PyPI

- Add demo source files for regeneration ([#11](https://github.com/ambient-code/mcp/pull/11),
  [`1c3a129`](https://github.com/ambient-code/mcp/commit/1c3a129de9a2754d926f9e22512fe873c8d92ff9))

Add editable source files for demos: - 8 asciinema .cast recordings - 8 shell scripts for demo
  execution - 8 animated .gif files - Advanced demo documentation - Asciinema configuration

These enable regenerating demos when tools change.

Co-authored-by: Claude Sonnet 4.5 <noreply@anthropic.com>

- Add GitHub Actions caching optimizations ([#14](https://github.com/ambient-code/mcp/pull/14),
  [`6c3334f`](https://github.com/ambient-code/mcp/commit/6c3334fbf4d8c7123f56deaa16bede5827970abb))

* feat: Add GitHub Actions caching optimizations

Implement three performance optimizations for CI/CD workflows:

1. Cache pruning: Add 'uv cache prune --ci' step after dependency installation to reduce cache size
  by 40-60% while maintaining performance. Removes pre-built wheels and unzipped source
  distributions, keeping only wheels built from source.

2. Python setup caching: Enable built-in pip caching via actions/setup-python@v5 to reduce Python
  package setup time.

3. Virtual environment caching: Cache .venv directory in CI workflow using actions/cache@v4 with
  pyproject.toml-based cache key. Provides 30-50% faster subsequent runs when dependencies
  unchanged.

Expected performance impact: - First run: +5s (cache population) - Subsequent runs: 30-50% faster
  (~35-40s vs ~60s) - Cache size: 40-60% reduction (~200-300MB vs ~500MB)

Changes: - .github/workflows/ci.yml: All three optimizations - .github/workflows/release.yml:
  Optimizations 1 & 2 (no venv caching since uvx uses isolated temporary environments)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

* fix: Correct test imports for formatter functions

Fix ImportError in test_server.py by updating imports to use the correct module and function names.
  Formatting functions were moved from server.py to formatters.py and don't have underscore
  prefixes.

Changes: - Import formatting functions from mcp_acp.formatters instead of mcp_acp.server - Remove
  underscore prefixes from function names (_format_* -> format_*) - Update all test method calls to
  use public function names

This resolves the CI import error: ImportError: cannot import name '_format_bulk_result' from
  'mcp_acp.server'

* Revert "fix: Correct test imports for formatter functions"

This reverts commit c201b99ccfd1fe555f4f32375ff0b21a91cb578a.

* chore: Remove cleanup scripts (moved to ambient-code/ops)

Cleanup-related files moved to dedicated ops repository: - cleanup-namespaces.sh → ops/scripts/ -
  README-CLEANUP.md → ops/scripts/README.md - CLEANUP-QUICKSTART.md (merged into ops README)

Updated .gitignore to remove cleanup file exclusions.

Changes: - Import formatting functions from mcp_acp.formatters instead of mcp_acp.server - Remove
  underscore prefixes from function names (_format_* -> format_*) - Update all test method calls to
  use public function names - Fix test method names that were accidentally corrupted by find/replace

Note: Some formatter tests still fail due to outdated expectations, but

that's a separate issue from the import error that was blocking CI.

---------

Co-authored-by: Claude Sonnet 4.5 <noreply@anthropic.com>

- Add label management and bulk operation safety
  ([`f882a57`](https://github.com/ambient-code/mcp/commit/f882a57ab8d8677380fad91ad5513460ceca92b1))

Added comprehensive label management and safety features:

Label Operations: - label_resource(): Generic labeling for any resource type - unlabel_resource():
  Remove labels from resources - bulk_label_resources(): Label multiple resources (max 3) -
  bulk_unlabel_resources(): Unlabel multiple resources (max 3) - list_sessions_by_user_labels():
  Convenience wrapper for label filtering

Bulk Safety Features: - MAX_BULK_ITEMS = 3 constant enforced across all bulk operations -
  Server-layer confirmation requirement for destructive bulk ops - Early count validation with
  helpful error messages - Enhanced dry-run output showing matched sessions

Label-Based Bulk Operations: - bulk_delete_sessions_by_label() - bulk_stop_sessions_by_label() -
  bulk_restart_sessions_by_label() - All include early validation and enhanced dry-run

MCP Server Updates: - 9 new tools for label management and bulk operations - Updated 3 existing
  tools (list_sessions, bulk_delete, bulk_stop) - Server-layer confirmation enforcement via
  _check_confirmation_then_execute()

Label Format: - Auto-prefix: acp.ambient-code.ai/label-{key}={value} - Simple validation (Kubernetes
  does heavy lifting) - Max 63 characters for keys/values

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Add manual trigger support to GitHub Actions workflows
  ([`6e346c4`](https://github.com/ambient-code/mcp/commit/6e346c4eeaedb0c2dfca03b3c72b1edf89426e9a))

Enable workflow_dispatch for both CI and release workflows, allowing manual execution from the
  GitHub Actions UI.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

- Switch from Test PyPI to production PyPI
  ([`f475c47`](https://github.com/ambient-code/mcp/commit/f475c4780bc219292e44d2b0b7a57b3b6faf9db5))

Update release workflow to publish to production PyPI instead of Test PyPI.

Changes: - Environment: testpypi → pypi (reuse existing pypi environment) - Remove repository-url
  (defaults to production PyPI) - Update comments to reflect production publishing

Next step: Configure trusted publisher on production PyPI at
  https://pypi.org/manage/account/publishing/ with: - Owner: ambient-code - Repository: mcp -
  Workflow: release.yml - Environment: pypi

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

### Testing

- Add unit tests for label management features
  ([`0e34703`](https://github.com/ambient-code/mcp/commit/0e34703c29302e18e78739aee1dea9c3f826a792))

Added comprehensive tests for: - Bulk operation safety (3-item limit validation) - Label resource
  operations (success + validation) - Unlabel resource operations - Bulk label/unlabel resources -
  List sessions by user labels - Bulk delete by label with limit enforcement

Fixed label selector regex to allow dots and slashes for full Kubernetes label format.

All tests pass.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>

# Architecture Guardrails

Last reviewed: 2026-07-29

## Purpose

This document defines the target dependency direction and non-increasing
structural budgets for Alavette Form. The goal is not to make every file small.
The goal is to keep ownership explicit, make change impact predictable, and stop
known hotspots from silently accumulating new responsibilities.

The executable baseline lives in `tests/test_code_health_budget.py`. When an
intentional refactor lowers a baseline, lower the matching budget in the same
change. Raising a budget requires an architecture note explaining why the
responsibility cannot be separated.

## Dependency Direction

The intended runtime direction is:

```text
composition root
    -> UI / Qt
    -> application use cases
    -> domain contracts
    -> pipeline contracts / document modules
    -> infrastructure adapters
```

Additional rules:

- UI may depend on application services, domain/config read models, and shared
  UI primitives.
- Application code must not depend on concrete widgets.
- Document modules depend on stable pipeline/domain contracts, not on the
  pipeline runner.
- Infrastructure implements ports owned by application/domain layers.
- Governance and audit projections consume domain read models; they do not own
  runtime configuration or UI state.
- `shared` code cannot depend on application-specific UI or services.
- Runtime module cycles are forbidden.

The current tree still contains package-level reciprocal dependencies between
`config` and `shared`, `pipeline` and `modules`, `ui` and `assistant`, and
`shared` and `services`. These are migration baselines, not desired
architecture. Their edge counts may only stay level or decrease.

## Structural Budgets

Budgets are differentiated by responsibility:

| Responsibility | Target | Warning | Freeze new responsibility |
| --- | ---: | ---: | ---: |
| UI page or presenter class | <= 600 lines, <= 40 methods | 800 lines | 1200 lines |
| Coordinator or application service | <= 500 lines, <= 25 methods | 800 lines | 1000 lines |
| Ordinary method | <= 50 lines, complexity <= 10 | 75 / 15 | 150 / 30 |
| Data-only governance projection | <= 1000 lines | 1500 lines | growth requires data-only evidence |
| Test module | <= 1000 lines | 1500 lines | 2500 lines |

Crossing a freeze line does not require a rewrite by itself. It means new
behavior must be placed behind a new owner and reached through an explicit
contract.

## UI Ownership

- Qt widgets live under application UI packages.
- Reusable controls own visual mechanics; pages own layout and page-specific
  orchestration.
- `TemplatePanel` is the composition root for the template surface. It owns
  widget construction, signal wiring, participation projection, and narrow
  delegation hooks. It must not reacquire extracted library,
  navigation-context, overview-projection, detail-lifecycle,
  session-persistence, or close transaction behavior.
- `TemplateDetailLifecycleMixin` owns lazy detail creation, first-load
  transitions, startup preloading, and loading/refresh feedback. The lifecycle
  owner may call the panel's detail-attachment, signal-wiring, state-sync, and
  dirty-state hooks; it must not read or write template files or draft-store
  transactions.
- `TemplateLibraryManagementMixin` owns template source/path status, filesystem
  watching, library refresh, import/work-mode synchronization, selector state,
  and new/duplicate/rename/open/delete/select actions. Text input and destructive
  confirmation enter through late-bound panel seams. This owner must not acquire
  draft persistence, close snapshots, detail lifecycle, or navigation context.
- `TemplateNavigationContextMixin` owns inbound navigation intent, detail-field
  focus, return-target state, and entry-context projection. It may read the
  current scene/template labels but must not persist drafts, mutate the template
  library, coordinate close state, or own participation controls.
- `TemplateOverviewProjectionMixin` owns normal and fail-safe overview
  projection construction plus applying the result to overview/navigation
  widgets. Runtime config and baseline resolution enter through late-bound panel
  seams. It must not persist drafts, watch or mutate the library, process
  navigation intents, or coordinate close state.
- `TemplateCloseTransaction` is the sole owner of prepared-close state, close
  snapshots, file backups, and two-phase close rollback.
  `TemplateClosePrompt` owns only the pending-draft dialog presentation, while
  `TemplatePanel` keeps the public close-protocol delegates and UI
  synchronization hooks, and
  `TemplateDraftSaveCoordinator` keeps target validation, collision checks, and
  batch persistence. The close transaction must not acquire ordinary template
  library management or editor navigation responsibilities.
- `TemplateSessionPersistenceMixin` owns draft dirty-state synchronization,
  session activation and rebinding, ordinary save preparation/commit,
  publication, copy creation, and shared-template impact confirmation. Runtime
  confirmation, library-path classification, and dependency resolution enter
  through late-bound panel seams so tests and integrations do not depend on
  implementation-module globals. The persistence owner must not acquire close
  snapshots, file watching, navigation, rename, or delete actions.
- A page-specific QSS block is acceptable. Styling used by two or more surfaces
  belongs in a shared component or theme helper.
- Literal colors are limited to theme definitions, color-picking controls,
  brand assets, and faithful document-preview rendering.
- Functional icons are registered once in
  `src/shared/ui/icons/catalog.py`. Application code uses semantic catalog IDs,
  not SVG paths or Unicode glyph substitutes.
- `QIcon()` is allowed only to intentionally clear an icon or inside the
  canonical renderer.

## Exceptions and Degradation

Document automation needs best-effort boundaries around optional Office, XML,
font, and renderer capabilities. Broad exception handling is acceptable only
when all of the following are true:

1. the boundary is genuinely optional or external;
2. the fallback state is explicit;
3. required output cannot be reported as successful;
4. the exception is logged, returned as evidence, or documented as an
   intentionally silent cleanup path.

New `except Exception: pass` or bare `except: pass` blocks are forbidden. The
existing count is a non-increasing migration baseline.

## Test Policy

- Behavior tests should assert public state, signals, artifacts, or contracts.
- Source/AST tests are reserved for negative architecture constraints such as
  forbidden imports, duplicate ownership, dynamic registration, or missing
  catalog entries.
- Source tests must follow the real owner after a responsibility is extracted;
  they must not force behavior back into a monolithic class.
- The fast engineering gate should remain suitable for local/PR feedback.
  Full tests remain a release gate and should be sharded when CI wall time
  becomes a bottleneck.

## Refactor Order

1. Freeze and extract `QuickExecutionDetail` responsibilities.
2. Preserve the completed `TemplatePanel` ownership split: detail lifecycle,
   library management, navigation context, overview projection, session
   persistence, close prompt, and close transactions have bounded owners
   enforced by structural budgets.
3. Split `ScenePanel` detail surfaces and scene transaction coordination.
4. Move pipeline protocols out of concrete runner/module ownership.
5. Move scene governance/audit projections out of runtime configuration.
6. Eliminate package-level reciprocal dependency baselines.

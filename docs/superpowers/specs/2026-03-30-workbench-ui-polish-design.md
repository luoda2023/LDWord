# Workbench UI Polish Design

## Goal

Turn the current Workbench from a structurally correct but visually rough command-center prototype into a coherent, readable, high-frequency control surface.

This design pass does **not** change the core Workbench information architecture that has already been approved and partially implemented:

- top current-task bar,
- middle left/right split,
- bottom recent-run area,
- left-column strategy + quick-card area,
- right-column execution center.

Instead, this pass focuses on visual hierarchy, semantic theming, card differentiation, spacing rhythm, and interaction emphasis so the page no longer feels like stacked feature blocks.

## Problem statement

The current Workbench is no longer a placeholder page, but it still looks like an intermediate engineering layout rather than a finished command center.

Observed issues:

1. too many surfaces look visually equivalent;
2. the execution center is positioned correctly, but not yet visually dominant;
3. strategy and quick cards do not yet feel like different classes of UI;
4. spacing and density are not yet disciplined enough to create a stable rhythm;
5. theme tokens exist, but the Workbench still lacks a clear page-level visual language.

So the next problem is no longer "where do things go?" but:

> how do we make the existing structure feel like one designed product surface?

## Product intent for this pass

This page should feel like a **professional task command center**, not:

- a settings form,
- a dashboard of equal-weight cards,
- a wizard,
- or a collection of embedded mini-panels.

The intended user impression is:

- "I can tell what task I'm working on"
- "I can see whether I'm ready to execute"
- "I can make small adjustments quickly"
- "I know where the main action is"
- "I can review what just happened without losing focus"

## In scope

1. Workbench-specific visual hierarchy
2. Card role differentiation
3. Command-center-specific naming and copy consistency
4. Workbench-specific semantic styling rules layered on top of the shared theme
5. Spacing, density, emphasis, and layout rhythm for the Workbench page
6. Making the execution center the primary visual action anchor
7. Making the current-task bar the primary information anchor

## Out of scope

1. Adding new homepage capability cards beyond the ones already approved
2. Replacing the approved Workbench information architecture
3. Moving full advanced editors back onto the homepage
4. Reworking unrelated pages outside Workbench
5. Rebuilding the global theme system outside the Workbench surface

## Core design decision

The Workbench must use **role-based visual hierarchy** instead of giving every surface the same visual weight.

### The four visual roles

#### 1. Current-task control strip
Represents the active task context.

Used by:
- top current-task bar

This is the page's primary information anchor.

#### 2. Execution control surface
Represents the page's primary action area.

Used by:
- right-side execution center

This is the page's primary action anchor.

#### 3. Task baseline / adjustment surfaces
Represents stable configuration and quick adjustments.

Used by:
- execution strategy card
- quick capability cards

These are important, but visually subordinate to the execution center.

#### 4. Result review surface
Represents secondary, after-the-fact information.

Used by:
- bottom recent-run panel

This must not compete with the execution center.

## Visual hierarchy rules

## 1. Current-task bar

### Role
First information anchor.

### Must communicate
- current document
- current strategy
- current status
- primary action entry

### Visual requirements
- compact height
- high readability
- clear left-to-right information flow
- stronger title/identity than ordinary cards
- no large explanatory text blocks
- no long-path noise in the main reading path

### Must not look like
- a generic toolbar
- a form row
- a plain white card with random text

## 2. Execution center

### Role
Primary action anchor.

### Must communicate
- whether execution is currently possible
- what this run will do
- where the primary action is
- what state the current/last run is in

### Visual requirements
- strongest card on the page
- clearest border/contrast/emphasis
- strongest button styling on the page
- explicit internal sections: readiness, summary, action/progress
- clearly stronger than all left-column cards

### Must not look like
- another summary card
- a plain info panel
- a passive log box

## 3. Strategy card

### Role
Baseline strategy summary.

### Must communicate
- current strategy identity
- current template
- current scene
- source type
- strict-mode state
- enabled-module count

### Visual requirements
- calmer than execution center
- more stable and "foundational" than quick cards
- concise summary, not a settings form
- easy to scan in 1-2 seconds

### Must not look like
- a deep config editor
- a second execution center
- a generic unlabeled info dump

## 4. Quick cards

### Role
High-frequency quick adjustments.

Used by current approved cards:
- heading numbering quick card
- quick fill card

### Visual requirements
- lighter than the strategy card
- clearly action-oriented
- consistent size rhythm across the grid
- concise title + short summary + 1-2 actions
- never expand into full editor behavior on the homepage

### Must not look like
- mini settings pages
- equal-weight clones of the strategy card
- dominant page anchors

## 5. Recent-run panel

### Role
Review, not primary action.

### Visual requirements
- visually calmer than the execution center
- compact default height
- long text must wrap safely
- can summarize recent outputs/reports/errors without becoming a second console

### Must not look like
- another execution center
- a giant growing content block
- the page's visual focal point

## Workbench-specific semantic styling layer

This pass should introduce or formalize a Workbench-specific styling vocabulary on top of shared theme tokens.

These may be implemented as explicit helper rules or Workbench-local token mappings rather than global theme-schema changes, but they must conceptually exist:

- `wb_surface_primary` - strongest surface, for execution center
- `wb_surface_secondary` - normal surface, for strategy card / task strip
- `wb_surface_muted` - quiet surface, for recent-run review
- `wb_border_primary` - stronger border for primary action surface
- `wb_border_secondary` - normal border for secondary surfaces
- `wb_status_ready_bg` / `wb_status_ready_text`
- `wb_status_blocked_bg` / `wb_status_blocked_text`
- `wb_action_primary_bg` / hover / pressed
- `wb_action_secondary_bg`

These do not all need to become global theme fields immediately, but the Workbench stylesheet must behave as if these semantic distinctions exist.

## Naming and copy rules

The Workbench should keep the approved command-center naming direction.

### Preferred labels
- `任务中控`
- `执行策略`
- `执行中心`
- `最近结果`
- `开始执行`
- `待执行`
- `执行中`
- `已完成`
- `部分完成`
- `执行失败`

### Copy rules
- Use Chinese operational language consistently
- Avoid mixing English status words like `IDLE` or `Ready` into the live UI unless the product direction explicitly changes later
- Keep labels short and control-oriented
- Reduce verbose explanatory copy in the page body

## Layout rhythm rules

### Global page rhythm
- current-task bar: compact
- middle region: main vertical mass of the page
- recent-run panel: compact and quiet

### Left column rhythm
- strategy card first
- capability grid second
- consistent gap between these blocks
- quick cards in a predictable two-column grid

### Right column rhythm
- tighter and more vertical
- built around operational sections
- should feel stable even if the left column changes more frequently

### Prohibited layout regressions
- no return to flat vertical stacking of all sections
- no full advanced editor mounted inline in the homepage body
- no new "special" homepage panel that bypasses the left/right/bottom structure

## Visual acceptance criteria

The Workbench UI polish pass is successful only if all of the following are true:

1. A user can identify the page's primary information anchor in under 3 seconds.
2. A user can identify the page's primary action anchor in under 3 seconds.
3. The execution center is visually stronger than the strategy card.
4. The strategy card is visually stronger than the quick cards.
5. The recent-run panel is visually quieter than both the execution center and strategy card.
6. Quick cards feel like quick actions, not mini configuration pages.
7. The page no longer feels like stacked feature blocks.
8. The Workbench has a distinct visual language instead of relying only on generic shared cards.

## Recommended implementation order for the UI polish pass

1. **Execution center visual strengthening**
   - make the action surface visually dominant
2. **Current-task bar refinement**
   - compress and clarify the top strip
3. **Strategy card polish**
   - stabilize the baseline summary surface
4. **Quick-card unification**
   - consistent density and action affordances
5. **Recent-run quieting**
   - make the bottom panel useful but non-dominant
6. **Whole-page spacing/rhythm pass**
   - align padding, gaps, and section balance

## File-level direction

This pass should primarily operate in:

- `src/ui/panels/workbench/styles.py`
- `src/ui/panels/workbench/command_bar.py`
- `src/ui/panels/workbench/strategy_card.py`
- `src/ui/panels/workbench/heading_quick_card.py`
- `src/ui/panels/workbench/quick_fill_card.py`
- `src/ui/panels/workbench/execution_center.py`
- `src/ui/panels/workbench/recent_run_panel.py`
- `src/ui/panels/workbench/panel.py`
- `tests/test_workbench_layout.py`

The intention is to refine visual hierarchy **without** rebreaking the layout skeleton or feature boundaries that are already in place.

## Non-goals for this pass

This pass does not require:

- new business behavior in the quick cards
- a full execution pipeline integration rewrite
- a new page architecture
- redesign of other non-Workbench pages
- adding more homepage feature cards before polish is complete

## Success criteria

This UI polish pass is complete when the Workbench no longer reads as "functionality stacked into a page," but instead reads as:

> a coherent task command center with a strong action anchor, a clear task anchor, disciplined secondary surfaces, and a quiet result-review region.

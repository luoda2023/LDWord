# Workbench Command Center Redesign

## Goal

Redesign the current Workbench homepage from an embedded configuration page into a real **high-frequency command center** for document formatting work.

The redesigned Workbench must support two equally important expert-user entry patterns:

1. **Document-driven start** - change the current document, keep the current strategy, execute again.
2. **Strategy-driven start** - change the current strategy, keep the current document, execute again.

The page should optimize for repeated expert usage, while still providing lightweight guardrails that prevent obvious mistakes before execution.

## Why the current Workbench is not enough

The current MVP proved that the shell can host a real Workbench panel and execute the real pipeline, but it still behaves like a configuration page rather than a command center.

Current problems:

- the page still feels linear instead of task-oriented;
- `HeadingNumberingPanel` occupies too much of the homepage and over-defines the entire Workbench;
- the current structure still implies "configure first, execute later" rather than "manage the current task from a stable control surface";
- the execution area is present, but not yet strong enough to act as the page's operational anchor;
- there is no durable placement strategy for additional high-frequency capabilities such as quick fill.

The redesign must fix the information architecture first, not just spacing or cosmetic styling.

## Product positioning for this page

This page is **not** a beginner wizard.

This page is **not** a full template editor.

This page is **not** a full scene editor.

This page **is**:

> a professional task command center for high-frequency document processing, with lightweight guardrails.

That means:

- fast access to the current document and current strategy;
- minimal clicks for repeat execution;
- clear readiness and execution feedback;
- only high-frequency adjustments on the homepage;
- deep configuration moved behind secondary entry points.

## Primary design decision

The homepage should adopt a **layered command-center** structure instead of a monolithic single-screen editor.

### Chosen layout model

- **Top bar**: current task command bar
- **Lower area**: left/right dual column
  - **left column**: strategy + quick capability cards
  - **right column**: fixed execution center
- **Bottom area**: recent run / report / error summary

This replaces the earlier layout where an entire advanced editor dominated the center of the page.

## Core page model

The homepage is centered around a single concept:

# Current Task

A task is the combination of:

- **current document**
- **current execution strategy**

The Workbench should treat both as first-class entry points. Neither should be subordinated to the other in the page structure.

### Consequence

The page must not force a single hardcoded start order like:

- choose document -> choose strategy -> configure -> run

Instead, the page should support all of these naturally:

- swap the document, keep the strategy, run again
- swap the strategy, keep the document, run again
- swap both, then run
- run again with no changes

## Information architecture

## 1. Current Task Command Bar

The top bar is the page's operational anchor.

It should always show:

- current document
- current strategy
- readiness state
- primary execute action

### Responsibilities

- communicate "what am I about to run?"
- communicate "can I run right now?"
- expose the primary execute action
- allow quick document/strategy switching

### It should not do

- deep editing
- large descriptive text blocks
- verbose path dumps
- detailed error logs

This bar must feel like a control strip, not a form.

## 2. Left Column: Task Adjustment Area

The left column is the expert user's adjustment surface.

It has three layers:

### 2.1 Strategy Card

This is the first and most important card in the left column.

It represents the current execution strategy as a first-class object.

The card should show:

- strategy name
- strategy source type (`default`, `recent`, `favorite`, `custom`)
- bound template
- bound scene
- strict execution state
- enabled module summary

The card should support:

- switch strategy
- save current state as a strategy
- duplicate strategy
- rename strategy
- restore strategy baseline

### 2.2 Quick Capability Grid

Below the strategy card, the homepage should show a grid of high-frequency capability cards.

This is the main extensibility surface of the page.

The grid should default to 2 columns on standard desktop widths.

The homepage should keep only **4-6 fixed cards** here long-term.

#### Initial fixed cards

1. **Heading Numbering Quick Card**
2. **Quick Fill Card**
3. **TOC Quick Card**
4. **Table Quick Card**

These represent the first stable homepage capabilities.

### 2.3 More Capabilities Area

At the bottom of the left column, there should be a deliberate overflow zone for non-default homepage capabilities.

This avoids endless homepage growth.

Examples:

- header/footer
- whitespace normalization
- references
- watermark
- links to full config pages

## 3. Right Column: Execution Center

The right column should be fixed and stable. It is the page's operational spine.

It should not scroll or grow with the left-column quick cards unless absolutely necessary.

The execution center has four subareas:

### 3.1 Readiness

Shows whether execution is currently allowed, with lightweight guardrails.

Examples:

- document ready / missing
- strategy ready / missing
- required data source missing
- execution blocked / ready

### 3.2 Execution Summary

Shows what this run will do.

Examples:

- current strategy name
- enabled modules for this run
- temporary quick overrides
- output location

### 3.3 Execution Controls

Shows:

- start execute button
- cancel action
- progress
- current stage name

### 3.4 Result Summary

Shows the most recent execution outcome in compact form.

Examples:

- success / partial success / failure / cancelled
- output document
- report entry points
- top-level failure summary

## 4. Bottom Area: Recent Run Panel

The bottom panel is for recent output review, not live execution control.

It should show:

- latest output file summary
- JSON / Markdown report links
- recent error summary
- optional expandable log/details section

This separates:

- "what is happening now?" (right column)
from
- "what happened last time?" (bottom panel)

## Execution Strategy Model

The homepage should promote an explicit **Execution Strategy** concept.

This is broader than just template + scene.

An execution strategy should summarize:

- template
- scene
- strict execution mode
- enabled module profile
- homepage-level quick overrides
- recent adjustments relevant to repeat execution

### Strategy types

The homepage should support these strategy categories:

1. **Default strategies** - built-in baseline strategies
2. **Recent strategies** - quickly reusable recent combinations
3. **Favorite strategies** - explicitly preserved user favorites
4. **Custom strategies** - user-authored freeform strategies saved from the current state

This is important because the user explicitly wants support for:

- repeated processing of one document class with small strategy changes
- repeated processing of different documents using a mostly stable strategy
- creation of multiple freely configurable strategy variants

## Quick cards vs advanced editors

A key boundary must be enforced:

### Homepage quick cards
Quick cards are allowed to expose:

- short summary state
- a few high-frequency adjustments
- reset-to-default
- open advanced configuration

### Homepage quick cards are not allowed to become

- full editors
- giant embedded forms
- complete scene/template editing surfaces

### Advanced configuration
Full editors should open via:

1. inline expand region in Workbench, or
2. a right-side drawer, or
3. a dedicated config page when appropriate

The first priority should be inline expansion or drawer behavior, not default full-page embedding.

## Heading Numbering redesign within Workbench

`HeadingNumberingPanel` should remain a full advanced editor, but it should no longer define the Workbench homepage layout.

### Homepage representation
Introduce **Heading Numbering Quick Card** with:

- current numbering scheme
- heading depth
- TOC inclusion summary
- one-line numbering preview
- actions:
  - quick adjust
  - restore default
  - advanced config

### Advanced entry
The full `HeadingNumberingPanel` opens only when explicitly requested.

This preserves the value of the existing work while preventing it from overwhelming the homepage.

## Quick Fill placement

Quick Fill should be a **default homepage card**, not a hidden future feature.

Reasoning:

- it is high-frequency and task-oriented
- it fits both document-driven and strategy-driven usage
- it belongs to the command center more than to deep template configuration

### Homepage representation
Introduce **Quick Fill Card** with:

- current fill source summary
- selected entity / asset summary
- mapping readiness
- actions:
  - quick fill setup
  - advanced mapping
  - preview fill scope

## Extension model for future capabilities

Not every capability belongs as a permanent homepage card.

The homepage must distinguish three levels:

### Level 1: fixed homepage cards
For high-frequency, task-level adjustments.

Examples:

- heading numbering
- quick fill
- toc
- table

### Level 2: optional homepage access via "more capabilities"
For medium-frequency features.

Examples:

- header/footer
- whitespace
- references
- watermark

### Level 3: dedicated config pages
For large and complex editing workflows.

Examples:

- full template configuration
- full scene configuration
- asset management
- deep mapping / rule editing

This prevents homepage sprawl.

## Naming direction

The visual and textual tone should shift toward a professional command-center style.

### Naming direction accepted
Shorter, firmer, expert-oriented terminology.

Recommended wording direction:

- `工作台` -> `任务中控`
- `模板与场景` -> `执行策略`
- `快捷配置` -> `快捷操作`
- `执行与结果` -> `执行中心`
- `开始排版` -> `开始执行`

### Status wording direction
Replace generic English status badges like `IDLE` with Chinese operational states such as:

- 待执行
- 执行中
- 已完成
- 部分完成
- 执行失败
- 已取消

## Visual direction

The page should look less like a loose configuration form and more like a command surface.

Desired characteristics:

- denser but controlled information hierarchy
- stronger primary action emphasis
- shorter labels
- less wasted vertical space
- reduced long-path noise in the main reading path
- clearer visual separation between task control, adjustment, execution, and review

## File and component architecture

To avoid turning `workbench_panel.py` into another monolithic file, the Workbench should be refactored into a dedicated component group.

### Recommended structure

```text
src/ui/panels/
- workbench_panel.py
- workbench/
  - __init__.py
  - panel.py
  - styles.py
  - state.py
  - command_bar.py
  - strategy_card.py
  - capability_grid.py
  - heading_quick_card.py
  - quick_fill_card.py
  - execution_center.py
  - recent_run_panel.py
  - more_capabilities_card.py
```

### Adapter additions

Recommended new adapters:

- `src/ui/adapters/workbench_strategy_adapter.py`
- `src/ui/adapters/workbench_execution_adapter.py`

#### Strategy adapter responsibilities

- summarize the current strategy
- manage switching / saving / duplication / rename / restore
- expose homepage-safe strategy state

#### Execution adapter responsibilities

- compute readiness
- compute run summary
- trigger pipeline execution
- summarize recent run state

## Compatibility boundaries

These pieces should remain stable and be reused rather than replaced:

- `src/ui/main_window.py`
- `src/ui/panel_registry.py`
- `src/ui/base_panel.py`
- `src/ui/bridge.py`
- `src/ui/panels/heading_numbering_panel.py`

The redesign should be additive and structural, not a discard-and-rebuild rewrite.

## Phased implementation order

The redesign should be implemented in this order:

1. **Information architecture and layout skeleton**
2. **Execution strategy system**
3. **Execution center redesign**
4. **Heading Numbering Quick Card**
5. **Quick Fill Card**
6. **More capabilities / extension model**
7. **Naming and visual polish**
8. **Focused Workbench regression test suite**

### Why this order

Because the main risk is structural failure, not visual imperfection.

If the page structure and responsibilities are wrong, all downstream styling work is wasted.

## Risks

### Risk 1: Workbench becomes another giant editor page
Mitigation: keep quick cards small and push depth into advanced editors.

### Risk 2: strategy model becomes too abstract for users
Mitigation: always show concrete template/scene bindings inside the strategy card summary.

### Risk 3: execution center becomes passive instead of central
Mitigation: keep execute readiness, run summary, and result summary all in the same fixed right rail.

### Risk 4: homepage grows without limit
Mitigation: fixed-card policy + more-capabilities overflow + dedicated config pages.

## Non-goals for this redesign slice

This redesign spec does not require:

- a full beginner wizard mode
- a complete visual rewrite of every subpage in the application
- a full implementation of all quick cards immediately
- replacing all advanced config pages with homepage cards

## Success criteria

The redesign is successful when:

1. the homepage clearly feels like a command center, not a config page;
2. an expert user can start from either the document or the strategy and execute with minimal friction;
3. the homepage no longer depends on a full embedded advanced editor to feel functional;
4. quick fill and future homepage features have a clear placement model;
5. the page remains extensible without becoming another monolith.

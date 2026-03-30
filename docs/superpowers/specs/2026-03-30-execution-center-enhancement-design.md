# Execution Center Enhancement Design

## Goal

Turn the current right-side execution center from a mostly static status card into a real execution-control surface for the Workbench.

This enhancement must let the user:

- start a real execution run,
- observe stage-level progress while the UI stays responsive,
- cancel an in-flight run,
- receive immediate end-state feedback,
- and propagate a summarized result into the bottom recent-run panel.

## Why this is the next step

The Workbench now has the correct page skeleton:

- top current-task bar,
- middle left/right split,
- left strategy + quick-card area,
- right execution center,
- bottom recent-run area.

That means the main structural problem has been solved. The next missing piece is that the execution center still does not fully behave like a control center. It has a location and a role, but not yet the full live execution loop that makes the page feel operational.

## Product intent for this enhancement
The execution center should become the page's primary action anchor.
The execution center should become the page?s primary action anchor.

A user should be able to tell, at a glance:

- whether the current task can run,
- what step is currently running,
- how far the run has progressed,
- whether the run succeeded / partially succeeded / failed / was cancelled,
- and what the latest result means.

This is not a batch queue, not a run history browser, and not a complete report center. It is a single-task operational console.

## In scope

1. Real execution lifecycle inside the Workbench
2. Background execution worker so the UI does not freeze
3. Execution-center state machine and signal flow
4. Start / cancel controls
5. Stage text + progress display
6. Immediate success / failure / partial success / cancelled feedback
7. Summary synchronization into the recent-run panel

## Out of scope

1. Batch queue management
2. Multi-run history list
3. Automatic retry logic
4. Full report viewer UI
5. Advanced execution analytics
6. New homepage capability cards

## Core design decision
- the execution center's role depends on live state updates,
Use a dedicated **background execution worker** rather than keeping pipeline execution on the UI thread.

This is the preferred path because:

- the current Workbench already has enough structure to support signal-based orchestration,
- the execution center?s role depends on live state updates,
- and a main-thread execution path would limit the usefulness of the new control surface.

## Component split

## 1. ExecutionCenter

### Role
Pure execution UI surface.

### Responsibilities
- expose start/cancel intent
- display readiness state
- display current stage text
- display progress
- display final execution state summary

### Not responsible for
- running the pipeline directly
- constructing execution payloads
- managing thread lifetime

## 2. WorkbenchPanel

### Role
Page-level coordinator.

### Responsibilities
- collect the current document and current strategy state
- decide whether execution can start
- create and manage the worker/thread
- connect execution signals to the execution center and recent-run panel
- restore UI state after the worker finishes

### Not responsible for
- embedding execution business logic directly
- implementing raw thread logic inline

## 3. ExecutionWorker

### Role
Background pipeline runner.

### Responsibilities
- run pipeline work in a background thread
- emit progress updates
- emit final result state
- respond to cancellation requests

### Not responsible for
- UI updates
- layout logic

## 4. WorkbenchExecutionAdapter

### Role
Execution-state adapter.

### Responsibilities
- derive readiness
- build execution summary text
- build progress state payloads
- build final execution result summary
- build recent-run summary state

This keeps status shaping out of the panel widget code.

## State model

## 1. ExecutionCenter state lifecycle

Recommended runtime states:

- `idle`
- `running`
- `success`
- `partial_success`
- `failed`
- `cancelled`

### Allowed transitions
- `idle -> running`
- `running -> success`
- `running -> partial_success`
- `running -> failed`
- `running -> cancelled`
- update the execution center's stage text and progress bar
### Prohibited transitions
- `running -> running` by double-start
- `idle -> cancelled`
- `success -> cancelled`

## 2. New state objects

This enhancement should extend `src/ui/panels/workbench/state.py` with at least:

### `ExecutionProgressState`
Fields should include:
- `stage_text`
- `current_step`
- `total_steps`
- `percent`

### `ExecutionResultState`
Fields should include:
- `status`
- `summary`
- `error_text`
- `output_path`
- `report_paths`
- `failed_count`

### `RecentRunState`
Fields should include:
- `status`
- `title`
- initial: `开始执行`
- running alternate action: `取消`
- terminal re-entry action: `再次执行` or `重新执行`
- `error_summary`

## Signal design

## ExecutionCenter signals

- `execute_requested`
- 正在准备执行
- 正在加载文档
- 正在应用标题编号
- 正在生成标录
- 正在保存结果
- 正在收尾
Minimum recommended signal surface:

- `execution_started`
- `progress_changed(progress_state)`
- `execution_succeeded(result_state)`
- `execution_partial(result_state)`
- `execution_failed(result_state)`
- `execution_cancelled()`
- `execution_finished()`

## WorkbenchPanel signal responsibilities

### On execute request
- validate readiness
- freeze relevant controls
- create and start worker
- move state to `running`

### On cancel request
- set the worker cancel flag
- keep UI in running/cancelling mode until the worker confirms cancellation

### On progress
- update the execution center?s stage text and progress bar

### On final result
- update the execution center final state
- update the recent-run panel
Mitigation: keep a strict split between 'current' and 'most recent'.
- dispose of worker/thread references safely

## Button behavior

## 1. Idle
- Start button enabled
- Cancel hidden or disabled

## 2. Running
- Start button disabled
- Cancel enabled
- Strategy/doc/quick controls locked

## 3. Success / Partial Success / Failed / Cancelled
- Start button re-enabled
- Cancel hidden or disabled
- Controls unlocked

### Label strategy
A stable wording system is preferred:

- initial: `????`
- running alternate action: `??`
- terminal re-entry action: `????` or `????`

## Progress model

The execution center should not show fake fine-grained progress.

Recommended display:

### 1. Stage text
Examples:
- ??????
- ??????
- ????????
- ??????
- ??????
- ????

### 2. Progress bar
### 3. Step count or percentage
Prefer stage count + progress bar over percentage alone, because the pipeline is naturally step-based.

## Recent-run synchronization

The execution center is for the **current run**.
The recent-run panel is for the **most recent finished run**.

### On success
Recent-run panel receives:
- completed status
- output path summary
- report summary

### On partial success
Recent-run panel receives:
- partial success status
- output path summary
- report summary
- failed module count summary

### On failure
Recent-run panel receives:
- failed status
- top-level error summary

### On cancelled
Recent-run panel receives:
- cancelled status
- optional cancellation summary

## UX rules

1. During execution, the execution center becomes the dominant live-feedback area.
2. The recent-run panel must not compete with the execution center while a run is still active.
3. The execution center must never expose multiple competing primary actions at once.
4. Cancellation should not visually complete until the worker actually stops.
5. Execution errors must surface in the execution center, not only in logs.

## File-level implementation direction

Primary files for this enhancement:

- `src/ui/panels/workbench/execution_worker.py` (new)
- `src/ui/adapters/workbench_execution_adapter.py`
- `src/ui/panels/workbench/execution_center.py`
- `src/ui/panels/workbench/recent_run_panel.py`
- `src/ui/panels/workbench/state.py`
- `src/ui/panels/workbench/panel.py`
- `tests/test_workbench_execution_center.py`
- `tests/test_workbench_layout.py`

## Recommended implementation order

1. Extend execution state models
2. Expand `WorkbenchExecutionAdapter`
3. Add `ExecutionWorker`
4. Extend `ExecutionCenter` UI surface
5. Wire execution lifecycle in `WorkbenchPanel`
6. Sync result state into `RecentRunPanel`
7. Add focused execution-flow tests
8. Re-run Workbench + full verification

## Risks

### Risk 1: UI thread blocking
Mitigation: use a real background worker / thread boundary.

### Risk 2: duplicate start requests
Mitigation: disable start during `running`.

### Risk 3: cancellation leaves stale UI state
Mitigation: treat cancellation as complete only after worker confirmation.

### Risk 4: result state duplicated between execution center and recent-run panel
Mitigation: keep a strict split between ?current? and ?most recent?.

## Success criteria

This enhancement is successful when:

1. the execution center can start a real run without freezing the UI;
2. a user can cancel a running task;
3. stage/progress updates are visible and meaningful;
4. the final execution state is reflected immediately in the execution center;
5. the recent-run panel receives a synchronized summary of the latest run;
6. the Workbench feels operational rather than merely structural.

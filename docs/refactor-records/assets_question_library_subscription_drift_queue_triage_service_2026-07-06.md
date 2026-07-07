# Assets Question Library Subscription Drift Queue And Triage Service Extraction

Date: 2026-07-06

## Scope

This step moved the first subscription-drift governance slice from `src/ui/panels/assets_panel.py` into `src/services/material_assets/question_library.py`.

New service functions include:

- `question_figure_library_master_subscription_drift_queue_entries`
- `build_question_figure_library_master_subscription_drift_queue_record`
- `question_figure_library_master_subscription_drift_queue_for`
- `question_figure_library_master_subscription_drift_queue_record_for_profiles`
- `question_figure_library_master_subscription_drift_triage_entries`
- `build_question_figure_library_master_subscription_drift_triage_approval_record`
- `question_figure_library_master_subscription_drift_triage_approval_for`
- `question_figure_library_master_subscription_drift_triage_approval_record_for_profiles`

Supporting projection helpers were also moved:

- JSON/list record value parsing
- drift queue package/event summaries
- drift queue id generation
- triage priority, assignee, and approval policy labels

Legacy private names are retained as aliases for older panel code and tests.

## Boundary

The service now owns deterministic drift queue and triage data:

- finding callback records that detected remote changes
- projecting queue rows
- building durable queue records
- finding queued records
- projecting triage rows
- building durable triage approval records
- finding approved triage records

The panel still owns side effects:

- applying queue metadata to profile asset items
- applying triage metadata to profile asset items
- appending records into profile histories
- refreshing Qt tables and status labels

## Why This Helps

Subscription drift is the next large governance area after registry sync, subscription lock, and change callback. Moving queue and triage data rules into the service layer prevents the panel from becoming the source of truth for governance state transitions.

This also prepares the next extraction slice: decision plan and decision execution can now build on service-level queue and triage records.

## Verification

Added service tests for:

- queue entry projection from remote-change callback records
- queue record creation and lookup
- triage entry projection from queued records
- triage priority and assignment projection
- triage approval record creation and lookup
- facade export and legacy alias identity

# Assets Question Library Subscription Lock Service Extraction

Date: 2026-07-06

## Scope

This step moved pure subscription-lock governance helpers from `src/ui/panels/assets_panel.py` into `src/services/material_assets/question_library.py`.

New service functions:

- `question_figure_master_subscription_lock_idempotency_key`
- `question_figure_master_subscription_lock_policy`
- `question_figure_master_subscription_lock_payload`
- `build_question_figure_library_master_subscription_lock_base_record`

The panel now also uses the existing service-level `question_figure_master_subscription_lock_endpoint` instead of keeping a duplicate endpoint scanner.

Legacy private names are retained as aliases for older panel code and tests.

## Boundary

The service now owns deterministic subscription-lock data shape:

- endpoint lookup
- idempotency key material
- lock policy defaults and metadata override handling
- outbound lock-governance payload
- durable base execution record

The panel still owns side effects:

- HTTP POST execution
- auth header preparation
- HTTP and network exception handling
- status label updates
- profile metadata mutation after successful lock governance

## Why This Helps

Subscription lock is part of the remote-writeback governance chain after registry sync. Moving its data contract into the service layer keeps the panel focused on user interaction and state refresh, while the durable governance record and outbound payload can be tested without Qt or network calls.

This leaves the next high-value extraction point as subscription change callback payload/base record normalization.

## Verification

Added service tests for:

- subscription lock endpoint lookup
- lock policy metadata overrides
- deterministic idempotency key prefix
- outbound lock-governance payload shape
- base execution record fields and JSON affected items
- facade export and legacy alias identity

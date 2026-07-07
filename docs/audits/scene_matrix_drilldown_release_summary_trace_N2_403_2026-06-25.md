# Scene Matrix Drilldown Release Summary Trace N2.403

N2.402 made the receipt-specific acceptance certificate rows searchable in the `release_acceptance_certificate` drilldown. N2.403 carries that user-facing drilldown expansion into the release gate human summary, so the terminal output does not only say that all drilldown groups are ready.

## Closed Link

The release gate already exposes `scene_matrix_drilldown_row_count` and `scene_matrix_drilldown_visible_row_count` in its payload. The human summary now prints the same row coverage:

| Summary marker | Expected ratio | Meaning |
| --- | ---: | --- |
| `drilldowns` | `37/37` | All drilldown groups are ready. |
| `drilldown_rows` | `553/553` | All user-visible drilldown rows are present after the N2.402 receipt rows. |

## Review Rule

Release reviewers must be able to see both the number of ready drilldown groups and the number of visible drilldown rows in the terminal summary. This closes the path from `acceptance_receipt_trace` searchability to the final release gate output.

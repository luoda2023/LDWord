def assert_expected_count_values(
    actual_counts: dict[str, int],
    expected_counts: dict[str, int],
) -> None:
    for count_id, expected_value in expected_counts.items():
        assert actual_counts[count_id] == expected_value, count_id

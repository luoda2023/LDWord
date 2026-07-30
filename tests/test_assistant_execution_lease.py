from src.assistant.application.execution_lease import ExecutionLease, ExecutionLeaseManager


def test_execution_lease_keeps_one_owner_and_releases_by_execution_id():
    manager = ExecutionLeaseManager()
    first = ExecutionLease("execution-1", "session-1", "now")
    second = ExecutionLease("execution-2", "session-2", "later")

    assert manager.acquire(first)
    assert not manager.acquire(first)
    assert not manager.acquire(second)
    assert manager.current == first
    assert not manager.release("execution-2")
    assert manager.release("execution-1")
    assert manager.acquire(second)

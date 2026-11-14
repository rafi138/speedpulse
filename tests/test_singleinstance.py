from speedpulse.core.singleinstance import SingleInstanceLock, default_lock_path


def test_second_instance_fails(tmp_path):
    first = SingleInstanceLock(tmp_path / "sp.lock")
    second = SingleInstanceLock(tmp_path / "sp.lock")
    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    assert second.acquire() is True
    second.release()


def test_reacquire_after_release(tmp_path):
    lock = SingleInstanceLock(tmp_path / "sp.lock")
    assert lock.acquire() is True
    lock.release()
    assert lock.acquire() is True
    lock.release()
    lock.release()  # double release is a no-op


def test_acquire_is_idempotent(tmp_path):
    lock = SingleInstanceLock(tmp_path / "sp.lock")
    assert lock.acquire() is True
    assert lock.acquire() is True  # already held


def test_default_lock_path_shape():
    path = default_lock_path()
    assert path.name.startswith("speedpulse")


def test_unusable_lock_path_fails_open(tmp_path):
    # A missing parent directory must not make the app refuse to start:
    # we run without the guard rather than pretending another instance exists.
    lock = SingleInstanceLock(tmp_path / "missing-dir" / "sp.lock")
    assert lock.acquire() is True
    lock.release()  # release without a held fd is a no-op

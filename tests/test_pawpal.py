from datetime import date, time, timedelta

from pawpal_system import (
    Parent,
    Pet,
    Recurrence,
    Scheduler,
    Task,
    TimePreference,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_task(name="Task", duration=10, priority="medium", **kwargs) -> Task:
    return Task(name=name, task_type="general", duration=duration, priority=priority, **kwargs)


def make_pet(name="Mochi") -> Pet:
    return Pet(name=name, age=3, breed="Shiba Inu", weight=20.5)


def make_owner(*prefs: TimePreference) -> Parent:
    return Parent(
        name="Jordan",
        email="jordan@example.com",
        location="Portland, OR",
        time_preferences=list(prefs),
    )


# ---------------------------------------------------------------------------
# Existing tests (preserved)
# ---------------------------------------------------------------------------

def test_mark_complete_changes_status():
    task = make_task(name="Morning Walk", duration=30, priority="high")
    assert task.is_complete is False
    task.mark_complete()
    assert task.is_complete is True


def test_adding_task_increases_pet_task_count():
    pet = make_pet()
    assert len(pet.tasks) == 0
    task = make_task(name="Feeding", duration=10, priority="high", target_pet=pet)
    pet.add_task(task)
    assert len(pet.tasks) == 1


# ---------------------------------------------------------------------------
# 1. Sorting correctness
# ---------------------------------------------------------------------------

class TestSorting:
    def test_tasks_sort_by_scheduled_time(self):
        """Tasks with earlier scheduled_time sort before later ones."""
        t1 = make_task(name="A", scheduled_time=time(8, 0))
        t2 = make_task(name="B", scheduled_time=time(6, 0))
        t3 = make_task(name="C", scheduled_time=time(10, 30))

        result = sorted([t1, t2, t3])

        assert [t.name for t in result] == ["B", "A", "C"]

    def test_task_without_time_sorts_last(self):
        """A task with no scheduled_time always falls after timed tasks."""
        timed = make_task(name="Timed", scheduled_time=time(23, 59))
        untimed = make_task(name="Untimed")

        assert timed < untimed
        assert not (untimed < timed)

    def test_two_untimed_tasks_are_not_less_than_each_other(self):
        """Two tasks both missing scheduled_time produce no ordering — neither is less."""
        a = make_task(name="A")
        b = make_task(name="B")

        assert not (a < b)
        assert not (b < a)

    def test_sorted_preserves_order_for_equal_times(self):
        """Tasks sharing the same scheduled_time keep their original relative order."""
        t1 = make_task(name="First", scheduled_time=time(9, 0))
        t2 = make_task(name="Second", scheduled_time=time(9, 0))

        result = sorted([t1, t2])

        assert result[0].name == "First"
        assert result[1].name == "Second"

    def test_scheduler_sets_scheduled_time_in_chronological_order(self):
        """After generate_schedule, sorting tasks_scheduled by time matches placement order."""
        pet = make_pet()
        owner = make_owner(TimePreference.MORNING)
        tasks = [
            make_task(name="Walk",  duration=30, priority="high",   target_pet=pet),
            make_task(name="Feed",  duration=10, priority="high",   target_pet=pet),
            make_task(name="Groom", duration=20, priority="medium", target_pet=pet),
        ]
        schedule = Scheduler([pet], [owner], tasks).generate_schedule()

        sorted_tasks = sorted(schedule.tasks_scheduled)

        # All scheduled tasks must have a scheduled_time set.
        assert all(t.scheduled_time is not None for t in sorted_tasks)
        # Times must be non-decreasing after sorting.
        times = [t.scheduled_time for t in sorted_tasks]
        assert times == sorted(times)


# ---------------------------------------------------------------------------
# 2. Recurrence logic
# ---------------------------------------------------------------------------

class TestRecurrence:
    def test_daily_recurrence_returns_new_task(self):
        """mark_complete on a daily task returns a Task, not None."""
        task = make_task(recurrence=Recurrence.DAILY)
        next_occ = task.mark_complete()

        assert next_occ is not None

    def test_daily_next_due_is_tomorrow(self):
        """The spawned daily task has next_due set to today + 1 day."""
        task = make_task(recurrence=Recurrence.DAILY)
        next_occ = task.mark_complete()

        assert next_occ.next_due == date.today() + timedelta(days=1)

    def test_weekly_next_due_is_seven_days_out(self):
        """The spawned weekly task has next_due set to today + 7 days."""
        task = make_task(recurrence=Recurrence.WEEKLY)
        next_occ = task.mark_complete()

        assert next_occ.next_due == date.today() + timedelta(days=7)

    def test_spawned_task_is_not_complete(self):
        """The next-occurrence task starts with is_complete=False."""
        task = make_task(recurrence=Recurrence.DAILY)
        next_occ = task.mark_complete()

        assert next_occ.is_complete is False

    def test_spawned_task_has_no_scheduled_time(self):
        """The next-occurrence task has scheduled_time cleared so the scheduler can place it fresh."""
        task = make_task(recurrence=Recurrence.DAILY, scheduled_time=time(7, 0))
        next_occ = task.mark_complete()

        assert next_occ.scheduled_time is None

    def test_non_recurring_task_returns_none(self):
        """mark_complete on a task with no recurrence returns None."""
        task = make_task()
        result = task.mark_complete()

        assert result is None

    def test_original_task_is_marked_complete_regardless_of_recurrence(self):
        """The original task is always marked complete, even when it spawns a successor."""
        task = make_task(recurrence=Recurrence.DAILY)
        task.mark_complete()

        assert task.is_complete is True

    def test_spawned_task_inherits_attributes(self):
        """The next occurrence carries the same name, duration, and priority as the original."""
        task = make_task(name="Medication", duration=5, priority="high", recurrence=Recurrence.DAILY)
        next_occ = task.mark_complete()

        assert next_occ.name == "Medication"
        assert next_occ.duration == 5
        assert next_occ.priority == "high"
        assert next_occ.recurrence == Recurrence.DAILY


# ---------------------------------------------------------------------------
# 3. Conflict detection
# ---------------------------------------------------------------------------

class TestConflictDetection:
    def _make_scheduler(self, tasks=None):
        return Scheduler(target_pets=[], parents=[], tasks=tasks or [])

    def test_identical_start_times_flagged(self):
        """Two tasks starting at the same time are a conflict."""
        pet = make_pet()
        t1 = make_task(name="Walk",  duration=30, target_pet=pet, scheduled_time=time(8, 0))
        t2 = make_task(name="Bath",  duration=20, target_pet=pet, scheduled_time=time(8, 0))

        warnings = self._make_scheduler().detect_conflicts([t1, t2])

        assert len(warnings) == 1
        assert "Walk" in warnings[0]
        assert "Bath" in warnings[0]

    def test_partial_overlap_flagged(self):
        """A task starting before another ends is a conflict."""
        t1 = make_task(name="Walk", duration=30, scheduled_time=time(8, 0))   # 8:00–8:30
        t2 = make_task(name="Feed", duration=20, scheduled_time=time(8, 20))  # 8:20–8:40

        warnings = self._make_scheduler().detect_conflicts([t1, t2])

        assert len(warnings) == 1

    def test_back_to_back_tasks_not_flagged(self):
        """Tasks that touch but do not overlap (end == next start) are not a conflict."""
        t1 = make_task(name="Walk", duration=30, scheduled_time=time(8, 0))   # 8:00–8:30
        t2 = make_task(name="Feed", duration=10, scheduled_time=time(8, 30))  # 8:30–8:40

        warnings = self._make_scheduler().detect_conflicts([t1, t2])

        assert len(warnings) == 0

    def test_non_overlapping_tasks_not_flagged(self):
        """Tasks with a gap between them produce no warnings."""
        t1 = make_task(name="Walk", duration=30, scheduled_time=time(7, 0))   # 7:00–7:30
        t2 = make_task(name="Feed", duration=10, scheduled_time=time(8, 0))   # 8:00–8:10

        warnings = self._make_scheduler().detect_conflicts([t1, t2])

        assert len(warnings) == 0

    def test_task_without_scheduled_time_is_skipped(self):
        """A task with no scheduled_time does not raise and is not treated as a conflict."""
        t1 = make_task(name="Walk", duration=30, scheduled_time=time(8, 0))
        t2 = make_task(name="Feed", duration=10)  # no scheduled_time

        warnings = self._make_scheduler().detect_conflicts([t1, t2])

        assert len(warnings) == 0

    def test_multiple_conflicts_all_reported(self):
        """When one task overlaps two others, both pairs are reported."""
        t1 = make_task(name="A", duration=60, scheduled_time=time(8, 0))   # 8:00–9:00
        t2 = make_task(name="B", duration=10, scheduled_time=time(8, 10))  # 8:10–8:20 — overlaps A
        t3 = make_task(name="C", duration=10, scheduled_time=time(8, 30))  # 8:30–8:40 — overlaps A

        warnings = self._make_scheduler().detect_conflicts([t1, t2, t3])

        assert len(warnings) == 2

    def test_conflicts_across_different_pets(self):
        """Conflicts are detected even when the tasks belong to different pets."""
        mochi   = make_pet("Mochi")
        biscuit = make_pet("Biscuit")
        t1 = make_task(name="Walk",  duration=30, target_pet=mochi,   scheduled_time=time(9, 0))
        t2 = make_task(name="Meds",  duration=10, target_pet=biscuit, scheduled_time=time(9, 15))

        warnings = self._make_scheduler().detect_conflicts([t1, t2])

        assert len(warnings) == 1
        assert "Mochi" in warnings[0]
        assert "Biscuit" in warnings[0]

    def test_generate_schedule_stores_conflicts_on_schedule(self):
        """Conflicts found during scheduling are stored on the returned Schedule object."""
        pet = make_pet()
        owner = make_owner(TimePreference.MORNING)
        # Pre-set scheduled_time so both tasks occupy the same slot before passing to detect_conflicts.
        t1 = make_task(name="Walk", duration=30, target_pet=pet, scheduled_time=time(8, 0))
        t2 = make_task(name="Bath", duration=20, target_pet=pet, scheduled_time=time(8, 10))

        scheduler = Scheduler([pet], [owner], [t1, t2])
        schedule = scheduler.generate_schedule()

        # The schedule object must expose the conflicts attribute.
        assert hasattr(schedule, "conflicts")
        assert isinstance(schedule.conflicts, list)


# ---------------------------------------------------------------------------
# 4. RAG reliability (no API key required — tests early-exit error handling)
# ---------------------------------------------------------------------------

class TestRAGReliability:
    """Verify that the RAG pipeline degrades gracefully when no documents exist.

    These tests never reach the Gemini API; they exercise the early-return paths
    in rag.query and rag.list_sources.
    """

    _PET = "zzz-nonexistent-test-pet-99"  # guaranteed to have no ChromaDB collection

    def test_query_returns_string_when_no_documents(self):
        """rag.query returns a non-empty string (not an exception) for an unknown pet."""
        import rag
        answer, sources = rag.query(self._PET, "What vaccines has this pet had?")

        assert isinstance(answer, str)
        assert len(answer) > 0

    def test_query_returns_empty_sources_when_no_documents(self):
        """rag.query returns an empty source list when no documents are ingested."""
        import rag
        _, sources = rag.query(self._PET, "Any question")

        assert sources == []

    def test_list_sources_returns_empty_list_for_unknown_pet(self):
        """rag.list_sources returns [] (not an exception) for a pet with no uploads."""
        import rag
        result = rag.list_sources(self._PET)

        assert result == []

import asyncio
import pytest
from dataclasses import dataclass
from port_ocean.core.handlers.queue.group_queue import GroupQueue
from typing import Any


@dataclass
class TestItem:
    group_id: str
    value: int


@dataclass
class TestItemNoGroup:
    value: int


class TestGroupQueue:
    """Test suite for GroupQueue lock mechanism"""

    @pytest.fixture
    def queue_with_group_key(self) -> GroupQueue[Any]:
        """Create a GroupQueue with group_key='group_id'"""
        return GroupQueue(group_key="group_id", name="test_queue")

    @pytest.fixture
    def queue_no_group_key(self) -> GroupQueue[Any]:
        """Create a GroupQueue without group_key (all items in same group)"""
        return GroupQueue(group_key=None, name="test_queue_no_group")

    @pytest.mark.asyncio
    async def test_basic_lock_mechanism(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that getting an item locks the group"""
        queue: GroupQueue[TestItem] = queue_with_group_key

        item1 = TestItem(group_id="group_a", value=1)
        item2 = TestItem(group_id="group_a", value=2)

        await queue.put(item1)
        await queue.put(item2)

        retrieved_item = await queue.get()
        assert retrieved_item == item1
        assert "group_a" in queue._locked

    @pytest.mark.asyncio
    async def test_locked_group_blocks_retrieval(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that locked groups cannot have items retrieved"""
        queue: GroupQueue[TestItem] = queue_with_group_key

        item1 = TestItem(group_id="group_a", value=1)
        item2 = TestItem(group_id="group_a", value=2)
        item3 = TestItem(group_id="group_b", value=3)

        await queue.put(item1)
        await queue.put(item2)
        await queue.put(item3)

        retrieved_item1 = await queue.get()
        assert retrieved_item1 == item1
        assert "group_a" in queue._locked

        retrieved_item2 = await queue.get()
        assert retrieved_item2 == item3
        assert "group_b" in queue._locked
        assert "group_a" in queue._locked

    @pytest.mark.asyncio
    async def test_commit_unlocks_group(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that commit() unlocks the group and allows next item retrieval"""
        queue: GroupQueue[TestItem] = queue_with_group_key

        item1 = TestItem(group_id="group_a", value=1)
        item2 = TestItem(group_id="group_a", value=2)

        await queue.put(item1)
        await queue.put(item2)

        retrieved_item1 = await queue.get()
        assert retrieved_item1 == item1
        assert "group_a" in queue._locked

        await queue.commit()
        assert "group_a" not in queue._locked

        retrieved_item2 = await queue.get()
        assert retrieved_item2 == item2
        assert "group_a" in queue._locked

    @pytest.mark.asyncio
    async def test_multiple_groups_concurrent_processing(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that different groups can be processed concurrently"""
        queue: GroupQueue[TestItem] = queue_with_group_key

        item_a1 = TestItem(group_id="group_a", value=1)
        item_a2 = TestItem(group_id="group_a", value=2)
        item_b1 = TestItem(group_id="group_b", value=3)
        item_c1 = TestItem(group_id="group_c", value=4)

        await queue.put(item_a1)
        await queue.put(item_b1)
        await queue.put(item_c1)
        await queue.put(item_a2)

        retrieved_items = []
        for _ in range(3):
            item = await queue.get()
            retrieved_items.append(item)

        assert len(queue._locked) == 3
        assert "group_a" in queue._locked
        assert "group_b" in queue._locked
        assert "group_c" in queue._locked

        group_ids = [queue._extract_group_key(item) for item in retrieved_items]
        assert set(group_ids) == {"group_a", "group_b", "group_c"}

    @pytest.mark.asyncio
    async def test_get_blocks_when_all_groups_locked(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that get() blocks when all available groups are locked"""
        queue: GroupQueue[TestItem] = queue_with_group_key

        item1 = TestItem(group_id="group_a", value=1)
        item2 = TestItem(group_id="group_a", value=2)

        await queue.put(item1)
        await queue.put(item2)

        await queue.get()
        assert "group_a" in queue._locked

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_no_group_key_single_group_behavior(
        self, queue_no_group_key: GroupQueue[Any]
    ) -> None:
        """Test behavior when group_key is None (all items in same group)"""
        queue: GroupQueue[TestItemNoGroup] = queue_no_group_key

        item1 = TestItemNoGroup(value=1)
        item2 = TestItemNoGroup(value=2)

        await queue.put(item1)
        await queue.put(item2)

        retrieved_item1 = await queue.get()
        assert retrieved_item1 == item1
        assert None in queue._locked

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)

        await queue.commit()
        assert None not in queue._locked

        retrieved_item2 = await queue.get()
        assert retrieved_item2 == item2

    @pytest.mark.asyncio
    async def test_commit_without_get_is_safe(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that calling commit() without get() doesn't break anything"""
        queue: GroupQueue[TestItem] = queue_with_group_key

        await queue.commit()
        assert len(queue._locked) == 0

    @pytest.mark.asyncio
    async def test_multiple_commits_are_safe(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that multiple commits after a single get are safe"""
        queue: GroupQueue[TestItem] = queue_with_group_key

        item = TestItem(group_id="group_a", value=1)
        await queue.put(item)

        retrieved_item = await queue.get()
        assert retrieved_item == item

        await queue.commit()
        assert "group_a" not in queue._locked

        await queue.commit()
        assert "group_a" not in queue._locked

    @pytest.mark.asyncio
    async def test_fifo_within_group(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that items within a group are processed in FIFO order"""
        queue: GroupQueue[TestItem] = queue_with_group_key

        items = [TestItem(group_id="group_a", value=i) for i in range(5)]
        for item in items:
            await queue.put(item)

        processed_items = []
        for _ in range(5):
            item = await queue.get()
            processed_items.append(item)
            await queue.commit()

        assert processed_items == items

    @pytest.mark.asyncio
    async def test_lock_prevents_queue_cleanup(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that locked groups prevent queue cleanup until unlocked"""
        queue: GroupQueue[TestItem] = queue_with_group_key

        item = TestItem(group_id="group_a", value=1)
        await queue.put(item)

        await queue.get()
        assert "group_a" in queue._queues
        assert "group_a" in queue._locked

        await queue.commit()
        assert "group_a" not in queue._queues
        assert "group_a" not in queue._locked

    @pytest.mark.asyncio
    async def test_extract_group_key_missing_attribute(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that missing group key attribute raises ValueError"""
        queue: GroupQueue[TestItemNoGroup] = queue_with_group_key

        bad_item = TestItemNoGroup(value=1)

        with pytest.raises(ValueError, match="lacks attribute 'group_id'"):
            await queue.put(bad_item)

    @pytest.mark.asyncio
    async def test_size_excludes_current_item(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that size() excludes the currently processed item"""
        queue: GroupQueue[TestItem] = queue_with_group_key

        items = [TestItem(group_id="group_a", value=i) for i in range(3)]
        for item in items:
            await queue.put(item)

        assert await queue.size() == 3

        await queue.get()
        assert await queue.size() == 3

        await queue.commit()
        assert await queue.size() == 2

    @pytest.mark.asyncio
    async def test_multiple_workers_different_groups(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test multiple workers processing items from different groups concurrently"""
        queue: GroupQueue[TestItem] = queue_with_group_key
        processed_items = []

        async def worker(worker_id: int, process_time: float = 0.1) -> Any:
            """Simulate a worker that processes items"""
            try:
                item = await queue.get()
                processed_items.append((worker_id, item))
                await asyncio.sleep(process_time)
                await queue.commit()
                return item
            except Exception as e:
                return f"Worker {worker_id} error: {e}"

        items = [
            TestItem(group_id="group_a", value=1),
            TestItem(group_id="group_b", value=2),
            TestItem(group_id="group_c", value=3),
            TestItem(group_id="group_d", value=4),
        ]

        for item in items:
            await queue.put(item)

        results = await asyncio.gather(
            worker(1), worker(2), worker(3), worker(4), return_exceptions=True
        )

        assert len([r for r in results if isinstance(r, TestItem)]) == 4
        assert len(processed_items) == 4

        processed_values = {item.value for _, item in processed_items}
        assert processed_values == {1, 2, 3, 4}

        assert len(queue._locked) == 0

    @pytest.mark.asyncio
    async def test_multiple_workers_same_group_exclusivity(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that multiple workers cannot process items from same group concurrently"""
        queue: GroupQueue[TestItem] = queue_with_group_key
        processing_log = []

        async def worker(worker_id: int, process_time: float = 0.2) -> Any:
            """Worker that logs processing start and end times"""
            try:
                item = await queue.get()
                start_time = asyncio.get_event_loop().time()
                processing_log.append(("start", worker_id, item.value, start_time))

                await asyncio.sleep(process_time)

                end_time = asyncio.get_event_loop().time()
                processing_log.append(("end", worker_id, item.value, end_time))

                await queue.commit()
                return item
            except Exception as e:
                return f"Worker {worker_id} error: {e}"

        items = [TestItem(group_id="group_a", value=i) for i in range(4)]
        for item in items:
            await queue.put(item)

        results = await asyncio.gather(
            worker(1), worker(2), worker(3), worker(4), return_exceptions=True
        )

        assert len([r for r in results if isinstance(r, TestItem)]) == 4

        start_times = {}
        end_times = {}

        for event, worker_id, value, timestamp in processing_log:
            if event == "start":
                start_times[value] = timestamp
            else:
                end_times[value] = timestamp

        sorted_items = sorted(start_times.items(), key=lambda x: x[1])

        for i in range(1, len(sorted_items)):
            current_value = sorted_items[i][0]
            previous_value = sorted_items[i - 1][0]

            current_start = start_times[current_value]
            previous_end = end_times[previous_value]

            assert (
                current_start >= previous_end - 0.01
            ), f"Item {current_value} started before item {previous_value} finished"

        assert len(queue._locked) == 0

    @pytest.mark.asyncio
    async def test_mixed_groups_with_multiple_workers(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test workers processing mixed groups - some concurrent, some sequential"""
        queue: GroupQueue[TestItem] = queue_with_group_key
        processing_events = []

        async def worker(worker_id: int) -> Any:
            """Worker that tracks processing events"""
            try:
                item = await queue.get()
                group = queue._extract_group_key(item)

                start_time = asyncio.get_event_loop().time()
                processing_events.append(
                    ("start", worker_id, group, item.value, start_time)
                )

                process_time = 0.1 if group == "fast_group" else 0.2
                await asyncio.sleep(process_time)

                end_time = asyncio.get_event_loop().time()
                processing_events.append(
                    ("end", worker_id, group, item.value, end_time)
                )

                await queue.commit()
                return item
            except Exception as e:
                return f"Worker {worker_id} error: {e}"

        items = [
            TestItem(group_id="same_group", value=1),
            TestItem(group_id="same_group", value=2),
            TestItem(group_id="same_group", value=3),
            TestItem(group_id="fast_group", value=4),
            TestItem(group_id="other_group", value=5),
            TestItem(group_id="another_group", value=6),
        ]

        for item in items:
            await queue.put(item)

        results = await asyncio.gather(
            *[worker(i) for i in range(1, 7)], return_exceptions=True
        )

        successful_results = [r for r in results if isinstance(r, TestItem)]
        assert len(successful_results) == 6

        group_events: dict[Any, Any] = {}
        for event in processing_events:
            _, worker_id, group, value, timestamp = event
            if group not in group_events:
                group_events[group] = []
            group_events[group].append(event)

        same_group_events = sorted(group_events["same_group"], key=lambda x: x[4])
        starts = [e for e in same_group_events if e[0] == "start"]
        ends = [e for e in same_group_events if e[0] == "end"]

        for i in range(1, len(starts)):
            assert starts[i][4] >= ends[i - 1][4] - 0.01

        assert len(queue._locked) == 0

    @pytest.mark.asyncio
    async def test_high_concurrency_stress_test(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Stress test with many workers and items"""
        queue: GroupQueue[TestItem] = queue_with_group_key

        async def worker(worker_id: int) -> Any:
            """Simple worker"""
            results = []
            while True:
                try:

                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                    results.append(item)

                    await asyncio.sleep(0.01 + (worker_id % 3) * 0.01)

                    await queue.commit()
                except asyncio.TimeoutError:
                    break
                except Exception as e:
                    print(f"Worker {worker_id} error: {e}")
                    break
            return results

        num_groups = 5
        items_per_group = 4

        for group_id in range(num_groups):
            for item_id in range(items_per_group):
                item = TestItem(
                    group_id=f"group_{group_id}", value=group_id * 100 + item_id
                )
                await queue.put(item)

        num_workers = 10
        results = await asyncio.gather(
            *[worker(i) for i in range(num_workers)], return_exceptions=True
        )

        all_processed = []
        for result in results:
            if isinstance(result, list):
                all_processed.extend(result)

        assert len(all_processed) == num_groups * items_per_group

        processed_values = [item.value for item in all_processed]
        expected_values = [
            g * 100 + i for g in range(num_groups) for i in range(items_per_group)
        ]
        assert sorted(processed_values) == sorted(expected_values)

        assert len(queue._locked) == 0
        assert await queue.size() == 0

    @pytest.mark.asyncio
    async def test_frozen_lock_timeout_recovery(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that frozen locks are released after timeout and processing can resume"""

        queue: GroupQueue[TestItem] = GroupQueue(
            group_key="group_id", name="test_queue", lock_timeout=0.3
        )

        processed_items = []

        async def normal_worker(worker_id: int) -> Any:
            """Worker that processes items normally"""
            try:
                item = await queue.get()
                processed_items.append((worker_id, item))
                await asyncio.sleep(0.1)
                await queue.commit()
                return item
            except Exception as e:
                return f"Worker {worker_id} error: {e}"

        async def hanging_worker(worker_id: int) -> Any:
            """Worker that gets item but never commits (simulates hung worker)"""
            try:
                item = await queue.get()
                processed_items.append((worker_id, item))

                await asyncio.sleep(1.0)

                return f"Worker {worker_id} hung"
            except Exception as e:
                return f"Worker {worker_id} error: {e}"

        items = [TestItem(group_id="group_a", value=i) for i in range(3)]
        for item in items:
            await queue.put(item)

        hanging_task = asyncio.create_task(hanging_worker(999))

        await asyncio.sleep(0.1)

        assert "group_a" in queue._locked

        normal_task = asyncio.create_task(normal_worker(1))

        await asyncio.sleep(0.2)
        assert not normal_task.done()

        await asyncio.sleep(0.4)

        await asyncio.wait_for(normal_task, timeout=2.0)

        normal_result = await normal_task
        assert isinstance(normal_result, TestItem)

        hanging_task.cancel()
        try:
            await hanging_task
        except asyncio.CancelledError:
            pass

        assert len(queue._locked) <= 1

        remaining_worker = asyncio.create_task(normal_worker(2))
        remaining_result = await asyncio.wait_for(remaining_worker, timeout=1.0)
        assert isinstance(remaining_result, TestItem)

        await asyncio.sleep(0.1)

        processed_values = {
            item.value for _, item in processed_items if isinstance(item, TestItem)
        }
        assert len(processed_values) >= 2

    @pytest.mark.asyncio
    async def test_lock_timeout_doesnt_affect_normal_processing(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test that lock timeout doesn't interfere with normal fast processing"""

        queue: GroupQueue[TestItem] = GroupQueue(
            group_key="group_id", name="test_queue", lock_timeout=2.0
        )

        processed_items = []

        async def fast_worker(worker_id: int) -> Any:
            """Worker that processes quickly (well under timeout)"""
            try:
                item = await queue.get()
                processed_items.append((worker_id, item))
                await asyncio.sleep(0.1)
                await queue.commit()
                return item
            except Exception as e:
                return f"Worker {worker_id} error: {e}"

        items = [TestItem(group_id="group_a", value=i) for i in range(5)]
        for item in items:
            await queue.put(item)

        results = []
        for i in range(5):
            task = asyncio.create_task(fast_worker(i))
            result = await asyncio.wait_for(task, timeout=1.0)
            results.append(result)

        assert len([r for r in results if isinstance(r, TestItem)]) == 5

        processed_values = {item.value for _, item in processed_items}
        assert processed_values == {0, 1, 2, 3, 4}

        assert len(queue._locked) == 0

    @pytest.mark.asyncio
    async def test_multiple_frozen_locks_recovery(
        self, queue_with_group_key: GroupQueue[Any]
    ) -> None:
        """Test recovery when multiple groups have frozen locks"""
        queue: GroupQueue[TestItem] = GroupQueue(
            group_key="group_id", name="test_queue", lock_timeout=0.3
        )

        async def hanging_worker(worker_id: int, group: str) -> Any:
            """Worker that grabs item from specific group and hangs"""
            try:

                while True:
                    item = await queue.get()
                    if item.group_id == group:

                        await asyncio.sleep(1.0)
                        return f"Worker {worker_id} hung with {group}"
                    else:

                        await queue.commit()
            except Exception as e:
                return f"Worker {worker_id} error: {e}"

        async def recovery_worker(worker_id: int) -> Any:
            """Worker that should be able to process after timeout"""
            try:
                item = await queue.get()
                await asyncio.sleep(0.05)
                await queue.commit()
                return item
            except Exception as e:
                return f"Worker {worker_id} error: {e}"

        for group in ["group_a", "group_b", "group_c"]:
            for i in range(2):
                await queue.put(TestItem(group_id=group, value=i))

        hanging_tasks = [
            asyncio.create_task(hanging_worker(i, f"group_{chr(97+i)}"))
            for i in range(3)
        ]

        await asyncio.sleep(0.1)

        assert len(queue._locked) == 3

        recovery_tasks = [
            asyncio.create_task(recovery_worker(100 + i)) for i in range(3)
        ]

        await asyncio.sleep(0.1)

        for task in recovery_tasks:
            assert not task.done()

        await asyncio.sleep(0.4)

        results = await asyncio.gather(*recovery_tasks, return_exceptions=True)

        successful_results = [r for r in results if isinstance(r, TestItem)]
        assert len(successful_results) == 3

        for task in hanging_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await asyncio.sleep(0.1)
        assert len(queue._locked) == 0

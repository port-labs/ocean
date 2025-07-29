import asyncio
import pytest
from dataclasses import dataclass
from port_ocean.core.handlers.queue.group_queue import GroupQueue


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
    def queue_with_group_key(self):
        """Create a GroupQueue with group_key='group_id'"""
        return GroupQueue(group_key="group_id", name="test_queue")

    @pytest.fixture
    def queue_no_group_key(self):
        """Create a GroupQueue without group_key (all items in same group)"""
        return GroupQueue(group_key=None, name="test_queue_no_group")

    @pytest.mark.asyncio
    async def test_basic_lock_mechanism(self, queue_with_group_key):
        """Test that getting an item locks the group"""
        queue = queue_with_group_key

        # Add items to the same group
        item1 = TestItem(group_id="group_a", value=1)
        item2 = TestItem(group_id="group_a", value=2)

        await queue.put(item1)
        await queue.put(item2)

        # Get first item - should lock group_a
        retrieved_item = await queue.get()
        assert retrieved_item == item1
        assert "group_a" in queue._locked

        # Check worker tracking (new implementation)
        worker_id = queue._get_worker_id()
        assert worker_id in queue._current_items
        assert queue._current_items[worker_id] == ("group_a", item1)
        assert queue._group_to_worker["group_a"] == worker_id

    @pytest.mark.asyncio
    async def test_locked_group_blocks_retrieval(self, queue_with_group_key):
        """Test that locked groups cannot have items retrieved"""
        queue = queue_with_group_key

        # Add multiple items to same group
        item1 = TestItem(group_id="group_a", value=1)
        item2 = TestItem(group_id="group_a", value=2)
        item3 = TestItem(group_id="group_b", value=3)

        await queue.put(item1)
        await queue.put(item2)
        await queue.put(item3)

        # Get first item from group_a
        retrieved_item1 = await queue.get()
        assert retrieved_item1 == item1
        assert "group_a" in queue._locked

        # Try to get another item - should get from group_b, not group_a
        retrieved_item2 = await queue.get()
        assert retrieved_item2 == item3  # From group_b
        assert "group_b" in queue._locked
        assert "group_a" in queue._locked  # group_a still locked

    @pytest.mark.asyncio
    async def test_commit_unlocks_group(self, queue_with_group_key):
        """Test that commit() unlocks the group and allows next item retrieval"""
        queue = queue_with_group_key

        item1 = TestItem(group_id="group_a", value=1)
        item2 = TestItem(group_id="group_a", value=2)

        await queue.put(item1)
        await queue.put(item2)

        # Get and commit first item
        retrieved_item1 = await queue.get()
        assert retrieved_item1 == item1
        assert "group_a" in queue._locked

        worker_id = queue._get_worker_id()
        await queue.commit()
        assert "group_a" not in queue._locked
        assert worker_id not in queue._current_items
        assert "group_a" not in queue._group_to_worker

        # Now we should be able to get the second item from group_a
        retrieved_item2 = await queue.get()
        assert retrieved_item2 == item2
        assert "group_a" in queue._locked

    @pytest.mark.asyncio
    async def test_multiple_groups_concurrent_processing(self, queue_with_group_key):
        """Test that different groups can be processed concurrently"""
        queue = queue_with_group_key

        # Add items to different groups
        item_a1 = TestItem(group_id="group_a", value=1)
        item_a2 = TestItem(group_id="group_a", value=2)
        item_b1 = TestItem(group_id="group_b", value=3)
        item_c1 = TestItem(group_id="group_c", value=4)

        await queue.put(item_a1)
        await queue.put(item_b1)
        await queue.put(item_c1)
        await queue.put(item_a2)

        # Should be able to get items from different groups
        retrieved_items = []
        for _ in range(3):  # Get 3 items from 3 different groups
            item = await queue.get()
            retrieved_items.append(item)

        # All three groups should be locked
        assert len(queue._locked) == 3
        assert "group_a" in queue._locked
        assert "group_b" in queue._locked
        assert "group_c" in queue._locked

        # Should have gotten one item from each group
        group_ids = [queue._extract_group_key(item) for item in retrieved_items]
        assert set(group_ids) == {"group_a", "group_b", "group_c"}

    @pytest.mark.asyncio
    async def test_get_blocks_when_all_groups_locked(self, queue_with_group_key):
        """Test that get() blocks when all available groups are locked"""
        queue = queue_with_group_key

        # Add items to single group
        item1 = TestItem(group_id="group_a", value=1)
        item2 = TestItem(group_id="group_a", value=2)

        await queue.put(item1)
        await queue.put(item2)

        # Get first item (locks group_a)
        await queue.get()
        assert "group_a" in queue._locked

        # Try to get second item - should block since group_a is locked
        # We'll use asyncio.wait_for with a short timeout to test this
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_no_group_key_single_group_behavior(self, queue_no_group_key):
        """Test behavior when group_key is None (all items in same group)"""
        queue = queue_no_group_key

        item1 = TestItemNoGroup(value=1)
        item2 = TestItemNoGroup(value=2)

        await queue.put(item1)
        await queue.put(item2)

        # Get first item
        retrieved_item1 = await queue.get()
        assert retrieved_item1 == item1
        assert None in queue._locked  # group key is None

        # Second get should block
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)

        # After commit, should be able to get second item
        await queue.commit()
        assert None not in queue._locked

        retrieved_item2 = await queue.get()
        assert retrieved_item2 == item2

    @pytest.mark.asyncio
    async def test_commit_without_get_is_safe(self, queue_with_group_key):
        """Test that calling commit() without get() doesn't break anything"""
        queue = queue_with_group_key

        # Should not raise any exceptions
        await queue.commit()
        assert len(queue._current_items) == 0
        assert len(queue._group_to_worker) == 0
        assert len(queue._locked) == 0

    @pytest.mark.asyncio
    async def test_multiple_commits_are_safe(self, queue_with_group_key):
        """Test that multiple commits after a single get are safe"""
        queue = queue_with_group_key

        item = TestItem(group_id="group_a", value=1)
        await queue.put(item)

        retrieved_item = await queue.get()
        assert retrieved_item == item

        # First commit
        await queue.commit()
        assert "group_a" not in queue._locked

        # Second commit should be safe
        await queue.commit()
        assert "group_a" not in queue._locked
        assert len(queue._current_items) == 0

    @pytest.mark.asyncio
    async def test_fifo_within_group(self, queue_with_group_key):
        """Test that items within a group are processed in FIFO order"""
        queue = queue_with_group_key

        # Add items to same group
        items = [TestItem(group_id="group_a", value=i) for i in range(5)]
        for item in items:
            await queue.put(item)

        # Process all items and verify FIFO order
        processed_items = []
        for _ in range(5):
            item = await queue.get()
            processed_items.append(item)
            await queue.commit()

        assert processed_items == items

    @pytest.mark.asyncio
    async def test_lock_prevents_queue_cleanup(self, queue_with_group_key):
        """Test that locked groups prevent queue cleanup until unlocked"""
        queue = queue_with_group_key

        item = TestItem(group_id="group_a", value=1)
        await queue.put(item)

        # Get item (locks group and keeps queue entry)
        await queue.get()
        assert "group_a" in queue._queues
        assert "group_a" in queue._locked

        # Commit should clean up empty queue
        await queue.commit()
        assert "group_a" not in queue._queues  # Queue cleaned up
        assert "group_a" not in queue._locked

    @pytest.mark.asyncio
    async def test_extract_group_key_missing_attribute(self, queue_with_group_key):
        """Test that missing group key attribute raises ValueError"""
        queue = queue_with_group_key

        # Item without group_id attribute
        bad_item = TestItemNoGroup(value=1)

        with pytest.raises(ValueError, match="lacks attribute 'group_id'"):
            await queue.put(bad_item)

    @pytest.mark.asyncio
    async def test_size_excludes_current_item(self, queue_with_group_key):
        """Test that size() excludes the currently processed item"""
        queue = queue_with_group_key

        items = [TestItem(group_id="group_a", value=i) for i in range(3)]
        for item in items:
            await queue.put(item)

        # Before get: size should be 3
        assert await queue.size() == 3

        # After get: size should be 2 (current item excluded)
        await queue.get()
        assert await queue.size() == 2

        # After commit: size should be 2 (item removed)
        await queue.commit()
        assert await queue.size() == 2

    # ===== CONCURRENT WORKER TESTS =====

    @pytest.mark.asyncio
    async def test_multiple_workers_different_groups(self, queue_with_group_key):
        """Test multiple workers processing items from different groups concurrently"""
        queue = queue_with_group_key
        processed_items = []
        processing_times = {}

        async def worker(worker_id: int, process_time: float = 0.1):
            """Simulate a worker that processes items"""
            try:
                item = await queue.get()
                start_time = asyncio.get_event_loop().time()

                # Record when processing started
                processing_times[item.value] = start_time
                processed_items.append((worker_id, item))

                # Simulate processing time
                await asyncio.sleep(process_time)

                await queue.commit()
                return item
            except Exception as e:
                return f"Worker {worker_id} error: {e}"

        # Add items from different groups
        items = [
            TestItem(group_id="group_a", value=1),
            TestItem(group_id="group_b", value=2),
            TestItem(group_id="group_c", value=3),
            TestItem(group_id="group_d", value=4),
        ]

        for item in items:
            await queue.put(item)

        # Start 4 workers concurrently
        results = await asyncio.gather(
            worker(1), worker(2), worker(3), worker(4), return_exceptions=True
        )

        # All workers should have succeeded
        assert len([r for r in results if isinstance(r, TestItem)]) == 4
        assert len(processed_items) == 4

        # All items should have been processed
        processed_values = {item.value for _, item in processed_items}
        assert processed_values == {1, 2, 3, 4}

        # With the fixed implementation, no groups should be locked after completion
        assert len(queue._locked) == 0
        assert len(queue._current_items) == 0
        assert len(queue._group_to_worker) == 0

    @pytest.mark.asyncio
    async def test_multiple_workers_same_group_exclusivity(self, queue_with_group_key):
        """Test that multiple workers cannot process items from same group concurrently"""
        queue = queue_with_group_key
        processing_log = []

        async def worker(worker_id: int, process_time: float = 0.2):
            """Worker that logs processing start and end times"""
            try:
                item = await queue.get()
                start_time = asyncio.get_event_loop().time()
                processing_log.append(("start", worker_id, item.value, start_time))

                # Simulate processing
                await asyncio.sleep(process_time)

                end_time = asyncio.get_event_loop().time()
                processing_log.append(("end", worker_id, item.value, end_time))

                await queue.commit()
                return item
            except Exception as e:
                return f"Worker {worker_id} error: {e}"

        # Add multiple items to the same group
        items = [TestItem(group_id="group_a", value=i) for i in range(4)]
        for item in items:
            await queue.put(item)

        # Start 4 workers - they should process items from group_a sequentially
        results = await asyncio.gather(
            worker(1), worker(2), worker(3), worker(4), return_exceptions=True
        )

        # All should succeed
        assert len([r for r in results if isinstance(r, TestItem)]) == 4

        # Verify sequential processing: no overlapping processing times for same group
        start_times = {}
        end_times = {}

        for event, worker_id, value, timestamp in processing_log:
            if event == "start":
                start_times[value] = timestamp
            else:
                end_times[value] = timestamp

        # Sort by start time to verify sequential processing
        sorted_items = sorted(start_times.items(), key=lambda x: x[1])

        # Verify no overlap: each item should start after the previous one ends
        for i in range(1, len(sorted_items)):
            current_value = sorted_items[i][0]
            previous_value = sorted_items[i - 1][0]

            current_start = start_times[current_value]
            previous_end = end_times[previous_value]

            # Current should start after previous ends (allowing small timing tolerance)
            assert (
                current_start >= previous_end - 0.01
            ), f"Item {current_value} started before item {previous_value} finished"

        # With fixed implementation, perfect cleanup
        assert len(queue._locked) == 0
        assert len(queue._current_items) == 0
        assert len(queue._group_to_worker) == 0

    @pytest.mark.asyncio
    async def test_mixed_groups_with_multiple_workers(self, queue_with_group_key):
        """Test workers processing mixed groups - some concurrent, some sequential"""
        queue = queue_with_group_key
        processing_events = []

        async def worker(worker_id: int):
            """Worker that tracks processing events"""
            try:
                item = await queue.get()
                group = queue._extract_group_key(item)

                start_time = asyncio.get_event_loop().time()
                processing_events.append(
                    ("start", worker_id, group, item.value, start_time)
                )

                # Variable processing time based on group
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

        # Add items: 3 to same group (sequential), 3 to different groups (concurrent)
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

        # Start 6 workers
        results = await asyncio.gather(
            *[worker(i) for i in range(1, 7)], return_exceptions=True
        )

        # All should succeed
        successful_results = [r for r in results if isinstance(r, TestItem)]
        assert len(successful_results) == 6

        # Group processing events by group
        group_events = {}
        for event in processing_events:
            _, worker_id, group, value, timestamp = event
            if group not in group_events:
                group_events[group] = []
            group_events[group].append(event)

        # Verify same_group items were processed sequentially
        same_group_events = sorted(group_events["same_group"], key=lambda x: x[4])
        starts = [e for e in same_group_events if e[0] == "start"]
        ends = [e for e in same_group_events if e[0] == "end"]

        # Each start should happen after previous end
        for i in range(1, len(starts)):
            assert starts[i][4] >= ends[i - 1][4] - 0.01

        # Perfect cleanup with fixed implementation
        assert len(queue._locked) == 0
        assert len(queue._current_items) == 0
        assert len(queue._group_to_worker) == 0

    @pytest.mark.asyncio
    async def test_high_concurrency_stress_test(self, queue_with_group_key):
        """Stress test with many workers and items"""
        queue = queue_with_group_key

        async def worker(worker_id: int):
            """Simple worker"""
            results = []
            while True:
                try:
                    # Use timeout to avoid infinite waiting
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                    results.append(item)

                    # Small random delay to simulate processing
                    await asyncio.sleep(0.01 + (worker_id % 3) * 0.01)

                    await queue.commit()
                except asyncio.TimeoutError:
                    break
                except Exception as e:
                    print(f"Worker {worker_id} error: {e}")
                    break
            return results

        # Add many items across multiple groups
        num_groups = 5
        items_per_group = 4

        for group_id in range(num_groups):
            for item_id in range(items_per_group):
                item = TestItem(
                    group_id=f"group_{group_id}", value=group_id * 100 + item_id
                )
                await queue.put(item)

        # Start many workers
        num_workers = 10
        results = await asyncio.gather(
            *[worker(i) for i in range(num_workers)], return_exceptions=True
        )

        # Collect all processed items
        all_processed = []
        for result in results:
            if isinstance(result, list):
                all_processed.extend(result)

        # Should have processed all items
        assert len(all_processed) == num_groups * items_per_group

        # Verify all items were processed exactly once
        processed_values = [item.value for item in all_processed]
        expected_values = [
            g * 100 + i for g in range(num_groups) for i in range(items_per_group)
        ]
        assert sorted(processed_values) == sorted(expected_values)

        # Perfect cleanup with fixed implementation
        assert len(queue._locked) == 0
        assert len(queue._current_items) == 0
        assert len(queue._group_to_worker) == 0
        assert await queue.size() == 0

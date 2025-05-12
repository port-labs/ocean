#!/usr/bin/env python3
"""
Memory leak test for JQ processing functionality.

This script tests the JQ compilation and execution functionality
for memory leaks without relying on the full Ocean context.
"""
import asyncio
import os
import time
import psutil
import json
import jq
import random
from typing import Dict, Any, List
import matplotlib.pyplot as plt
import numpy as np
from loguru import logger

# Configure logging
logger.add("memory_test.log", rotation="100 MB")


class JQMemoryLeakTester:
    """Tests JQ processing for memory leaks."""

    def __init__(self, iterations: int = 100000, data_size: int = 5000):
        """Initialize tester.

        Args:
            iterations: Number of test iterations to run
            data_size: Size of test dataset (number of items)
        """
        self.iterations = iterations
        self.data_size = data_size
        self.process = psutil.Process(os.getpid())
        self.memory_usage = []
        self.compiled_patterns = {}

    def compile(self, pattern: str) -> Any:
        """Compile a JQ pattern if not already compiled."""
        if pattern not in self.compiled_patterns:
            self.compiled_patterns[pattern] = jq.compile(pattern)
        return self.compiled_patterns[pattern]

    def generate_test_data(self) -> List[Dict[str, Any]]:
        """Generate test data with nested structures."""
        data = []

        # Create a variety of test data structures
        for i in range(self.data_size):
            # Randomly vary structure to test different JSON paths
            has_deep_nesting = random.random() > 0.3
            has_arrays = random.random() > 0.2
            has_mixed_types = random.random() > 0.5
            array_size = random.randint(1, 15)

            item = {
                "id": f"test-{i}",
                "name": f"Test Item {i}",
                "timestamp": time.time(),
                "properties": {
                    "value": i,
                    "enabled": i % 2 == 0,
                    "priority": random.choice(["low", "medium", "high"]),
                    "tags": [f"tag-{j}" for j in range(random.randint(0, 10))],
                },
                "metadata": {
                    "created_at": "2024-05-11T14:30:00Z",
                    "updated_at": "2024-05-11T15:45:00Z",
                    "version": f"1.{random.randint(0, 9)}.{random.randint(0, 99)}",
                    "is_active": random.choice([True, False]),
                },
            }

            # Add complex nested structure sometimes
            if has_deep_nesting:
                item["nested"] = {
                    "level1": {
                        "level2": {
                            "level3": {
                                "deep_value": f"deep-{i}",
                                "numbers": list(range(random.randint(0, 20))),
                                "flag": random.choice([True, False, None]),
                            }
                        }
                    }
                }

            # Add arrays of objects sometimes
            if has_arrays:
                item["array_of_objects"] = [
                    {
                        "key": f"key-{i}-{j}",
                        "value": f"value-{i}-{j}",
                        "score": random.randint(1, 100),
                        "valid": random.choice([True, False]),
                    }
                    for j in range(array_size)
                ]

            # Add mixed type fields sometimes
            if has_mixed_types:
                mixed_values = [
                    i,
                    str(i),
                    i % 2 == 0,
                    {"nested_key": i},
                    [1, 2, 3],
                    None,
                    [{"a": 1}, {"b": 2}],
                ]
                item["mixed_field"] = random.choice(mixed_values)

            # Add some conditionally present fields
            if i % 3 == 0:
                item["optional_field"] = "present"

            if i % 7 == 0:
                item["rare_field"] = {
                    "data": [random.random() for _ in range(5)],
                    "summary": {"min": 0, "max": 1},
                }

            data.append(item)

        return data

    def generate_jq_expressions(self) -> List[str]:
        """Generate a variety of JQ expressions to test."""
        # Simple field access
        basic_expressions = [
            ".id",
            ".name",
            ".properties.value",
            ".properties.enabled",
            ".metadata.version",
            ".timestamp",
        ]

        # Array operations with null checks
        array_expressions = [
            ".properties.tags // [] | length",
            "if .properties.tags then .properties.tags[] else empty end",
            ".properties.tags // [] | map(. | length) | add // 0",
            "if .array_of_objects then .array_of_objects[] | .key else empty end",
            "if .array_of_objects then .array_of_objects[] | select(.valid == true) | .score else null end",
            "if .array_of_objects then .array_of_objects | map(.score) | add else 0 end",
        ]

        # Conditional logic
        conditional_expressions = [
            "if .properties.enabled then .id else null end",
            "if .metadata.is_active and .properties.enabled then .name else .id end",
            '.properties | if .priority == "high" then .value else null end',
            '.properties | if .value > 100 then "high" elif .value > 50 then "medium" else "low" end',
        ]

        # Object transformation with null checks
        transformation_expressions = [
            ".properties | {value, enabled}",
            "{id: .id, tags: (.properties.tags // []), is_active: (.metadata.is_active // false)}",
            "if .array_of_objects then .array_of_objects[] | {item_key: .key, item_score: .score} else {} end",
            "if .nested then {deep: .nested.level1.level2.level3.deep_value} else {} end",
        ]

        # Complex multi-step operations with null checks
        complex_expressions = [
            ".properties.tags // [] | map(. | length) | add // 0",
            "if .array_of_objects then .array_of_objects[] | select(.valid // false) | .score | . * 2 else null end",
            "if .nested then .nested.level1.level2.level3.numbers // [] | map(. * 2) | add // 0 else 0 end",
            "{id: .id, count: (.properties.tags // [] | length), is_valid: ((.properties.enabled // false) and (.metadata.is_active // false))}",
            '[.id, .name, (.properties.value | tostring)] | join("-")',
        ]

        # Mix different types of expressions
        all_expressions = (
            basic_expressions
            + array_expressions
            + conditional_expressions
            + transformation_expressions
            + complex_expressions
        )

        return all_expressions

    def measure_memory(self) -> float:
        """Measure current memory usage in MB."""
        # gc.collect()  # Force garbage collection
        return self.process.memory_info().rss / (1024 * 1024)

    def stop_iterator_handler(self, func: Any) -> Any:
        """
        Wrap the function to handle StopIteration exceptions.
        Prevents StopIteration from stopping the thread and skipping further processing.
        """

        def inner() -> Any:
            try:
                return func()
            except StopIteration:
                return None

        return inner

    async def search(self, data: dict[str, Any], pattern: str) -> Any:
        """Search data using JQ pattern."""
        try:
            loop = asyncio.get_event_loop()
            compiled_pattern = self.compile(pattern)
            func = compiled_pattern.input_value(data)
            result = await loop.run_in_executor(
                None, self.stop_iterator_handler(func.first)
            )

            # Log the result (randomly sample 0.5% of results to avoid flooding logs)
            if random.random() < 0.005:
                result_preview = str(result)
                if len(result_preview) > 100:
                    result_preview = result_preview[:97] + "..."
                logger.info(f"JQ Pattern: '{pattern}' | Result: {result_preview}")

            return result
        except Exception as exc:
            logger.debug(
                f"Search failed for pattern '{pattern}' in data: {data}, Error: {exc}"
            )
            return None

    async def run_test(self):
        """Run the memory leak test."""
        logger.info(f"Starting memory leak test with {self.iterations} iterations")

        # Initialize test data
        test_data = self.generate_test_data()
        logger.info(f"Generated {len(test_data)} test data items")

        # Define test patterns
        patterns = self.generate_jq_expressions()
        logger.info(f"Using {len(patterns)} different JQ expressions")

        # Record initial memory
        initial_memory = self.measure_memory()
        self.memory_usage.append(initial_memory)
        logger.info(f"Initial memory usage: {initial_memory:.2f} MB")

        # Print pattern list for reference
        logger.info("JQ Patterns being tested:")
        for i, pattern in enumerate(patterns):
            logger.info(f"  {i+1}. {pattern}")

        # Run test iterations
        data_batch_size = min(10, len(test_data))

        for i in range(self.iterations):
            if i % 50 == 0:
                logger.info(f"Running iteration {i}/{self.iterations}")

            # Randomly select data items and patterns for each iteration
            selected_data = random.sample(test_data, data_batch_size)
            selected_patterns = random.sample(patterns, min(5, len(patterns)))

            for data_item in selected_data:
                for pattern in selected_patterns:
                    await self.search(data_item, pattern)

            # Measure and record memory
            memory = self.measure_memory()
            self.memory_usage.append(memory)

            if i % 50 == 0:
                logger.info(f"Memory usage at iteration {i}: {memory:.2f} MB")
                logger.info(
                    f"Compiled patterns cache size: {len(self.compiled_patterns)}"
                )

        # Final memory measurement
        final_memory = self.measure_memory()
        logger.info(f"Final memory usage: {final_memory:.2f} MB")
        logger.info(f"Memory difference: {final_memory - initial_memory:.2f} MB")
        logger.info(f"Final pattern cache size: {len(self.compiled_patterns)}")

        # Analyze results
        self.analyze_results()

    def analyze_results(self):
        """Analyze memory usage results and generate graphs."""
        # Save raw data
        with open("memory_test_results.json", "w") as f:
            json.dump(
                {
                    "iterations": list(range(len(self.memory_usage))),
                    "memory_usage": self.memory_usage,
                    "test_parameters": {
                        "iterations": self.iterations,
                        "data_size": self.data_size,
                        "compiled_patterns": len(self.compiled_patterns),
                    },
                },
                f,
            )

        # Plot memory usage
        plt.figure(figsize=(12, 6))
        plt.plot(range(len(self.memory_usage)), self.memory_usage)
        plt.title("JQ Processing Memory Usage")
        plt.xlabel("Iteration")
        plt.ylabel("Memory (MB)")
        plt.grid(True)
        plt.savefig("memory_usage.png")

        # Calculate trend line
        x = np.array(range(len(self.memory_usage)))
        y = np.array(self.memory_usage)
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)

        # Plot trend line
        plt.plot(x, p(x), "r--")
        plt.savefig("memory_usage_with_trend.png")

        logger.info(f"Memory trend: {z[0]:.6f} MB/iteration")
        if z[0] > 0.01:
            logger.warning("Potential memory leak detected! Positive growth trend")
        else:
            logger.info("No significant memory leak detected")


async def main():
    # Run more iterations for better trend analysis
    tester = JQMemoryLeakTester(iterations=10000, data_size=200)
    await tester.run_test()


if __name__ == "__main__":
    asyncio.run(main())

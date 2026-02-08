"""
Multi-session concurrency test for Claude Control.
Verifies that long-running requests don't block other requests.
"""
import asyncio
import aiohttp
import time
from datetime import datetime

BASE_URL = "http://localhost:8000/api"

async def create_session(session: aiohttp.ClientSession, name: str) -> dict:
    """Create a new session."""
    async with session.post(f"{BASE_URL}/sessions", json={"session_name": name}) as resp:
        return await resp.json()

async def execute_prompt(session: aiohttp.ClientSession, session_id: str, prompt: str, timeout: int = 300) -> dict:
    """Execute a prompt."""
    async with session.post(
        f"{BASE_URL}/sessions/{session_id}/execute",
        json={"prompt": prompt, "timeout": timeout},
        timeout=aiohttp.ClientTimeout(total=timeout + 30)
    ) as resp:
        return await resp.json()

async def check_health(session: aiohttp.ClientSession) -> dict:
    """Check server health."""
    async with session.get(f"{BASE_URL.replace('/api', '')}/health") as resp:
        return await resp.json()

async def list_sessions(session: aiohttp.ClientSession) -> list:
    """List all sessions."""
    async with session.get(f"{BASE_URL}/sessions") as resp:
        return await resp.json()

async def delete_session(session: aiohttp.ClientSession, session_id: str):
    """Delete a session."""
    async with session.delete(f"{BASE_URL}/sessions/{session_id}") as resp:
        return await resp.json()

def log(msg: str):
    """Print with timestamp."""
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}")

async def main():
    print("=" * 70)
    print("Claude Control - Multi-Session Concurrency Test")
    print("=" * 70)

    async with aiohttp.ClientSession() as http:
        # 1. Check server health
        log("Checking server health...")
        health = await check_health(http)
        log(f"Server status: {health['status']}")

        # 2. Create two sessions
        log("\nCreating two sessions...")
        session1 = await create_session(http, "slow-session")
        session2 = await create_session(http, "fast-session")
        log(f"Session 1 (slow): {session1['session_id'][:8]}...")
        log(f"Session 2 (fast): {session2['session_id'][:8]}...")

        # 3. Define tasks
        # Long-running task (takes 10+ seconds)
        long_prompt = """
        Please count from 1 to 100, explaining each number in detail.
        Take your time and be thorough about each number's properties:
        - Is it prime?
        - Is it even or odd?
        - What are its factors?
        - Any interesting mathematical properties?

        This is a test of long-running execution.
        """

        # Quick task
        quick_prompt = "What is 2+2? Answer with just the number."

        # 4. Run concurrent tests
        log("\n--- Test 1: Parallel execution across sessions ---")
        log("Starting long task in Session 1...")
        log("Starting quick task in Session 2 at the same time...")

        start_time = time.time()

        # Run both in parallel
        async def run_long():
            log("  [Session1] Long task started")
            result = await execute_prompt(http, session1['session_id'], long_prompt, timeout=120)
            elapsed = time.time() - start_time
            log(f"  [Session1] Long task COMPLETED in {elapsed:.1f}s - success={result.get('success')}")
            return result

        async def run_quick():
            log("  [Session2] Quick task started")
            result = await execute_prompt(http, session2['session_id'], quick_prompt, timeout=30)
            elapsed = time.time() - start_time
            log(f"  [Session2] Quick task COMPLETED in {elapsed:.1f}s - success={result.get('success')}")
            return result

        results = await asyncio.gather(run_long(), run_quick())

        long_result, quick_result = results
        total_time = time.time() - start_time

        log(f"\nTotal parallel execution time: {total_time:.1f}s")

        # 5. Check if quick task finished before long task
        # (This is implicit from the logs, but we verify both succeeded)
        log("\n--- Results Analysis ---")
        log(f"Long task success: {long_result.get('success')}")
        log(f"Quick task success: {quick_result.get('success')}")

        # 6. Test: Can we access API while execution is in progress?
        log("\n--- Test 2: API accessibility during execution ---")
        log("Starting long task in Session 1...")

        async def long_task():
            return await execute_prompt(http, session1['session_id'], long_prompt, timeout=120)

        async def check_api_periodically():
            """Check if API is responsive during long execution."""
            checks = []
            for i in range(5):
                await asyncio.sleep(1)
                start = time.time()
                try:
                    health = await check_health(http)
                    elapsed = (time.time() - start) * 1000
                    checks.append(elapsed)
                    log(f"  API check #{i+1}: {elapsed:.0f}ms - status={health['status']}")
                except Exception as e:
                    log(f"  API check #{i+1}: FAILED - {e}")
                    checks.append(-1)
            return checks

        long_task_coro = long_task()
        api_check_coro = check_api_periodically()

        _, api_results = await asyncio.gather(long_task_coro, api_check_coro)

        # 7. Analyze API responsiveness
        successful_checks = [r for r in api_results if r > 0]
        if successful_checks:
            avg_response_time = sum(successful_checks) / len(successful_checks)
            max_response_time = max(successful_checks)
            log(f"\nAPI Response Analysis:")
            log(f"  Successful checks: {len(successful_checks)}/5")
            log(f"  Average response time: {avg_response_time:.0f}ms")
            log(f"  Max response time: {max_response_time:.0f}ms")

            if avg_response_time < 500:
                log("  ✅ API remains responsive during long execution!")
            else:
                log("  ⚠️  API might be slightly slow during execution")
        else:
            log("  ❌ API was blocked during execution!")

        # 8. Cleanup
        log("\n--- Cleanup ---")
        await delete_session(http, session1['session_id'])
        await delete_session(http, session2['session_id'])
        log("Sessions deleted.")

        print("\n" + "=" * 70)
        print("Test complete!")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())

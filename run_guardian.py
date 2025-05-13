import asyncio
import sys
from pathlib import Path

# Add the project root to sys.path to allow imports from 'core'
# Assumes run_guardian.py is in the project root
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

try:
    from core.codebase_guardian import UnifiedGuardian
except ImportError as e:
    print(
        f"Error: Could not import UnifiedGuardian. Ensure you are in the project root and 'core' module is accessible."
    )
    print(f"Details: {e}")
    sys.exit(1)


async def main():
    print("Starting UnifiedGuardian independently...")
    guardian = UnifiedGuardian()
    try:
        await guardian.start()
    except KeyboardInterrupt:
        print("UnifiedGuardian stopped by user.")
    except Exception as e:
        print(f"An error occurred in UnifiedGuardian: {e}")
    finally:
        if hasattr(guardian, "observer") and guardian.observer.is_alive():
            guardian.observer.stop()
            guardian.observer.join()
        print("UnifiedGuardian has shut down.")


if __name__ == "__main__":
    asyncio.run(main())

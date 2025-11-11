#!/usr/bin/env python3
"""
Run the residency matching workflow using search keys only (no GPT).
"""

import asyncio
import os
import importlib.util

service_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "residency_matching_service_search_only.py")

spec = importlib.util.spec_from_file_location("residency_matching_service_search_only", service_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Unable to load residency_matching_service_search_only from {service_path}")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)  # type: ignore[arg-type]
ResidencyMatchingServiceSearchOnly = module.ResidencyMatchingService


async def main():
    print("🚀 Starting Residency Matching Process (Search Keys Only)")
    print("=" * 50)
    print("⏳ Initializing service...")
    try:
        service = ResidencyMatchingServiceSearchOnly()
        print("✅ Service initialized. Running search-key matching...")
        await service.match_all_residencies()
        print("\n✅ Residency matching (search keys only) completed successfully!")
    except Exception as exc:
        print(f"\n❌ Error during residency matching: {exc}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())

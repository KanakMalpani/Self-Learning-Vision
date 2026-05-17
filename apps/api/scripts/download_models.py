from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.model_assets import insightface_health


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or download optional Self-Learning Vision models.")
    parser.add_argument("--provider", choices=["insightface"], default="insightface")
    parser.add_argument("--model", default="buffalo_l")
    parser.add_argument("--cache-dir", default=os.getenv("MODEL_CACHE_DIR", "./data/models"))
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)

    if args.download:
        cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            from insightface.app import FaceAnalysis
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "provider": args.provider,
                        "status": "optional_dependency_missing",
                        "detail": f"Install production provider extras first: {exc}",
                    },
                    indent=2,
                )
            )
            return 2
        analyzer = FaceAnalysis(name=args.model, root=str(cache_dir), providers=["CPUExecutionProvider"])
        analyzer.prepare(ctx_id=-1, det_size=(640, 640))

    health = insightface_health(str(cache_dir), args.model)
    print(
        json.dumps(
            {
                "provider": health.provider_id,
                "ready": health.ready,
                "status": health.status,
                "detail": health.detail,
                "model_cache_dir": health.model_cache_dir,
                "optional_dependencies": health.optional_dependencies,
            },
            indent=2,
        )
    )
    return 0 if health.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())

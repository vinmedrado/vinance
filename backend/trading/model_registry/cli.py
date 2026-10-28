from __future__ import annotations

import argparse
import json

from .service import PromotionStatus, get_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Trading V2 model promotion registry")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    subparsers.add_parser("check")
    promote = subparsers.add_parser("promote")
    promote.add_argument("model_id")
    promote.add_argument("status", choices=[item.value for item in PromotionStatus])
    promote.add_argument("--validation-run-id")
    promote.add_argument("--approved-by", required=True)
    args = parser.parse_args()
    registry = get_registry()
    if args.command == "list":
        result = [entry.public_dict() for entry in registry.list()]
    elif args.command == "check":
        result = registry.health()
    else:
        result = registry.promote(
            model_id=args.model_id,
            status=PromotionStatus(args.status),
            validation_run_id=args.validation_run_id,
            approved_by=args.approved_by,
        )
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

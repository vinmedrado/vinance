from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable, Mapping, Sequence


ENGINE_VERSION = "household-financial-state-v1"
STALE_AFTER_DAYS = 45
MONEY_QUANTUM = Decimal("0.01")
RATIO_QUANTUM = Decimal("0.01")


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _money(value: Decimal | None) -> Decimal | None:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP) if value is not None else None


def _ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return ((numerator / denominator) * Decimal("100")).quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _sum_amounts(records: Sequence[Mapping[str, Any]], field: str) -> Decimal | None:
    if not records:
        return None
    values = [_decimal(record.get(field)) for record in records]
    if any(value is None for value in values):
        return None
    return _money(sum((value for value in values if value is not None), Decimal("0")))


def _month_records(
    records: Sequence[Mapping[str, Any]], field: str, as_of: date
) -> list[Mapping[str, Any]]:
    return [
        record
        for record in records
        if (record_date := _as_date(record.get(field))) is not None
        and record_date.year == as_of.year
        and record_date.month == as_of.month
    ]


def _is_stale(value: Any, *, evaluated_at: datetime) -> bool:
    observed = _as_datetime(value)
    if observed is None:
        observed_date = _as_date(value)
        if observed_date is None:
            return False
        observed = datetime.combine(observed_date, datetime.min.time(), tzinfo=timezone.utc)
    return (evaluated_at - observed).days > STALE_AFTER_DAYS


def _dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _valid_records(
    records: Sequence[Mapping[str, Any]],
    *,
    household_id: int,
    active_member_ids: set[int],
    known_member_ids: set[int],
    domain: str,
    inconsistencies: list[str],
) -> list[Mapping[str, Any]]:
    valid: list[Mapping[str, Any]] = []
    for record in records:
        record_id = record.get("id", "unknown")
        try:
            record_household_id = int(record.get("household_id"))
            user_id = int(record.get("user_id"))
        except (TypeError, ValueError):
            inconsistencies.append(f"{domain}.{record_id}.invalid_owner")
            continue
        scope = str(record.get("ownership_scope", "")).upper()
        if record_household_id != household_id:
            inconsistencies.append(f"{domain}.{record_id}.household_mismatch")
            continue
        if scope not in {"PERSONAL", "HOUSEHOLD"}:
            inconsistencies.append(f"{domain}.{record_id}.invalid_ownership_scope")
            continue
        if scope == "PERSONAL" and user_id not in active_member_ids:
            if user_id not in known_member_ids:
                inconsistencies.append(f"{domain}.{record_id}.owner_not_member")
            continue
        if scope == "HOUSEHOLD" and user_id not in known_member_ids:
            inconsistencies.append(f"{domain}.{record_id}.recorder_not_member")
            continue
        valid.append(record)
    return valid


def _profile_by_user(profiles: Sequence[Mapping[str, Any]]) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for profile in profiles:
        try:
            result[int(profile["user_id"])] = profile
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _recurring_income(
    incomes: Sequence[Mapping[str, Any]],
    profiles: Sequence[Mapping[str, Any]],
    member_ids: set[int],
    *,
    missing: list[str],
    provenance: dict[str, Any],
) -> Decimal | None:
    personal = [item for item in incomes if item.get("ownership_scope") == "PERSONAL" and item.get("is_recurring")]
    shared = [item for item in incomes if item.get("ownership_scope") == "HOUSEHOLD" and item.get("is_recurring")]
    profile_map = _profile_by_user(profiles)
    values: list[Decimal] = []
    fallback_users: list[int] = []
    missing_member_income = False

    for user_id in sorted(member_ids):
        owned = [item for item in personal if int(item["user_id"]) == user_id]
        if owned:
            value = _sum_amounts(owned, "amount")
        else:
            profile = profile_map.get(user_id)
            value = _decimal(profile.get("monthly_salary")) if profile else None
            if value is not None:
                fallback_users.append(user_id)
        if value is None:
            missing.append(f"members.{user_id}.recurring_income")
            missing_member_income = True
        else:
            values.append(value)

    if shared:
        shared_value = _sum_amounts(shared, "amount")
        if shared_value is None:
            missing.append("income.shared.amount")
        else:
            values.append(shared_value)

    provenance["recurring_monthly_income"] = {
        "primary": "incomes",
        "financial_profile_fallback_user_ids": fallback_users,
    }
    if missing_member_income or not values:
        return None
    return _money(sum(values, Decimal("0")))


def _expense_metrics(
    expenses: Sequence[Mapping[str, Any]], missing: list[str]
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    total = _sum_amounts(expenses, "amount")
    if not expenses:
        missing.append("expenses.monthly")
        return None, None, None
    if total is None:
        missing.append("expenses.amount")
        return None, None, None
    unknown_nature = [item for item in expenses if item.get("expense_nature") not in {"FIXED", "VARIABLE"}]
    if unknown_nature:
        missing.extend(f"expenses.{item.get('id', 'unknown')}.expense_nature" for item in unknown_nature)
        return None, None, total
    fixed_records = [item for item in expenses if item["expense_nature"] == "FIXED"]
    variable_records = [item for item in expenses if item["expense_nature"] == "VARIABLE"]
    fixed = _sum_amounts(fixed_records, "amount")
    variable = _sum_amounts(variable_records, "amount")
    if not fixed_records:
        missing.append("expenses.fixed")
    if not variable_records:
        missing.append("expenses.variable")
    return fixed, variable, total


def _asset_metrics(
    assets: Sequence[Mapping[str, Any]],
    profiles: Sequence[Mapping[str, Any]],
    member_ids: set[int],
    *,
    missing: list[str],
    inconsistencies: list[str],
    provenance: dict[str, Any],
) -> tuple[Decimal | None, Decimal | None, dict[str, dict[str, Decimal | None]] | None]:
    active = [item for item in assets if item.get("status", "ACTIVE") == "ACTIVE"]
    profile_map = _profile_by_user(profiles)
    effective_assets = list(active)
    fallback_users: list[int] = []
    for user_id in sorted(member_ids):
        personal_reserve_assets = [
            item
            for item in active
            if item.get("ownership_scope") == "PERSONAL"
            and int(item["user_id"]) == user_id
            and item.get("asset_class") == "EMERGENCY_RESERVE"
        ]
        if personal_reserve_assets:
            continue
        profile = profile_map.get(user_id)
        value = _decimal(profile.get("emergency_reserve")) if profile else None
        if value is None:
            missing.append(f"members.{user_id}.assets")
        else:
            effective_assets.append(
                {
                    "id": f"profile-{user_id}",
                    "user_id": user_id,
                    "ownership_scope": "PERSONAL",
                    "asset_class": "EMERGENCY_RESERVE",
                    "current_value": value,
                }
            )
            fallback_users.append(user_id)

    if not effective_assets:
        missing.append("assets.current_value")
        missing.append("assets.emergency_reserve")
        return None, None, None

    unknown = [item for item in effective_assets if _decimal(item.get("current_value")) is None]
    missing.extend(f"assets.{item.get('id', 'unknown')}.current_value" for item in unknown)
    inconsistencies.extend(
        f"assets.{item.get('id', 'unknown')}.negative_current_value"
        for item in effective_assets
        if (value := _decimal(item.get("current_value"))) is not None and value < 0
    )
    total_assets = _sum_amounts(effective_assets, "current_value")
    by_class: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for item in effective_assets:
        value = _decimal(item.get("current_value"))
        if value is not None:
            by_class[str(item.get("asset_class", "OTHER"))] += value
    distribution = {
        asset_class: {
            "amount": _money(amount),
            "percentage": _ratio(amount, total_assets),
        }
        for asset_class, amount in sorted(by_class.items())
    }
    reserve_records = [item for item in effective_assets if item.get("asset_class") == "EMERGENCY_RESERVE"]
    emergency_reserve = _sum_amounts(reserve_records, "current_value") if reserve_records else None
    if emergency_reserve is None:
        missing.append("assets.emergency_reserve")
    provenance["total_assets"] = {
        "primary": "owned_assets" if active else "financial_profiles.emergency_reserve",
        "financial_profile_fallback_user_ids": fallback_users,
    }
    provenance["emergency_reserve"] = {
        "primary": "owned_assets" if any(item.get("asset_class") == "EMERGENCY_RESERVE" for item in active) else "financial_profiles.emergency_reserve",
        "financial_profile_fallback_user_ids": fallback_users,
    }
    return total_assets, emergency_reserve, distribution


def _liability_metrics(
    liabilities: Sequence[Mapping[str, Any]], missing: list[str], inconsistencies: list[str]
) -> tuple[Decimal | None, Decimal | None]:
    if not liabilities:
        missing.extend(["liabilities.current_balance", "liabilities.monthly_payment"])
        return None, None
    active = [item for item in liabilities if item.get("status", "ACTIVE") in {"ACTIVE", "DEFAULTED"}]
    for item in liabilities:
        balance = _decimal(item.get("current_balance"))
        payment = _decimal(item.get("monthly_payment"))
        if balance is not None and balance < 0:
            inconsistencies.append(f"liabilities.{item.get('id', 'unknown')}.negative_balance")
        if payment is not None and payment < 0:
            inconsistencies.append(f"liabilities.{item.get('id', 'unknown')}.negative_payment")
        if item.get("status") == "PAID" and balance is not None and balance > 0:
            inconsistencies.append(f"liabilities.{item.get('id', 'unknown')}.paid_with_balance")
    if not active:
        return Decimal("0.00"), Decimal("0.00")
    unknown_balance = [item for item in active if _decimal(item.get("current_balance")) is None]
    unknown_payment = [item for item in active if _decimal(item.get("monthly_payment")) is None]
    missing.extend(f"liabilities.{item.get('id', 'unknown')}.current_balance" for item in unknown_balance)
    missing.extend(f"liabilities.{item.get('id', 'unknown')}.monthly_payment" for item in unknown_payment)
    return _sum_amounts(active, "current_balance"), _sum_amounts(active, "monthly_payment")


def _goal_views(
    goals: Sequence[Mapping[str, Any]], missing: list[str], inconsistencies: list[str]
) -> list[dict[str, Any]]:
    if not goals:
        missing.append("goals")
        return []
    result: list[dict[str, Any]] = []
    for item in goals:
        target = _decimal(item.get("target_amount"))
        current = _decimal(item.get("current_amount"))
        if target is None or target <= 0:
            inconsistencies.append(f"goals.{item.get('id', 'unknown')}.invalid_target_amount")
        if current is None:
            missing.append(f"goals.{item.get('id', 'unknown')}.current_amount")
            gap = None
        elif current < 0:
            inconsistencies.append(f"goals.{item.get('id', 'unknown')}.negative_current_amount")
            gap = None
        elif target is None:
            gap = None
        else:
            gap = _money(max(target - current, Decimal("0")))
        result.append(
            {
                "id": item.get("id"),
                "user_id": item.get("user_id"),
                "ownership_scope": item.get("ownership_scope"),
                "name": item.get("name"),
                "target_amount": _money(target),
                "current_amount": _money(current),
                "funding_gap": gap,
                "deadline": _as_date(item.get("deadline")),
                "priority": item.get("priority"),
                "status": item.get("status"),
            }
        )
    return result


def _calculate_metrics(
    *,
    incomes: Sequence[Mapping[str, Any]],
    expenses: Sequence[Mapping[str, Any]],
    liabilities: Sequence[Mapping[str, Any]],
    assets: Sequence[Mapping[str, Any]],
    goals: Sequence[Mapping[str, Any]],
    profiles: Sequence[Mapping[str, Any]],
    member_ids: set[int],
    missing: list[str],
    inconsistencies: list[str],
    provenance: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inconsistencies.extend(
        f"incomes.{item.get('id', 'unknown')}.negative_amount"
        for item in incomes
        if (value := _decimal(item.get("amount"))) is not None and value < 0
    )
    inconsistencies.extend(
        f"expenses.{item.get('id', 'unknown')}.negative_amount"
        for item in expenses
        if (value := _decimal(item.get("amount"))) is not None and value < 0
    )
    recurring = _recurring_income(incomes, profiles, member_ids, missing=missing, provenance=provenance)
    if incomes:
        non_recurring_records = [item for item in incomes if not item.get("is_recurring")]
        non_recurring = _sum_amounts(non_recurring_records, "amount")
        if not non_recurring_records:
            missing.append("income.non_recurring")
    else:
        non_recurring = None
        missing.append("income.non_recurring")
    fixed, variable, total_expenses = _expense_metrics(expenses, missing)
    total_assets, reserve, distribution = _asset_metrics(
        assets,
        profiles,
        member_ids,
        missing=missing,
        inconsistencies=inconsistencies,
        provenance=provenance,
    )
    total_liabilities, debt_service = _liability_metrics(liabilities, missing, inconsistencies)
    goals_view = _goal_views(goals, missing, inconsistencies)

    total_income = _money(recurring + non_recurring) if recurring is not None and non_recurring is not None else None
    cash_flow = _money(total_income - total_expenses) if total_income is not None and total_expenses is not None else None
    disposable = _money(recurring - total_expenses) if recurring is not None and total_expenses is not None else None
    savings_capacity = _money(max(disposable, Decimal("0"))) if disposable is not None else None
    investment_capacity = (
        _money(max(disposable - debt_service, Decimal("0")))
        if disposable is not None and debt_service is not None
        else None
    )
    net_worth = _money(total_assets - total_liabilities) if total_assets is not None and total_liabilities is not None else None
    reserve_months = (
        (reserve / total_expenses).quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)
        if reserve is not None and total_expenses is not None and total_expenses > 0
        else None
    )
    debt_to_income = _ratio(
        total_liabilities,
        _money(recurring * Decimal("12")) if recurring is not None else None,
    )
    debt_service_ratio = _ratio(debt_service, recurring)
    savings_rate = _ratio(savings_capacity, recurring)

    return (
        {
            "recurring_monthly_income": recurring,
            "non_recurring_income": non_recurring,
            "total_income": total_income,
            "fixed_expenses": fixed,
            "variable_expenses": variable,
            "total_expenses": total_expenses,
            "cash_flow": cash_flow,
            "disposable_income": disposable,
            "savings_capacity": savings_capacity,
            "investment_capacity": investment_capacity,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "net_worth": net_worth,
            "emergency_reserve": reserve,
            "emergency_reserve_months": reserve_months,
            "monthly_debt_service": debt_service,
            "debt_to_income": debt_to_income,
            "debt_service_ratio": debt_service_ratio,
            "savings_rate": savings_rate,
            "asset_distribution": distribution,
        },
        goals_view,
    )


def _stale_fields(
    *,
    incomes: Sequence[Mapping[str, Any]],
    expenses: Sequence[Mapping[str, Any]],
    liabilities: Sequence[Mapping[str, Any]],
    assets: Sequence[Mapping[str, Any]],
    profiles: Sequence[Mapping[str, Any]],
    provenance: Mapping[str, Any],
    evaluated_at: datetime,
) -> list[str]:
    stale: list[str] = []
    month = evaluated_at.date()
    transactional_checks = (
        ("incomes", incomes, "received_at"),
        ("expenses", expenses, "due_date"),
    )
    for domain, records, field in transactional_checks:
        current = _month_records(records, field, month)
        observed_dates = [_as_date(item.get(field)) for item in records]
        latest = max((item for item in observed_dates if item is not None), default=None)
        if records and not current and latest is not None and _is_stale(latest, evaluated_at=evaluated_at):
            stale.append(domain)

    point_in_time_checks = (
        ("liabilities", liabilities, ("balance_as_of", "updated_at")),
        ("assets", assets, ("value_as_of", "updated_at")),
    )
    for domain, records, fields in point_in_time_checks:
        for item in records:
            observed = next((item.get(field) for field in fields if item.get(field) is not None), None)
            if observed is not None and _is_stale(observed, evaluated_at=evaluated_at):
                stale.append(f"{domain}.{item.get('id', 'unknown')}")

    fallback_users = set()
    for field in ("recurring_monthly_income", "total_assets", "emergency_reserve"):
        fallback_users.update(provenance.get(field, {}).get("financial_profile_fallback_user_ids", []))
    for profile in profiles:
        if profile.get("user_id") in fallback_users and _is_stale(profile.get("updated_at"), evaluated_at=evaluated_at):
            stale.append(f"financial_profiles.{profile.get('id', 'unknown')}")
    return _dedupe(stale)


def _confidence(metrics: Mapping[str, Any], goals: Sequence[Mapping[str, Any]], *, stale: bool, inconsistent: bool) -> int:
    weights = {
        "recurring_monthly_income": 15,
        "non_recurring_income": 5,
        "fixed_expenses": 7,
        "variable_expenses": 7,
        "total_expenses": 10,
        "total_assets": 15,
        "total_liabilities": 15,
        "emergency_reserve": 10,
        "monthly_debt_service": 8,
    }
    score = sum(weight for field, weight in weights.items() if metrics.get(field) is not None)
    if goals and all(item.get("current_amount") is not None for item in goals):
        score += 8
    if stale:
        score -= 15
    if inconsistent:
        score -= 25
    return max(0, min(100, score))


def calculate_financial_state(
    normalized_inputs: dict[str, Any], *, evaluated_at: datetime | None = None
) -> dict[str, Any]:
    """Calculate an auditable household state without manufacturing missing values.

    The function is deterministic for the same normalized inputs and ``evaluated_at``.
    It never reads the database, mutates its input, recommends investments, or invokes
    any market/trading component.
    """

    evaluated = evaluated_at or datetime.now(timezone.utc)
    if evaluated.tzinfo is None:
        evaluated = evaluated.replace(tzinfo=timezone.utc)
    evaluated = evaluated.astimezone(timezone.utc)
    data = deepcopy(normalized_inputs)
    household = data.get("household") or {}
    try:
        household_id = int(household["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("normalized_inputs.household.id is required") from exc

    inconsistencies: list[str] = []
    known_members: list[dict[str, Any]] = []
    for raw_member in list(data.get("members") or []):
        try:
            user_id = int(raw_member["user_id"])
        except (KeyError, TypeError, ValueError):
            inconsistencies.append("members.invalid_user_id")
            continue
        member = dict(raw_member)
        member["user_id"] = user_id
        known_members.append(member)
    members = [
        item for item in known_members if str(item.get("status", "ACTIVE")) == "ACTIVE"
    ]
    member_ids = {item["user_id"] for item in members}
    known_member_ids = {item["user_id"] for item in known_members}
    if not member_ids:
        raise ValueError("at least one active household member is required")

    incomes = _valid_records(
        list(data.get("incomes") or []),
        household_id=household_id,
        active_member_ids=member_ids,
        known_member_ids=known_member_ids,
        domain="incomes",
        inconsistencies=inconsistencies,
    )
    expenses = _valid_records(
        list(data.get("expenses") or []),
        household_id=household_id,
        active_member_ids=member_ids,
        known_member_ids=known_member_ids,
        domain="expenses",
        inconsistencies=inconsistencies,
    )
    liabilities = _valid_records(
        list(data.get("liabilities") or []),
        household_id=household_id,
        active_member_ids=member_ids,
        known_member_ids=known_member_ids,
        domain="liabilities",
        inconsistencies=inconsistencies,
    )
    assets = _valid_records(
        list(data.get("assets") or []),
        household_id=household_id,
        active_member_ids=member_ids,
        known_member_ids=known_member_ids,
        domain="assets",
        inconsistencies=inconsistencies,
    )
    goals = _valid_records(
        list(data.get("goals") or []),
        household_id=household_id,
        active_member_ids=member_ids,
        known_member_ids=known_member_ids,
        domain="goals",
        inconsistencies=inconsistencies,
    )
    profiles: list[dict[str, Any]] = []
    for raw_profile in list(data.get("financial_profiles") or []):
        try:
            profile_user_id = int(raw_profile["user_id"])
        except (KeyError, TypeError, ValueError):
            inconsistencies.append("financial_profiles.invalid_user_id")
            continue
        if profile_user_id in member_ids:
            profile = dict(raw_profile)
            profile["user_id"] = profile_user_id
            profiles.append(profile)

    month_incomes = _month_records(incomes, "received_at", evaluated.date())
    month_expenses = _month_records(expenses, "due_date", evaluated.date())
    missing: list[str] = []
    provenance: dict[str, Any] = {}
    metrics, goals_view = _calculate_metrics(
        incomes=month_incomes,
        expenses=month_expenses,
        liabilities=liabilities,
        assets=assets,
        goals=goals,
        profiles=profiles,
        member_ids=member_ids,
        missing=missing,
        inconsistencies=inconsistencies,
        provenance=provenance,
    )

    stale_fields = _stale_fields(
        incomes=incomes,
        expenses=expenses,
        liabilities=liabilities,
        assets=assets,
        profiles=profiles,
        provenance=provenance,
        evaluated_at=evaluated,
    )
    member_views: list[dict[str, Any]] = []
    profile_map = _profile_by_user(profiles)
    for member in sorted(members, key=lambda item: int(item.get("user_id", 0))):
        user_id = int(member["user_id"])
        member_missing: list[str] = []
        member_inconsistencies: list[str] = []
        member_provenance: dict[str, Any] = {}
        member_metrics, member_goals = _calculate_metrics(
            incomes=[item for item in month_incomes if item.get("ownership_scope") == "PERSONAL" and int(item["user_id"]) == user_id],
            expenses=[item for item in month_expenses if item.get("ownership_scope") == "PERSONAL" and int(item["user_id"]) == user_id],
            liabilities=[item for item in liabilities if item.get("ownership_scope") == "PERSONAL" and int(item["user_id"]) == user_id],
            assets=[item for item in assets if item.get("ownership_scope") == "PERSONAL" and int(item["user_id"]) == user_id],
            goals=[item for item in goals if item.get("ownership_scope") == "PERSONAL" and int(item["user_id"]) == user_id],
            profiles=[profile_map[user_id]] if user_id in profile_map else [],
            member_ids={user_id},
            missing=member_missing,
            inconsistencies=member_inconsistencies,
            provenance=member_provenance,
        )
        member_views.append(
            {
                "user_id": user_id,
                "full_name": member.get("full_name"),
                "metrics": member_metrics,
                "goals": member_goals,
                "missing_fields": _dedupe(member_missing),
                "inconsistencies": _dedupe(member_inconsistencies),
                "provenance": member_provenance,
            }
        )

    missing_fields = _dedupe(missing)
    inconsistencies = _dedupe(inconsistencies)
    core_fields = ("recurring_monthly_income", "total_expenses", "total_assets", "total_liabilities")
    known_core = sum(metrics[field] is not None for field in core_fields)
    if inconsistencies:
        quality = "INCONSISTENT"
    elif known_core < 2:
        quality = "INSUFFICIENT"
    elif stale_fields:
        quality = "STALE"
    elif missing_fields:
        quality = "PARTIAL"
    else:
        quality = "COMPLETE"

    return {
        "household_id": household_id,
        "engine_version": ENGINE_VERSION,
        "evaluated_at": evaluated,
        "metrics": metrics,
        "goals": goals_view,
        "member_views": member_views,
        "data_quality": quality,
        "confidence": _confidence(
            metrics,
            goals_view,
            stale=bool(stale_fields),
            inconsistent=bool(inconsistencies),
        ),
        "missing_fields": missing_fields,
        "inconsistencies": inconsistencies,
        "stale_fields": stale_fields,
        "provenance": provenance,
    }

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EntityResult:
    entity: str
    status: str
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_skipped: int = 0
    error: str | None = None


@dataclass
class PipelineSummary:
    pipeline_name: str
    dry_run: bool = False
    items: list[EntityResult] = field(default_factory=list)

    def add(self, result: EntityResult) -> None:
        self.items.append(result)

    @property
    def total_processados(self) -> int:
        return len(self.items)

    @property
    def total_sucesso(self) -> int:
        return sum(1 for item in self.items if item.status == 'success')

    @property
    def total_falhas(self) -> int:
        return sum(1 for item in self.items if item.status == 'failed')

    @property
    def total_ignorados(self) -> int:
        return sum(1 for item in self.items if item.status == 'skipped')

    @property
    def rows_inserted(self) -> int:
        return sum(item.rows_inserted for item in self.items)

    @property
    def rows_updated(self) -> int:
        return sum(item.rows_updated for item in self.items)

    @property
    def rows_skipped(self) -> int:
        return sum(item.rows_skipped for item in self.items)

    def errors(self) -> list[str]:
        return [f'{item.entity}: {item.error}' for item in self.items if item.error]

    def status(self) -> str:
        if self.total_falhas == 0:
            return 'DRY_RUN' if self.dry_run else 'SUCCESS'
        if self.total_sucesso > 0 or self.total_ignorados > 0:
            return 'PARTIAL_SUCCESS'
        return 'ERROR'

    def as_dict(self) -> dict[str, Any]:
        return {
            'pipeline_name': self.pipeline_name,
            'status': self.status(),
            'dry_run': self.dry_run,
            'rows_inserted': self.rows_inserted,
            'rows_updated': self.rows_updated,
            'rows_skipped': self.rows_skipped,
            'total_processados': self.total_processados,
            'total_sucesso': self.total_sucesso,
            'total_falhas': self.total_falhas,
            'total_ignorados': self.total_ignorados,
            'errors': self.errors(),
            'items': [item.__dict__ for item in self.items],
        }


def print_summary(result: dict[str, Any]) -> None:
    print('\n' + '=' * 80)
    print(f"PIPELINE: {result.get('pipeline_name')}")
    print(f"STATUS: {result.get('status')} | DRY_RUN: {result.get('dry_run')}")
    if result.get('total_assets_loaded') is not None:
        print(f"Ativos carregados: {result.get('total_assets_loaded')} | filtro asset_class: {result.get('asset_class_filter')}")
    print('-' * 80)
    for item in result.get('items', []):
        err = f" | erro={item.get('error')}" if item.get('error') else ''
        print(
            f"{item.get('entity')} | {item.get('status')} | "
            f"inserted={item.get('rows_inserted', 0)} | "
            f"updated={item.get('rows_updated', 0)} | "
            f"skipped={item.get('rows_skipped', 0)}{err}"
        )
    print('-' * 80)
    print(
        f"Resumo: processados={result.get('total_processados')} | "
        f"sucesso={result.get('total_sucesso')} | "
        f"falhas={result.get('total_falhas')} | "
        f"ignorados={result.get('total_ignorados')} | "
        f"rows_inserted={result.get('rows_inserted')}"
    )
    print('=' * 80)

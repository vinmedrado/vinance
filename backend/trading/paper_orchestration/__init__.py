"""Manual, Paper-only orchestration over the canonical Trading V2 engines."""

from .service import ManualPaperOrchestrator, SignalPlan, build_signal_plan

__all__ = ["ManualPaperOrchestrator", "SignalPlan", "build_signal_plan"]

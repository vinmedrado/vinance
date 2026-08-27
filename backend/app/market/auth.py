"""Integração obrigatória com autenticação existente do FinanceOS.

Ajuste este import caso o projeto use outro caminho, mas não crie fallback inseguro.
"""
from backend.app.auth.dependencies import get_current_user

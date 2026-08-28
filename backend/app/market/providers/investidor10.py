import logging
import random
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import unicodedata
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://investidor10.com.br"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

logger = logging.getLogger(__name__)



class Investidor10Provider:
    def __init__(self, delay_min=1.2, delay_max=2.8, retries=2, timeout=12):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.retries = retries
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def sleep(self):
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    @staticmethod
    def clean_text(text: Optional[str]) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    @staticmethod
    def normalize_string(value):
        if value is None:
            return None

        value = str(value).strip()
        value = unicodedata.normalize("NFKD", value)
        value = value.encode("ascii", "ignore").decode("utf-8")
        value = re.sub(r"\s+", " ", value)

        return value.strip().title()

    @classmethod
    def extract(cls, pattern: str, text: str, flags=re.I | re.DOTALL) -> Optional[str]:
        match = re.search(pattern, text, flags)
        return cls.clean_text(match.group(1)) if match else None

    @staticmethod
    def br_number_to_float(value):
        if value is None:
            return None

        value = str(value).replace("R$", "").replace("US$", "").replace("%", "").strip()
        value = value.replace(".", "").replace(",", ".")
        value = re.sub(r"[^\d.-]", "", value)

        if value in ("", ".", "-", "-."):
            return None

        return float(value)

    @classmethod
    def br_money_to_float(cls, value):
        if value is None:
            return None

        raw = str(value).strip().upper()
        multiplier = 1

        if "TRILH" in raw or " T" in raw or raw.endswith("T"):
            multiplier = 1_000_000_000_000
        elif "BILH" in raw or " BI" in raw or raw.endswith("B"):
            multiplier = 1_000_000_000
        elif "MILH" in raw or " M" in raw or raw.endswith("M"):
            multiplier = 1_000_000
        elif "K" in raw:
            multiplier = 1_000

        number = cls.br_number_to_float(raw)
        return number * multiplier if number is not None else None

    @staticmethod
    def to_int(value):
        if value is None:
            return None

        value = re.sub(r"[^\d]", "", str(value))
        return int(value) if value else None

    def fetch_html(self, path: str):
        url = f"{BASE_URL}{path}"
        last_error = None

        blocked_terms = [
            "Attention Required",
            "Cloudflare",
            "Sorry, you have been blocked",
        ]

        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.encoding = "utf-8"

                # Erro permanente: não faz sentido repetir.
                if response.status_code == 410:
                    raise RuntimeError("HTTP 410")

                if response.status_code == 404:
                    raise RuntimeError("HTTP 404")

                # Erro temporário: pode tentar novamente.
                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = RuntimeError(f"HTTP {response.status_code}")

                    if attempt < self.retries:
                        time.sleep(min(2 * attempt, 6))
                        continue

                    raise last_error

                if response.status_code != 200:
                    raise RuntimeError(f"HTTP {response.status_code}")

                html = response.text

                # Bloqueio não deve ficar insistindo em loop.
                if any(term in html for term in blocked_terms):
                    raise RuntimeError("Bloqueado por proteção do site")

                return html, url

            except requests.exceptions.Timeout as e:
                last_error = e

                if attempt < self.retries:
                    time.sleep(min(2 * attempt, 6))
                    continue

            except requests.exceptions.RequestException as e:
                last_error = e

                if attempt < self.retries:
                    time.sleep(min(2 * attempt, 6))
                    continue

            except RuntimeError as e:
                last_error = e
                msg = str(e)

                # 410/404/bloqueio não precisam de retry.
                if "HTTP 410" in msg or "HTTP 404" in msg or "Bloqueado" in msg:
                    break

                if attempt < self.retries:
                    time.sleep(min(2 * attempt, 6))
                    continue

        raise RuntimeError(f"Falha ao buscar {url}: {last_error}")

    def soup_and_text(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        full_text = self.clean_text(" ".join(soup.stripped_strings))
        return soup, full_text

    def extract_name(self, soup, ticker: str, market_label: str):
        title_tag = soup.find("title")
        desc_tag = soup.find("meta", attrs={"name": "description"})

        title = self.clean_text(title_tag.get_text()) if title_tag else ""
        description = desc_tag.get("content", "") if desc_tag else ""

        name = None

        if market_label == "FII":
            name = self.extract(r"fundo imobiliário\s+(.*?)\s+-\s+FII", description)

        elif market_label == "ACAO":
            if title:
                parts = [p.strip() for p in title.split(" - ")]

                if len(parts) >= 2:
                    name = parts[1]
                else:
                    name = title.replace(ticker.upper(), "").strip()

        if not name and title:
            name = title.split(" - ")[0]
            name = name.replace(f"{ticker.upper()} FII", "").strip()
            name = name.replace(ticker.upper(), "").strip()

        return self.normalize_string(name) if name else None

    def scrape_fii(self, ticker: str):
        ticker = ticker.upper()

        html, url = self.fetch_html(f"/fiis/{ticker.lower()}/")
        soup, full_text = self.soup_and_text(html)

        raw = {
            "ticker": ticker,
            "name": self.extract_name(soup, ticker, "FII"),
            "mercado": "FII",
            "url": url,

            "valor_atual": (
                self.extract(r"VALOR ATUAL\s*R\$\s*([\d.,]+)", full_text)
                or self.extract(r"COTAÇÃO\s*R\$\s*([\d.,]+)", full_text)
                or self.extract(r"R\$\s*([\d.,]+)\s*VALOR ATUAL", full_text)
                or self.extract(r"R\$\s*([\d.,]+)", full_text)
            ),

            "patrimonio": self.extract(
                r"patrimônio de\s*R\$\s*([\d.,]+\s*(?:Milhões|Bilhões|milhões|bilhões|M|B))",
                full_text,
            ),

            "p_vp": (
                self.extract(rf"{ticker}\s+P/VP\s*:\s*([\d,]+)", full_text)
                or self.extract(r"P/VP\s+([\d,]+)", full_text)
            ),

            "ultimo_rendimento": (
                self.extract(r"ÚLTIMO RENDIMENTO\s*R\$\s*([\d.,]+)", full_text)
                or self.extract(r"último rendimento.*?R\$\s*([\d.,]+)", full_text)
            ),

            "dividend_yield": (
                self.extract(r"Dividend Yield de\s*([\d,]+)%", full_text)
                or self.extract(r"Dividend Yield\s+([\d,]+)%", full_text)
            ),

            "dividendos_12m": self.extract(
                r"distribuiu\s+R\$\s*([\d,]+)\s+em dividendos",
                full_text,
            ),

            "proximo_rendimento": self.extract(
                r"Próximo rendimento.*?R\$\s*([\d.,]+)",
                full_text,
            ),

            "data_proximo_rendimento": self.extract(
                r"Data do próximo rendimento.*?(\d{2}/\d{2}/\d{4})",
                full_text,
            ),

            "numero_cotistas": (
                self.extract(r"NUMERO DE COTISTAS\s+([\d.]+)", full_text)
                or self.extract(r"NÚMERO DE COTISTAS\s+([\d.]+)", full_text)
            ),

            "valorizacao_12m": self.extract(r"variação de\s*([\d,]+)%", full_text),

            "taxa_administracao": (
                self.extract(r"cobra\s+([\d,]+)%\s*a\.a", full_text)
                or self.extract(r"taxa de administração de aproximadamente\s+([\d,]+)%", full_text)
            ),

            "liquidez_diaria": self.extract(
                r"Liquidez Diária\s*R\$\s*([\d.,]+\s*[KMB]?)",
                full_text,
            ),

            "segmento": self.extract(r"SEGMENTO\s+([A-Za-zÀ-ÿ]+)", full_text),

            "tipo_gestao": self.extract(r"TIPO DE GESTÃO\s+([A-Za-zÀ-ÿ]+)", full_text),

            "vacancia": self.extract(r"VACÂNCIA\s+([\d,]+%)", full_text),

            "data_processado": datetime.now().date().isoformat(),
            "source": "INVESTIDOR10",
        }

        raw["segmento"] = self.normalize_string(raw["segmento"])
        raw["tipo_gestao"] = self.normalize_string(raw["tipo_gestao"])

        normalized = {
            **raw,

            "valor_atual_num": self.br_number_to_float(raw["valor_atual"]),
            "patrimonio_num": self.br_money_to_float(raw["patrimonio"]),
            "p_vp_num": self.br_number_to_float(raw["p_vp"]),
            "ultimo_rendimento_num": self.br_number_to_float(raw["ultimo_rendimento"]),
            "dividend_yield_num": self.br_number_to_float(raw["dividend_yield"]),
            "dividendos_12m_num": self.br_number_to_float(raw["dividendos_12m"]),
            "proximo_rendimento_num": self.br_number_to_float(raw["proximo_rendimento"]),
            "numero_cotistas_num": self.to_int(raw["numero_cotistas"]),
            "valorizacao_12m_num": self.br_number_to_float(raw["valorizacao_12m"]),
            "taxa_administracao_num": self.br_number_to_float(raw["taxa_administracao"]),
            "liquidez_diaria_num": self.br_money_to_float(raw["liquidez_diaria"]),
            "vacancia_num": self.br_number_to_float(raw["vacancia"]),
        }

        return normalized

    @staticmethod
    def tipo_erro(msg):
        """Classifica erros do Investidor10 em categorias estáveis para observabilidade."""
        msg = str(msg or "").lower()

        if "http 410" in msg:
            return "410_REMOVIDO"
        if "http 404" in msg or "ativo não encontrado" in msg or "ativo nao encontrado" in msg:
            return "404_NAO_ENCONTRADO"
        if "http 429" in msg or "rate limit" in msg:
            return "429_RATE_LIMIT"
        if "timeout" in msg or "timed out" in msg:
            return "TIMEOUT"
        if "cloudflare" in msg or "bloqueado" in msg or "attention required" in msg:
            return "BLOQUEIO"
        if "could not convert" in msg or "invalid literal" in msg:
            return "PARSE_NUM"
        if "none" in msg and "attribute" in msg:
            return "HTML_INESPERADO"
        if "connection" in msg or "remote disconnected" in msg:
            return "CONEXAO"
        if "falha ao buscar" in msg:
            return "FETCH"

        return "OUTRO"

    @classmethod
    def classify_error(cls, error):
        return cls.tipo_erro(error)

    @staticmethod
    def _normalize_mercado(mercado: str) -> str:
        mercado_normalizado = str(mercado or "").strip().upper()
        aliases = {
            "FII": "FIIS",
            "FIIS": "FIIS",
            "ACAO": "ACOES",
            "AÇÃO": "ACOES",
            "ACOES": "ACOES",
            "AÇÕES": "ACOES",
            "ETF": "ETF",
            "ETFS": "ETF",
            "BDR": "BDR",
            "BDRS": "BDR",
        }
        if mercado_normalizado not in aliases:
            raise ValueError(f"Mercado inválido: {mercado}")
        return aliases[mercado_normalizado]

    def _scrape_by_market(self, mercado: str, ticker: str):
        if mercado == "FIIS":
            return self.scrape_fii(ticker)
        if mercado == "ACOES":
            return self.scrape_acao(ticker)
        if mercado == "ETF":
            return self.scrape_etf(ticker)
        if mercado == "BDR":
            return self.scrape_bdr(ticker)
        raise ValueError(f"Mercado inválido: {mercado}")

    def _execute_ticker(self, mercado: str, ticker: str):
        jitter = {
            "FIIS": (0.20, 0.80),
            "ACOES": (0.25, 0.90),
            "ETF": (0.40, 1.20),
            "BDR": (0.80, 1.80),
        }.get(mercado, (0.30, 1.00))
        time.sleep(random.uniform(*jitter))

        started = time.perf_counter()
        try:
            data = self._scrape_by_market(mercado, ticker)
            segundos = time.perf_counter() - started
            return {
                "ok": True,
                "mercado": mercado,
                "ticker": ticker,
                "segundos": segundos,
                "data": data,
                "erro": None,
                "tipo_erro": None,
            }
        except Exception as exc:  # noqa: BLE001 - provider must isolate per-asset failures
            segundos = time.perf_counter() - started
            erro = str(exc)
            return {
                "ok": False,
                "mercado": mercado,
                "ticker": ticker,
                "segundos": segundos,
                "data": None,
                "erro": erro,
                "tipo_erro": self.classify_error(erro),
            }

    def scrape_many(self, mercado: str, tickers: list[str], workers: int | None = None) -> dict:
        mercado_normalizado = self._normalize_mercado(mercado)
        clean_tickers = []
        seen = set()
        for ticker in tickers or []:
            clean = str(ticker or "").strip().upper()
            if clean and clean not in seen:
                clean_tickers.append(clean)
                seen.add(clean)

        started = time.perf_counter()
        default_workers = {
            "FIIS": 2,
            "ACOES": 2,
            "ETF": 2,
            "BDR": 1,
        }
        selected_workers = int(workers or default_workers[mercado_normalizado])
        selected_workers = max(1, selected_workers)

        if not clean_tickers:
            return {
                "mercado": mercado_normalizado,
                "ativos": 0,
                "ok": 0,
                "erros": 0,
                "sucesso_pct": 0.0,
                "tempo_segundos": 0.0,
                "ativos_por_min": 0.0,
                "workers": selected_workers,
                "results": [],
                "errors": [],
            }

        logger.info(
            "Investidor10 scrape_many started",
            extra={"mercado": mercado_normalizado, "ativos": len(clean_tickers), "workers": selected_workers},
        )

        results = []
        errors = []
        errors_by_type = Counter()

        with ThreadPoolExecutor(max_workers=selected_workers) as executor:
            futures = {
                executor.submit(self._execute_ticker, mercado_normalizado, ticker): ticker
                for ticker in clean_tickers
            }
            for future in as_completed(futures):
                result = future.result()
                if result["ok"]:
                    results.append(result["data"])
                    logger.info(
                        "Investidor10 ticker scraped",
                        extra={
                            "mercado": mercado_normalizado,
                            "ticker": result["ticker"],
                            "segundos": round(result["segundos"], 3),
                        },
                    )
                else:
                    errors_by_type[result["tipo_erro"]] += 1
                    error_item = {
                        "mercado": mercado_normalizado,
                        "ticker": result["ticker"],
                        "tipo_erro": result["tipo_erro"],
                        "erro": result["erro"],
                        "segundos": round(result["segundos"], 3),
                        "processado_em": datetime.now().isoformat(),
                    }
                    errors.append(error_item)
                    logger.warning("Investidor10 ticker failed", extra=error_item)

        elapsed = time.perf_counter() - started
        total = len(clean_tickers)
        ok = len(results)
        erros = len(errors)
        sucesso_pct = (ok / max(total, 1)) * 100
        ativos_por_min = (total / elapsed) * 60 if elapsed > 0 else 0.0

        logger.info(
            "Investidor10 scrape_many finished",
            extra={
                "mercado": mercado_normalizado,
                "ativos": total,
                "ok": ok,
                "erros": erros,
                "sucesso_pct": round(sucesso_pct, 2),
                "tempo_segundos": round(elapsed, 3),
                "ativos_por_min": round(ativos_por_min, 2),
                "errors_by_type": dict(errors_by_type),
            },
        )

        return {
            "mercado": mercado_normalizado,
            "ativos": total,
            "ok": ok,
            "erros": erros,
            "sucesso_pct": sucesso_pct,
            "tempo_segundos": elapsed,
            "ativos_por_min": ativos_por_min,
            "workers": selected_workers,
            "results": results,
            "errors": errors,
        }

    def scrape_many_fiis(self, tickers):
        results = []
        errors = []

        for index, ticker in enumerate(tickers, start=1):
            try:
                print(f"[{index}/{len(tickers)}] Buscando {ticker}...")
                data = self.scrape_fii(ticker)
                results.append(data)

            except Exception as e:
                print(f"Erro em {ticker}: {e}")
                errors.append({
                    "ticker": ticker,
                    "error": str(e),
                    "processed_at": datetime.now().isoformat(),
                })

            self.sleep()

        return results, errors

    def scrape_acao(self, ticker: str):
        ticker = ticker.upper()

        html, url = self.fetch_html(f"/acoes/{ticker.lower()}/")
        soup, full_text = self.soup_and_text(html)
        last_dividend = self.extract_last_dividend_stock(full_text)

        raw = {
            "ticker": ticker,
            "name": self.extract_name(soup, ticker, "ACAO"),
            "mercado": "ACAO",
            "url": url,

            "valor_atual": (
                self.extract(r"VALOR ATUAL\s*R\$\s*([\d.,]+)", full_text)
                or self.extract(r"COTAÇÃO\s*R\$\s*([\d.,]+)", full_text)
                or self.extract(r"R\$\s*([\d.,]+)\s*VALOR ATUAL", full_text)
                or self.extract(r"R\$\s*([\d.,]+)", full_text)
            ),

            "dividend_yield": (
                self.extract(r"Dividend Yield de\s*([\d,]+)%", full_text)
                or self.extract(r"Dividend Yield\s+([\d,]+)%", full_text)
                or self.extract(r"DY\s+([\d,]+)%", full_text)
            ),

            "p_l": (
                self.extract(r"P/L\s+([\d,.-]+)", full_text)
                or self.extract(r"PREÇO/LUCRO\s+([\d,.-]+)", full_text)
            ),

            "lpa": (
                self.extract(r"LPA\s+R?\$?\s*([\d,.-]+)", full_text)
                or self.extract(r"LUCRO POR AÇÃO\s+R?\$?\s*([\d,.-]+)", full_text)
            ),

            "p_vp": (
                self.extract(r"P/VP\s+([\d,.-]+)", full_text)
                or self.extract(r"P/VPA\s+([\d,.-]+)", full_text)
            ),

            "roe": self.extract(r"ROE\s+([\d,.-]+%)", full_text),

            "roic": self.extract(r"ROIC\s+([\d,.-]+%)", full_text),

            "valor_mercado": (
                self.extract(r"VALOR DE MERCADO\s*R\$\s*([\d.,]+\s*(?:Milhões|Bilhões|milhões|bilhões|M|B)?)", full_text)
                or self.extract(r"Valor de mercado\s*R\$\s*([\d.,]+\s*(?:Milhões|Bilhões|milhões|bilhões|M|B)?)", full_text)
            ),

            "patrimonio_liquido": (
                self.extract(r"PATRIMÔNIO LÍQUIDO\s*R\$\s*([\d.,]+\s*(?:Milhões|Bilhões|milhões|bilhões|M|B)?)", full_text)
                or self.extract(r"Patrimônio Líquido\s*R\$\s*([\d.,]+\s*(?:Milhões|Bilhões|milhões|bilhões|M|B)?)", full_text)
            ),


            "ultimo_dividendo": last_dividend["ultimo_dividendo"],
            "data_com_ultimo_dividendo": last_dividend["data_com_ultimo_dividendo"],
            "data_pagamento_ultimo_dividendo": last_dividend["data_pagamento_ultimo_dividendo"],

            "valorizacao_12m": self.extract(r"variação de\s*([\d,.-]+)%", full_text),

            "liquidez_media_diaria": (
                self.extract(r"Liquidez Média Diária\s*R\$\s*([\d.,]+\s*[KMB]?)", full_text)
                or self.extract(r"Liquidez Diária\s*R\$\s*([\d.,]+\s*[KMB]?)", full_text)
            ),

            "margem_bruta": self.extract(r"MARGEM BRUTA\s+([\d,.-]+%)", full_text),
            "margem_ebit": self.extract(r"MARGEM EBIT\s+([\d,.-]+%)", full_text),
            "margem_liquida": self.extract(r"MARGEM LÍQUIDA\s+([\d,.-]+%)", full_text),

            "divida_liquida": self.extract(
                r"DÍVIDA LÍQUIDA\s*R\$\s*([\d.,]+\s*(?:Milhões|Bilhões|milhões|bilhões|M|B)?)",
                full_text,
            ),

            "divida_liquida_ebitda": self.extract(r"Dívida Líquida / Ebitda\s+([\d,.-]+)", full_text),
            "ev_ebitda": self.extract(r"EV/EBITDA\s+([\d,.-]+)", full_text),
            "psr": self.extract(r"P/Receita\s*\(PSR\)\s*([\d,.-]+)", full_text),
            "p_ativo": self.extract(r"P/ATIVO\s+([\d,.-]+)", full_text),
            "p_ebit": self.extract(r"P/EBIT\s+([\d,.-]+)", full_text),

            "cagr_receita_5a": self.extract(r"CAGR Receitas 5 anos\s+([\d,.-]+%)", full_text),
            "cagr_lucro_5a": self.extract(r"CAGR Lucros 5 anos\s+([\d,.-]+%)", full_text),

            "setor": None,
            "subsetor": None,
            "segmento": None,

            "data_processado": datetime.now().date().isoformat(),
            "source": "INVESTIDOR10",
        }

        for field in ["name", "setor", "subsetor", "segmento"]:
            raw[field] = self.normalize_string(raw[field])

        normalized = {
            **raw,

            "valor_atual_num": self.br_number_to_float(raw["valor_atual"]),
            "dividend_yield_num": self.br_number_to_float(raw["dividend_yield"]),
            "p_l_num": self.br_number_to_float(raw["p_l"]),
            "lpa_num": self.br_number_to_float(raw["lpa"]),
            "p_vp_num": self.br_number_to_float(raw["p_vp"]),
            "roe_num": self.br_number_to_float(raw["roe"]),
            "roic_num": self.br_number_to_float(raw["roic"]),
            "valor_mercado_num": self.br_money_to_float(raw["valor_mercado"]),
            "patrimonio_liquido_num": self.br_money_to_float(raw["patrimonio_liquido"]),
            "ultimo_dividendo_num": self.br_number_to_float(raw["ultimo_dividendo"]),
            "valorizacao_12m_num": self.br_number_to_float(raw["valorizacao_12m"]),
            "liquidez_media_diaria_num": self.br_money_to_float(raw["liquidez_media_diaria"]),
            "margem_bruta_num": self.br_number_to_float(raw["margem_bruta"]),
            "margem_ebit_num": self.br_number_to_float(raw["margem_ebit"]),
            "margem_liquida_num": self.br_number_to_float(raw["margem_liquida"]),
            "divida_liquida_num": self.br_money_to_float(raw["divida_liquida"]),
            "divida_liquida_ebitda_num": self.br_number_to_float(raw["divida_liquida_ebitda"]),
            "ev_ebitda_num": self.br_number_to_float(raw["ev_ebitda"]),
            "psr_num": self.br_number_to_float(raw["psr"]),
            "p_ativo_num": self.br_number_to_float(raw["p_ativo"]),
            "p_ebit_num": self.br_number_to_float(raw["p_ebit"]),
            "cagr_receita_5a_num": self.br_number_to_float(raw["cagr_receita_5a"]),
            "cagr_lucro_5a_num": self.br_number_to_float(raw["cagr_lucro_5a"]),
        }

        return normalized

    def extract_last_dividend_stock(self, full_text):
        matches = re.findall(
        r"(Dividendos|JCP|Juros Sobre Capital Próprio)\s+"
        r"(\d{2}/\d{2}/\d{4})\s+"
        r"(\d{2}/\d{2}/\d{4})\s+"
        r"([\d,]+)",
        full_text,
        re.I,
        )

        if not matches:
            return {
                "ultimo_dividendo": None,
                "data_com_ultimo_dividendo": None,
                "data_pagamento_ultimo_dividendo": None,
            }

        validos = []

        for tipo, data_com, data_pag, valor in matches:
            try:
                data_pag_obj = datetime.strptime(data_pag, "%d/%m/%Y")

                # ignora datas futuras absurdas
                if data_pag_obj <= datetime.now():
                    validos.append({
                        "tipo": tipo,
                        "data_com": data_com,
                        "data_pagamento": data_pag,
                        "valor": valor,
                        "data_obj": data_pag_obj,
                    })

            except:
                pass

        if not validos:
            return {
                "ultimo_dividendo": None,
                "data_com_ultimo_dividendo": None,
                "data_pagamento_ultimo_dividendo": None,
            }

        # pega o mais recente
        validos.sort(key=lambda x: x["data_obj"], reverse=True)

        ultimo = validos[0]

        return {
            "ultimo_dividendo": ultimo["valor"],
            "data_com_ultimo_dividendo": ultimo["data_com"],
            "data_pagamento_ultimo_dividendo": ultimo["data_pagamento"],
        }

    def scrape_many_acoes(self, tickers):
        results = []
        errors = []

        for index, ticker in enumerate(tickers, start=1):
            try:
                print(f"[{index}/{len(tickers)}] Buscando {ticker}...")
                data = self.scrape_acao(ticker)
                results.append(data)

            except Exception as e:
                print(f"Erro em {ticker}: {e}")
                errors.append({
                    "ticker": ticker,
                    "error": str(e),
                    "processed_at": datetime.now().isoformat(),
                })

            self.sleep()

        return results, errors

    def extract_rentabilidade_table(self, soup):
        target = None

        for div in soup.find_all("div", class_=lambda c: c and "tw-overflow-hidden" in c):
            text = self.clean_text(" ".join(div.stripped_strings))

            if "rentabilidade" in text.lower() and "rentabilidade real" in text.lower():
                target = text
                break

        if not target:
            return {
                "rentabilidade_1m": None,
                "rentabilidade_3m": None,
                "rentabilidade_1a": None,
                "rentabilidade_2a": None,
                "rentabilidade_5a": None,
                "rentabilidade_10a": None,
            }

        # remove a parte de rentabilidade real para pegar só a primeira linha
        target = target.split("rentabilidade real")[0]

        valores = re.findall(r"-?[\d.]*,\d+%", target)

        if len(valores) < 6:
            return {
                "rentabilidade_1m": None,
                "rentabilidade_3m": None,
                "rentabilidade_1a": None,
                "rentabilidade_2a": None,
                "rentabilidade_5a": None,
                "rentabilidade_10a": None,
            }

        return {
            "rentabilidade_1m": valores[0],
            "rentabilidade_3m": valores[1],
            "rentabilidade_1a": valores[2],
            "rentabilidade_2a": valores[3],
            "rentabilidade_5a": valores[4],
            "rentabilidade_10a": valores[5],
        }


    def scrape_bdr(self, ticker: str):
        ticker = ticker.upper()

        html, url = self.fetch_html(f"/bdrs/{ticker.lower()}/")
        soup, full_text = self.soup_and_text(html)

        valor_mercado_card = self.extract_card_simple_value(soup, "Valor de mercado")
        patrimonio_card = self.extract_card_simple_value(soup, "Patrimônio Líquido")

        rentabilidade = self.extract_rentabilidade_table(soup)

        title = self.clean_text(soup.title.text) if soup.title else ""
        name = None

        if title:
            parts = [p.strip() for p in title.split(" - ")]
            name = parts[1] if len(parts) >= 2 else title.replace(ticker, "").strip()
            name = self.normalize_string(name)

        raw = {
            "ticker": ticker,
            "name": name,
            "mercado": "BDR",
            "url": url,

            "preco_atual": (
                self.extract(r"VALOR ATUAL\s*R\$\s*([\d.,]+)", full_text)
                or self.extract(r"COTAÇÃO\s*R\$\s*([\d.,]+)", full_text)
                or self.extract(r"R\$\s*([\d.,]+)\s*VALOR ATUAL", full_text)
                or self.extract(r"R\$\s*([\d.,]+)", full_text)
            ),

            "rentabilidade_1m": rentabilidade["rentabilidade_1m"],
            "rentabilidade_3m": rentabilidade["rentabilidade_3m"],
            "rentabilidade_1a": rentabilidade["rentabilidade_1a"],
            "rentabilidade_2a": rentabilidade["rentabilidade_2a"],
            "rentabilidade_5a": rentabilidade["rentabilidade_5a"],
            "rentabilidade_10a": rentabilidade["rentabilidade_10a"],


            "dividend_yield": (
                self.extract(r"Dividend Yield\s*([\d,.-]+%)", full_text)
                or self.extract(r"DY\s*([\d,.-]+%)", full_text)
            ),

            "p_vpa": (
                self.extract(r"P/VPA\s+([\d,.-]+)", full_text)
                or self.extract(r"P/VP\s+([\d,.-]+)", full_text)
            ),

            "patrimonio_liquido": patrimonio_card,

            "valor_mercado": valor_mercado_card,

            "p_l": (
                self.extract(r"P/L\s+([\d,.-]+)", full_text)
                or self.extract(r"PREÇO/LUCRO\s+([\d,.-]+)", full_text)
            ),

            "lpa": (
                self.extract(r"LPA\s+R?\$?\s*([\d,.-]+)", full_text)
                or self.extract(r"LUCRO POR AÇÃO\s+R?\$?\s*([\d,.-]+)", full_text)
            ),

            "roe": self.extract(r"ROE\s+([\d,.-]+%)", full_text),
            "roic": self.extract(r"ROIC\s+([\d,.-]+%)", full_text),

            "margem_bruta": self.extract(r"MARGEM BRUTA\s+([\d,.-]+%)", full_text),
            "margem_ebit": self.extract(r"MARGEM OPERACIONAL\s+([\d,.-]+%)", full_text),
            "margem_liquida": self.extract(r"MARGEM LÍQUIDA\s+([\d,.-]+%)", full_text),

            "ev_ebitda": self.extract(r"P/EBITDA\s+([\d,.-]+)", full_text),
            "psr": self.extract(r"P/Receita\s*\(PSR\)\s*([\d,.-]+)", full_text),
            "p_ativo": self.extract(r"P/ATIVO\s+([\d,.-]+)", full_text),
            "p_ebit": self.extract(r"P/EBIT\s+([\d,.-]+)", full_text),

            "cagr_receita_5a": self.extract(r"CAGR Receitas 5 anos\s+([\d,.-]+%)", full_text),
            "cagr_lucro_5a": self.extract(r"CAGR Lucros 5 anos\s+([\d,.-]+%)", full_text),

            "volatilidade": self.extract(r"Volatilidade\s*([\d,.-]+%)", full_text),
            "score": self.extract(r"Score\s*([\d,.-]+)", full_text),
            "tendencia": self.extract(r"Tendência\s*([A-Za-zÀ-ÿ ]+)", full_text),

            "liquidez_media_diaria": (
                self.extract(r"Liquidez Média Diária\s*R\$\s*([\d.,]+\s*[KMB]?)", full_text)
                or self.extract(r"Liquidez Diária\s*R\$\s*([\d.,]+\s*[KMB]?)", full_text)
            ),

            "setor": None,
            "subsetor": None,
            "pais_origem": None,
            "moeda": "BRL",

            "data_processado": datetime.now().date().isoformat(),
            "source": "INVESTIDOR10",
        }

        normalized = {
            **raw,

            "preco_atual_num": self.br_number_to_float(raw["preco_atual"]),

            "rentabilidade_1m_num": self.br_number_to_float(raw["rentabilidade_1m"]),
            "rentabilidade_3m_num": self.br_number_to_float(raw["rentabilidade_3m"]),
            "rentabilidade_1a_num": self.br_number_to_float(raw["rentabilidade_1a"]),
            "rentabilidade_2a_num": self.br_number_to_float(raw["rentabilidade_2a"]),
            "rentabilidade_5a_num": self.br_number_to_float(raw["rentabilidade_5a"]),
            "rentabilidade_10a_num": self.br_number_to_float(raw["rentabilidade_10a"]),

            "dividend_yield_num": self.br_number_to_float(raw["dividend_yield"]),
            "p_vpa_num": self.br_number_to_float(raw["p_vpa"]),
            "patrimonio_liquido_num": self.br_money_to_float(raw["patrimonio_liquido"]),
            "valor_mercado_num": self.br_money_to_float(raw["valor_mercado"]),

            "p_l_num": self.br_number_to_float(raw["p_l"]),
            "lpa_num": self.br_number_to_float(raw["lpa"]),
            "roe_num": self.br_number_to_float(raw["roe"]),
            "roic_num": self.br_number_to_float(raw["roic"]),

            "margem_bruta_num": self.br_number_to_float(raw["margem_bruta"]),
            "margem_ebit_num": self.br_number_to_float(raw["margem_ebit"]),
            "margem_liquida_num": self.br_number_to_float(raw["margem_liquida"]),

            "ev_ebitda_num": self.br_number_to_float(raw["ev_ebitda"]),
            "psr_num": self.br_number_to_float(raw["psr"]),
            "p_ativo_num": self.br_number_to_float(raw["p_ativo"]),
            "p_ebit_num": self.br_number_to_float(raw["p_ebit"]),

            "cagr_receita_5a_num": self.br_number_to_float(raw["cagr_receita_5a"]),
            "cagr_lucro_5a_num": self.br_number_to_float(raw["cagr_lucro_5a"]),

            "volatilidade_num": self.br_number_to_float(raw["volatilidade"]),
            "score_num": self.br_number_to_float(raw["score"]),
            "liquidez_media_diaria_num": self.br_money_to_float(raw["liquidez_media_diaria"]),
        }

        return normalized

    def extract_card_simple_value(self, soup, title):
        for cell in soup.find_all("div", class_="cell"):
            title_el = cell.find("span", class_="title")
            if not title_el:
                continue

            cell_title = self.clean_text(title_el.get_text(" ", strip=True)).lower()

            if cell_title == title.lower():
                simple = cell.find("div", class_="simple-value")
                if simple:
                    return self.clean_text(simple.get_text(" ", strip=True))

        return None

    def scrape_many_bdrs(self, tickers):
        results = []
        errors = []

        for index, ticker in enumerate(tickers, start=1):
            try:
                print(f"[{index}/{len(tickers)}] Buscando {ticker}...")
                data = self.scrape_bdr(ticker)
                results.append(data)

            except Exception as e:
                print(f"Erro em {ticker}: {e}")
                errors.append({
                    "ticker": ticker,
                    "error": str(e),
                    "processed_at": datetime.now().isoformat(),
                })

            self.sleep()

        return results, errors

    def scrape_etf(self, ticker: str):
        ticker = ticker.upper()

        html, url = self.fetch_html(f"/etfs/{ticker.lower()}/")
        soup, full_text = self.soup_and_text(html)

        rentabilidade = self.extract_rentabilidade_table(soup)

        title = self.clean_text(soup.title.text) if soup.title else ""
        name = (
            title.replace("ETF", "")
            .replace("Cotação, Histórico de Rentabilidade e Gráficos - Investidor10", "")
            .strip()
        )
        name = self.normalize_string(name)

        raw = {
            "ticker": ticker,
            "name": name,
            "mercado": "ETF",
            "url": url,

            "valor_atual": (
                self.extract(r"VALOR ATUAL\s*R\$\s*([\d.,]+)", full_text)
                or self.extract(r"COTAÇÃO\s*R\$\s*([\d.,]+)", full_text)
                or self.extract(r"R\$\s*([\d.,]+)\s*VALOR ATUAL", full_text)
                or self.extract(r"R\$\s*([\d.,]+)", full_text)
            ),

            "variacao_12m": self.extract(r"variação de\s*([\d,.-]+)%", full_text),

            "rentabilidade_1m": rentabilidade["rentabilidade_1m"],
            "rentabilidade_3m": rentabilidade["rentabilidade_3m"],
            "rentabilidade_1a": rentabilidade["rentabilidade_1a"],
            "rentabilidade_2a": rentabilidade["rentabilidade_2a"],
            "rentabilidade_5a": rentabilidade["rentabilidade_5a"],
            "rentabilidade_10a": rentabilidade["rentabilidade_10a"],

            "dividend_yield": (
                self.extract(r"Dividend Yield\s*([\d,.-]+%)", full_text)
                or self.extract(r"DY\s*([\d,.-]+%)", full_text)
            ),

            "taxa": (
                self.extract(r"Taxa\s*([\d,.-]+%)", full_text)
                or self.extract(r"Taxa de administração\s*([\d,.-]+%)", full_text)
            ),

            "patrimonio": None,

            "liquidez_media_diaria": (
                self.extract(r"Liquidez Média Diária\s*R\$\s*([\d.,]+\s*[KMB]?)", full_text)
                or self.extract(r"Liquidez Diária\s*R\$\s*([\d.,]+\s*[KMB]?)", full_text)
            ),

            "indice_referencia": None,

            "tipo": None,
            "votabilidade": None,
            "risco": None,

            "data_processado": datetime.now().date().isoformat(),
            "source": "INVESTIDOR10",
        }

        normalized = {
            **raw,
            "valor_atual_num": self.br_number_to_float(raw["valor_atual"]),
            "variacao_12m_num": self.br_number_to_float(raw["variacao_12m"]),
            "rentabilidade_1m_num": self.br_number_to_float(raw["rentabilidade_1m"]),
            "rentabilidade_3m_num": self.br_number_to_float(raw["rentabilidade_3m"]),
            "rentabilidade_1a_num": self.br_number_to_float(raw["rentabilidade_1a"]),
            "rentabilidade_2a_num": self.br_number_to_float(raw["rentabilidade_2a"]),
            "rentabilidade_5a_num": self.br_number_to_float(raw["rentabilidade_5a"]),
            "rentabilidade_10a_num": self.br_number_to_float(raw["rentabilidade_10a"]),
            "dividend_yield_num": self.br_number_to_float(raw["dividend_yield"]),
            "taxa_num": self.br_number_to_float(raw["taxa"]),
            "patrimonio_num": self.br_money_to_float(raw["patrimonio"]),
            "liquidez_media_diaria_num": self.br_money_to_float(raw["liquidez_media_diaria"]),
        }

        return normalized

    def scrape_many_etfs(self, tickers):
        results = []
        errors = []

        for index, ticker in enumerate(tickers, start=1):
            try:
                print(f"[{index}/{len(tickers)}] Buscando {ticker}...")
                data = self.scrape_etf(ticker)
                results.append(data)

            except Exception as e:
                print(f"Erro em {ticker}: {e}")
                errors.append({
                    "ticker": ticker,
                    "error": str(e),
                    "processed_at": datetime.now().isoformat(),
                })

            self.sleep()

        return results, errors

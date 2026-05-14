# FinanceOS — PATCH 37

Refinamento do Machine Learning

Incluído:
- Novos targets:
  - future_return_positive
  - future_return_regression
  - future_return_class
- Validação temporal:
  - --split-mode temporal/random
  - default temporal
  - train/test por período
- Modelos por tipo:
  - classificação: RandomForestClassifier / GradientBoostingClassifier
  - regressão: RandomForestRegressor / GradientBoostingRegressor
- Métricas:
  - classificação: accuracy, precision, recall, f1, roc_auc
  - regressão: mae, rmse, r2, directional_accuracy
- Filtros:
  - min_quality_score
  - min_history_days
- Tabela:
  - ml_model_evaluations
- Feature importance Top 10 na UI
- Prediction melhorada:
  - classificação: probabilidade classe positiva/high
  - regressão: retorno previsto
  - confiança heurística para regressão
- UI ML atualizada

Não alterado:
- backtest
- multi_factor.py
- strategy_runner.py
- jobs/fila
- orquestrador
- automações

Execução:
python scripts/ml_build_dataset.py --asset-class=equity --start-date=2020-01-01 --end-date=2024-01-01 --target=future_return_positive --horizon-days=21 --min-quality-score=45 --min-history-days=180
python scripts/ml_train_model.py --dataset-id=1 --model-type=random_forest --split-mode=temporal
python scripts/ml_predict.py --model-id=1 --asset-class=equity --limit=50 --min-quality-score=45 --min-history-days=180
streamlit run legacy_streamlit/app.py

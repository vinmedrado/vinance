# FinanceOS — PATCH 36

ML Foundation integrada ao Backtest e Frontend

Incluído:
- Estrutura:
  - ml/features/
  - ml/datasets/
  - ml/models/
  - ml/predictions/
  - ml/reports/
- Serviços:
  - services/ml_common.py
  - services/ml_feature_service.py
  - services/ml_dataset_service.py
  - services/ml_training_service.py
  - services/ml_prediction_service.py
  - services/ml_model_registry.py
- Scripts:
  - scripts/ml_build_dataset.py
  - scripts/ml_train_model.py
  - scripts/ml_predict.py
- Página:
  - pages/17_Machine_Learning.py
- Tabelas:
  - ml_datasets
  - ml_models
  - ml_predictions
  - ml_runs

Características:
- Feature engineering baseado em dados existentes
- Dataset builder com target future_return_positive
- Treino com RandomForestClassifier e GradientBoostingClassifier
- Previsões com score, label, confiança e explicação determinística
- Comparação auxiliar ML vs Backtest
- Integração com Home e Saúde do Sistema

Não alterado:
- multi_factor.py
- strategy_runner.py
- lógica de backtest
- jobs/fila
- orquestrador
- lógica de estratégia

Execução:
python scripts/ml_build_dataset.py --asset-class=equity --start-date=2020-01-01 --end-date=2024-01-01 --target=future_return_positive --horizon-days=21
python scripts/ml_train_model.py --dataset-id=1 --model-type=random_forest
python scripts/ml_predict.py --model-id=1 --asset-class=equity --limit=50
streamlit run legacy_streamlit/app.py

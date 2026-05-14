# FinanceOS — PATCH 37.1

Robustez do Machine Learning

Incluído:
- Scaler no treinamento:
  - none
  - standard
  - minmax
- Scaler fitado apenas no treino e reaplicado na predição
- Proteção contra data leakage:
  - datas ausentes
  - poucas datas únicas
  - target nulo em excesso
  - split temporal com train_end < test_start
  - features futuras removidas
- Feature selection:
  - none
  - importance
  - correlation
- Parâmetros:
  - top_features
  - correlation_threshold
- Ensemble simples:
  - ensemble_basic classifier
  - ensemble_basic regressor
  - pesos 0.5/0.5
- Prediction usando:
  - scaler salvo
  - selected_features salvas
- Ranking visual:
  - rank
  - ticker
  - predicted_score
  - predicted_label
  - confidence
  - data_quality_score
  - reliability_status
  - model_id
  - prediction_date
  - recommendation: Forte / Boa / Neutra / Evitar
- UI ML atualizada:
  - scaler
  - feature_selection
  - top_features
  - correlation_threshold
  - ensemble_basic
  - leakage checks
  - selected/removed features
  - ranking visual Top 10

Não implementado:
- ML + backtest combinado
- decisor final
- auto-ajuste
- trading
- execução automática baseada em ML

Execução:
python scripts/ml_build_dataset.py --asset-class=equity --start-date=2020-01-01 --end-date=2024-01-01 --target=future_return_positive --horizon-days=21 --min-quality-score=45 --min-history-days=180
python scripts/ml_train_model.py --dataset-id=1 --model-type=ensemble_basic --split-mode=temporal --scaler=standard --feature-selection=importance --top-features=20
python scripts/ml_predict.py --model-id=1 --asset-class=equity --limit=50 --min-quality-score=45 --min-history-days=180
streamlit run legacy_streamlit/app.py

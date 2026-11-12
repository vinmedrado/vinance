-- Apenas leitura da origem. Sem mutacoes em public.asset_prices.
select
    id as price_id,
    trim(symbol) as symbol,
    "date" as price_timestamp,
    cast("date" as date) as price_date,
    close as close_price,
    volume,
    coalesce(source, '__missing_source__') as source_name,
    created_at as ingested_at
from {{ source('vinance_app', 'asset_prices') }}

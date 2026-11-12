-- Uma observacao diaria por ativo e fonte, inclusive cripto com varias coletas.
-- Mantem a leitura mais recente do dia; nao altera o historico operacional.
with ranked as (
    select
        *,
        row_number() over (
            partition by symbol, source_name, price_date
            order by price_timestamp desc, ingested_at desc nulls last, price_id desc
        ) as observation_rank
    from {{ ref('stg_asset_prices') }}
    where symbol <> ''
      and price_timestamp is not null
      and close_price > 0
)
select
    md5(jsonb_build_array(symbol, source_name, price_date)::text) as price_day_key,
    symbol,
    source_name,
    price_date,
    close_price,
    volume,
    price_timestamp as last_observation_at,
    price_id as source_price_id
from ranked
where observation_rank = 1

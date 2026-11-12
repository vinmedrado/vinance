-- Ultima cotacao diaria valida para cada ativo e fonte.
with ranked as (
    select
        *,
        row_number() over (
            partition by symbol, source_name
            order by price_date desc, last_observation_at desc, source_price_id desc
        ) as latest_rank
    from {{ ref('mart_daily_asset_prices') }}
)
select
    md5(jsonb_build_array(symbol, source_name)::text) as asset_source_key,
    symbol,
    source_name,
    price_date,
    close_price,
    volume,
    last_observation_at
from ranked
where latest_rank = 1

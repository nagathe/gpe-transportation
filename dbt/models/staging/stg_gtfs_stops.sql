with source as (
    select * from raw.gtfs_stops
)

select
    stop_id,
    stop_name,
    stop_lat::float,
    stop_lon::float,
    ST_SetSRID(ST_MakePoint(stop_lon::float, stop_lat::float), 4326) as geom
from source
where stop_id is not null
  and stop_lat is not null
  and stop_lon is not null
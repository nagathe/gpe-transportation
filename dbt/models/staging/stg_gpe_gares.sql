with source as (
    select * from raw.gpe_gares
),

cleaned as (
    select
        nom_gare,
        ligne_gpe       as ligne,
        interconnexion,
        geometry        as geom,
        st_y(geometry)  as latitude,
        st_x(geometry)  as longitude
    from source
    where nom_gare is not null
)

select * from cleaned

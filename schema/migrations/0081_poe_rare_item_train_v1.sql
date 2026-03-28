CREATE TABLE IF NOT EXISTS poe_trade.poe_rare_item_train
(
    item_id String,
    observed_at DateTime64(3, 'UTC'),
    league LowCardinality(String),
    category LowCardinality(String),
    base_type LowCardinality(String),
    ilvl UInt16,
    corrupted UInt8,
    fractured UInt8,
    synthesised UInt8,
    prefix_count UInt8,
    suffix_count UInt8,
    explicit_count UInt8,
    implicit_count UInt8,
    price_chaos Float32,

    has_exp_mana_flat UInt8 DEFAULT 0,
    val_exp_mana_flat Nullable(Float32) DEFAULT NULL,
    tier_exp_mana_flat Nullable(UInt8) DEFAULT NULL,

    has_exp_item_rarity_pct UInt8 DEFAULT 0,
    val_exp_item_rarity_pct Nullable(Float32) DEFAULT NULL,
    tier_exp_item_rarity_pct Nullable(UInt8) DEFAULT NULL,

    has_exp_life_flat UInt8 DEFAULT 0,
    val_exp_life_flat Nullable(Float32) DEFAULT NULL,
    tier_exp_life_flat Nullable(UInt8) DEFAULT NULL,

    has_exp_energy_shield_flat UInt8 DEFAULT 0,
    val_exp_energy_shield_flat Nullable(Float32) DEFAULT NULL,
    tier_exp_energy_shield_flat Nullable(UInt8) DEFAULT NULL,

    has_exp_all_attrs_flat UInt8 DEFAULT 0,
    val_exp_all_attrs_flat Nullable(Float32) DEFAULT NULL,
    tier_exp_all_attrs_flat Nullable(UInt8) DEFAULT NULL,

    has_exp_all_elem_res_pct UInt8 DEFAULT 0,
    val_exp_all_elem_res_pct Nullable(Float32) DEFAULT NULL,
    tier_exp_all_elem_res_pct Nullable(UInt8) DEFAULT NULL,

    has_exp_fire_res_pct UInt8 DEFAULT 0,
    val_exp_fire_res_pct Nullable(Float32) DEFAULT NULL,
    tier_exp_fire_res_pct Nullable(UInt8) DEFAULT NULL,

    has_exp_cold_res_pct UInt8 DEFAULT 0,
    val_exp_cold_res_pct Nullable(Float32) DEFAULT NULL,
    tier_exp_cold_res_pct Nullable(UInt8) DEFAULT NULL,

    has_exp_lightning_res_pct UInt8 DEFAULT 0,
    val_exp_lightning_res_pct Nullable(Float32) DEFAULT NULL,
    tier_exp_lightning_res_pct Nullable(UInt8) DEFAULT NULL,

    has_exp_chaos_res_pct UInt8 DEFAULT 0,
    val_exp_chaos_res_pct Nullable(Float32) DEFAULT NULL,
    tier_exp_chaos_res_pct Nullable(UInt8) DEFAULT NULL,

    has_exp_dex_flat UInt8 DEFAULT 0,
    val_exp_dex_flat Nullable(Float32) DEFAULT NULL,
    tier_exp_dex_flat Nullable(UInt8) DEFAULT NULL,

    has_exp_int_flat UInt8 DEFAULT 0,
    val_exp_int_flat Nullable(Float32) DEFAULT NULL,
    tier_exp_int_flat Nullable(UInt8) DEFAULT NULL,

    has_exp_str_flat UInt8 DEFAULT 0,
    val_exp_str_flat Nullable(Float32) DEFAULT NULL,
    tier_exp_str_flat Nullable(UInt8) DEFAULT NULL,

    has_exp_cast_speed_pct UInt8 DEFAULT 0,
    val_exp_cast_speed_pct Nullable(Float32) DEFAULT NULL,
    tier_exp_cast_speed_pct Nullable(UInt8) DEFAULT NULL,

    has_exp_attack_speed_pct UInt8 DEFAULT 0,
    val_exp_attack_speed_pct Nullable(Float32) DEFAULT NULL,
    tier_exp_attack_speed_pct Nullable(UInt8) DEFAULT NULL,

    has_exp_fire_damage_flat UInt8 DEFAULT 0,
    val_exp_fire_damage_flat Nullable(Float32) DEFAULT NULL,
    tier_exp_fire_damage_flat Nullable(UInt8) DEFAULT NULL,

    has_exp_cold_damage_flat UInt8 DEFAULT 0,
    val_exp_cold_damage_flat Nullable(Float32) DEFAULT NULL,
    tier_exp_cold_damage_flat Nullable(UInt8) DEFAULT NULL,

    has_exp_lightning_damage_flat UInt8 DEFAULT 0,
    val_exp_lightning_damage_flat Nullable(Float32) DEFAULT NULL,
    tier_exp_lightning_damage_flat Nullable(UInt8) DEFAULT NULL,

    has_exp_phys_damage_flat UInt8 DEFAULT 0,
    val_exp_phys_damage_flat Nullable(Float32) DEFAULT NULL,
    tier_exp_phys_damage_flat Nullable(UInt8) DEFAULT NULL,

    has_imp_armour_pct UInt8 DEFAULT 0,
    val_imp_armour_pct Nullable(Float32) DEFAULT NULL,
    tier_imp_armour_pct Nullable(UInt8) DEFAULT NULL,

    has_imp_evasion_pct UInt8 DEFAULT 0,
    val_imp_evasion_pct Nullable(Float32) DEFAULT NULL,
    tier_imp_evasion_pct Nullable(UInt8) DEFAULT NULL
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(observed_at)
ORDER BY (league, category, base_type, observed_at, item_id);

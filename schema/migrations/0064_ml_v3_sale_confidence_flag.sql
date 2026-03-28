ALTER TABLE poe_trade.ml_v3_training_examples
ADD COLUMN IF NOT EXISTS sale_confidence_flag UInt8 AFTER label_weight;

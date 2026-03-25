-- 房源场景多标签（TF-IDF+LR）概率，与 travel_purpose 键一致
-- 首次跑 listing_scene_pipeline.py 前在目标库执行一次（MySQL）
ALTER TABLE listings
  ADD COLUMN scene_scores TEXT NULL COMMENT '场景标签概率 JSON（couple/family/business/exam）'
  AFTER landlord_module_json;

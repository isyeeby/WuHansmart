-- 房源到最近医院 POI 的直线距离（千米），由 listing_scene_pipeline 计算并回写
-- 可与 scene_scores 一并维护；首次需要可手工执行（MySQL）
ALTER TABLE listings
  ADD COLUMN nearest_hospital_km DECIMAL(9, 3) NULL COMMENT '至最近POI医院直线距离km'
  AFTER scene_scores;

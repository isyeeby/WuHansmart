-- 最近医院 POI 名称，与 nearest_hospital_km 由 listing_scene_pipeline 一并回写
ALTER TABLE listings
  ADD COLUMN nearest_hospital_name VARCHAR(200) NULL COMMENT '最近POI医院名称'
  AFTER nearest_hospital_km;

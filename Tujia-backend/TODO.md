# 后端待办与可选扩展

> 与代码同步时请改日期。完整文档索引见 [`docs/README.md`](docs/README.md)。

## 仍可选的扩展

- [ ] `analysis`：`district-detail`、`seasonal-effect` 等路由（若产品需要再开）
- [ ] Redis：配置已预留，业务路径未接
- [ ] 生产：收紧 JWT/CORS、关闭演示向默认用户（见 `app/core/security.py`）

## 数据与运维

- MySQL / Hive 导入与 Docker：`docs/HIVE_GUIDE.md`、`scripts/export_mysql_for_hive.py`、`scripts/hive_docker_import.py`
- 接口清单与烟测：`docs/MODULE_AUDIT_AND_SMOKE.md`、`pytest tests/test_smoke_routes.py`

**Swagger**：以运行中的 `http://localhost:8000/docs` 为准。

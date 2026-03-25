# tujiaALL（途家民宿分析全栈）

本目录为**工作区根**，包含前后端两个子项目：

| 目录 | 说明 |
|------|------|
| [Tujia-backend](Tujia-backend/) | FastAPI 后端、Hive/MySQL、模型与脚本 |
| [TuJiaFeature](TuJiaFeature/) | React 前端 |

**后端文档总索引**（阅读顺序、接口、数据层、Hive、论文素材）：[Tujia-backend/docs/README.md](Tujia-backend/docs/README.md)

## Git 与部署分支

- **`main`**：完整 monorepo（前后端 + `deploy/` Nginx 与说明）。
- **`deploy-backend`**：`git subtree split` 自 `Tujia-backend`，克隆后仓库根目录即后端项目。
- **`deploy-frontend`**：自 `TuJiaFeature`，根目录即前端项目。

上线清单与推送命令见 [deploy/README.md](deploy/README.md)。更新子树分支：在 `main` 上提交后重新执行 `git subtree split --prefix=... -b ...`（可加 `--force` 覆盖同名分支）。

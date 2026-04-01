# tujiaALL（途家民宿分析全栈）

本目录为**工作区根**，包含前后端两个子项目：

| 目录 | 说明 |
|------|------|
| [Tujia-backend](Tujia-backend/) | FastAPI 后端、Hive/MySQL、模型与脚本 |
| [TuJiaFeature](TuJiaFeature/) | React 前端 |

**后端文档总索引**（阅读顺序、接口、数据层、Hive、论文素材）：[Tujia-backend/docs/README.md](Tujia-backend/docs/README.md)

## Git 与部署分支

- **`main`**：完整 monorepo（前后端 + `deploy/` Nginx 与说明）。
- **`deploy-backend`**：与 **`Tujia-backend/`** 同步；`git subtree split --prefix=Tujia-backend`，克隆后仓库根即后端项目。
- **`deploy-frontend`**：与 **`TuJiaFeature/`** 同步；`--prefix=TuJiaFeature`，根目录即前端项目。

上线清单与推送命令见 [deploy/README.md](deploy/README.md)。更新子树分支：见该文档（需先删除旧 `deploy-*` 分支再 `subtree split`）。

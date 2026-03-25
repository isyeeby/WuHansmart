# 部署说明（途家 monorepo）

## 仓库分支

| 分支 | 内容 | 典型用途 |
|------|------|----------|
| `main` | 前端 `TuJiaFeature/` + 后端 `Tujia-backend/` + 本目录 Nginx 示例 | 完整源码、联调、文档 |
| `deploy-backend` | 仅后端目录历史（`git subtree split`，仓库根即 `Tujia-backend` 内容） | 服务器只拉后端、CI 只构建 API |
| `deploy-frontend` | 仅前端目录历史（根即 `TuJiaFeature`） | 静态托管/只构建前端 |

创建子树分支（在 `main` 提交之后执行一次即可）：

```bash
git subtree split --prefix=Tujia-backend -b deploy-backend
git subtree split --prefix=TuJiaFeature -b deploy-frontend
```

`main` 有新提交后若要刷新子树分支：先 `git branch -D deploy-backend deploy-frontend`，再执行上面两条 `git subtree split`（常见 Windows 版 Git 无 `--force` 覆盖选项）。

推送：

```bash
git remote add origin <你的仓库 URL>
git push -u origin main
git push -u origin deploy-backend
git push -u origin deploy-frontend
```

单独克隆某分支到空目录：

```bash
git clone -b deploy-backend --single-branch <URL> tujia-api
git clone -b deploy-frontend --single-branch <URL> tujia-web
```

## 后端上线清单（`Tujia-backend`）

1. Python 3.10+，安装依赖：`pip install -r requirements-prod.txt`
2. 复制 `.env.example` 为 `.env`，填写 `SECRET_KEY`、`DATABASE_URL`、生产 `DEBUG=False`、`CORS_ORIGINS`（前端完整源，逗号分隔）
3. 将 `models/*.pkl`、`models/*.npz` 放到服务器 `models/`（若训练产物未进库）
4. 大体积 JSON（如日历全量）勿进 Git；按运维规范放到数据目录并在代码/配置中引用
5. 启动：`gunicorn main:app -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 --workers 2`（工作目录为 `Tujia-backend`）  
   示例 systemd：`Tujia-backend/deploy/gunicorn.example.service`

## 前端上线清单（`TuJiaFeature`）

1. `npm ci` 或 `npm install`，复制 `.env.production.example` 为 `.env.production`（同域部署可保持 `VITE_API_BASE_URL` 为空）
2. `npm run build`，将 `dist/` 交给 Nginx/OSS/CDN
3. 与后端同域时，使用仓库根目录 `deploy/nginx-tujia.conf`：`root` 指向 `dist`，`/api` 反代到本机 `8000`

## Nginx

见同目录 `nginx-tujia.conf`。

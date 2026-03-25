# 后端部署片段

- **完整 Nginx（静态 + /api）**：在 monorepo 的 `deploy/nginx-tujia.conf`（仅 `main` 分支或完整克隆可见）。
- **systemd 示例**：`gunicorn.example.service`（请修改 `User`、`WorkingDirectory`、虚拟环境路径）。

单机仅后端时，用 Nginx 将 `location /api/` 代理到 `127.0.0.1:8000` 即可。

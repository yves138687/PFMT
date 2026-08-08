# PFMT 生产环境部署手册：FRP + 阿里云 Nginx

本文采用以下部署方式：阿里云 Nginx 提供前端静态资源和 HTTPS，只有后端 API、文件上传、预览与下载通过 FRP 返回内网 PFMT 主机。

```text
浏览器 --HTTPS:443--> 阿里云 Nginx
                         |-- /              --> /opt/pfmt/web/dist
                         `-- /api、/health  --> 127.0.0.1:18080
                                                  |
                                                  `-- frps/frpc --> 内网 127.0.0.1:8000
```

## 1. 部署前准备

需要准备：

- 一个已完成实名认证和解析的域名，例如 `pfmt.example.com`。
- 一台阿里云 Linux 服务器，推荐 Ubuntu 24.04 LTS 或同等受支持系统。
- 阿里云服务器已安装 Nginx，且安全组允许公网访问 TCP 80、443。
- 内网 Windows 主机能够持续联网，并安装 PowerShell 7、Conda、Node.js 和 pnpm。
- FRP 客户端与服务端使用完全相同的版本；从 FRP 官方 GitHub Release 下载并校验文件摘要。
- 内网主机具有稳定的数据盘，且 `D:\PFMT_DATA` 不位于 Git 仓库内。

本文约定：

| 项目 | 示例值 |
|---|---|
| 域名 | `pfmt.example.com` |
| 阿里云公网 IP | `203.0.113.10` |
| FRP 控制端口 | `7000` |
| FRP API 代理端口 | `18080` |
| 内网后端地址 | `127.0.0.1:8000` |
| 阿里云前端目录 | `/opt/pfmt/web/dist` |

所有示例域名、IP、Token 和路径都必须替换为实际值。FRP Token 不要提交到 Git。

## 2. 准备生产环境配置

仓库根目录已生成 `.env.production`，并通过 `.gitignore` 排除。应用实际读取根目录 `.env`，因此在内网部署主机执行：

```powershell
Set-Location D:\workspace\MyProject\PFMT
Copy-Item -LiteralPath .env.production -Destination .env -Force
```

打开 `.env`，至少修改：

```dotenv
PFMT_CORS_ORIGINS=https://你的真实域名
PFMT_STORAGE_ROOT=D:/PFMT_DATA
```

生成的管理员密码和 JWT 密钥已经具备生产强度，但仍应存入密码管理器。不要把 `.env`、`.env.production` 或它们的内容发到聊天、工单和代码仓库。

创建持久化目录，并限制只有运行 PFMT 的 Windows 账户可以访问：

```powershell
$pfmtDataRoot = 'D:\PFMT_DATA'
New-Item -ItemType Directory -Force -Path $pfmtDataRoot, "$pfmtDataRoot\data", "$pfmtDataRoot\logs", "$pfmtDataRoot\backup", "$pfmtDataRoot\tmp", "$pfmtDataRoot\preview" | Out-Null
```

如果现有 `storage` 中已有数据库或加密文件，不要初始化新库。停止服务后，将整个现有存储目录作为一个整体迁移，并同步调整 `PFMT_STORAGE_ROOT`。

## 3. 构建和启动 PFMT

初始化 Python 3.12 环境并执行检查：

```powershell
Set-Location D:\workspace\MyProject\PFMT
pwsh ./scripts/dev/bootstrap_dev.ps1
pwsh ./scripts/dev/run_tests.ps1 -SkipInstall
```

构建前端：

```powershell
Set-Location D:\workspace\MyProject\PFMT\web
pnpm install --frozen-lockfile
pnpm build
```

生产后端必须关闭热更新：

```powershell
Set-Location D:\workspace\MyProject\PFMT
pwsh ./scripts/dev/start_server.ps1 -NoReload
```

在内网主机另开终端验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

预期返回 `status = ok`。不要把 `PFMT_SERVER_HOST` 改为 `0.0.0.0`，FRP 客户端访问本机回环地址即可。

生产运行建议用 WinSW 或 NSSM 将上述无热更新命令注册为 Windows 服务，设置：

- 使用专用低权限 Windows 账户运行。
- 启动类型为自动，并配置失败后自动重启。
- 工作目录为仓库根目录。
- 服务依赖网络可用，但不要用 Vite 开发服务器提供生产前端。

## 4. 在阿里云安装和配置 frps

在阿里云下载对应平台的 FRP 压缩包，将 `frps` 安装到 `/opt/frp/frps`，配置文件保存为 `/etc/frp/frps.toml`：

```toml
bindAddr = "0.0.0.0"
bindPort = 7000

auth.method = "token"
auth.token = "替换为至少32字节的高强度随机Token"

transport.tls.force = true

allowPorts = [
  { single = 18080 }
]

log.to = "/var/log/frp/frps.log"
log.level = "info"
log.maxDays = 14
```

创建 `/etc/systemd/system/frps.service`：

```ini
[Unit]
Description=FRP Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=frp
Group=frp
ExecStart=/opt/frp/frps -c /etc/frp/frps.toml
Restart=on-failure
RestartSec=5s
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

创建专用账户、日志目录并启动：

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin frp
sudo install -d -o frp -g frp /var/log/frp
sudo chown root:root /etc/frp/frps.toml
sudo chmod 600 /etc/frp/frps.toml
sudo systemctl daemon-reload
sudo systemctl enable --now frps
sudo systemctl status frps
```

阿里云安全组和主机防火墙：

- TCP 80、443：允许公网访问。
- TCP 7000：优先只允许内网主机的出口公网 IP。
- TCP 18080：不要在阿里云安全组中向公网放行。
- FRP Dashboard 不启用。

Nginx 和 frps 位于同一台主机，因此即使安全组不开放 18080，Nginx 仍可通过 `127.0.0.1:18080` 访问代理。

## 5. 在内网 Windows 配置 frpc

将 `frpc.exe` 放到 `D:\software\frp\frpc.exe`，将配置保存为 Git 仓库外的 `D:\software\frp\frpc.toml`：

```toml
serverAddr = "阿里云公网IP"
serverPort = 7000

auth.method = "token"
auth.token = "与frps完全一致的Token"

transport.tls.enable = true

[[proxies]]
name = "pfmt-api"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8000
remotePort = 18080
```

先前台验证：

```powershell
& 'D:\software\frp\frpc.exe' -c 'D:\software\frp\frpc.toml'
```

在阿里云执行：

```bash
curl --fail http://127.0.0.1:18080/health
```

预期返回 `{"status":"ok"}`。验证后同样用 WinSW 或 NSSM 将 frpc 注册为自动启动服务，并限制配置文件 ACL，防止其他本机账户读取 Token。

## 6. 上传前端产物到阿里云

将内网构建出的 `web/dist` 内容上传到阿里云临时目录，再原子切换版本。示例：

```powershell
scp -r D:\workspace\MyProject\PFMT\web\dist\* deploy@203.0.113.10:/tmp/pfmt-dist/
```

阿里云执行：

```bash
sudo install -d -o root -g www-data /opt/pfmt/web/dist
sudo rsync -a --delete /tmp/pfmt-dist/ /opt/pfmt/web/dist/
sudo find /opt/pfmt/web/dist -type d -exec chmod 755 {} \;
sudo find /opt/pfmt/web/dist -type f -exec chmod 644 {} \;
```

## 7. 配置 Nginx 和 HTTPS

先将域名 A/AAAA 记录解析到阿里云公网 IP。创建 `/etc/nginx/sites-available/pfmt.conf`：

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name pfmt.example.com;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name pfmt.example.com;

    ssl_certificate /etc/letsencrypt/live/pfmt.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pfmt.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    root /opt/pfmt/web/dist;
    index index.html;

    client_max_body_size 5g;
    client_body_timeout 3600s;

    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    location /api/ {
        proxy_pass http://127.0.0.1:18080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 15s;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_request_buffering off;
    }

    location = /health {
        proxy_pass http://127.0.0.1:18080/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /assets/ {
        try_files $uri =404;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

首次申请证书时，先只启用 HTTP server，确认域名解析后使用 Certbot：

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d pfmt.example.com
sudo certbot renew --dry-run
sudo nginx -t
sudo systemctl reload nginx
```

不同 Nginx 版本对 `http2` 指令语法可能有提示；以 `nginx -t` 结果为准。不要在 HTTPS 证书生效前输入生产账户密码。

## 8. 上线验收

按顺序检查每一层：

```powershell
# 内网 FastAPI
Invoke-RestMethod http://127.0.0.1:8000/health
```

```bash
# 阿里云 FRP 出口
curl --fail http://127.0.0.1:18080/health

# Nginx 本机 HTTPS，域名解析生效后执行
curl --fail https://pfmt.example.com/health
curl --fail -I https://pfmt.example.com/
```

浏览器验收：

1. 访问 HTTPS 域名并登录。
2. 刷新 `/dashboard`，确认不会出现 Nginx 404。
3. 上传、预览、下载一个测试文件。
4. 新建隐藏文件和目录，退出再登录，确认隐藏内容默认不可见。
5. 检查浏览器开发者工具，确认 API 均访问同域 `/api`，没有 Mixed Content 或 CORS 错误。
6. 确认公网无法访问 `公网IP:18080` 和 FRP Dashboard。

首次登录后修改管理员密码。修改 `.env` 中的初始密码不会自动修改数据库内已经创建的用户密码，应通过应用提供的密码修改流程完成；若当前版本尚无该入口，应在正式导入数据前确定最终密码。

## 9. 备份与恢复

必须作为同一恢复点保存：

- `D:\PFMT_DATA\pfmt.sqlite3`
- `D:\PFMT_DATA\data` 下的所有加密对象
- `.env` 和 FRP 配置，单独加密保存
- 数据库中的文件加密密钥记录

安全的轻量备份流程：

1. 暂停 PFMT 后端，阻止数据库和文件对象继续写入。
2. 复制整个 `D:\PFMT_DATA` 到带时间戳的备份目录。
3. 计算备份清单和摘要，确认复制完整。
4. 重新启动 PFMT，并检查 `/health`。
5. 定期在隔离目录执行恢复演练，而不是只验证压缩包能打开。

不要在服务持续写入时直接复制 SQLite 文件。备份文件包含数据库、密钥材料和隐私数据，必须加密并限制访问。

## 10. 升级与回滚

升级前：

1. 记录当前 Git 提交和前端发布目录。
2. 停止后端并完成一致性备份。
3. 在内网运行后端测试和 `pnpm build`。
4. 先升级内网后端，再上传新 `dist`。
5. 执行第 8 节全部验收。

发生异常时：

1. 停止后端，避免新版本继续写数据库。
2. 恢复原代码版本、完整数据库和对应的加密对象目录。
3. 恢复上一版 `web/dist`。
4. 重启 FastAPI、frpc、frps 和 Nginx，并逐层检查健康状态。

不能只回滚 SQLite 而保留新文件对象，也不能只回滚文件对象而保留新数据库。

## 11. 常见故障定位

| 现象 | 优先检查 |
|---|---|
| 域名 502 | 内网后端、frpc、frps、阿里云 `127.0.0.1:18080` |
| 刷新页面 404 | Nginx `try_files $uri $uri/ /index.html` |
| 上传返回 413 | Nginx `client_max_body_size` |
| 大文件上传超时 | FRP 稳定性、Nginx 三个 timeout、内网上行带宽 |
| 登录后立即 401 | `.env` JWT 密钥变化、系统时间、数据库会话状态 |
| 浏览器 CORS 错误 | 前端是否使用 `/api`、`PFMT_CORS_ORIGINS` 是否为真实 HTTPS 域名 |
| 生产后端拒绝启动 | 管理员密码长度、默认密码、JWT 密钥长度、`PFMT_ENV` |
| 加密文件无法打开 | 文件对象、数据库 key 记录和备份版本是否匹配 |

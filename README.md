# 森空岛自动签到（明日方舟 + 终末地）

在 Linux / 阿里云 ECS 上每天定时为 **明日方舟** 与 **明日方舟：终末地** 执行森空岛签到。

基于 [devnakx/skyland_auto_checkin](https://github.com/devnakx/skyland_auto_checkin) 改编，**无需青龙面板**，使用 `cron` + Python 即可。

---

## 一、获取 Token（在你自己的电脑上操作）

1. 浏览器打开并登录 [森空岛](https://www.skland.com/)
2. **保持登录状态**，新开标签访问：  
   https://web-api.skland.com/account/info/hg
3. 复制 JSON 里 `data.content` 的字符串（很长的一串），这就是 Token  
4. **切勿**把 Token 发给他人或上传到公开仓库

多账号：在 `.env` 里用英文分号 `;` 分隔，例如 `tokenA;tokenB`。

---

## 二、部署到阿里云 ECS

以下以 **Ubuntu 22.04 / Debian** 为例，CentOS 将 `apt` 换成 `yum` 即可。

### 1. 登录服务器

```bash
ssh root@你的ECS公网IP
```

### 2. 安装 Python（若尚未安装）

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

### 3. 上传项目到服务器

**方式 A：本机用 scp 上传（在 Windows 本机 PowerShell 执行）**

```powershell
scp -r "D:\Cursor Project\skd checkin" root@你的ECS公网IP:/opt/skland-checkin
```

**方式 B：在 ECS 上用 git（若你已推到 GitHub）**

```bash
sudo mkdir -p /opt/skland-checkin
sudo git clone <你的仓库地址> /opt/skland-checkin
```

**方式 C：在 ECS 上手动打包上传后解压到 `/opt/skland-checkin`**

### 4. 初始化

```bash
cd /opt/skland-checkin
chmod +x deploy.sh run.sh install-cron.sh
./deploy.sh
```

### 5. 配置 Token

```bash
nano /opt/skland-checkin/.env
```

修改示例：

```env
SKYLAND_TOKEN=这里粘贴你的token
SKYLAND_NOTIFY=false
```

需要微信/邮件推送时（[Server 酱](https://sct.ftqq.com/)）：

```env
SKYLAND_NOTIFY=true
SERVERCHAN_SENDKEY=你的SendKey
```

保存：`Ctrl+O` 回车，`Ctrl+X` 退出。

### 6. 手动测试一次

```bash
cd /opt/skland-checkin
./run.sh
tail -50 logs/checkin-$(date +%Y%m%d).log
```

日志里应看到 `[明日方舟]`、`[明日方舟：终末地]` 的签到结果。

### 7. 设置每天凌晨 3 点自动执行

```bash
cd /opt/skland-checkin
./install-cron.sh
```

确认时区为北京时间：

```bash
timedatectl
# 若不是 Shanghai：
sudo timedatectl set-timezone Asia/Shanghai
```

查看 cron 是否生效：

```bash
crontab -l
```

---

## 三、日常维护

| 操作 | 命令 |
|------|------|
| 查看今日日志 | `tail -f /opt/skland-checkin/logs/checkin-$(date +%Y%m%d).log` |
| 立即签到 | `cd /opt/skland-checkin && ./run.sh` |
| 修改 Token | 编辑 `.env` 后无需重启，下次 cron 自动读取 |
| 取消定时 | `crontab -e`，删除带 `# skland-checkin` 的那一行 |

Token 失效（日志出现登录/鉴权失败）时：在浏览器重新登录森空岛，再访问 hg 接口获取新 Token，更新 `.env`。

---

## 四、文件说明

| 文件 | 说明 |
|------|------|
| `main.py` | 签到主程序 |
| `.env` | Token 与通知配置（**不要提交到 Git**） |
| `run.sh` | 执行一次并写入 `logs/` |
| `install-cron.sh` | 添加每天 03:00 的 cron |
| `deploy.sh` | 创建虚拟环境并安装依赖 |

---

## 五、注意事项

1. **IP 风控**：Token 建议在常用网络下获取；ECS 使用固定公网 IP 一般比 GitHub Actions 更稳定。若频繁失败，可尝试在 ECS 所在网络环境下重新获取 Token。
2. **账号安全**：`.env` 含登录凭证，请限制权限：`chmod 600 .env`
3. **接口变更**：鹰角可能调整接口，若长期失败请关注上游项目或 Issue。
4. **合规风险**：自动化签到可能违反服务条款，请自行承担风险。

---

## 六、修改签到时间

编辑 cron（`crontab -e`），将 `0 3` 改为所需时间（分钟 小时）：

```cron
0 3 * * * /opt/skland-checkin/run.sh # skland-checkin
```

例如每天 8:30：`30 8 * * * /opt/skland-checkin/run.sh # skland-checkin`

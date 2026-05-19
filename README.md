# Multi-Journal Weekly Research Digest

> 每周一 09:00（北京时间）自动抓取 8 个高水平期刊的最新研究文章，
> 翻译标题与摘要、按学科自动分类总结，整理成 Word 文档发送到指定邮箱。
> 完全运行在 GitHub Actions 上，无需自己的服务器。

---

## 📚 覆盖期刊

| # | 期刊 | 出版方 | 周均文章数 | 过滤策略 |
|---|------|------|---------|---------|
| 1 | Nature | Springer Nature | ~25 | DOI 前缀 + nature.com 补摘要 |
| 2 | Science | AAAS | ~30 | Crossref 摘要长度 |
| 3 | Nature Materials | Springer Nature | ~5–10 | DOI + `prism.section` |
| 4 | Nature Nanotechnology | Springer Nature | ~5–8 | DOI + `prism.section` |
| 5 | Nature Machine Intelligence | Springer Nature | ~7 | DOI + `prism.section` |
| 6 | Nature Sensors | Springer Nature | ~5 | DOI + `prism.section` |
| 7 | Advanced Materials | Wiley | ~70 | Semantic Scholar 文章类型 |
| 8 | Advanced Functional Materials | Wiley | ~120 | Semantic Scholar 文章类型 |

**单次邮件预计 200–270 篇研究文章**，文档约 150–250 页。

---

## ✨ 功能特性

- 🗓️ **定时自动**：每周一 09:00（北京时间）GitHub Actions 自动运行
- 📚 **多数据源混合**：Crossref API（论文列表）+ nature.com 网页抓取（补摘要）+ Semantic Scholar API（Wiley 文章类型识别）
- 🔍 **精准过滤**：按 DOI 前缀、文章类型、标题黑名单等多重规则，只保留原创研究文章（排除 Review、Editorial、News & Views、Correction 等）
- 🌐 **中英双语**：标题和摘要都翻译成中文（Google Translate 后端，无需 API key）
- 📊 **自动分类总结**：按学科自动归类到 14 个细分领域，附高频关键词
- 📄 **Word 输出**：结构化 .docx 文件，包含每个期刊的独立表格 + 末尾分类总结
- 📧 **QQ 邮箱自动发送**：SMTP 安全发送，凭证全走 GitHub Secrets
- 🔒 **凭证安全**：代码中无任何明文密码

---

## 📋 项目结构

```
nature-science-digest/
├── .github/
│   └── workflows/
│       └── weekly-digest.yml      # GitHub Actions 调度配置
├── src/
│   ├── __init__.py
│   ├── scraper.py                 # 多期刊抓取（Crossref/nature.com/Semantic Scholar）
│   ├── translator.py              # 中文翻译（deep-translator）
│   ├── classifier.py              # 关键词分类 + 总结
│   ├── document.py                # Word 文档生成（python-docx）
│   ├── email_sender.py            # SMTP 邮件发送
│   └── main.py                    # 主程序入口
├── requirements.txt               # Python 依赖
├── test_smtp.py                   # 本地 SMTP 测试脚本
├── .env.example                   # 环境变量模板
├── .gitignore                     # 防止泄露密码
└── README.md                      # 本文件
```

---

## 🚀 部署步骤（10 分钟）

### 第 1 步：创建 GitHub 仓库

1. 登录 [github.com](https://github.com/)，点击右上角 `+` → `New repository`
2. 仓库名随意，例如 `nature-science-digest`
4. **重要：选 Private（私有）** —— 即使代码里没有密码，也不要公开
4. 不勾选 "Add a README"（项目里已有），点 `Create repository`

### 第 2 步：上传代码

#### 方法 A：网页拖拽（推荐）

进入空仓库 → `uploading an existing file` → 把解压后的所有文件拖进去 → 提交。

⚠️ **隐藏文件需单独处理**：以 `.` 开头的文件（`.github/`、`.gitignore`、`.env.example`）可能不会一起被拖上去。解决方法：

- **Windows**：文件资源管理器 → 查看 → 勾选 "隐藏的项目"
- **macOS**：按 `Cmd + Shift + .` 显示隐藏文件
- **或者**：直接在 GitHub 网页 `Add file → Create new file`，文件名输入完整路径如 `.github/workflows/weekly-digest.yml`，粘贴内容提交

#### 方法 B：Git 命令行

```bash
cd 解压后的nature-science-digest文件夹
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

### 第 3 步：配置 GitHub Secrets ⚠️ 关键步骤

**先做：生成 QQ 邮箱授权码**

1. 登录 [QQ 邮箱网页版](https://mail.qq.com/)
2. 设置 → 账户 → 找到 "POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务"
3. 点击 "开启"（如已开启，建议关闭再重开生成新码）
4. 按提示发短信验证，会得到 16 位授权码
5. **复制下来**

然后在 GitHub 仓库页面：

1. `Settings` → 左侧 `Secrets and variables` → `Actions`
2. 点 `New repository secret`，添加这三个：

| Name | Value | 说明 |
|------|-------|-----|
| `SMTP_USER` | `your-email@qq.com` | 您的 QQ 邮箱地址（发件人）|
| `SMTP_PASS` | 16 位授权码（去空格）| QQ SMTP 授权码，**不是登录密码** |
| `RECIPIENT` | `your-email@qq.com` | 收件邮箱（可与发件相同）|

### 第 4 步：手动触发验证

1. 仓库 `Actions` 标签 → 第一次访问可能需要点击启用 Actions
2. 左侧选 `Weekly Multi-Journal Digest`
3. 右上角 `Run workflow` → 绿色按钮
4. 等 **8–15 分钟**（首次跑要抓 270+ 篇文章并翻译）
5. 看到绿色 ✓ 表示成功，检查 QQ 邮箱 📬

### 第 5 步：完成

定时任务已生效。**接下来每周一早上 09:00（北京时间）自动收到邮件，无需任何手动操作。**

---

## ⚙️ 自定义配置

### 修改运行时间

编辑 `.github/workflows/weekly-digest.yml` 里的 cron：

| 想要的北京时间 | cron 表达式 |
|------|------|
| 周一 09:00（默认）| `0 1 * * 1` |
| 周一 18:00 | `0 10 * * 1` |
| 周二 09:00 | `0 1 * * 2` |
| 每天 09:00 | `0 1 * * *` |

公式：北京时间 = UTC + 8 小时。GitHub Actions 用 UTC 时区。

### 添加 / 移除期刊

编辑 `src/scraper.py` 顶部的 `JOURNAL_CONFIG` 列表。

**添加新期刊**（以 *Cell* 为例）：

```python
{
    "name": "Cell",
    "issn": "0092-8674",
    "doi_prefix": None,                # Cell 没有独特 DOI 前缀
    "filter_strategy": "wiley",        # 用 Semantic Scholar 过滤
    "display_short": "Cell",
},
```

**移除某个期刊**：直接删除或注释掉对应那一项即可。

**常见期刊 ISSN**：

| 期刊 | ISSN | 推荐策略 |
|------|------|------|
| Cell | 0092-8674 | wiley |
| Nature Communications | 2041-1723 | nature_family（前缀 `s41467-`）|
| Nature Chemistry | 1755-4330 | nature_family（前缀 `s41557-`）|
| Nature Biotechnology | 1087-0156 | nature_family（前缀 `s41587-`）|
| PNAS | 0027-8424 | science |
| Joule | 2542-4351 | wiley |
| ACS Nano | 1936-0851 | wiley |
| Angewandte Chemie | 1433-7851 | wiley |

### 调整时间窗口

修改 GitHub Secret `DAYS_BACK` 的值（如未设置默认 8）。

- `7` — 严格只看最近一周
- `8`（默认）— 一周 + 1 天缓冲，避免漏掉刚发表的
- `14` — 抓最近两周，覆盖度更高但有重复
- `30` — 月度盘点

### 修改分类规则

编辑 `src/classifier.py` 顶部的 `CATEGORY_KEYWORDS` 列表：

```python
("新类别名", ["关键词1", "关键词2", ...]),
```

匹配规则是：文章标题或摘要中（不区分大小写）含任一关键词，就归入该类别。一篇文章可同时属于多个类别。

---

## 🔧 常见问题

### Q1：第一次跑 Actions 失败，报 SMTP 认证错误

99% 是授权码问题：

- ✓ `SMTP_PASS` 是 **16 位授权码**（字母数字组合），不是 QQ 登录密码
- ✓ 授权码 **不要带空格**
- ✓ QQ 邮箱里 SMTP 服务真的开启了
- 还不行：关闭 SMTP 服务再重新开启，生成新的授权码

### Q2：报错 `ValueError: invalid literal for int() with base 10: ''`

老版本的 bug，新版已修复。如还遇到，检查 `src/main.py` 的环境变量读取是否用 `or` 而不是 `,` 作为默认值：

```python
# 正确
days_back = int(os.environ.get("DAYS_BACK") or "8")
# 错误（空字符串时会崩）
days_back = int(os.environ.get("DAYS_BACK", "8"))
```

### Q3：某些期刊文章数比官网少几篇

可能原因（按可能性排序）：

1. **Crossref 索引延迟**：Crossref 通常滞后 1–3 天。把 `DAYS_BACK` 调成 `10` 或 `14` 通常能补上
2. **Wiley + Semantic Scholar 滞后**：Adv. Materials / AFM 最新几篇可能 SS 还没分类，但脚本会保留它们，不会少
3. **官网"近一周"算法不同**：Nature 官网可能按"周一到周一"或"online first 时间"算，与我们的 publication date 略有差异
4. **某篇被误判为非研究文章**：检查 Actions 日志里的 `SKIP` 行，看是哪篇被剔除了

### Q4：邮件内容很空（"暂未检索到新文章"）

- 周一邮件正常应有 200+ 篇文章
- 如果连续两周空，去 Actions 看日志，可能 Crossref API 临时故障或限流

### Q5：运行时间超过 30 分钟超时了

修改 `.github/workflows/weekly-digest.yml`：

```yaml
timeout-minutes: 45  # 或 60
```

如果还慢，可以暂时移除 Advanced Functional Materials（这个最多），或者把 `NATURE_FETCH_DELAY_SEC` 从 `0.6` 改成 `0.3`（更激进但有被限流风险）。

### Q6：翻译出来是 `[翻译失败]`

Google Translate 偶尔被限流。一般下次跑就好了。如果持续：
- 减少期刊数量
- 或换 DeepL（需要免费 API key，质量更好）

### Q7：怎么改成不要翻译，只要英文？

编辑 `src/main.py`，注释掉这两行：

```python
# from .translator import translate_articles
# translate_articles(articles)
```

但 Word 表格里的"中文标题"和"中文摘要"列就会是空的。也可以在 `src/document.py` 里删除那两列。

### Q8：GitHub Actions 免费额度够用吗？

完全够。免费账户每月 2000 分钟，本任务每次约 10 分钟，每周一次 = 每月约 40 分钟（2%）。

### Q9：公开仓库定时任务会被暂停吗？

如果仓库 **公开** 且 60 天没人推代码或运行 Actions，定时任务会被 GitHub 自动暂停（环保措施）。**私有仓库不受此限制**，建议保持私有。

如果用公开仓库，每月手动点一次 Run workflow 或推个小提交即可保持活跃。

---

## 🧪 本地测试

如想在部署前先本地跑一次：

```bash
# 1. 进入项目目录
cd nature-science-digest

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量（或复制 .env.example 为 .env 填写）
export SMTP_USER=your-email@qq.com
export SMTP_PASS=your_auth_code
export RECIPIENT=your-email@qq.com

# 4. 先测 SMTP 连接是否正常（不抓取，只发一封测试邮件）
python test_smtp.py

# 5. 完整运行
python -m src.main
```

Windows PowerShell：

```powershell
$env:SMTP_USER="your-email@qq.com"
$env:SMTP_PASS="your_auth_code"
$env:RECIPIENT="your-email@qq.com"
python -m src.main
```

输出文件保存在 `output/MultiJournal_Digest_YYYYMMDD.docx`。

---

## 🔐 安全注意事项

1. **绝对不要** 把 `.env` 提交到 git（`.gitignore` 已经排除）
2. **绝对不要** 把 SMTP 授权码硬编码到源代码里
3. **绝对不要** 把仓库设为 Public（即使代码无密码，Actions 日志也可能泄漏）
4. 如果授权码意外泄露（聊天、截图、群里），立即去 QQ 邮箱关闭并重开 SMTP 服务作废它
5. 定期检查 GitHub `Settings → Security log` 看有无异常登录

---

## 📜 数据来源与版权

- **Crossref REST API**（[api.crossref.org](https://api.crossref.org/)）：免费，无需密钥
- **nature.com**：仅抓取 Dublin Core 元数据（`<meta name="dc.description">`），用于 Google Scholar 等公开索引的部分
- **Semantic Scholar API**（[api.semanticscholar.org](https://api.semanticscholar.org/)）：免费学术 API
- **Google Translate**（通过 deep-translator）：免费翻译服务

摘要版权归原期刊及作者所有，本工具仅作个人学术阅读用途，请勿用于商业再分发。

---

## 🛠️ 技术栈

- Python 3.11+
- `requests` — HTTP 请求
- `python-docx` — Word 文档生成
- `deep-translator` — 英译中
- GitHub Actions — 定时调度

---

## 📝 License

MIT — 自由使用、修改、分发，无任何担保。

---

## 🙋 联系与反馈

本项目源自个人需求，欢迎 Fork 并按自己的研究方向定制。

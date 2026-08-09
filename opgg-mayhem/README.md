# ARAM: Mayhem 出装助手

一个本地小工具：选择英雄后，自动抓取 OP.GG 的 ARAM: Mayhem 数据，
展示该英雄的出装（核心出装 / 鞋子 / 出门装 / 装备统计）、符文、技能加点与强化符文。

## 使用方法

1. 双击 `start.cmd`（会自动找 Python 并启动本地服务器）；
2. 浏览器会自动打开 `http://localhost:8765`；
3. 在搜索框输入英雄名（支持中文名 / 英文名 / ID，例如：暗夜猎手、vayne、67），
   点击结果即可查看数据。

页面默认展示示例英雄「暗夜猎手」，也可以点「↻ 重新抓取」强制更新。

## 手动启动

```bat
python opgg_mayhem_server.py [--port 8765]
```

然后访问 `http://localhost:8765`。

## 部署到 GitHub Pages（全自动，无需手动操作）

项目支持静态部署：抓取脚本在 GitHub 的服务器上自动运行，每周更新数据并自动发布。

### 只需做一次（约 2 分钟）

1. 把本仓库推送到 GitHub（公开仓库即可，Actions 免费）；
2. 打开仓库 **Settings → Pages**，Source 选择 **GitHub Actions**；
3. 推送后第一次需要去 Actions 页面点一次 **Run workflow**，生成初始数据并部署；
4. 完成。之后每周自动更新，不需要任何操作。

### 自动化做了什么

- 每周一 **北京时间 05:00**（周日 21:00 UTC），GitHub Actions 自动运行
  [`.github/workflows/update-data.yml`](../.github/workflows/update-data.yml)；
- 在 GitHub 服务器上抓取全部英雄的 ARAM: Mayhem 数据，生成静态 JSON；
- 自动部署到 GitHub Pages，页面上的数据自动更新；
- 抓取失败时不会覆盖上一次的部署，页面保持可用；
- 想立即更新，在仓库 Actions 页面点 **Run workflow** 按钮即可（这就是手动更新按钮）。

### 静态模式说明

- GitHub Pages 上页面自动进入静态模式：只读取仓库 `data/` 下的 JSON，不再需要本地服务器；
- 静态模式下「重新抓取」按钮会自动隐藏，页头显示「每周自动更新」；
- 本地双击 `index.html`（服务器未启动时）也会走静态模式，但需要服务器在 8765 端口才能在线抓取。

## 接口

| 路径 | 说明 |
| --- | --- |
| `/` | 工具页面 |
| `/api/champions` | 英雄列表（缓存 24 小时） |
| `/api/champion/<slug>` | 指定英雄的 ARAM: Mayhem 数据（缓存 30 分钟） |
| `/api/champion/<slug>?refresh=1` | 强制重新抓取 |

## 数据来源与说明

- 数据抓取自 [OP.GG ARAM: Mayhem](https://op.gg/zh-cn/lol/modes/aram-mayhem) 页面，
  页面为服务端渲染，数据内嵌在页面 HTML 的 RSC 流中，本工具直接解析该数据；
- OP.GG 官方接口（MCP）未提供 ARAM: Mayhem 出装数据，Riot 官方 API 也没有该模式数据，
  因此这是目前唯一稳定的获取方式；
- 抓取结果保存在本地 `cache/` 目录，30 分钟内重复查看不会再次请求 OP.GG；
- 仅供个人学习参考，请勿用于商业用途，注意抓取频率。

## 文件说明

| 文件 | 说明 |
| --- | --- |
| `index.html` | 工具页面（纯 HTML/CSS/JS） |
| `opgg_mayhem_scraper.py` | 抓取与解析（仅标准库） |
| `generate_static.py` | 静态数据生成器（GitHub Actions 用） |
| `opgg_mayhem_server.py` | 本地服务器（仅标准库） |
| `start.cmd` | 一键启动脚本 |
| `.github/workflows/update-data.yml` | 每周一自动抓取 + 部署工作流（可手动触发） |

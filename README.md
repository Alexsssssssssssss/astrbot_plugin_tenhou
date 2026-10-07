# AstrBot 天凤战绩查询插件

在 AstrBot 中安装本插件后，发送 `/thpt 玩家名`，例如 `/thpt fioq421`。

插件请求 nodocchi.moe 网站前端使用的公开接口
`https://nodocchi.moe/api/listuser.php?name=玩家名`，根据返回的真实对局记录分别显示三麻、四麻的：

- 收录场数、记录起止日期
- 各顺位次数及比例、平均顺位、平均对局得点
- 数据源返回的 R 值（如有）及最近 5 场对局
- 最新牌谱推算的段位、段位 PT 及截止时间

统计覆盖接口本次返回的各桌级、东风及半庄记录，不保证完整历史。对局时间使用 UTC+8。
对局得点不是段位 PT。段位/PT 按 nodocchi 网站公开的升降段规则、历史规则变更及账号重置记录重建，
只计段位战，标注为“推算”和最后一场段位战的截止时间；并非官方实时值。
漏收、账号重置或未同步对局可能造成偏差。规则不支持或资料不足时显示“暂不可用”，不会猜测数值。
天凤位不显示普通段位 PT，也不将网站的虚拟 PT 当作真实 PT。
没有收录记录、网络失败或接口异常会明确提示，不会显示虚假的查询成功信息。

## 网络配置

默认使用系统 `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`，没有系统代理时直接连接。
如需指定代理，可在 AstrBot 插件配置中设置 `proxy_url`；留空即可使用默认行为。
不再要求本地 `127.0.0.1:7890` 服务。`timeout_seconds` 默认 30 秒，允许 1～120 秒。
如使用 SOCKS 代理，另行安装 `httpx[socks]`。请勿将代理密码提交到 Git。
云环境须允许访问 `nodocchi.moe`。

## 开发与验证

需要 Python 3.10+ 和 AstrBot（本次验证版本：Python 3.12、AstrBot 4.28.2）。
在已安装 AstrBot 的 Python 环境运行：

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

测试验证段位/PT 重建、升降段、三麻、历史规则和账号重置，并使用 HTTPX MockTransport 验证统计、参数编码、网络错误和接口重试，不依赖外部网站。
真实联网验证：在 AstrBot 中发送 `/thpt fioq421`，核对返回场数、最近对局及详情链接。
数据源属于第三方网站，其接口或收录范围可能变化。

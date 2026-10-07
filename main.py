import asyncio
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

if __package__:
    from .rank import format_rank_lines
else:
    from rank import format_rank_lines

API_URL = 'https://nodocchi.moe/api/listuser.php'
CN_TIME = timezone(timedelta(hours=8))


class DataError(ValueError):
    """The upstream response cannot safely be interpreted as player records."""


class ServiceBusy(Exception):
    pass


async def fetch_records(client: httpx.AsyncClient, name: str):
    # The website's retry value is in milliseconds, while logs are prepared.
    for attempt in range(3):
        response = await client.get(API_URL, params={'name': name})
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            raise DataError('数据源未返回有效 JSON') from exc
        if isinstance(data, dict) and 'retry' in data:
            retry = data['retry']
            if (isinstance(retry, bool) or not isinstance(retry, (int, float))
                    or not math.isfinite(retry) or retry <= 0):
                raise DataError('数据源重试信息异常')
            if attempt == 2 or retry > 10000:
                raise ServiceBusy
            await asyncio.sleep(retry / 1000)
            continue
        return data


def format_records(name: str, data) -> str:
    link = 'https://nodocchi.moe/tenhoulog/#!&name=' + quote(name, safe='')
    if data is False or (isinstance(data, dict) and data.get('name') == name
                         and data.get('list') == []):
        return f'未找到玩家【{name}】的公开对局记录。请确认名称；无收录记录不代表账号不存在。\n{link}'
    if (not isinstance(data, dict) or data.get('name') != name
            or not isinstance(data.get('list'), list)):
        raise DataError('数据源返回的玩家或记录格式异常')
    groups = {3: [], 4: []}
    for row in data['list']:
        if not isinstance(row, dict):
            raise DataError('对局记录格式异常')
        players = row.get('playernum')
        if type(players) is not int or players not in groups:
            raise DataError('对局人数异常')
        positions = [i for i in range(1, players + 1) if row.get(f'player{i}') == name]
        if len(positions) != 1:
            raise DataError('对局中无法唯一确定玩家顺位')
        order = positions[0]  # Upstream player1..player4 are ordered by placement.
        try:
            point = float(row[f'player{order}ptr'])
            timestamp = int(row['starttime'])
            if not math.isfinite(point):
                raise ValueError
            date = datetime.fromtimestamp(timestamp, CN_TIME)
        except (KeyError, ValueError, TypeError, OverflowError, OSError) as exc:
            raise DataError('对局时间或成绩异常') from exc
        groups[players].append((timestamp, date, order, point))
    lines = [f'🀄 天凤战绩【{name}】', '数据源：nodocchi.moe（本次返回的公开对局记录）']
    lines.extend(format_rank_lines(name, data))
    rates = data.get('rate', {})
    for players in (4, 3):
        records = groups[players]
        if not records:
            continue
        records.sort(key=lambda record: record[0])
        count = len(records)
        orders = Counter(record[2] for record in records)
        title = '四麻' if players == 4 else '三麻'
        lines.extend([
            f'\n{title}：{count} 场',
            f'记录范围：{records[0][1]:%Y-%m-%d} ～ {records[-1][1]:%Y-%m-%d}',
            '顺位：' + ' / '.join(f'{i}位 {orders[i]} ({orders[i] / count:.1%})' for i in range(1, players + 1)),
            f'平均顺位：{sum(record[2] for record in records) / count:.3f}',
            f'平均对局得点：{sum(record[3] for record in records) / count:+.2f}（非段位 PT）',
        ])
        rate = rates.get(str(players)) if isinstance(rates, dict) else None
        if isinstance(rate, (int, float)) and not isinstance(rate, bool) and math.isfinite(rate):
            lines.append(f'数据源 R 值：{rate:g}（非实时保证）')
        lines.append('最近 5 场（UTC+8）：')
        for _, date, order, point in reversed(records[-5:]):
            lines.append(f'  {date:%m-%d %H:%M}  {order}位  {point:+.1f}')
    lines.extend(['\n统计包含各桌级及东风/半庄，以数据源收录为准，不保证完整历史。', f'详情：{link}'])
    return '\n'.join(lines)


@register('tenhou_tracker', 'dawwq', '天凤战绩及段位/PT推算', '1.2.0')
class TenhouTracker(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}

    @filter.command('thpt')
    async def query_thpt(self, event: AstrMessageEvent, name: str = ''):
        """查询天凤公开对局战绩，用法：/thpt 玩家名。"""
        name = name.strip()
        if not name:
            yield event.plain_result('请提供天凤玩家名称！例如：/thpt fioq421')
            return
        if len(name) > 100 or any(ord(char) < 32 for char in name):
            yield event.plain_result('玩家名称过长或包含控制字符，请检查输入。')
            return
        yield event.plain_result(f'正在获取玩家【{name}】的天凤战绩...')
        try:
            proxy = str(self.config.get('proxy_url', '')).strip() or None
            timeout = float(self.config.get('timeout_seconds', 30))
            if not math.isfinite(timeout) or not 1 <= timeout <= 120:
                raise ValueError('timeout_seconds 必须在 1～120 秒之间')
            # Without an explicit proxy, HTTPX honors system proxy variables.
            async with httpx.AsyncClient(
                proxy=proxy, timeout=timeout, follow_redirects=True,
                headers={'User-Agent': 'astrbot_plugin_tenhou/1.2.0', 'Accept': 'application/json'},
            ) as client:
                data = await fetch_records(client, name)
            result = format_records(name, data)
        except ServiceBusy:
            result = '数据源正在整理玩家记录，请稍后重试。'
        except httpx.TimeoutException:
            result = '查询超时，请稍后重试或检查代理配置。'
        except httpx.HTTPStatusError as exc:
            result = f'查询失败：数据源返回 HTTP {exc.response.status_code}，请稍后重试。'
        except httpx.RequestError:
            result = '查询失败：无法连接数据源，请检查网络及代理配置。'
        except DataError as exc:
            result = f'查询失败：{exc}。请稍后重试。'
        except (ValueError, TypeError):
            result = '查询失败：插件网络配置无效，请检查代理地址和超时设置。'
        yield event.plain_result(result)

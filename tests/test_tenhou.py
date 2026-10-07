import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx
import main


def record(players, order, point, timestamp):
    row = {'playernum': players, 'starttime': timestamp, 'sctype': 'b',
           'playerlevel': 0, 'playlength': 1}
    for position in range(1, players + 1):
        row[f'player{position}'] = '测试' if position == order else f'other{position}'
        row[f'player{position}ptr'] = str(point if position == order else 0)
    return row


class StatisticsTests(unittest.TestCase):
    def test_groups_statistics_and_sorted_recent(self):
        data = {'name': '测试', 'rate': {'4': 1972}, 'list': [
            record(4, 4, -40, 1700003600), record(3, 2, 5, 1700000000),
            record(4, 1, 50, 1700000000)]}
        result = main.format_records('测试', data)
        self.assertIn('四麻：2 场', result)
        self.assertIn('三麻：1 场', result)
        self.assertIn('1位 1 (50.0%)', result)
        self.assertIn('平均顺位：2.500', result)
        self.assertIn('平均对局得点：+5.00', result)
        self.assertIn('R 值：1972', result)
        self.assertLess(result.index('4位  -40.0'), result.index('1位  +50.0'))
        self.assertIn('name=%E6%B5%8B%E8%AF%95', result)

    def test_no_records(self):
        for data in [False, {'name': '测试', 'list': []}]:
            self.assertIn('未找到', main.format_records('测试', data))

    def test_invalid_payloads_are_not_success(self):
        for data in [None, True, [], {}, {'name': 'wrong', 'list': []},
                     {'name': '测试', 'list': [record(4, 0, 0, 1700000000)]},
                     {'name': '测试', 'list': [record(4, 1, 'nan', 1700000000)]}]:
            with self.subTest(data=data), self.assertRaises(main.DataError):
                main.format_records('测试', data)

    def test_recent_is_limited(self):
        data = {'name': '测试', 'list': [record(4, 1, i, 1700000000+i) for i in range(10)]}
        result = main.format_records('测试', data)
        self.assertEqual(sum(line.startswith('  ') for line in result.splitlines()), 5)


class NetworkTests(unittest.IsolatedAsyncioTestCase):
    async def fetch(self, handler, name='测试&name=other'):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await main.fetch_records(client, name)

    async def test_encoded_name_and_real_api_path(self):
        def handler(request):
            self.assertEqual(request.url.path, '/api/listuser.php')
            self.assertEqual(dict(request.url.params), {'name': '测试&name=other'})
            return httpx.Response(200, json=False)
        self.assertIs(await self.fetch(handler), False)

    async def test_retry_then_success(self):
        responses = iter([{'retry': 100}, {'name': '测试', 'list': []}])
        with patch.object(main.asyncio, 'sleep', new_callable=AsyncMock) as sleep:
            data = await self.fetch(lambda request: httpx.Response(200, json=next(responses)), '测试')
        sleep.assert_awaited_once_with(0.1)
        self.assertEqual(data['list'], [])

    async def test_retry_is_bounded(self):
        with patch.object(main.asyncio, 'sleep', new_callable=AsyncMock) as sleep:
            with self.assertRaises(main.ServiceBusy):
                await self.fetch(lambda request: httpx.Response(200, json={'retry': 10}))
        self.assertEqual(sleep.await_count, 2)

    async def test_invalid_json(self):
        with self.assertRaises(main.DataError):
            await self.fetch(lambda request: httpx.Response(200, text='<html>maintenance</html>'))

    async def test_http_status(self):
        with self.assertRaises(httpx.HTTPStatusError):
            await self.fetch(lambda request: httpx.Response(403))

    async def command(self, handler, name='测试', config=None):
        class Event:
            def plain_result(self, text):
                return text
        original = httpx.AsyncClient
        def factory(**kwargs):
            self.assertIsNone(kwargs['proxy'])
            return original(transport=httpx.MockTransport(handler), **kwargs)
        plugin = main.TenhouTracker(None, config)
        with patch.object(main.httpx, 'AsyncClient', factory):
            return [result async for result in plugin.query_thpt(Event(), name)]

    async def test_command_success(self):
        data = {'name': '测试', 'list': [record(4, 1, 45, 1700000000)]}
        result = await self.command(lambda request: httpx.Response(200, json=data))
        self.assertEqual(len(result), 2)
        self.assertIn('四麻：1 场', result[-1])
        self.assertIn('段位/PT（最新牌谱推算，非官方实时值）', result[-1])
        self.assertIn('四麻：9级 / 0 PT', result[-1])

    async def test_command_network_errors(self):
        for error, expected in [(httpx.ConnectError('failed'), '无法连接'),
                                (httpx.ReadTimeout('timeout'), '查询超时')]:
            def handler(request):
                raise error
            result = await self.command(handler)
            self.assertIn(expected, result[-1])
            self.assertNotIn('战绩摘要', result[-1])

    async def test_command_missing_name(self):
        result = await self.command(lambda request: self.fail('must not request'), name=' ')
        self.assertEqual(len(result), 1)
        self.assertIn('请提供', result[0])

    async def test_invalid_config(self):
        result = await self.command(lambda request: self.fail('must not request'), config={'timeout_seconds': 0})
        self.assertIn('配置无效', result[-1])


if __name__ == '__main__':
    unittest.main()

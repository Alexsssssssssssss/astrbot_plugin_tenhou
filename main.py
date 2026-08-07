from astrbot.api.all import *
import httpx
from bs4 import BeautifulSoup

@register("tenhou_tracker", "YourName", "天凤战绩查询插件", "1.0.0")
class TenhouTracker(Star):
    def __init__(self, context: Context):
        super().__init__(context)
    
    @filter.command("thpt")
    async def query_thpt(self, event: AstrMessageEvent, name: str):
        '''查询天凤段位与战绩 (用法: /thpt 玩家名)'''
        if not name:
            yield event.plain_result("请提供天凤玩家名称！例如: /thpt 你的天凤ID")
            return
            
        yield event.plain_result(f"正在前往 Nodocchi 查询玩家【{name}】的天凤数据，请稍候...")
        
        try:
            url = f"https://nodocchi.cl/mypage/?name={name}"
            # 异步请求 Nodocchi 页面
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=15.0)
                
            if resp.status_code != 200:
                yield event.plain_result(f"查询失败，Nodocchi 返回状态码: {resp.status_code}")
                return

            # 这里目前是模拟的假数据。
            # 下一步我们需要根据 Nodocchi 真实的网页结构，用 BeautifulSoup 提取真实数据替换这里。
            rank_4, pt_4 = "雀豪1", "1200/2000"
            rank_3, pt_3 = "雀圣1", "500/2000"
            recent_stats = "1位: 5次, 2位: 2次, 3位: 1次, 4位: 2次"

            reply_msg = (
                f"🀄 玩家【{name}】天凤战绩 🀄\n"
                f"------------------------\n"
                f"【四麻】{rank_4} (PT: {pt_4})\n"
                f"【三麻】{rank_3} (PT: {pt_3})\n"
                f"------------------------\n"
                f"【最近十场战绩】\n{recent_stats}"
            )
            
            yield event.plain_result(reply_msg)
            
        except httpx.TimeoutException:
            yield event.plain_result("查询超时，可能网络连接失败，请稍后再试。")
        except Exception as e:
            yield event.plain_result(f"执行时发生未知错误: {str(e)}")

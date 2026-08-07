from astrbot.api.all import *
from astrbot.api.event import filter
import httpx

@register("tenhou_tracker", "YourName", "天凤战绩查询插件", "1.0.0")
class TenhouTracker(Star):
    def __init__(self, context: Context):
        super().__init__(context)
    
    @filter.command("thpt")
    async def query_thpt(self, event: AstrMessageEvent, name: str):
        '''查询天凤段位与战绩 (用法: /thpt 玩家名)'''
        if not name:
            yield event.plain_result("请提供天凤玩家名称！例如: /thpt fioq421")
            return
            
        yield event.plain_result(f"正在查询玩家【{name}】的战绩数据...")
        
        try:
            # 使用 nodocchi 网页端真正的玩家数据查询接口
            api_url = f"https://nodocchi.moe/api/user.cgi?name={name}"
            proxy_url = "http://127.0.0.1:7897"  # 如果你的代理端口不是 7890 请修改
            
            async with httpx.AsyncClient(proxy=proxy_url) as client:
                resp = await client.get(api_url, timeout=15.0)
                
            if resp.status_code != 200:
                yield event.plain_result(f"查询失败，服务器返回状态码: {resp.status_code}")
                return

            data = resp.json()
            
            if not data:
                yield event.plain_result(f"未找到玩家【{name}】的记录。")
                return

            # 解析返回的玩家真实数据
            nickname = data.get("name", name)
            
            # 提取四麻与三麻的关键段位和积分字段
            # 根据 nodocchi 官方 api 结构
            detail_4 = data.get("rate4", {})
            dan_4 = detail_4.get("dan", "未知") if isinstance(detail_4, dict) else "未知"
            
            detail_3 = data.get("rate3", {})
            dan_3 = detail_3.get("dan", "未知") if isinstance(detail_3, dict) else "未知"
            
            reply_msg = (
                f"🀄 玩家【{nickname}】天凤战绩 🀄\n"
                f"------------------------\n"
                f"【四人麻将段位】{dan_4}\n"
                f"【三人麻将段位】{dan_3}\n"
                f"------------------------\n"
                f"🔗 详细页面: https://nodocchi.moe/tenhoulog/#!&name={name}"
            )
            
            yield event.plain_result(reply_msg)
            
        except Exception as e:
            yield event.plain_result(f"解析数据时发生错误: {str(e)}")

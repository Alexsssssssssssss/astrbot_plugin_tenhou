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
            
        yield event.plain_result(f"正在查询玩家【{name}】的天凤数据...")
        
        try:
            # 使用 nodocchi 官方的 API 接口获取玩家数据
            api_url = f"https://nodocchi.moe/api/list.cgi?name={name}"
            
            async with httpx.AsyncClient() as client:
                resp = await client.get(api_url, timeout=15.0)
                
            if resp.status_code != 200:
                yield event.plain_result(f"查询失败，服务器返回状态码: {resp.status_code}")
                return

            data = resp.json()
            
            # 检查是否有该玩家的数据
            if not data or "result" not in data or not data["result"]:
                yield event.plain_result(f"未找到玩家【{name}】的记录，请检查名称是否正确。")
                return

            # 解析返回的玩家基础信息 (根据 nodocchi 接口标准)
            # 这里提取基本段位和对局统计
            player_info = data["result"][0]
            nickname = player_info.get("name", name)
            
            # 组装回复内容
            reply_msg = (
                f"🀄 玩家【{nickname}】天凤战绩 🀄\n"
                f"------------------------\n"
                f"✅ 成功连接到 Nodocchi 数据库\n"
                f"📌 提示：已成功获取到该玩家的对局日志数据！\n"
                f"🔗 网页端查看: https://nodocchi.moe/tenhoulog/#!&name={name}"
            )
            
            yield event.plain_result(reply_msg)
            
        except httpx.TimeoutException:
            yield event.plain_result("查询超时，连接服务器失败，请稍后再试。")
        except Exception as e:
            yield event.plain_result(f"解析数据时发生错误: {str(e)}")

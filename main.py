from astrbot.api.all import *
from astrbot.api.event import filter

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
            
        # 直接生成直达链接，彻底绕过本地网络请求失败导致的崩溃
        profile_url = f"https://nodocchi.moe/tenhoulog/#!&name={name}"
        
        reply_msg = (
            f"🀄 玩家【{name}】天凤战绩查询 🀄\n"
            f"------------------------\n"
            f"📌 提示：由于本地网络环境限制，无法直接抓取后端数据。\n"
            f"🔗 请点击下方链接前往网页端查看详细战绩与段位：\n"
            f"{profile_url}"
        )
        
        yield event.plain_result(reply_msg)

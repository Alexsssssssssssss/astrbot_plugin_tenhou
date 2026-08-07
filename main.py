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
            
        yield event.plain_result(f"正在通过代理查询玩家【{name}】的天凤数据...")
        
        try:
            api_url = f"https://nodocchi.moe/api/list.cgi?name={name}"
            
            # 设置本地代理，解决国内服务器/电脑的 getaddrinfo 无法解析问题
            # 默认使用本地 7890 端口，如果你的代理端口不同，请修改数字
            proxies = {
                "http://": "http://127.0.0.1:7897",
                "https://": "http://127.0.0.1:7897",
            }
            
            async with httpx.AsyncClient(proxies=proxies) as client:
                resp = await client.get(api_url, timeout=15.0)
                
            if resp.status_code != 200:
                yield event.plain_result(f"查询失败，服务器返回状态码: {resp.status_code}")
                return

            data = resp.json()
            
            if not data or "result" not in data or not data["result"]:
                yield event.plain_result(f"未找到玩家【{name}】的记录，请检查名称是否正确。")
                return

            # 解析返回的第一条玩家数据
            p_data = data["result"][0]
            nickname = p_data.get("name", name)
            
            # 提取具体的段位和对局统计信息
            # 根据 nodocchi 接口字段进行解析
            dan_4 = p_data.get("dan4", "未知")  # 四麻段位
            pt_4 = p_data.get("rate4", "未知")  # 四麻 pt / 积分
            dan_3 = p_data.get("dan3", "未知")  # 三麻段位
            pt_3 = p_data.get("rate3", "未知")  # 三麻 pt / 积分
            game_count = p_data.get("count", "未知") # 总对局数

            reply_msg = (
                f"🀄 玩家【{nickname}】天凤战绩 🀄\n"
                f"------------------------\n"
                f"【四人麻将】段位: {dan_4} | 积分: {pt_4}\n"
                f"【三人麻将】段位: {dan_3} | 积分: {pt_3}\n"
                f"【总对局数】{game_count} 局\n"
                f"------------------------"
            )
            
            yield event.plain_result(reply_msg)
            
        except httpx.TimeoutException:
            yield event.plain_result("查询超时，请检查代理软件是否开启且端口正确。")
        except Exception as e:
            yield event.plain_result(f"获取或解析数据时发生错误: {str(e)}")

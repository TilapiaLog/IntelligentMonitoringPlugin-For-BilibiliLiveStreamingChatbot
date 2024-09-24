from flask import Flask, render_template, jsonify,send_file # 导入Flask及其相关模块
import asyncio  # 导入异步编程模块
import logging  # 导入日志模块
import os  # 导入操作系统模块
import aiohttp  # 导入异步HTTP客户端模块
import blivedm  # 导入直播弹幕处理模块
import blivedm.models.web as web_models  # 导入web模型
import threading  # 导入线程模块
import random  # 导入随机数模块
from collections import defaultdict  # 导入默认字典
from wordcloud import WordCloud  # 导入词云模块
import matplotlib.pyplot as plt  # 导入matplotlib用于绘图
import io
# 创建Flask应用
app = Flask(__name__)

# 创建输出目录和日志目录
os.makedirs('OutPut', exist_ok=True)  # 创建输出目录
os.makedirs('OutPut/DanmuLog', exist_ok=True)  # 创建弹幕日志目录
os.makedirs('OutPut/ViolationLog', exist_ok=True)  # 创建违规日志目录

# 自定义日志过滤器类
class WarningKeywordFilter(logging.Filter):
    def __init__(self, keywords):  # 初始化方法，接收关键词列表
        super().__init__()  # 调用父类初始化
        self.keywords = keywords  # 存储关键词

    def filter(self, record):  # 过滤方法
        if record.levelno == logging.INFO:  # 如果日志级别为INFO
            return not any(keyword in record.getMessage() for keyword in self.keywords)  # 过滤包含关键词的日志
        return True  # 其他级别的日志不过滤

# 配置日志记录
logging.basicConfig(
    filename='app.log',  # 日志文件名
    filemode='a',  # 追加模式
    format='%(asctime)s - %(levelname)s - %(message)s',  # 日志格式
    level=logging.DEBUG  # 日志级别
)

logger = logging.getLogger()  # 获取日志记录器

# 加载配置文件
def load_config():
    with open('Database/room_ids.txt', 'r', encoding='utf-8') as f:  # 读取房间ID文件
        room_ids = [int(line.strip()) for line in f.readlines()]  # 解析房间ID为整数列表
    
    with open('Database/keywords.txt', 'r', encoding='utf-8') as f:  # 读取关键词文件
        keywords = [line.strip() for line in f.readlines()]  # 解析关键词为列表
    
    with open('Database/sessdata.txt', 'r', encoding='utf-8') as f:  # 读取会话数据文件
        sessdata = f.read().strip()  # 读取会话数据
    
    return room_ids, keywords, sessdata  # 返回房间ID、关键词和会话数据

# 加载配置
TEST_ROOM_IDS, WARNING_KEYWORDS, SESSDATA = load_config()  # 调用加载配置函数
logger.addFilter(WarningKeywordFilter(WARNING_KEYWORDS))  # 添加关键词过滤器

# 存储弹幕消息
normal_danmu_messages = []  # 存储普通弹幕消息
violation_danmu_messages = []  # 存储违规弹幕消息
violation_user_count = defaultdict(int)  # 存储违规用户名计数
all_danmu_messages = []  # 存储所有弹幕消息

class MyHandler(blivedm.BaseHandler):
    def _on_danmaku(self, client: blivedm.BLiveClient, message: web_models.DanmakuMessage):
        # 处理普通弹幕
        log_message = f'普通弹幕：来自[{client.room_id}]直播间 UID[{client.uid}]  用户名[{message.uname}]  弹幕内容[{message.msg}]'
        logger.info(log_message)
        print(log_message)
        normal_danmu_messages.append(log_message)
        all_danmu_messages.append(message.msg)  # 收集所有弹幕内容
        with open(f'OutPut/DanmuLog/{client.room_id}_danmu.log', 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')

        # 检查是否为违规弹幕
        message_content = message.msg.strip().lower()
        if any(keyword.strip().lower() in message_content for keyword in WARNING_KEYWORDS):
            violation_log_message = f'违规弹幕：来自[{client.room_id}]直播间 UID[{client.uid}]  用户名[{message.uname}]  弹幕内容[{message.msg}]'
            logger.warning(violation_log_message)
            print(violation_log_message)
            violation_danmu_messages.append(violation_log_message)
            violation_user_count[message.uname] += 1
            with open(f'OutPut/ViolationLog/{client.room_id}_violation.log', 'a', encoding='utf-8') as f:
                f.write(violation_log_message + '\n')
                f.write(f'UID[{client.uid}] 用户名[{message.uname}]  违规次数[{violation_user_count[message.uname]}]\n')

    def _on_super_chat(self, client: blivedm.BLiveClient, message: web_models.SuperChatMessage):
        # 处理超级弹幕
        log_message = f'超级弹幕： 来自[{client.room_id}]直播间 UID[{client.uid}]  用户名[{message.uname}]  弹幕内容[{message.message}]'
        logger.info(log_message)
        print(log_message)
        normal_danmu_messages.append(log_message)
        all_danmu_messages.append(message.message)  # 收集所有弹幕内容
        with open(f'OutPut/DanmuLog/{client.room_id}_danmu.log', 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')

@app.route('/')  # 定义根路由
def index():
    return render_template('index.html')  # 渲染主页面

@app.route('/danmu')  # 定义弹幕路由
def get_danmu():
    return jsonify({  # 返回JSON格式的弹幕数据
        'normal': normal_danmu_messages,  # 普通弹幕
        'violation': violation_danmu_messages  # 违规弹幕
    })

@app.route('/violation_counts')  # 定义违规计数路由
def get_violation_counts():
    return jsonify(violation_user_count)  # 返回违规用户计数的JSON数据

@app.route('/wordcloud')  # 定义词云路由
def generate_wordcloud():
    text = ' '.join(all_danmu_messages)  # 将所有弹幕内容合并为一个字符串
    wordcloud = WordCloud(
        width=800,
        height=400,
        background_color='white',
        font_path='Ttf/SimHei.ttf'  # 指定中文字体路径
    ).generate(text)  # 生成词云

    # 将词云图像保存到字节流中
    img = io.BytesIO()
    plt.figure(figsize=(10, 5))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')  # 不显示坐标轴
    plt.savefig(img, format='png')  # 保存为PNG格式
    img.seek(0)  # 重置字节流位置

    return send_file(img, mimetype='image/png')  # 返回词云图像

async def main():  # 主异步函数
    async with aiohttp.ClientSession() as session:  # 创建异步HTTP会话
        try:
            await run_single_client(session)  # 运行单个客户端
            await run_multi_clients(session)  # 运行多个客户端
        except Exception as e:  # 捕获异常
            logging.error(f"发生错误: {e}")  # 记录错误日志
        finally:
            logging.info("程序结束，所有客户端已停止。")  # 记录程序结束信息

async def run_single_client(session):  # 运行单个客户端的异步函数
    room_id = random.choice(TEST_ROOM_IDS)  # 随机选择房间ID
    client = blivedm.BLiveClient(room_id, session=session)  # 创建直播客户端
    handler = MyHandler()  # 创建弹幕处理器
    client.set_handler(handler)  # 设置处理器

    retry_attempts = 5  # 重试次数
    for attempt in range(retry_attempts):  # 尝试连接
        try:
            await client.join()  # 加入直播间
            break  # 成功连接，跳出循环
        except Exception as e:  # 捕获连接异常
            logging.error(f"连接失败: {e}, 尝试重新连接... (尝试次数: {attempt + 1})")  # 记录连接失败日志
            await asyncio.sleep(2)  # 等待2秒后重试
        finally:
            await client.stop_and_close()  # 停止并关闭客户端

async def run_multi_clients(session):  # 运行多个客户端的异步函数
    clients = [blivedm.BLiveClient(room_id, session=session) for room_id in TEST_ROOM_IDS]  # 创建多个客户端
    handler = MyHandler()  # 创建弹幕处理器
    for client in clients:  # 为每个客户端设置处理器
        client.set_handler(handler)
        client.start()  # 启动客户端

    try:
        await asyncio.gather(*(client.join() for client in clients))  # 等待所有客户端加入
    finally:
        await asyncio.gather(*(client.stop_and_close() for client in clients))  # 停止并关闭所有客户端

def run_asyncio_loop():  # 运行异步事件循环的函数
    asyncio.run(main())  # 启动主异步函数

if __name__ == '__main__':  # 如果是主程序
    threading.Thread(target=run_asyncio_loop, daemon=True).start()  # 启动异步事件循环的线程
    app.run(host='0.0.0.0', port=5000)  # 启动Flask应用
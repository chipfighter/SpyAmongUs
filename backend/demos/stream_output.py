import getpass
import os

# 得到api
if not os.environ.get("DEEPSEEK_API_KEY"):
  os.environ["DEEPSEEK_API_KEY"] = getpass.getpass("输入Deepseek的api: ")

from langchain_deepseek import ChatDeepSeek

llm = ChatDeepSeek(
    model="deepseek-chat",
    temperature=1.3,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=os.environ["DEEPSEEK_API_KEY"]
)

messages = [
    ("system", "你是乐于助人的小助手"),
    ("human", "你好"),
]

# 启动流式对话
stream = llm.stream(messages)
# 获取第一个片段
full = next(stream).content
print(full, end="", flush=True)  # 首次输出

# 逐步输出每个数据块，覆盖之前的内容
for chunk in stream:
    print("\r", end="")  # 清空当前行的内容
    full += chunk.content
    print(full, end="", flush=True)  # 输出新的片段，覆盖上一个片段

print()  # 输出换行
print("完整的返回内容：")
print(full)  # 输出最终的完整内容
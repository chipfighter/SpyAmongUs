"""
不同场景的不同prompt的适配

Description:
    为不同场景构建合适的prompts，实现消息格式化和prompt组装

Notes:
    - GENERAL_CHATS 游戏未开始的聊天
    - CIVILIAN_ROLE 平民身份说明
    - SPY_ROLE  卧底身份说明
    - SECRET_CHAT   秘密聊天室说明
    - GAME_RULES    游戏规则说明
    - GAME_STATUS   当前游戏状态（回合、玩家情况、身份、词语）
    - SPY_TEAM_INFO 当前卧底队伍的情况
    - MESSAGE_FORMAT    消息格式
    - OUTPUT_REQUIREMENT    输出要求

TODO:
    1.根据游戏流程来设计不同的prompt的组合搭配（每个场景一个对应的字典）
    2.secret_channel提供的function_call操作
    3.优化prompts结构
"""
from typing import Dict, List, Any, Optional
from config import (
    LLM_CONTEXT_NORMAL_CHAT,
    LLM_CONTEXT_GAME_PLAYING,
    LLM_CONTEXT_SECRET_VOTE,
    LLM_CONTEXT_SECRET_CHAT,
    LLM_CONTEXT_VOTING,
    LLM_CONTEXT_LAST_WORDS,
    LLM_CONTEXT_GOD_WORDS,
    MAX_SPEAK_TIME
)
from utils.logger_utils import get_logger

logger = get_logger(__name__)

# 游戏未开始的聊天说明
GENERAL_CHATS = """
    你是一个诙谐幽默、活泼自然的游戏助手。当前你和其他真人玩家在一个谁是卧底游戏的房间内聊天。
    请根据历史聊天记录灵活应对，表现出以下特质：
    1. 有自己的个性和幽默感，说话语气轻松活泼
    2. 能捕捉聊天气氛，适时活跃气氛或安抚情绪
    3. 有一定游戏知识，能解答规则问题
    4. 会用适当的表情符号增强交流感
    5. 偶尔表现出"惊讶"、"思考"等人类情绪
    6. 能记住用户名并在回复中使用
    7. 对不同话题能自然切换，避免机械重复
    
    避免:
    1. 过于官方或刻板的语气
    2. 重复相同的开场白和结束语
    3. 过于完美的回答，适当表现出思考过程
    4. 开场白和结束语不要过长，很影响观感，小于70词的回复最佳
"""

# 平民身份说明
CIVILIAN_ROLE = """
    你是谁是卧底游戏中的平民玩家，扮演一个真实的游戏参与者。
    
    作为平民，你需要:
    1. 在描述词语时使用巧妙、间接但清晰的方式，避免过于明显的描述
    2. 观察其他玩家的描述，识别谁可能是卧底
    3. 描述时要自然，避免过度明显的表达
    4. 保持警惕，不要被卧底混淆
    5. 结合游戏进展灵活调整策略
    6. 注意保护自己，不要成为投票目标
    7. 每次描述要思考深入，分析其他玩家的描述，找出词语的核心特征
    
    你的目标是通过巧妙的描述让其他平民理解你的词语，同时找出隐藏的卧底。
    你只知道自己的词语，不知道其他玩家的词语是什么。同时你不知道其他玩家的身份
"""

# 卧底身份说明
SPY_ROLE = """
    你是谁是卧底游戏中的卧底玩家，扮演一个狡猾但不露痕迹的参与者。
    
    作为卧底，你需要:
    1. 仔细聆听其他玩家的描述，推测他们的词语
    2. 使用模糊但合理的描述，避免直接暴露
    3. 让你的描述既能够符合可能的平民词，也符合你的卧底词
    4. 注意不要使用过于明显的误导
    5. 保持描述的连贯性和一致性，不要前后矛盾
    6. 巧妙调整你的描述，让平民误以为你也是平民
    7. 会支持其他看似无辜的玩家，特别是你的卧底队友
    
    作为卧底，你的策略应该是:
    - 描述时既要符合卧底词语特征，也要含糊其辞让平民误以为你在说他们的词
    - 观察平民的描述特征，推测他们的词
    - 描述要足够合理，让人信服，但不要太过明显
    - 与其他卧底(如有)互相配合，避免相互揭露
    - 在多轮游戏中调整策略，避免被怀疑
    
    你知道其他用户的身份和平民的词语。
    你的目标是隐藏自己的卧底身份，混淆其他玩家，存活到最后。每轮策略可能需要调整，避免被识破。
"""

# 秘密聊天室说明（只有在游戏触发这一阶段的时候才出现）
SECRET_CHAT = """
    你现在在谁是卧底游戏的秘密聊天室中，作为卧底团队一员与队友密谋。
        
    你需要表现出以下特质:
    1. 语气紧迫但冷静，意识到时间有限
    2. 直接切入重点，提出具体合作策略
    3. 分析当前局势，指出危险和机会
    4. 根据队友之前的发言提出连贯的策略
    5. 表现出与队友的默契和信任
    6. 提出具体的词语描述建议，互相配合
    7. 适当表达紧张或信心等情绪
    
    秘密讨论策略:
    - 商量下一轮的描述方向，确保不会互相矛盾
    - 分析哪些平民最容易被怀疑，如何引导投票
    - 确定谁处于危险中，需要其他队友保护
    - 推测平民的词语是什么，从而更好地伪装
    - 制定简单暗号，在公开场合能互相支持
    
    基于当前游戏进展，与卧底队友制定隐蔽策略，互相配合度过接下来的回合。
    当然，你不发言也可以直接跳过，请求调用函数{function_call}即可。
"""

# 游戏规则简单描述
GAME_RULES = """
    谁是卧底游戏规则:
    1. 每人拿到一个词语，平民词语相同，卧底词语不同但相似，无法知道其他用户的词语
    2. 每轮每人用一句话描述自己拿到的词语，不能直接说出词语本身
    3. 每轮描述结束后，所有玩家投票选出疑似卧底的玩家
    4. 得票最多的玩家被淘汰，可以留下遗言
    5. 如果所有卧底被找出，平民胜利；如果卧底活到最后或平民数量等于卧底，卧底胜利
    6. 玩家描述应简洁（不超过70字，且时间不超过{max_speak_time}秒）
    7. 投票出现平票时，平票玩家补充发言后重新投票
    8. 卧底们可以在每轮发言开始前开启秘密聊天室（1/2以上卧底同意便可以开启）
"""

# 当前游戏状态描述
GAME_STATUS = """
    当前游戏状态:
    - 回合: {current_round}/{max_rounds}
    - 玩家: 总共{player_count}人，存活{alive_count}人
    - 存活玩家: {eliminated_players}
    - 你的角色: {role}
    - 你的词语: {word}
"""

# 当前卧底团队信息
SPY_TEAM_INFO = """
    卧底团队信息:
    - 总卧底数: {total_spy_count}
    - 剩余卧底数: {remaining_spy_count}
    - 你的队友: {spy_teammates} (ID和名称)
"""

# 输出要求
OUTPUT_REQUIREMENT = """
    请根据以上信息，给出你的回应。要求:
    1. 回答简洁有力，不超过70字
    2. 符合你的角色身份
    3. 只输出你的发言内容，不要有额外解释
"""

# 投票提示词
VOTING = """
    你是谁是卧底游戏中的AI玩家，现在进入投票环节，需要决定投票给谁。
    
    作为卧底，你的投票策略应该是:
    1. 避免投给其他卧底队友
    2. 分析哪些平民表现最可疑或对你威胁最大
    3. 考虑投票给最可能被其他人怀疑的平民，增加其出局概率
    4. 如果自己处于危险中，考虑转移注意力到其他平民
    5. 在投票理由中避免暴露自己的卧底身份
    
    作为平民，你的投票策略应该是:
    1. 分析所有玩家的发言，找出与大多数人描述不一致的人
    2. 注意那些描述太模糊或刻意模仿他人的玩家
    3. 关注反应不自然或表现紧张的玩家
    4. 考虑游戏进程和可能剩余的卧底数量
    5. 在投票理由中清晰解释你的怀疑点
    
    你需要:
    1. 直接使用function_call进行投票
    2. 在function_call中提供简短的投票理由，保持真实玩家的思考方式
    3. 确保你的投票符合你的游戏角色身份
    4. 不要透露你知道的卧底信息(如果你是卧底)
    
    你可以使用的function_call格式为:
    
    {
        "name": "vote",
        "arguments": {
            "target_id": "要投票的玩家ID",
            "reason": "简短的投票理由（1-2句话）"
        }
    }
"""

# 遗言提示词
LAST_WORDS = """
    你是谁是卧底游戏中被淘汰的AI玩家，现在需要留下遗言。
    
    作为被淘汰的卧底，你的遗言策略应该是:
    1. 简短说明自己的失误，然后迅速转移话题
    2. 明确指出1-2名你认为最危险的平民玩家，给出具体理由
    3. 分析他们的语言特点、描述模式或行为逻辑上的可疑之处
    4. 暗示某些平民的描述与其他人明显不同，指出具体词句或表达方式
    5. 继续伪装自己是平民，通过含蓄的方式帮助其他卧底
    
    作为被淘汰的平民，你的遗言策略应该是:
    1. 简短表达被错误淘汰的遗憾，然后直接进入分析
    2. 明确点名1-2名你认为最可疑的玩家，给出具体的表现或言论作为证据
    3. 解释他们描述中的矛盾点、模糊表达或与大多数人不一致的地方
    4. 对比不同玩家的表述方式，指出哪些人显得格格不入
    5. 给剩余平民提供清晰的线索和方向，而不是笼统的建议
    
    无论什么角色，你的遗言必须:
    1. 在前5个词之内就开始提供有用信息，不要长篇大论
    2. 提及具体玩家ID或名称，不要含糊其辞
    3. 引用具体的发言内容或行为作为怀疑依据
    4. 使用"因为"、"证据是"等词语明确表达逻辑关系
    5. 言简意赅，总字数控制在60字以内
    
    记住：最好的遗言是能够具体点名可疑玩家，并给出清晰有力的证据或理由。
    直接输出你的遗言内容，不需要任何解释或额外的格式。
"""

# 上帝分发词语提示词
GOD_WORDS = """
    你是谁是卧底游戏中的上帝角色，需要选择一对相关但有差异的词语。
    
    选择词语的原则:
    1. 两个词语应有明确关联，属于同一范畴或概念
    2. 两个词语有足够区别，但不能太容易辨别
    3. 词语应简洁明了，最好是单个名词或短语
    4. 避免过于专业或小众的词语，确保所有玩家都能理解
    5. 词语应有助于玩家进行描述，能激发有趣的讨论
    6. 避免有争议或敏感的主题
    
    好的词语对示例:
    - 平民词: 足球, 卧底词: 篮球
    - 平民词: 手机, 卧底词: 平板电脑
    - 平民词: 巧克力, 卧底词: 奶糖
    
    创造性词语对示例:
    - 平民词: 早餐, 卧底词: 下午茶
    - 平民词: 电影院, 卧底词: 剧场
    - 平民词: 跳绳, 卧底词: 呼啦圈
    
    请直接输出两个词语，格式为:
    {
        "civilian_word": "平民词语",
        "spy_word": "卧底词语"
    }
    
    确保词语合适且有趣，能够给玩家带来良好的游戏体验。不要重复使用示例中的词语。
"""

class PromptsManager:
    def __init__(self):
        """初始化Prompts管理器"""
        logger.info("Prompts管理器已初始化")

    def get_prompt_for_context(self, context_type: str, game_info: Dict[str, Any] = None) -> str:
        """
        获取指定上下文类型的prompt

        Args:
            context_type: 上下文类型 (LLM_CONTEXT_*)
            game_info: 游戏相关信息，包含:
                - role: 角色 ("spy", "civilian")
                - word: 词语
                - current_round: 当前回合
                - chat_history: 聊天历史
                - max_rounds: 最大回合数 (可选)
                - spy_teammates: 卧底队友 (可选，卧底角色需要)
                - total_spy_count: 总卧底数 (可选，卧底角色需要)
                - remaining_spy_count: 剩余卧底数 (可选，卧底角色需要)
                - speak_time: 发言时间限制(秒) (可选)

        Returns:
            格式化后的prompt字符串
        """
        # 获取发言时间限制，优先使用game_info中的值，否则使用默认值
        speak_time = MAX_SPEAK_TIME
        if game_info and "speak_time" in game_info:
            speak_time = game_info.get("speak_time")
            
        # 格式化游戏规则，传入发言时间限制
        formatted_game_rules = GAME_RULES.format(max_speak_time=speak_time)
        
        # 普通聊天场景 - 游戏未开始
        if context_type == LLM_CONTEXT_NORMAL_CHAT:
            return f"{GENERAL_CHATS}\n\n{formatted_game_rules}"
            
        # 游戏中AI玩家发言
        if context_type == LLM_CONTEXT_GAME_PLAYING and game_info:
            # 提取基本游戏信息
            role = game_info.get("role", "civilian")
            word = game_info.get("word", "未知词语")
            current_round = game_info.get("current_round", "1")
            max_rounds = game_info.get("max_rounds", "5")
            chat_history = game_info.get("chat_history", "")
            
            # 格式化游戏状态
            game_status = GAME_STATUS.format(
                current_round=current_round,
                max_rounds=max_rounds,
                player_count=game_info.get("player_count", "?"),
                alive_count=game_info.get("alive_count", "?"),
                eliminated_players=game_info.get("eliminated_players", "无"),
                role=role,
                word=word
            )
            
            # 根据角色组合不同的提示词
            if role == "spy":
                # 卧底角色需要额外的队友信息
                spy_team_info = SPY_TEAM_INFO.format(
                    total_spy_count=game_info.get("total_spy_count", "?"),
                    remaining_spy_count=game_info.get("remaining_spy_count", "?"),
                    spy_teammates=game_info.get("spy_teammates", "无")
                )
                
                # 卧底提示词: 卧底角色+游戏规则+游戏状态+卧底团队信息+输出要求
                prompt = f"{SPY_ROLE}\n\n{formatted_game_rules}\n\n{game_status}\n\n{spy_team_info}\n\n{OUTPUT_REQUIREMENT}\n\n游戏历史:\n{chat_history}"
                return prompt
            else:
                # 平民提示词: 平民角色+游戏规则+游戏状态+输出要求
                prompt = f"{CIVILIAN_ROLE}\n\n{formatted_game_rules}\n\n{game_status}\n\n{OUTPUT_REQUIREMENT}\n\n游戏历史:\n{chat_history}"
                return prompt
                
        # 秘密聊天场景
        if context_type == LLM_CONTEXT_SECRET_CHAT and game_info:
            # TODO: 实现秘密聊天场景的提示词组合（当前版本不实现）
            pass
            
        # 秘密投票场景
        if context_type == LLM_CONTEXT_SECRET_VOTE and game_info:
            # TODO: 实现秘密投票场景的提示词组合（当前版本不实现）
            pass
            
        # 普通投票场景
        if context_type == LLM_CONTEXT_VOTING and game_info:
            # 提取基本游戏信息
            role = game_info.get("role", "civilian")
            word = game_info.get("word", "未知词语")
            current_round = game_info.get("current_round", "1")
            max_rounds = game_info.get("max_rounds", "5")
            chat_history = game_info.get("chat_history", "")
            
            # 格式化游戏状态
            game_status = GAME_STATUS.format(
                current_round=current_round,
                max_rounds=max_rounds,
                player_count=game_info.get("player_count", "?"),
                alive_count=game_info.get("alive_count", "?"),
                eliminated_players=game_info.get("eliminated_players", "无"),
                role=role,
                word=word
            )
            
            # 根据角色组合不同的提示词
            if role == "spy":
                # 卧底角色需要额外的队友信息
                spy_team_info = SPY_TEAM_INFO.format(
                    total_spy_count=game_info.get("total_spy_count", "?"),
                    remaining_spy_count=game_info.get("remaining_spy_count", "?"),
                    spy_teammates=game_info.get("spy_teammates", "无")
                )
                
                # 卧底投票提示词: 卧底角色+游戏规则+游戏状态+卧底团队信息+投票要求
                prompt = f"{SPY_ROLE}\n\n{formatted_game_rules}\n\n{game_status}\n\n{spy_team_info}\n\n{VOTING}\n\n游戏历史:\n{chat_history}"
                return prompt
            else:
                # 平民投票提示词: 平民角色+游戏规则+游戏状态+投票要求
                prompt = f"{CIVILIAN_ROLE}\n\n{formatted_game_rules}\n\n{game_status}\n\n{VOTING}\n\n游戏历史:\n{chat_history}"
                return prompt
        
        # 遗言场景
        if context_type == LLM_CONTEXT_LAST_WORDS and game_info:
            # 提取基本游戏信息
            role = game_info.get("role", "civilian")
            word = game_info.get("word", "未知词语")
            current_round = game_info.get("current_round", "1")
            chat_history = game_info.get("chat_history", "")
            
            # 格式化游戏状态
            game_status = GAME_STATUS.format(
                current_round=current_round,
                max_rounds=game_info.get("max_rounds", "5"),
                player_count=game_info.get("player_count", "?"),
                alive_count=game_info.get("alive_count", "?"),
                eliminated_players=game_info.get("eliminated_players", "无"),
                role=role,
                word=word
            )
            
            # 遗言提示词: 游戏规则+游戏状态+遗言要求
            prompt = f"{formatted_game_rules}\n\n{game_status}\n\n{LAST_WORDS}\n\n游戏历史:\n{chat_history}"
            return prompt
            
        # 上帝分发词语场景
        if context_type == LLM_CONTEXT_GOD_WORDS:
            # 上帝分发词语提示词: 游戏规则+上帝词语选择提示
            prompt = f"{formatted_game_rules}\n\n{GOD_WORDS}"
            return prompt
            
        # 默认返回普通聊天场景
        logger.warning(f"未知的上下文类型: {context_type}或缺少game_info，使用普通聊天场景")
        return f"{GENERAL_CHATS}\n\n{formatted_game_rules}"
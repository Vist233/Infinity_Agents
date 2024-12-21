from flask import Flask, render_template, request, session, jsonify
from flask_session import Session
from datetime import timedelta
import os
from phi.agent import Agent, RunResponse
from phi.model.openai.like import OpenAILike
from config import API_KEY

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Session配置
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = 'flask_session'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['DEBUG'] = True
app.config['TEMPLATES_AUTO_RELOAD'] = False
Session(app)

# 确保会话目录存在
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

class PaperAISimple:
    def __init__(self):
        # 初始化 agent，使用与示例相同的配置
        self.agent = Agent(
            model=OpenAILike(
                id="yi-lightning",  # 使用 yi-large 而不是 yi-lightning
                api_key=API_KEY,
                base_url="https://api.lingyiwanwu.com/v1"
            ),
            show_tool_calls=True,
            markdown=True,
            reasoning=True,
            instructions=[
                "You are a helpful research assistant specialized in agricultural science and plant biology.",
                "When analyzing topics, focus on biological characteristics, cultivation methods, and research developments.",
                "Provide detailed and structured responses with clear sections."
            ]
        )
        
    def generate_response(self, topic: str) -> str:
        """生成回复"""
        try:
            print(f"开始生成关于 {topic} 的回复...")
            
            prompt = f"""
            Please provide a comprehensive analysis of {topic}, including:
            1. Biological Characteristics
            2. Cultivation Methods
            3. Research Developments
            4. Future Prospects
            
            Make sure to structure your response clearly and provide detailed information.
            """
            
            # 直接使用 run 方法，不设置超时
            run: RunResponse = self.agent.run(prompt)
            print(f"获取到响应: {run}")
            
            if run and run.content:
                return run.content
            else:
                print("响应内容为空")
                return "抱歉，生成回复时出现错误。"
                
        except Exception as e:
            print(f"生成回复时出错: {e}")
            return f"抱歉，处理过程中出现错误: {str(e)}"

paperai = PaperAISimple()

@app.route("/", methods=["GET", "POST"])
def index():
    if "messages" not in session:
        session["messages"] = []
    
    messages = session.get("messages", [])
    
    if request.method == "POST":
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            user_input = request.form.get("userInput")
            agent = request.form.get("agent")
            
            if user_input:
                try:
                    if agent == "paperai":
                        # 测试响应
                        if user_input == "量子计算":
                            ai_response = "这里是ai的回复"
                        else:
                            print(f"开始处理查询: {user_input}")
                            ai_response = paperai.generate_response(user_input)
                            print(f"获取到 AI 响应: {ai_response[:100]}...")
                    else:
                        ai_response = "请选择正确的 AI 助手。"
                    
                    response_data = {
                        "messages": [
                            {"type": "user", "text": user_input},
                            {"type": "ai", "text": ai_response}
                        ]
                    }
                    print(f"返回响应数据: {response_data}")
                    return jsonify(response_data)
                    
                except Exception as e:
                    error_msg = f"处理请求时出错: {str(e)}"
                    print(error_msg)
                    return jsonify({
                        "messages": [
                            {"type": "user", "text": user_input},
                            {"type": "ai", "text": error_msg}
                        ]
                    })
    
    return render_template("main.html", messages=messages)

if __name__ == "__main__":
    app.run(
        host='0.0.0.0', 
        port=8080, 
        debug=True,
        use_reloader=False
    )
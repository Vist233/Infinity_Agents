import uuid
from flask import Flask, render_template, request, session, send_file
from phi.workflow import RunEvent
from phi.storage.workflow.sqlite import SqlWorkflowStorage
import os
import io
import zipfile
from flask_session import Session
from datetime import timedelta

from config import SECRET_KEY, DATABASE_DIR
from codeAI import CodeAIWorkflow
from paperAI import PaperSummaryGenerator


class DialogueManager:
    def __init__(self, assistant):
        self.assistant = assistant

    def process_user_input(self, user_input, conversation_history, logs):
        logs.append(f"用户发送: {user_input}\n")
        response = ""

        try:
            if self.assistant == paperai:
                self.assistant.session_id = f"generate-summary-on-{user_input}"
                print("开始处理 paperai 响应")
                
                # 获取最后一个响应
                last_response = None
                for res in self.assistant.run(logs, user_input):
                    print(f"收到响应: {res}")
                    last_response = res
                
                # 使用最后一个响应
                if last_response and last_response.event == RunEvent.workflow_completed:
                    logs.append("Workflow completed.\n")
                    if hasattr(last_response, 'content') and last_response.content:
                        response = last_response.content
                        print(f"设置响应内容: {response}")
                    else:
                        print("响应没有内容")
                        response = "抱歉，处理过程中出现错误。"
                else:
                    print("没有收到完整的响应")
                    response = "抱歉，没有收到有效的响应。"

            elif self.assistant == codeai:
                for res in self.assistant.run(logs, user_input):
                    if res.event == RunEvent.workflow_completed:
                        logs.append("Workflow completed.\n")
                        response = res.content

        except Exception as e:
            error_msg = f"处理过程中出错: {str(e)}"
            print(f"错误详情: {error_msg}")
            response = error_msg
            logs.append(f"{response}\n")

        print(f"最终返回响应: {response}")
        return response

app = Flask(__name__)
app.secret_key = SECRET_KEY
logs = ["系统初始化完成\n"]  # 右下角

# Initialize processing workspace
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

# 构建目标目录路径
processing_space_dir = os.path.join(parent_dir, 'ProcessingSpace')
database_dir = DATABASE_DIR
print(f"Parent directory: {parent_dir}")

# 创建目录并切换到该目录
if not os.path.exists(processing_space_dir):
    os.makedirs(processing_space_dir)
os.chdir(processing_space_dir)

# Generate a new session ID
WORKING_SPACE = f"{app.secret_key}"
os.makedirs(WORKING_SPACE, exist_ok=True)
os.chdir(WORKING_SPACE)
app.config["WORKING_SPACE"] = WORKING_SPACE

# Create database directory before initializing storage
os.makedirs(database_dir, exist_ok=True)

paperai = PaperSummaryGenerator(
    storage=SqlWorkflowStorage(
        table_name="generate_summary_workflows",
        db_file="tmp/workflows.db",
    ),
)
codeai = CodeAIWorkflow(
    session_id=app.secret_key,
    storage=SqlWorkflowStorage(
        table_name=app.secret_key,
        db_file="./../Database/CodeWorkflows.db",
    ),
)
paperai_manager = DialogueManager(paperai)
codeai_manager = DialogueManager(codeai)

app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(parent_dir, 'flask_session')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
Session(app)

# 确保会话目录存在
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if "messages" not in session:
        session["messages"] = []
    
    messages = session.get("messages", [])

    if request.method == "POST":
        user_input = request.form.get("userInput")
        agent = request.form.get("agent")
        
        if user_input:
            if agent == "paperai":
                response = paperai_manager.process_user_input(user_input, "", logs)
            elif agent == "codeai":
                response = codeai_manager.process_user_input(user_input, "", logs)
            else:
                response = "未指定有效的 Agent。"

            print(f"用户输入: {user_input}")  # 调试日志
            print(f"AI 响应: {response}")     # 调试日志
            print(f"响应类型: {type(response)}")  # 检查响应类型

            # 添加新消息到会话
            messages.append({"type": "user", "text": user_input})
            messages.append({"type": "ai", "text": str(response)})  # 确保转换为字符串
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                response_data = {
                    "messages": [
                        {"type": "user", "text": user_input},
                        {"type": "ai", "text": str(response)}
                    ]
                }
                print(f"返回的数据: {response_data}")  # 检查返回的数据
                return response_data

    return render_template("main.html", messages=messages, logs=logs)

@app.route("/upload", methods=["POST"])
def upload():
    logs = []
    uploaded_files = []

    if "files" in request.files:
        uploaded_files_list = request.files.getlist("files")
        for file in uploaded_files_list:
            if file and file.filename:
                filename = file.filename
                file_save_path = os.path.join(app.config["WORKING_SPACE"], filename)
                file.save(file_save_path)
                uploaded_files.append(filename)
                logs.append(f"文件 '{filename}' 已成功上传至 {file_save_path}")

    return {"logs": logs, "uploaded_files": uploaded_files}, 200

@app.route("/download", methods=["GET"])
def download():
    """将 WORKING_SPACE 中的所有文件打包为 ZIP 并提供下载"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(app.config["WORKING_SPACE"]):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=app.config["WORKING_SPACE"])
                zip_file.write(file_path, arcname)
    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name="uploaded_files.zip",
        mimetype="application/zip",
    )

if __name__ == "__main__":
    extra_files = [
        'templates/',
        'static/',
        'app.py'
    ]
    
    app.run(
        host='0.0.0.0', 
        port=8080, 
        debug=True,
        extra_files=extra_files,  # 只监控这些文件的变化
        use_reloader=True
    )

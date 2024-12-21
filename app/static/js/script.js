     //上传文件
    document.getElementById("fileInput").addEventListener("change", async function (event) {
      const fileList = document.getElementById("fileList");
      const files = event.target.files;

      const formData = new FormData();
      for (const file of files) {
        formData.append("files", file);

        const listItem = document.createElement("li");
        listItem.textContent = file.name;
        fileList.appendChild(listItem);
      }

      try {
        const response = await fetch("/upload", {
          method: "POST",
          body: formData,
        });

        if (response.ok) {
          const result = await response.json();
          console.log("文件上传成功:", result);

          if (result.logs) {
            result.logs.forEach((log) => {
              const logItem = document.createElement("li");
              logItem.textContent = log;
              document.querySelector(".log-list").appendChild(logItem);
            });
          }
        } else {
          console.error("文件上传失败", response.statusText);
        }
      } catch (error) {
        console.error("文件上传发生错误", error);
      }
    });

        // 下载所有文件
    document.getElementById("downloadAllButton").addEventListener("click", async function () {
      try {
        const response = await fetch("/download", { method: "GET" });
        if (response.ok) {
          const blob = await response.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.style.display = "none";
          a.href = url;
          a.download = "files.zip"; // 打包为 ZIP 文件
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          console.log("文件下载成功");
        } else {
          console.error("文件下载失败", response.statusText);
        }
      } catch (error) {
        console.error("文件下载发生错误", error);
      }
    });

  document.addEventListener("DOMContentLoaded", () => {
    const bubbles = document.querySelectorAll(".bubble");

    bubbles.forEach((bubble) => {
      const markdownText = bubble.getAttribute("data-markdown");
      if (markdownText) {
        // 使用 marked.js 解析 Markdown
        bubble.innerHTML = marked(markdownText);
      }
    });
  });

document.querySelector('.input-area').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const userInput = document.getElementById('userInput');
    const agent = document.querySelector('.agent-select');
    const messageArea = document.getElementById('messageArea');
    const sendButton = document.querySelector('.send-button');
    
    if (!userInput.value.trim()) return;
    
    // 禁用输入和发送按钮
    userInput.disabled = true;
    sendButton.disabled = true;
    sendButton.textContent = '处理中...';
    
    // 显示用户消息
    const userDiv = document.createElement('div');
    userDiv.className = 'message user';
    const userBubble = document.createElement('div');
    userBubble.className = 'bubble';
    userBubble.textContent = userInput.value;
    userDiv.appendChild(userBubble);
    messageArea.appendChild(userDiv);
    
    // 显示加载消息
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message ai';
    const loadingBubble = document.createElement('div');
    loadingBubble.className = 'bubble';
    loadingBubble.textContent = '正在思考中...';
    loadingDiv.appendChild(loadingBubble);
    messageArea.appendChild(loadingDiv);
    
    // 滚动到底部
    messageArea.scrollTop = messageArea.scrollHeight;
    
    try {
        const formData = new FormData();
        formData.append('userInput', userInput.value);
        formData.append('agent', agent.value);
        
        const response = await fetch('/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log('收到的响应数据:', result);
            
            // 移除加载消息
            loadingDiv.remove();
            
            // 处理 AI 回复
            if (result.messages && result.messages.length >= 2) {
                const aiMessage = result.messages[1];
                console.log('AI 消息:', aiMessage);
                
                if (aiMessage.text) {
                    // 创建 AI 消息元素
                    const aiDiv = document.createElement('div');
                    aiDiv.className = 'message ai';
                    const aiBubble = document.createElement('div');
                    aiBubble.className = 'bubble';
                    
                    // 处理换行和空格
                    const formattedText = aiMessage.text
                        .replace(/\n/g, '<br>')  // 将换行符转换为 HTML 换行
                        .replace(/\s{2,}/g, ' '); // 将多个空格合并为一个
                    
                    aiBubble.innerHTML = formattedText;
                    aiDiv.appendChild(aiBubble);
                    messageArea.appendChild(aiDiv);
                    
                    console.log('添加的 AI 消息 HTML:', aiDiv.outerHTML);
                    
                    // 滚动到底部
                    messageArea.scrollTop = messageArea.scrollHeight;
                } else {
                    console.error('AI 消息文本为空');
                }
            } else {
                console.error('响应消息格式不正确:', result);
            }
        } else {
            console.error('请求失败:', response.status);
            loadingBubble.textContent = '抱歉，处理请求时出错了';
        }
    } catch (error) {
        console.error('发送消息时出错:', error);
        loadingBubble.textContent = '抱歉，发送消息时出错了';
    } finally {
        // 恢复输入状态
        userInput.disabled = false;
        sendButton.disabled = false;
        sendButton.textContent = 'Send Message';
        userInput.value = '';
        userInput.focus();
    }
});

// 移除之前添加的样式，使用 CSS 文件中的样式
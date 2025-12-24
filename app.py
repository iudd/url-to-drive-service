import os
import io
import requests
import gradio as gr
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from urllib.parse import urlparse, unquote

# ---------------------------------------------------------
# 1. 鉴权与服务初始化 (使用 OAuth 2.0 Refresh Token 模式)
# ---------------------------------------------------------
def get_drive_service():
    """
    使用环境变量中的 Refresh Token 动态构建 Credentials 对象。
    这种方式不需要本地存储 token.json 文件，也不受 Service Account 存储限制。
    """
    # 必需的环境变量检查
    client_id = os.environ.get("G_CLIENT_ID")
    client_secret = os.environ.get("G_CLIENT_SECRET")
    refresh_token = os.environ.get("G_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        raise EnvironmentError("❌ 缺少必要的 OAuth 环境变量 (G_CLIENT_ID, G_CLIENT_SECRET, G_REFRESH_TOKEN)")

    # 构建 OAuth 2.0 Credentials
    # token=None 表示当前没有 Access Token，库会自动使用 refresh_token 去换取
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    
    return build("drive", "v3", credentials=creds)

# ---------------------------------------------------------
# 2. 核心流式处理逻辑 (内存优化)
# ---------------------------------------------------------
class StreamingUploadFile(io.IOBase):
    """
    包装 requests 的 raw stream，使其表现得像一个文件对象，
    供 Google Drive API 的 MediaIoBaseUpload 使用。
    这样可以避免将整个文件读入内存。
    """
    def __init__(self, response):
        self.response = response
        self.raw = response.raw
        self.position = 0

    def read(self, size=-1):
        # 必须实现 read 方法，供 upload chunk 使用
        chunk = self.raw.read(size)
        if chunk:
            self.position += len(chunk)
        return chunk

    def seek(self, offset, whence=io.SEEK_SET):
        # Google Upload 在某些重试或断点续传场景可能调用 seek
        # 对于 requests stream，我们只能处理 'seek to current' 或 'seek to 0' (如果还没开始)
        if whence == io.SEEK_SET and offset == self.position:
            return self.position
        if whence == io.SEEK_CUR and offset == 0:
            return self.position
        # 注意: 真实的完全流式转发很难支持真正的 seek。
        return self.position

    def tell(self):
        return self.position

def get_filename_from_response(response, url):
    """尝试从 Content-Disposition 获取文件名，否则从 URL 解析"""
    content_disposition = response.headers.get("Content-Disposition")
    if content_disposition:
        import re
        fname = re.findall('filename="?([^"]+)"?', content_disposition)
        if fname:
            return unquote(fname[0])
    
    # Fallback 到 URL
    parsed = urlparse(url)
    return os.path.basename(unquote(parsed.path)) or "downloaded_file"

def process_upload(file_url, progress=gr.Progress()):
    """
    主处理函数：下载 -> 流式上传 -> 设置权限 -> 返回链接
    """
    if not file_url:
        return "❌ 错误: 请输入有效的 URL"
    
    try:
        progress(0, desc="🚀 初始化连接...")
        
        # 1. 建立下载连接 (stream=True)
        # headers={'User-Agent': 'Mozilla/5.0'} 有时能防止 403
        with requests.get(file_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            
            filename = get_filename_from_response(response, file_url)
            filesize = int(response.headers.get('Content-Length', 0))
            
            msg_size = f"{filesize / 1024 / 1024:.2f} MB" if filesize > 0 else "未知大小"
            progress(0.1, desc=f"📥 准备传输: {filename} ({msg_size})")

            # 2. 准备上传到 Google Drive
            service = get_drive_service()
            folder_id = os.environ.get("GDRIVE_FOLDER_ID") # 可选，默认为根目录
            
            file_metadata = {'name': filename}
            if folder_id:
                file_metadata['parents'] = [folder_id]

            # 使用自定义的 StreamingUploadFile 包装器
            stream_wrapper = StreamingUploadFile(response)
            
            # resumable=True 允许分块上传，对大文件更稳定
            # chunksize=10*1024*1024 (10MB) 
            media = MediaIoBaseUpload(
                stream_wrapper,
                mimetype=response.headers.get('Content-Type', 'application/octet-stream'),
                resumable=True,
                chunksize=10 * 1024 * 1024 
            )

            progress(0.2, desc="☁️ 正在流式上传到 Google Drive...")
            
            # 执行上传
            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webContentLink, webViewLink'
            )
            
            # 执行上传
            file = request.execute()
            file_id = file.get('id')
            
            progress(0.9, desc="🔓 正在设置公开权限...")

            # 3. 设置权限为公开 (Reader, Anyone)
            service.permissions().create(
                fileId=file_id,
                body={'role': 'reader', 'type': 'anyone'}
            ).execute()

            # 4. 返回结果
            web_link = file.get('webContentLink', file.get('webViewLink'))
            return f"""✅ **转存成功!**
            
**文件名**: {filename}
**文件ID**: {file_id}
**下载链接**: [点击下载]({web_link})

*(文件已保存到您的 Google Drive，并已设为公开分享)*
"""

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ **发生错误**: {str(e)}"

# ---------------------------------------------------------
# 3. 构建 Gradio 界面
# ---------------------------------------------------------
with gr.Blocks(title="URL to Drive Saver") as demo:
    gr.Markdown("# 🚀 URL to Google Drive Saver (Streamed)")
    gr.Markdown("输入视频/文件 URL，后端将自动**流式**转存到您的 Google Drive。")
    
    with gr.Row():
        url_input = gr.Textbox(label="文件 URL", placeholder="https://example.com/video.mp4")
        submit_btn = gr.Button("开始转存", variant="primary")
    
    output_markdown = gr.Markdown(label="状态日志")

    submit_btn.click(
        fn=process_upload,
        inputs=url_input,
        outputs=output_markdown,
        api_name="save_to_drive"  # 暴露 API 端点 /api/save_to_drive
    )

# 启动 (开启 API，允许 CORS)
if __name__ == "__main__":
    demo.queue(max_size=5).launch(server_name="0.0.0.0", show_api=True, share=False)

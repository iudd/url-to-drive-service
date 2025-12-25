import os
import io
import requests
import logging
import http.client as http_client
import gradio as gr
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from urllib.parse import urlparse, unquote

# ---------------------------------------------------------
# 0. 配置详细日志 (Debug Logging)
# ---------------------------------------------------------
# 开启 http.client 的调试输出，查看底层请求
http_client.HTTPConnection.debuglevel = 1

# 配置 logging
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

def log_msg(msg):
    print(f"👉 [DEBUG] {msg}")

# ---------------------------------------------------------
# 1. 鉴权与服务初始化 (使用 OAuth 2.0 Refresh Token 模式)
# ---------------------------------------------------------
def get_drive_service():
    """
    使用环境变量中的 Refresh Token 动态构建 Credentials 对象。
    """
    client_id = os.environ.get("G_CLIENT_ID")
    client_secret = os.environ.get("G_CLIENT_SECRET")
    refresh_token = os.environ.get("G_REFRESH_TOKEN")
    
    log_msg(f"正在检查环境变量...")
    log_msg(f"Client ID: {'✅ 存在' if client_id else '❌ 缺失'}")
    log_msg(f"Client Secret: {'✅ 存在' if client_secret else '❌ 缺失'}")
    log_msg(f"Refresh Token: {'✅ 存在' if refresh_token else '❌ 缺失'}")

    if not all([client_id, client_secret, refresh_token]):
        raise EnvironmentError("❌ 缺少必要的 OAuth 环境变量")

    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )
        
        # 尝试刷新一次 Token 以验证有效性
        log_msg("正在尝试验证 Token 有效性...")
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        log_msg(f"✅ Token 验证成功! Access Token: {creds.token[:10]}...")
        
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        log_msg(f"❌ 鉴权初始化失败: {str(e)}")
        raise e

# ---------------------------------------------------------
# 2. 核心流式处理逻辑
# ---------------------------------------------------------
class StreamingUploadFile(io.IOBase):
    def __init__(self, response):
        self.response = response
        self.raw = response.raw
        self.position = 0

    def read(self, size=-1):
        chunk = self.raw.read(size)
        if chunk:
            self.position += len(chunk)
        return chunk

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET and offset == self.position:
            return self.position
        if whence == io.SEEK_CUR and offset == 0:
            return self.position
        return self.position

    def tell(self):
        return self.position

def get_filename_from_response(response, url):
    content_disposition = response.headers.get("Content-Disposition")
    if content_disposition:
        import re
        fname = re.findall('filename="?([^"]+)"?', content_disposition)
        if fname:
            return unquote(fname[0])
    parsed = urlparse(url)
    return os.path.basename(unquote(parsed.path)) or "downloaded_file"

def process_upload(file_url, progress=gr.Progress()):
    if not file_url:
        return "❌ 错误: 请输入有效的 URL"
    
    try:
        # 1. 验证 Drive API 连接
        log_msg("开始 process_upload 任务")
        service = get_drive_service()
        
        # 简单测试 API 是否通畅
        log_msg("测试 API 调用 (files.list)...")
        service.files().list(pageSize=1).execute()
        log_msg("API 调用正常")

        # 2. 建立下载
        progress(0, desc="🚀 初始化连接...")
        with requests.get(file_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            
            filename = get_filename_from_response(response, file_url)
            filesize = int(response.headers.get('Content-Length', 0))
            log_msg(f"准备下载文件: {filename}, 大小: {filesize}")
            
            progress(0.1, desc=f"📥 准备传输: {filename}")

            folder_id = os.environ.get("GDRIVE_FOLDER_ID")
            file_metadata = {'name': filename}
            if folder_id:
                log_msg(f"目标文件夹 ID: {folder_id}")
                file_metadata['parents'] = [folder_id]

            stream_wrapper = StreamingUploadFile(response)
            
            media = MediaIoBaseUpload(
                stream_wrapper,
                mimetype=response.headers.get('Content-Type', 'application/octet-stream'),
                resumable=True,
                chunksize=5 * 1024 * 1024  # 降低 chunksize 到 5MB 试试
            )

            progress(0.2, desc="☁️ 正在流式上传...")
            
            log_msg("开始执行 create 请求...")
            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webContentLink, webViewLink'
            )
            
            # 手动执行上传循环，以便捕获每一步的错误
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress_percent = int(status.progress() * 100)
                    log_msg(f"上传进度: {progress_percent}%")
            
            file = response
            file_id = file.get('id')
            log_msg(f"上传完成，File ID: {file_id}")
            
            progress(0.9, desc="🔓 正在设置公开权限...")
            service.permissions().create(
                fileId=file_id,
                body={'role': 'reader', 'type': 'anyone'}
            ).execute()

            web_link = file.get('webContentLink', file.get('webViewLink'))
            return f"✅ **转存成功!**\n\n**文件名**: {filename}\n**下载链接**: [点击下载]({web_link})"

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        log_msg(f"❌ 发生严重错误:\n{error_msg}")
        return f"❌ **发生错误**: {str(e)}\n\n(请查看 Logs 获取详细调试信息)"

# ---------------------------------------------------------
# 3. 构建界面
# ---------------------------------------------------------
with gr.Blocks(title="URL to Drive Saver") as demo:
    gr.Markdown("# 🚀 URL to Google Drive Saver (Debug Mode)")
    
    with gr.Row():
        url_input = gr.Textbox(label="文件 URL")
        submit_btn = gr.Button("开始转存", variant="primary")
    
    output_markdown = gr.Markdown(label="状态日志")

    submit_btn.click(
        fn=process_upload,
        inputs=url_input,
        outputs=output_markdown,
        api_name="save_to_drive"
    )

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", show_api=True)

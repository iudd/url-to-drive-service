import os
import io
import requests
import gradio as gr
import logging
import http.client
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from urllib.parse import urlparse, unquote
from googleapiclient.errors import HttpError

# ---------------------------------------------------------
# 0. 配置日志
# ---------------------------------------------------------
http.client.HTTPConnection.debuglevel = 0
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 1. 鉴权与服务初始化
# ---------------------------------------------------------
def get_drive_service():
    client_id = os.environ.get("G_CLIENT_ID")
    client_secret = os.environ.get("G_CLIENT_SECRET")
    refresh_token = os.environ.get("G_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        raise EnvironmentError("❌ 缺少必要的 OAuth 环境变量")

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    return build("drive", "v3", credentials=creds)

# ---------------------------------------------------------
# 2. 核心流式处理逻辑 (重写版 - 解决 0KB 问题)
# ---------------------------------------------------------
class RequestsStreamWrapper(io.IOBase):
    """
    将 requests 的 iter_content 封装为 file-like 对象。
    解决直接读取 raw 可能导致的 0KB 或 Gzip 问题。
    """
    def __init__(self, response):
        self.iterator = response.iter_content(chunk_size=1024 * 1024) # 每次从网络取 1MB
        self.buffer = b""
        self.position = 0

    def read(self, size=-1):
        # 如果缓冲区为空且需要读取，尝试从网络获取数据
        if not self.buffer:
            try:
                self.buffer = next(self.iterator)
            except StopIteration:
                return b"" # 流结束

        # 如果 size 为 -1，读取所有（危险，通常不应在流式上传中使用）
        if size == -1:
            data = self.buffer
            self.buffer = b""
            # 继续读取直到结束
            try:
                while True:
                    data += next(self.iterator)
            except StopIteration:
                pass
            self.position += len(data)
            return data

        # 读取指定大小
        length = len(self.buffer)
        
        # 如果当前缓冲区不够，且流还没断，继续获取直到够用或流结束
        while length < size:
            try:
                chunk = next(self.iterator)
                self.buffer += chunk
                length += len(chunk)
            except StopIteration:
                break

        # 从缓冲区切片返回
        data = self.buffer[:size]
        self.buffer = self.buffer[size:] # 剩余的留给下次
        self.position += len(data)
        return data

    def seek(self, offset, whence=io.SEEK_SET):
        # 欺骗 Google API，假装我们支持 seek，实际上只能原地踏步
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
        # --- 1. 鉴权 ---
        service = get_drive_service()

        # --- 2. 下载 ---
        logger.info(f"📥 开始下载: {file_url}")
        
        # stream=True 是必须的
        with requests.get(file_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            
            filename = get_filename_from_response(response, file_url)
            filesize = int(response.headers.get('Content-Length', 0))
            msg_size = f"{filesize / 1024 / 1024:.2f} MB" if filesize > 0 else "未知大小"
            
            progress(0.1, desc=f"📥 准备传输: {filename} ({msg_size})")

            # --- 3. 准备上传 ---
            folder_id = os.environ.get("GDRIVE_FOLDER_ID", "").strip()
            file_metadata = {'name': filename}
            if folder_id:
                file_metadata['parents'] = [folder_id]

            # 使用新的 Wrapper
            stream_wrapper = RequestsStreamWrapper(response)
            
            # 关键：设置 chunksize，Google 会按照这个大小调用 read()
            # 5MB 是 Google 推荐的最小分片
            media = MediaIoBaseUpload(
                stream_wrapper,
                mimetype=response.headers.get('Content-Type', 'application/octet-stream'),
                resumable=True,
                chunksize=5 * 1024 * 1024 
            )

            progress(0.2, desc="☁️ 正在流式上传...")
            
            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            )
            
            # --- 4. 执行上传 ---
            response_upload = None
            while response_upload is None:
                status, response_upload = request.next_chunk()
                if status:
                    progress_percent = int(status.progress() * 100)
                    if progress_percent % 10 == 0:
                        logger.info(f"⏳ 上传进度: {progress_percent}%")

            file = response_upload
            file_id = file.get('id')
            logger.info(f"✅ 上传完成，ID: {file_id}, 大小非0检查: 需去网盘确认")
            
            # --- 5. 权限设置 ---
            web_link = file.get('webViewLink', f"https://drive.google.com/file/d/{file_id}/view")
            perm_msg = "🔒 私有"
            
            try:
                progress(0.9, desc="🔓 设置权限...")
                service.permissions().create(
                    fileId=file_id,
                    body={'role': 'reader', 'type': 'anyone'}
                ).execute()
                perm_msg = "🌍 公开"
            except HttpError:
                pass

            return f"""✅ **转存成功!**
            
**文件名**: {filename}
**状态**: {perm_msg}
**文件ID**: {file_id}
**链接**: [点击打开]({web_link})
"""

    except Exception as e:
        logger.error(f"❌ 错误: {e}", exc_info=True)
        return f"❌ **发生错误**: {str(e)}"

with gr.Blocks(title="URL to Drive Saver") as demo:
    gr.Markdown("# 🚀 URL to Google Drive Saver")
    with gr.Row():
        url_input = gr.Textbox(label="文件 URL")
        submit_btn = gr.Button("开始转存", variant="primary")
    output_markdown = gr.Markdown(label="结果")
    submit_btn.click(process_upload, inputs=url_input, outputs=output_markdown)

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", show_api=True)

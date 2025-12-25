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
import google.auth.exceptions
from googleapiclient.errors import HttpError

# ---------------------------------------------------------
# 0. 配置日志
# ---------------------------------------------------------
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
# 2. 核心流式处理逻辑 (彻底重写的 Buffer 适配器)
# ---------------------------------------------------------
class ResponseStream(io.IOBase):
    """
    将 requests 的 response.iter_content() 适配为 file-like object。
    解决 0KB 问题的关键组件。
    """
    def __init__(self, iter_content):
        self._iter = iter_content
        self._buffer = b""
        self._position = 0

    def read(self, size=-1):
        # 如果需要读取全部 (size=-1)，或者缓冲区不够，就从流中拉取
        while size == -1 or len(self._buffer) < size:
            try:
                chunk = next(self._iter)
                self._buffer += chunk
            except StopIteration:
                break
            # 为了防止内存爆掉，如果不需要全部读取，拉到足够数据就停
            if size != -1 and len(self._buffer) >= size:
                break

        if size == -1:
            data = self._buffer
            self._buffer = b""
        else:
            data = self._buffer[:size]
            self._buffer = self._buffer[size:]
        
        self._position += len(data)
        return data

    def seek(self, offset, whence=io.SEEK_SET):
        # 仅支持获取当前位置 (tell) 和重置到开始 (seek(0) - 但流无法真正的回退)
        # Google API 有时会尝试 seek(0) 来确认
        if whence == io.SEEK_SET and offset == self._position:
            return self._position
        if whence == io.SEEK_CUR and offset == 0:
            return self._position
        return self._position

    def tell(self):
        return self._position

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

        # --- 2. 下载 (使用 stream=True) ---
        logger.info(f"📥 开始下载: {file_url}")
        
        # 关键修改：增加 stream=True
        with requests.get(file_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            
            filename = get_filename_from_response(response, file_url)
            filesize = int(response.headers.get('Content-Length', 0))
            msg_size = f"{filesize / 1024 / 1024:.2f} MB" if filesize > 0 else "未知大小"
            
            progress(0.1, desc=f"📥 准备: {filename} ({msg_size})")

            # --- 3. 准备上传 ---
            folder_id = os.environ.get("GDRIVE_FOLDER_ID", "").strip()
            file_metadata = {'name': filename}
            if folder_id:
                file_metadata['parents'] = [folder_id]

            # 关键修改：使用 iter_content 生成器
            # chunk_size 设置为 1MB，确保缓冲区平滑
            content_iterator = response.iter_content(chunk_size=1024*1024)
            stream_wrapper = ResponseStream(content_iterator)
            
            media = MediaIoBaseUpload(
                stream_wrapper,
                mimetype=response.headers.get('Content-Type', 'application/octet-stream'),
                resumable=True,
                chunksize=10 * 1024 * 1024 
            )

            progress(0.2, desc="☁️ 正在流式上传...")
            
            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            )
            
            # --- 4. 执行上传 ---
            file = None
            response_obj = None
            while response_obj is None:
                status, response_obj = request.next_chunk()
                if status:
                    progress_percent = int(status.progress() * 100)
                    if progress_percent % 10 == 0:
                        logger.info(f"⏳ 上传进度: {progress_percent}%")

            file = response_obj
            file_id = file.get('id')
            logger.info(f"✅ 上传完成，ID: {file_id}")
            
            # --- 5. 权限设置 ---
            web_link = file.get('webViewLink', f"https://drive.google.com/file/d/{file_id}/view")
            perm_status = "🔒 私有"
            
            try:
                progress(0.9, desc="🔓 设置权限...")
                service.permissions().create(
                    fileId=file_id,
                    body={'role': 'reader', 'type': 'anyone'}
                ).execute()
                perm_status = "🌍 公开"
            except Exception:
                pass # 忽略权限错误

            return f"""✅ **转存成功!**
            
**文件名**: {filename}
**文件ID**: {file_id}
**状态**: {perm_status}
**下载链接**: [点击打开]({web_link})
"""

    except Exception as e:
        logger.error(f"❌ 错误: {e}", exc_info=True)
        return f"❌ **发生错误**: {str(e)}"

# ---------------------------------------------------------
# 3. 构建界面
# ---------------------------------------------------------
with gr.Blocks(title="URL to Drive Saver") as demo:
    gr.Markdown("# 🚀 URL to Google Drive Saver")
    
    with gr.Row():
        url_input = gr.Textbox(label="文件 URL", placeholder="https://example.com/video.mp4")
        submit_btn = gr.Button("开始转存", variant="primary")
    
    output_markdown = gr.Markdown(label="结果")

    submit_btn.click(
        fn=process_upload,
        inputs=url_input,
        outputs=output_markdown,
        api_name="save_to_drive"
    )

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", show_api=True)

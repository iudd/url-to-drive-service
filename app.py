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
# 2. 核心流式处理逻辑 (改进版：ResponseStream)
# ---------------------------------------------------------
class ResponseStream(io.IOBase):
    def __init__(self, iter_content):
        self._iter = iter_content
        self._buffer = b""
        self._position = 0

    def read(self, size=-1):
        # 如果需要读所有内容 (size=-1)，这对于大文件很危险，但在 chunk 上传中通常不会发生
        if size == -1:
            out = self._buffer + b"".join(self._iter)
            self._buffer = b""
            self._position += len(out)
            return out

        # 只要 buffer 不够且迭代器还有数据，就继续填充
        while len(self._buffer) < size:
            try:
                chunk = next(self._iter)
                self._buffer += chunk
            except StopIteration:
                break
        
        # 取出数据
        length = min(len(self._buffer), size)
        data = self._buffer[:length]
        self._buffer = self._buffer[length:]
        self._position += length
        return data

    def tell(self):
        return self._position

    def seek(self, offset, whence=io.SEEK_SET):
        # 仅允许“假装”seek 到当前位置或0 (如果还没开始读)
        if offset == self._position:
            return self._position
        if offset == 0 and self._position == 0:
            return 0
        # logger.warning(f"⚠️ 忽略不支持的 Seek: offset={offset}, pos={self._position}")
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
        # --- 1. 初始化 ---
        service = get_drive_service()

        # --- 2. 下载 ---
        logger.info(f"📥 开始下载: {file_url}")
        # stream=True 是必须的
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

            # 关键修改：使用 iter_content(chunk_size)
            # chunk_size 设置为 1MB，保证流的平滑
            stream_wrapper = ResponseStream(response.iter_content(chunk_size=1024*1024))
            
            media = MediaIoBaseUpload(
                stream_wrapper,
                mimetype=response.headers.get('Content-Type', 'application/octet-stream'),
                resumable=True,
                chunksize=5 * 1024 * 1024  # 上传分块设为 5MB
            )

            progress(0.2, desc="☁️ 正在流式上传...")
            
            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink, size'
            )
            
            response_obj = None
            while response_obj is None:
                status, response_obj = request.next_chunk()
                if status:
                    p = int(status.progress() * 100)
                    if p % 10 == 0: logger.info(f"⏳ 上传进度: {p}%")

            file = response_obj
            file_id = file.get('id')
            uploaded_size = int(file.get('size', 0))
            logger.info(f"✅ 上传完成，ID: {file_id}, 大小: {uploaded_size/1024/1024:.2f} MB")
            
            # --- 4. 权限设置 ---
            web_link = file.get('webViewLink', f"https://drive.google.com/file/d/{file_id}/view")
            perm_status = "🔒 私有"
            
            try:
                service.permissions().create(
                    fileId=file_id,
                    body={'role': 'reader', 'type': 'anyone'}
                ).execute()
                perm_status = "🌍 公开"
            except Exception:
                pass

            return f"""✅ **转存成功!**
            
**文件名**: {filename}
**实际大小**: {uploaded_size / 1024 / 1024:.2f} MB
**状态**: {perm_status}
**链接**: [Google Drive]({web_link})
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

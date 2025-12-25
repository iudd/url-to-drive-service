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
logging.basicConfig(level=logging.INFO) # 关闭Debug，只看关键信息
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
        # --- 1. 初始化 ---
        service = get_drive_service()

        # --- 2. 下载 ---
        logger.info(f"📥 开始下载: {file_url}")
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

            stream_wrapper = StreamingUploadFile(response)
            
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
                fields='id, webContentLink, webViewLink'
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.debug(f"进度: {int(status.progress() * 100)}%")

            file = response
            file_id = file.get('id')
            logger.info(f"✅ 上传完成，ID: {file_id}")
            
            # --- 4. 尝试设置权限 (容错处理) ---
            web_link = file.get('webContentLink', file.get('webViewLink'))
            permission_status = "🔒 私有 (默认)"
            
            try:
                progress(0.9, desc="🔓 正在尝试公开分享...")
                service.permissions().create(
                    fileId=file_id,
                    body={'role': 'reader', 'type': 'anyone'}
                ).execute()
                permission_status = "🌍 已公开"
            except HttpError as e:
                logger.warning(f"⚠️ 无法设置为公开 (这是正常的): {e}")
                permission_status = "🔒 私有 (Google 限制了自动公开，请去网盘手动分享)"

            return f"""✅ **转存成功!**
            
**文件名**: {filename}
**文件ID**: {file_id}
**状态**: {permission_status}
**下载链接**: [点击打开]({web_link})
*(注: 如果链接打不开，请去您的 Google Drive 查看)*
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

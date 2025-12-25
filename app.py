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
# 0. 配置日志 (INFO Level - 关闭太详细的底层调试)
# ---------------------------------------------------------
http.client.HTTPConnection.debuglevel = 0
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 1. 鉴权与服务初始化
# ---------------------------------------------------------
def get_drive_service():
    """
    使用环境变量中的 Refresh Token 动态构建 Credentials 对象。
    """
    client_id = os.environ.get("G_CLIENT_ID")
    client_secret = os.environ.get("G_CLIENT_SECRET")
    refresh_token = os.environ.get("G_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        logger.error("❌ 环境变量缺失")
        raise EnvironmentError("❌ 缺少必要的 OAuth 环境变量 (G_CLIENT_ID, G_CLIENT_SECRET, G_REFRESH_TOKEN)")

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
        try:
            chunk = self.raw.read(size)
            if chunk:
                self.position += len(chunk)
            return chunk
        except Exception as e:
            logger.error(f"❌ 读取下载流失败: {e}")
            raise

    def seek(self, offset, whence=io.SEEK_SET):
        # 仅支持获取当前位置和重置到当前位置 (伪 Seek)
        if whence == io.SEEK_SET and offset == self.position:
            return self.position
        if whence == io.SEEK_CUR and offset == 0:
            return self.position
        # logger.warning(f"⚠️ 忽略不支持的 Seek 操作: offset={offset}, whence={whence}")
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
        # --- 🔍 验证 Token ---
        try:
            service = get_drive_service()
            service.about().get(fields="user").execute()
        except Exception as e:
            logger.error(f"❌ Token 验证失败: {e}")
            return f"❌ **鉴权错误**: 无法连接 Google Drive API。\n详情: {e}"

        # --- 🚀 开始下载 ---
        progress(0, desc="🚀 初始化连接...")
        logger.info(f"📥 开始下载 URL: {file_url}")
        
        with requests.get(file_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            
            filename = get_filename_from_response(response, file_url)
            filesize = int(response.headers.get('Content-Length', 0))
            msg_size = f"{filesize / 1024 / 1024:.2f} MB" if filesize > 0 else "未知大小"
            
            progress(0.1, desc=f"📥 准备传输: {filename} ({msg_size})")

            # --- ☁️ 准备上传 ---
            folder_id = os.environ.get("GDRIVE_FOLDER_ID")
            file_metadata = {'name': filename}
            if folder_id and folder_id.strip():
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
                fields='id, webViewLink'
            )
            
            # --- 🔥 执行上传 ---
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
            logger.info(f"✅ 上传完成，File ID: {file_id}")
            
            # --- 🔓 尝试设置权限 (容错处理) ---
            web_link = file.get('webViewLink', f"https://drive.google.com/file/d/{file_id}/view")
            permission_msg = "🔓 已设置为公开"
            
            try:
                progress(0.9, desc="🔓 正在设置权限...")
                service.permissions().create(
                    fileId=file_id,
                    body={'role': 'reader', 'type': 'anyone'}
                ).execute()
            except HttpError as e:
                logger.warning(f"⚠️ 无法设置公开权限 (HTTP {e.resp.status}): {e}")
                permission_msg = "🔒 私有文件 (权限设置被拒绝)"
            except Exception as e:
                logger.warning(f"⚠️ 设置权限时发生未知错误: {e}")
                permission_msg = "🔒 私有文件 (设置出错)"

            return f"""✅ **转存成功!**
            
**文件名**: {filename}
**状态**: {permission_msg}
**文件ID**: {file_id}
**查看链接**: [点击打开 Google Drive]({web_link})
"""

    except BrokenPipeError:
        return "❌ **上传中断**: 连接被 Google 拒绝。通常是因为网络不稳定，请重试。"
    except Exception as e:
        logger.error(f"❌ 全局异常捕获: {str(e)}", exc_info=True)
        return f"❌ **发生错误**: {str(e)}"

# ---------------------------------------------------------
# 3. 构建界面
# ---------------------------------------------------------
with gr.Blocks(title="URL to Drive Saver") as demo:
    gr.Markdown("# 🚀 URL to Google Drive Saver")
    
    with gr.Row():
        url_input = gr.Textbox(label="文件 URL", placeholder="https://example.com/video.mp4")
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

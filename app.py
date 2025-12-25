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

# ---------------------------------------------------------
# 0. 配置日志 (Debug Level)
# ---------------------------------------------------------
# 开启 HTTP 调试日志
http.client.HTTPConnection.debuglevel = 1

# 配置 Python Logging
logging.basicConfig(level=logging.DEBUG)
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

    logger.info("🔑 正在构建凭据对象...")
    logger.debug(f"Client ID: {client_id[:5]}...")
    logger.debug(f"Refresh Token: {refresh_token[:5]}...")

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
        if whence == io.SEEK_SET and offset == self.position:
            return self.position
        if whence == io.SEEK_CUR and offset == 0:
            return self.position
        logger.warning(f"⚠️ 尝试 Seek 到不支持的位置: {offset}, 当前: {self.position}")
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
        # --- 🔍 验证 Token 有效性 ---
        logger.info("🔍 开始上传前验证 Token...")
        try:
            service = get_drive_service()
            # 尝试做一个轻量级请求来验证 Token
            service.about().get(fields="user").execute()
            logger.info("✅ Token 验证通过！")
        except google.auth.exceptions.RefreshError as re:
            logger.error(f"❌ Token 刷新失败 (无效或过期): {re}")
            return f"❌ **鉴权失败**: Refresh Token 无效或已过期。\n详情: {re}\n请重新生成 Token。"
        except Exception as e:
            logger.error(f"❌ Token 验证时发生未知错误: {e}")
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
            logger.info(f"📄 文件名: {filename}, 大小: {msg_size}")

            # --- ☁️ 准备上传 ---
            folder_id = os.environ.get("GDRIVE_FOLDER_ID")
            file_metadata = {'name': filename}
            if folder_id:
                # 验证文件夹 ID 是否为空字符串
                if folder_id.strip():
                    file_metadata['parents'] = [folder_id]
                    logger.info(f"📂 目标文件夹 ID: {folder_id}")
                else:
                    logger.warning("⚠️ GDRIVE_FOLDER_ID 为空，将上传到根目录")

            stream_wrapper = StreamingUploadFile(response)
            
            media = MediaIoBaseUpload(
                stream_wrapper,
                mimetype=response.headers.get('Content-Type', 'application/octet-stream'),
                resumable=True,
                chunksize=10 * 1024 * 1024 
            )

            progress(0.2, desc="☁️ 正在流式上传到 Google Drive...")
            logger.info("🚀 发起 create 请求...")
            
            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webContentLink, webViewLink'
            )
            
            # --- 🔥 执行上传 ---
            file = None
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress_percent = int(status.progress() * 100)
                    # progress(0.2 + (0.7 * status.progress()), desc=f"☁️ 上传中: {progress_percent}%")
                    logger.debug(f"⏳ 上传进度: {progress_percent}%")

            file = response
            file_id = file.get('id')
            logger.info(f"✅ 上传完成，File ID: {file_id}")
            
            progress(0.9, desc="🔓 正在设置公开权限...")

            service.permissions().create(
                fileId=file_id,
                body={'role': 'reader', 'type': 'anyone'}
            ).execute()

            web_link = file.get('webContentLink', file.get('webViewLink'))
            return f"""✅ **转存成功!**
            
**文件名**: {filename}
**文件ID**: {file_id}
**下载链接**: [点击下载]({web_link})
"""

    except BrokenPipeError:
        logger.error("❌ BrokenPipeError: 连接被 Google 意外关闭。")
        return "❌ **上传中断**: 连接被 Google 拒绝。通常是因为 Token 无效、配额超限或网络不稳。请检查 Logs 获取详细 HTTP 响应。"
    except Exception as e:
        logger.error(f"❌ 全局异常捕获: {str(e)}", exc_info=True)
        return f"❌ **发生错误**: {str(e)}"

# ---------------------------------------------------------
# 3. 构建界面
# ---------------------------------------------------------
with gr.Blocks(title="URL to Drive Saver") as demo:
    gr.Markdown("# 🚀 URL to Google Drive Saver (Debug Mode)")
    
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
    demo.queue(max_size=5).launch(server_name="0.0.0.0", show_api=True, share=False)

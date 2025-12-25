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
# 0. 配置日志
# ---------------------------------------------------------
# 关闭过于详细的 HTTP 调试日志，以免刷屏
# http.client.HTTPConnection.debuglevel = 1

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
        try:
            chunk = self.raw.read(size)
            if chunk:
                self.position += len(chunk)
            return chunk
        except Exception as e:
            logger.error(f"❌ 读取下载流失败: {e}")
            raise

    def seek(self, offset, whence=io.SEEK_SET):
        # Google Drive Upload 可能会尝试 seek(0) 来获取大小或重试
        if whence == io.SEEK_SET and offset == self.position:
            return self.position
        if whence == io.SEEK_CUR and offset == 0:
            return self.position
        # 忽略不支持的 seek 操作，通常不影响流式上传
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
        try:
            service = get_drive_service()
        except Exception as e:
            return f"❌ **鉴权错误**: {str(e)}"

        # --- 2. 下载 ---
        progress(0, desc="🚀 初始化连接...")
        logger.info(f"📥 开始下载 URL: {file_url}")
        
        with requests.get(file_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            
            filename = get_filename_from_response(response, file_url)
            filesize = int(response.headers.get('Content-Length', 0))
            msg_size = f"{filesize / 1024 / 1024:.2f} MB" if filesize > 0 else "未知大小"
            
            progress(0.1, desc=f"📥 准备: {filename} ({msg_size})")

            # --- 3. 上传配置 ---
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
                fields='id, webContentLink, webViewLink'
            )
            
            # --- 4. 执行上传 ---
            file = None
            response_upload = None
            while response_upload is None:
                status, response_upload = request.next_chunk()
                if status:
                    progress_percent = int(status.progress() * 100)
                    # 可以在日志里看进度，不需要频繁打扰前端
                    # logger.debug(f"⏳ 上传进度: {progress_percent}%")

            file = response_upload
            file_id = file.get('id')
            logger.info(f"✅ 上传完成，File ID: {file_id}")
            
            # --- 5. 权限设置 (容错处理) ---
            link_status = "🔒 私有文件 (仅自己可见)"
            web_link = f"https://drive.google.com/file/d/{file_id}/view"
            
            try:
                progress(0.9, desc="🔓 尝试设置公开权限...")
                service.permissions().create(
                    fileId=file_id,
                    body={'role': 'reader', 'type': 'anyone'}
                ).execute()
                link_status = "🌍 公开链接"
                # 获取直链
                web_link = file.get('webContentLink', web_link)
            except Exception as perm_err:
                logger.warning(f"⚠️ 无法设置为公开权限 (可能是 Google 安全策略限制): {perm_err}")
                link_status = "🔒 私有文件 (Google 拒绝了公开分享，请去网盘查看)"

            return f"""✅ **转存成功!**
            
**文件名**: {filename}
**状态**: {link_status}
**文件链接**: [点击打开 Google Drive]({web_link})
"""

    except BrokenPipeError:
        logger.error("❌ BrokenPipeError")
        return "❌ **上传中断**: 连接被 Google 拒绝。请检查网络或 Token。"
    except Exception as e:
        logger.error(f"❌ 错误: {str(e)}", exc_info=True)
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
    demo.queue(max_size=5).launch(server_name="0.0.0.0", show_api=True, share=False)

import os
import io
import requests
import gradio as gr
import logging
import http.client
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.exceptions import RefreshError, DefaultCredentialsError
from urllib.parse import urlparse, unquote

# ---------------------------------------------------------
# 0. 配置详细日志 (Debug Logging)
# ---------------------------------------------------------
# 开启 http.client 的调试输出，这会打印到底层 stdout
http.client.HTTPConnection.debuglevel = 1

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
        error_msg = "❌ 缺少必要的 OAuth 环境变量: "
        missing = []
        if not client_id: missing.append("G_CLIENT_ID")
        if not client_secret: missing.append("G_CLIENT_SECRET")
        if not refresh_token: missing.append("G_REFRESH_TOKEN")
        raise EnvironmentError(error_msg + ", ".join(missing))

    logger.info(f"正在初始化凭据... Client ID 前缀: {client_id[:10]}...")

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    
    return build("drive", "v3", credentials=creds)

def test_token_validity(service):
    """
    在上传前先测试 Token 是否有效（尝试列出前1个文件）
    """
    try:
        logger.info("🔍 正在测试 Token 有效性 (Files.list)...")
        results = service.files().list(pageSize=1, fields="files(id, name)").execute()
        files = results.get('files', [])
        logger.info(f"✅ Token 测试通过！成功获取文件列表 (找到 {len(files)} 个文件)")
        return True
    except RefreshError as e:
        logger.error(f"❌ Token 刷新失败 (RefreshError): {e}")
        logger.error("请检查 G_REFRESH_TOKEN 是否过期，或 Client ID/Secret 是否匹配。")
        return False
    except Exception as e:
        logger.error(f"❌ Token 测试发生其他错误: {type(e).__name__}: {e}")
        return False

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
        # 1. 初始化 Drive 服务并测试连接
        progress(0, desc="🔐 正在验证 Google Drive 权限...")
        service = get_drive_service()
        
        if not test_token_validity(service):
            return "❌ **鉴权失败**: 无法连接 Google Drive API。请检查 Logs 获取详细错误信息 (RefreshError)。"

        # 2. 建立下载连接
        progress(0.1, desc="🚀 正在连接下载源...")
        with requests.get(file_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            
            filename = get_filename_from_response(response, file_url)
            filesize = int(response.headers.get('Content-Length', 0))
            msg_size = f"{filesize / 1024 / 1024:.2f} MB" if filesize > 0 else "未知大小"
            
            progress(0.2, desc=f"📥 准备传输: {filename} ({msg_size})")

            # 3. 准备上传
            folder_id = os.environ.get("GDRIVE_FOLDER_ID")
            file_metadata = {'name': filename}
            if folder_id:
                file_metadata['parents'] = [folder_id]
                logger.info(f"目标文件夹 ID: {folder_id}")

            stream_wrapper = StreamingUploadFile(response)
            
            media = MediaIoBaseUpload(
                stream_wrapper,
                mimetype=response.headers.get('Content-Type', 'application/octet-stream'),
                resumable=True,
                chunksize=5 * 1024 * 1024  # 降低 Chunk Size 到 5MB 以减少超时概率
            )

            progress(0.3, desc="☁️ 正在流式上传 (这可能需要几分钟)...")
            logger.info("开始执行 service.files().create ...")
            
            try:
                request = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webContentLink, webViewLink'
                )
                file = request.execute()
                
            except Exception as upload_err:
                logger.error(f"❌ 上传中断: {upload_err}")
                # 尝试捕获更详细的响应
                if hasattr(upload_err, 'content'):
                    logger.error(f"API 响应内容: {upload_err.content}")
                raise upload_err

            file_id = file.get('id')
            logger.info(f"✅ 上传完成，文件 ID: {file_id}")
            
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

    except Exception as e:
        logger.exception("全流程捕获到异常")
        return f"❌ **发生错误**: {str(e)}\n\n(请查看 Space Logs 获取详细 Debug 信息)"

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

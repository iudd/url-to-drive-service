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
# 2. 核心流式处理逻辑 (Raw Stream 模式)
# ---------------------------------------------------------
class RawStreamAdapter(io.IOBase):
    """
    直接适配 requests.response.raw 对象。
    关键点：
    1. 启用 decode_content=True 处理 Gzip。
    2. 模拟 seek/tell 以满足 Google API 的接口检查。
    """
    def __init__(self, raw_response_obj):
        self._raw = raw_response_obj
        self._position = 0
        
        # ⚠️ 核心修复: 强制 urllib3 自动处理 Gzip 解压
        self._raw.decode_content = True

    def read(self, size=-1):
        # 如果 size 为 -1，读取所有（不推荐但要做兼容）
        if size == -1:
            size = None # read() 不传参默认读所有
        
        try:
            chunk = self._raw.read(size) or b""
            self._position += len(chunk)
            
            # 调试日志：监控前几个包，确保有数据
            if self._position < 1024 * 1024: 
                logger.debug(f"🔍 正在读取流数据... 本次读取: {len(chunk)} 字节, 总计: {self._position}")
                
            return chunk
        except Exception as e:
            logger.error(f"❌ 数据流读取异常: {e}")
            raise

    def seek(self, offset, whence=io.SEEK_SET):
        # Google Upload 可能会在开始前 seek(0)
        if offset == self._position:
            return self._position
        if offset == 0 and self._position == 0:
            return 0
        # 如果还没读过数据，允许 seek(0)
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
        service = get_drive_service()

        logger.info(f"📥 开始下载: {file_url}")
        
        with requests.get(file_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            
            filename = get_filename_from_response(response, file_url)
            filesize = int(response.headers.get('Content-Length', 0))
            msg_size = f"{filesize / 1024 / 1024:.2f} MB" if filesize > 0 else "未知大小"
            
            progress(0.1, desc=f"📥 准备: {filename} ({msg_size})")

            folder_id = os.environ.get("GDRIVE_FOLDER_ID", "").strip()
            file_metadata = {'name': filename}
            if folder_id:
                file_metadata['parents'] = [folder_id]

            # 关键修复：直接使用 Raw Adapter + Gzip 解码
            stream_wrapper = RawStreamAdapter(response.raw)
            
            media = MediaIoBaseUpload(
                stream_wrapper,
                mimetype=response.headers.get('Content-Type', 'application/octet-stream'),
                resumable=True,
                chunksize=10 * 1024 * 1024  # 10MB 分片
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
            
            logger.info(f"✅ 上传完成. ID: {file_id}")
            logger.info(f"📊 云端文件大小: {uploaded_size} 字节 ({uploaded_size/1024/1024:.2f} MB)")
            
            # 安全检查：如果还是 0KB，直接报错
            if uploaded_size == 0 and filesize > 0:
                 return f"❌ **上传警告**: 文件已创建但大小为 0KB。可能源服务器不支持流式读取或压缩格式异常。\nID: {file_id}"

            # 权限设置
            web_link = file.get('webViewLink', f"https://drive.google.com/file/d/{file_id}/view")
            perm_status = "🔒 私有"
            try:
                service.permissions().create(
                    fileId=file_id, body={'role': 'reader', 'type': 'anyone'}
                ).execute()
                perm_status = "🌍 公开"
            except Exception: pass

            return f"""✅ **转存成功!**
            
**文件名**: {filename}
**云端大小**: {uploaded_size / 1024 / 1024:.2f} MB
**状态**: {perm_status}
**链接**: [点击打开]({web_link})
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

    submit_btn.click(process_upload, inputs=url_input, outputs=output_markdown)

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", show_api=True)

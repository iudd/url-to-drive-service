import os
import requests
import gradio as gr
import logging
import shutil
import tempfile
import time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from urllib.parse import urlparse, unquote

# ---------------------------------------------------------
# 0. 配置日志
# ---------------------------------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 1. 鉴权
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

def get_filename_from_url(response, url):
    content_disposition = response.headers.get("Content-Disposition")
    if content_disposition:
        import re
        fname = re.findall('filename="?([^"]+)"?', content_disposition)
        if fname:
            return unquote(fname[0])
    parsed = urlparse(url)
    return os.path.basename(unquote(parsed.path)) or f"file_{int(time.time())}"

# ---------------------------------------------------------
# 2. 核心逻辑：下载到本地 -> 上传 (最稳健方案)
# ---------------------------------------------------------
def process_upload(file_url, progress=gr.Progress()):
    if not file_url:
        return "❌ 错误: 请输入 URL"
    
    temp_path = None
    try:
        # --- 1. 鉴权检查 ---
        try:
            service = get_drive_service()
        except Exception as e:
            return f"❌ 鉴权失败: {e}"

        # --- 2. 下载到临时文件 ---
        progress(0, desc="🚀 正在连接资源...")
        logger.info(f"📥 准备下载: {file_url}")
        
        with requests.get(file_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            
            filename = get_filename_from_url(response, file_url)
            total_size = int(response.headers.get('Content-Length', 0))
            
            # 创建临时文件
            fd, temp_path = tempfile.mkstemp(suffix=f"_{filename}")
            os.close(fd) # 关闭句柄，让 open 去处理
            
            msg_size = f"{total_size / 1024 / 1024:.2f} MB" if total_size > 0 else "未知大小"
            logger.info(f"💾 开始下载到临时文件: {temp_path} ({msg_size})")
            progress(0.1, desc=f"📥 正在下载到中转站: {filename}...")

            # 下载并写入硬盘
            downloaded = 0
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # 更新下载进度
                        if total_size > 0:
                            p = 0.1 + (0.4 * (downloaded / total_size))
                            progress(p, desc=f"📥 下载中: {downloaded/1024/1024:.1f}/{msg_size}")

        # --- 3. 校验本地文件 ---
        local_size = os.path.getsize(temp_path)
        logger.info(f"✅ 本地下载完成，大小: {local_size} bytes")
        
        if local_size == 0:
            os.remove(temp_path)
            return "❌ **下载失败**: 源文件无法读取或为空 (0KB)。请检查 URL 是否有效。"

        # --- 4. 上传到 Google Drive ---
        progress(0.5, desc=f"☁️ 正在上传到 Google Drive ({local_size/1024/1024:.2f} MB)...")
        
        folder_id = os.environ.get("GDRIVE_FOLDER_ID", "").strip()
        file_metadata = {'name': filename}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        # 使用 MediaFileUpload (针对本地文件，极其稳定)
        media = MediaFileUpload(
            temp_path,
            mimetype='application/octet-stream', # 让 Google 自动检测或作为二进制
            resumable=True
        )

        request = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, size'
        )

        # 执行分片上传
        response_obj = None
        while response_obj is None:
            status, response_obj = request.next_chunk()
            if status:
                # 映射进度 0.5 -> 1.0
                p = 0.5 + (0.5 * status.progress())
                progress(p, desc=f"☁️ 上传中: {int(status.progress()*100)}%")
                # logger.info(f"上传进度: {int(status.progress()*100)}%")

        # --- 5. 完成处理 ---
        file = response_obj
        file_id = file.get('id')
        cloud_size = int(file.get('size', 0))
        
        logger.info(f"✅ Google Drive 接收完成. ID: {file_id}, 大小: {cloud_size}")
        
        # 再次校验云端大小
        status_msg = ""
        if cloud_size == 0:
            status_msg = "\n⚠️ **警告**: 云端文件显示为 0KB，请检查网盘。"
        
        # 权限
        web_link = file.get('webViewLink', f"https://drive.google.com/file/d/{file_id}/view")
        perm_str = "🔒 私有"
        try:
            service.permissions().create(
                fileId=file_id, body={'role': 'reader', 'type': 'anyone'}
            ).execute()
            perm_str = "🌍 公开"
        except Exception: pass

        # 清理临时文件
        try:
            os.remove(temp_path)
            logger.info("🗑️ 临时文件已清理")
        except: pass

        return f"""✅ **转存成功!**
        
**文件名**: {filename}
**大小**: {cloud_size / 1024 / 1024:.2f} MB
**状态**: {perm_str}
**链接**: [点击打开 Google Drive]({web_link})
{status_msg}
"""

    except Exception as e:
        logger.error(f"❌ 流程异常: {e}", exc_info=True)
        # 确保清理
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        return f"❌ **发生错误**: {str(e)}"

# ---------------------------------------------------------
# 3. 界面
# ---------------------------------------------------------
with gr.Blocks(title="URL to Drive Saver") as demo:
    gr.Markdown("# 🚀 URL to Google Drive Saver (Stable Mode)")
    
    with gr.Row():
        url_input = gr.Textbox(label="文件 URL", placeholder="https://example.com/video.mp4")
        submit_btn = gr.Button("开始转存", variant="primary")
    
    output_markdown = gr.Markdown(label="状态")

    submit_btn.click(process_upload, inputs=url_input, outputs=output_markdown)

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", show_api=True)

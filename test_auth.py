import os
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import google.auth.exceptions

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_auth_only():
    print("="*50)
    print("🚀 Google Drive 鉴权独立测试")
    print("="*50)

    client_id = os.environ.get("G_CLIENT_ID")
    client_secret = os.environ.get("G_CLIENT_SECRET")
    refresh_token = os.environ.get("G_REFRESH_TOKEN")

    print(f"Client ID (前5位): {client_id[:5] if client_id else 'MISSING'}")
    print(f"Refresh Token (前5位): {refresh_token[:5] if refresh_token else 'MISSING'}")

    if not all([client_id, client_secret, refresh_token]):
        print("❌ 环境变量缺失，无法测试。")
        return

    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )
        
        print("\n⏳ 正在构建 Drive 服务并刷新 Token...")
        service = build("drive", "v3", credentials=creds)
        
        print("🔍 正在请求用户信息 (about.get)...")
        about = service.about().get(fields="user,storageQuota").execute()
        
        user = about.get('user', {})
        quota = about.get('storageQuota', {})
        
        print("\n" + "="*50)
        print("✅ 鉴权成功！连接正常！")
        print("="*50)
        print(f"👤 用户名: {user.get('displayName')}")
        print(f"📧 邮箱: {user.get('emailAddress')}")
        print(f"💾 已用空间: {int(quota.get('usage', 0)) / 1024 / 1024 / 1024:.2f} GB")
        print(f"☁️ 总空间: {int(quota.get('limit', 0)) / 1024 / 1024 / 1024:.2f} GB")
        print("="*50)
        
    except google.auth.exceptions.RefreshError as e:
        print("\n❌ 鉴权失败: Refresh Token 无效或过期")
        print(f"详细错误: {e}")
        print("👉 即使您觉得是新的，也请重新生成。Google 可能因为 IP 变动暂时封锁了旧 Token。")
    except Exception as e:
        print("\n❌ 发生未知错误")
        print(f"详细错误: {e}")

if __name__ == "__main__":
    test_auth_only()

import os
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import google.auth.exceptions

# 配置详细日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_google_auth():
    print("\n" + "="*50)
    print("🕵️‍♂️ Google OAuth 鉴权深度诊断工具")
    print("="*50 + "\n")

    # 1. 检查环境变量
    client_id = os.environ.get("G_CLIENT_ID")
    client_secret = os.environ.get("G_CLIENT_SECRET")
    refresh_token = os.environ.get("G_REFRESH_TOKEN")

    print(f"Client ID: {client_id[:10]}... (长度: {len(client_id) if client_id else 0})")
    print(f"Refresh Token: {refresh_token[:10]}... (长度: {len(refresh_token) if refresh_token else 0})")

    if not all([client_id, client_secret, refresh_token]):
        print("\n❌ 严重错误: 环境变量缺失！请检查 Settings -> Repository Secrets")
        return

    # 2. 构建凭据
    print("\n🔄 正在构建 Credentials 对象...")
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )

    # 3. 尝试刷新 Token (关键步骤)
    print("⚡ 正在尝试刷新 Access Token (连接 Google)...")
    try:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        print(f"\n✅ 成功！获取到 Access Token: {creds.token[:10]}...")
    except google.auth.exceptions.RefreshError as e:
        print(f"\n❌ 刷新失败: {e}")
        print("💡 原因分析:")
        print("1. Refresh Token 已过期 (测试版应用7天过期)")
        print("2. Refresh Token 与 Client ID 不匹配 (必须是一套)")
        print("3. Refresh Token 被手动撤销")
        return
    except Exception as e:
        print(f"\n❌ 网络连接失败: {e}")
        return

    # 4. 尝试 API 调用
    print("\n📡 正在测试 Drive API 调用 (About: get)...")
    try:
        service = build("drive", "v3", credentials=creds)
        about = service.about().get(fields="user").execute()
        user_info = about.get('user', {})
        print(f"\n✅ API 调用成功！")
        print(f"👤 用户名: {user_info.get('displayName')}")
        print(f"📧 邮箱: {user_info.get('emailAddress')}")
    except Exception as e:
        print(f"\n❌ API 调用失败: {e}")

if __name__ == "__main__":
    test_google_auth()

import os
from google_auth_oauthlib.flow import InstalledAppFlow

def get_refresh_token():
    """
    获取 Google OAuth 2.0 Refresh Token 的辅助脚本
    """
    # 定义需要的权限范围 (读写权限)
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    print("="*50)
    print("🚀 Google Drive Refresh Token 获取助手")
    print("="*50)
    
    # 检查 client_secrets.json
    if not os.path.exists('client_secrets.json'):
        print("\n❌ 错误: 未找到 'client_secrets.json' 文件")
        print("请按照以下步骤操作:")
        print("1. 访问 Google Cloud Console (https://console.cloud.google.com/)")
        print("2. 创建/选择项目 -> API 和服务 -> 凭据")
        print("3. 创建 OAuth 客户端 ID (应用类型选 '桌面应用')")
        print("4. 下载 JSON 文件，重命名为 'client_secrets.json' 并放到当前目录")
        return

    try:
        # 创建授权流程
        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secrets.json',
            SCOPES
        )
        
        print("\n📋 正在启动浏览器进行授权...")
        print("请在浏览器中登录您的 Google 账号并允许访问。")
        
        # 运行本地服务器
        # run_local_server 会自动打开浏览器并监听回调
        creds = flow.run_local_server(port=0)
        
        print("\n" + "="*50)
        print("✅ 授权成功！")
        print("="*50)
        print(f"\n您的 Refresh Token:\n\n{creds.refresh_token}\n")
        print("="*50)
        print("\n⚠️ 下一步操作:")
        print("1. 复制上面的 Refresh Token")
        print("2. 在 Hugging Face Space 的 Settings -> Repository Secrets 中添加:")
        print("   - G_REFRESH_TOKEN: (粘贴上面的值)")
        print("   - G_CLIENT_ID: (从 client_secrets.json 中获取)")
        print("   - G_CLIENT_SECRET: (从 client_secrets.json 中获取)")
        
    except Exception as e:
        print(f"\n❌ 发生错误: {str(e)}")

if __name__ == "__main__":
    get_refresh_token()

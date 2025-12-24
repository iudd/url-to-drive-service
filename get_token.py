
if __name__ == "__main__":
    import os
    from google_auth_oauthlib.flow import InstalledAppFlow
    
    # 定义需要的权限范围
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    try:
        # 创建授权流程
        # 注意: 这里假设你已经下载了 client_secrets.json 文件
        if not os.path.exists('client_secrets.json'):
            print("❌ 未找到 client_secrets.json 文件")
            print("请从 Google Cloud Console 下载 OAuth 客户端凭据并重命名为 client_secrets.json")
            exit(1)
            
        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secrets.json',
            SCOPES
        )
        
        # 运行本地服务器进行授权
        print("🚀 正在启动浏览器进行授权...")
        creds = flow.run_local_server(port=0)
        
        print("\n" + "="*50)
        print("✅ 授权成功!")
        print("="*50)
        print(f"G_REFRESH_TOKEN: {creds.refresh_token}")
        print("="*50)
        print("\n请保存好这个 Refresh Token，并将其添加到 Hugging Face Space 的 Secrets 中。")
        
    except ImportError:
        print("❌ 缺少必要的库")
        print("请运行: pip install google-auth-oauthlib")
    except Exception as e:
        print(f"❌ 发生错误: {str(e)}")

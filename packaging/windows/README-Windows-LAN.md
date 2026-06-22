# Team-Happy 局域网模式

局域网模式适合让同一个 Wi-Fi / 同一个路由器下的电脑、手机、平板访问你这台电脑上的 Team-Happy。

## 启动

双击：

```text
start-team-happy-lan.bat
```

局域网模式会：

- 监听 `0.0.0.0:1242`
- 自动开启登录：`AUTH_ENABLED=true`
- 使用 `data/` 保存项目和配置
- 在黑窗口里显示本机访问地址和局域网访问地址

## 访问

本机访问：

```text
http://127.0.0.1:1242
```

同 Wi-Fi / 同路由器下的其他设备访问：

```text
http://你的局域网IP:1242
```

例如：

```text
http://192.168.1.23:1242
```

## 登录

默认用户名：

```text
admin
```

如果没有提前配置密码，Team-Happy 会在首次启动时自动生成密码，并写入根目录的 `.env`：

```text
AUTH_PASSWORD=xxxxxxxxxxxxxxxx
```

如果你想手动设置密码，可以在 Team-Happy 根目录新建或编辑 `.env`：

```env
AUTH_ENABLED=true
AUTH_USERNAME=admin
AUTH_PASSWORD=你的密码
```

保存后重新启动 `start-team-happy-lan.bat`。

## Windows 防火墙

如果其他设备打不开，请在 Windows 防火墙允许 Python / uvicorn 访问专用网络，或放行 TCP 端口 `1242`。

## 安全提醒

- 只在可信任的局域网中使用。
- 不要把 `1242` 端口直接暴露到公网。
- 公网访问请使用 HTTPS、反向代理或内网穿透登录保护方案。
- 不要使用免登录模式对局域网以外的人开放。

"""NoneBot2 运行时：框架负责连接 / 事件 / 插件，老引擎作为库复用。

目录：
  nb/compat.py                  NoneBot ↔ 老 Bot 接口适配（唯一胶水层）
  nb/plugins/legacy_bridge.py   把 qqbot.plugins.* 挂到 NoneBot 上
  nb/plugins/nb_sys.py          NoneBot 原生指令（/nb 状态 等）
  main_nb.py                    启动入口（等同于旧 main.py）
"""

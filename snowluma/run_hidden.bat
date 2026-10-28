@echo off
rem 由任务计划程序以「当前用户 / 有限权限」调用：这样 node 是 Medium 完整性，才能注入 QQ
cd /d "%~dp0"
start "" /min "%~dp0node.exe" index.mjs

@echo off
REM ==========================================
REM  グレースケール画像処理ツール – 起動スクリプト
REM ==========================================

echo ====================================
echo  Dash アプリを起動します
echo  http://localhost:8050
echo ====================================

cd /d "%~dp0"

REM --- 開発モード (ホットリロード有効) ---
python app.py

REM --- 本番モード (Waitress) ---
REM python -c "from waitress import serve; from app import server; serve(server, host='0.0.0.0', port=8050)"

pause

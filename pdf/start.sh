#!/bin/bash

echo "=========================================="
echo "  PDF OCR Web Application"
echo "=========================================="
echo ""

# 检查 Python
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "Error: Python is not installed or not in PATH"
        exit 1
    fi
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

echo "Using: $($PYTHON_CMD --version)"
echo ""

# 检查 Tesseract
echo "Checking Tesseract installation..."
if ! command -v tesseract &> /dev/null; then
    echo "Warning: Tesseract is not installed"
    echo "Please install Tesseract OCR:"
    echo "  Ubuntu/Debian: sudo apt install tesseract-ocr tesseract-ocr-chi-sim"
    echo "  macOS: brew install tesseract tesseract-lang"
    echo ""
fi

# 安装依赖
echo "Installing backend dependencies..."
cd backend
$PYTHON_CMD -m pip install -r requirements.txt --quiet

cd ..

# 创建必要目录
mkdir -p backend/uploads
mkdir -p backend/outputs

# 启动后端
echo ""
echo "Starting backend server..."
cd backend
$PYTHON_CMD -m uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# 等待后端启动
sleep 2

# 启动前端
echo "Starting frontend server..."
cd frontend
$PYTHON_CMD -m http.server 8080 &
FRONTEND_PID=$!
cd ..

echo ""
echo "=========================================="
echo "  Application is running!"
echo "=========================================="
echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:8080"
echo ""
echo "  Press Ctrl+C to stop the servers"
echo "=========================================="
echo ""

# 打开浏览器
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8080
elif command -v open &> /dev/null; then
    open http://localhost:8080
fi

# 等待中断信号
trap "echo ''; echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

# 保持脚本运行
wait

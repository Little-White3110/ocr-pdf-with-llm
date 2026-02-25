# PDF OCR Web

一个基于 Web 的 PDF OCR 处理工具，支持中文识别和大纲生成。

## 功能特性

- **PDF OCR 文字识别** - 支持中英文混合识别
- **LLM 大纲生成** - 使用 AI 自动生成文档大纲
- **批量处理** - 支持多文件批量上传和处理
- **深色模式** - 支持亮色/深色主题切换
- **实时进度** - 显示处理进度和状态
- **文本下载** - 提供清理后的纯文本文件下载

## 系统要求

- Python 3.10+
- Tesseract OCR（包含中文语言包）
- Ghostscript（可选，用于高级图像处理）

## 快速开始

### Windows

1. 安装 [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
2. 安装中文语言包：`chi_sim`、`chi_sim_vert`
3. 双击运行 `start.bat`

### Linux/Mac

```bash
# 安装 Tesseract
sudo apt install tesseract-ocr tesseract-ocr-chi-sim  # Ubuntu/Debian
brew install tesseract tesseract-lang                  # macOS

# 运行启动脚本
chmod +x start.sh
./start.sh
```

### 手动启动

```bash
# 安装依赖
pip install -r backend/requirements.txt

# 启动后端
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 启动前端（新终端）
cd frontend
python -m http.server 8080
```

## 使用方法

1. 打开浏览器访问 `http://localhost:8080`
2. 点击上传区域或拖拽 PDF 文件
3. 选择是否生成大纲（需要配置 LLM API）
4. 等待处理完成
5. 下载 OCR 处理后的 PDF 或文本文件

## 配置

### LLM 配置

点击右上角设置按钮，配置以下信息：

- **API Key** - LLM API 密钥
- **Base URL** - API 基础地址（如 DeepSeek、OpenAI 等）
- **模型** - 使用的模型名称

### OCR 参数

默认使用以下 OCR 参数：

- 语言：中文简体 + 竖排 + 英文
- 引擎：LSTM 神经网络
- DPI：400

## 项目结构

```
pdf-ocr-web/
├── backend/           # 后端代码
│   ├── main.py        # FastAPI 主程序
│   ├── ocr_service.py # OCR 处理服务
│   ├── llm_service.py # LLM 服务
│   ├── task_manager.py# 任务管理
│   └── requirements.txt
├── frontend/          # 前端代码
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── docs/              # 文档
│   └── guide.html     # 使用指南
├── start.bat          # Windows 启动脚本
├── start.sh           # Linux/Mac 启动脚本
└── README.md
```

## 详细使用指南

请查看 [使用指南](docs/guide.html)

## 许可证

[MIT License](LICENSE)

# 媒体文件重复清理工具

这是一个用于清理重复媒体文件的Python脚本工具。它可以识别并清理以下类型的重复文件：

1. 相同分辨率和大小的图片文件
2. 图片副本文件（带有数字后缀的副本）
3. 与视频同名的图片文件
4. 相同大小、时长和帧率的视频文件

## 功能特点

- 支持多种图片格式（jpg, jpeg, png, gif, bmp, webp）
- 支持多种视频格式（mp4, mkv, avi, mov, wmv, flv, webm）
- 智能选择要保留的文件（基于文件名长度和修改时间）
- 详细的日志记录
- 用户交互式确认删除操作
- 统计信息显示

## 使用要求

- Python 3.x
- Pillow 库（用于图片处理）
- FFmpeg（用于视频信息获取）

## 安装依赖

```bash
pip install Pillow
```

## 使用方法

1. 确保已安装所需依赖
2. 运行脚本：`python media_duplicate_cleaner.py`
3. 在弹出的对话框中选择要处理的目录
4. 按照提示确认删除操作

## 注意事项

- 删除操作不可恢复，请谨慎操作
- 建议在操作前备份重要文件
- 程序会生成日志文件记录所有删除操作

## 🎬 支持的文件格式

### 图片格式
- JPG/JPEG
- PNG
- GIF
- BMP
- WebP

### 视频格式
- MP4
- MKV
- AVI
- MOV
- WMV
- FLV
- WebM

## 📋 系统要求

- Python 3.6+
- FFmpeg（用于视频分析）
- Windows/macOS/Linux

## 🚀 安装

1. **克隆仓库**
   ```bash
   git clone https://github.com/yourusername/media-duplicate-cleaner.git
   cd media-duplicate-cleaner
   ```

2. **安装FFmpeg**
   
   **Windows:**
   - 下载 [FFmpeg](https://ffmpeg.org/download.html)
   - 将FFmpeg添加到系统环境变量PATH中

   **macOS:**
   ```bash
   brew install ffmpeg
   ```

   **Linux (Ubuntu/Debian):**
   ```bash
   sudo apt update
   sudo apt install ffmpeg
   ```

3. **验证安装**
   ```bash
   ffmpeg -version
   ```

## 📖 使用方法

### 基本用法
```bash
python media_duplicate_cleaner.py <目录路径>
```

### 使用示例
```bash
# 扫描并清理图片目录
python media_duplicate_cleaner.py "D:\我的图片"

# 扫描并清理视频收藏
python media_duplicate_cleaner.py "/Users/username/Movies"
```

## 🔍 重复检测逻辑

### 图片文件
- 通过文件名模式匹配识别副本（如 "照片(1).jpg"）
- 当原始文件和带序号文件同时存在时，自动删除副本

### 视频文件
1. **文件大小分组**：首先按文件大小进行初步分组
2. **元数据分析**：使用FFmpeg提取视频时长和帧率
3. **精确匹配**：当大小、时长和帧率都接近时，认为是重复
4. **智能保留**：在重复组中优先保留：
   - 文件名最短的（通常是原始文件）
   - 修改时间最早的
   - 无明显副本标识的文件

## 📊 操作界面

运行工具后，您将看到详细的扫描结果：

```
开始处理目录: D:\媒体文件
扫描目录: 153

找到 287 个需要删除的重复文件

========================================================
目录: D:\媒体文件\度假照片
删除文件数: 23
========================================================

📷 图片文件 (23个):
  1. 海滩照片(1).jpg (图片: 3.45MB)
  2. 家庭合影(1).jpg (图片: 5.12MB)

🎬 视频文件 (5个):

  重复组 1 - 大小: 1524.36MB, 时长: 120.35s, 帧率: 24.00fps
  ├─ 删除文件 (2个):
  ├─ 1. 电影名称(1).mp4
  └─ 2. 电影名称 副本.mp4

总计要删除 287 个重复文件
确定要删除上述所有文件吗？(y/N): 
```

## 📄 日志文件

工具会在当前目录生成详细的日志文件，命名格式：
```
delete_operation_YYYYMMDD_HHMMSS.log
```

日志包含：
- 扫描的目录信息
- 检测到的重复文件详情
- 删除操作结果
- 错误信息（如有）

## ⚠️ 注意事项

1. **首次使用**：建议先在测试目录上运行，熟悉工具的工作方式
2. **备份重要数据**：处理重要数据前请先备份
3. **FFmpeg依赖**：确保FFmpeg已正确安装，否则视频分析功能不可用
4. **权限问题**：确保对扫描目录有读写权限
5. **不可撤销**：删除操作执行后无法撤销，请仔细检查

## 🐛 故障排除

### 常见问题

**Q: "无法创建日志文件"错误**
- A: 检查当前目录的写入权限，或以管理员权限运行

**Q: FFmpeg相关错误**
- A: 确保FFmpeg已正确安装并添加到系统PATH

**Q: 扫描速度过慢**
- A: 大量视频文件分析需要时间，属于正常现象

**Q: 删除失败**
- A: 查看日志文件了解具体原因，常见原因包括文件被占用、权限不足等

## 📝 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🤝 贡献

欢迎提交 Issues 和 Pull Requests！

## 📞 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 [Issue](https://github.com/yourusername/media-duplicate-cleaner/issues)
- 发送邮件至：your.email@example.com

---
⭐ 如果这个工具对您有帮助，请给项目点个星！ 
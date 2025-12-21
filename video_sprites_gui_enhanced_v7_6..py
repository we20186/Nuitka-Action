# video_sprites_gui_enhanced_v7_6.py
# Enhanced version v7.6 - 极速专业版 (完整修复版)
# 
# 【v7.6 修复与改进】
# - 修复试用退出机制：使用总秒数倒计时，确保准确退出
# - 添加颜色选择器：所有背景色输入都支持可视化选择
# - 优化用户体验：颜色预览、预设颜色、友好的交互
# - 安全退出流程：停止任务 -> 提示用户 -> 延迟退出
#
# Dependencies:
# pip install opencv-python pillow PySide6 numpy rembg imageio imageio-ffmpeg onnxruntime

import sys
import os
import math
import traceback
import shutil
import hashlib
import subprocess
import threading
import queue
import time
import json
import gc
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, date
from io import BytesIO
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==================== 设置模型路径环境变量 ====================
BIEMO_DIR = Path.cwd() / "biemo"
BIEMO_DIR.mkdir(parents=True, exist_ok=True)

# 设置 rembg/u2net 模型下载路径
os.environ["U2NET_HOME"] = str(BIEMO_DIR / "models")
os.environ["REMBG_HOME"] = str(BIEMO_DIR / "models")

# 确保模型目录存在
(BIEMO_DIR / "models").mkdir(parents=True, exist_ok=True)

# ==================== 依赖检测系统 ====================
class DependencyChecker:
    """检测所有必要的依赖库"""
    
    REQUIRED_PACKAGES = [
        ("cv2", "opencv-python", "图像处理核心库"),
        ("PIL", "Pillow", "图像格式支持"),
        ("numpy", "numpy", "数值计算"),
        ("imageio", "imageio", "视频/GIF读写"),
    ]
    
    OPTIONAL_PACKAGES = [
        ("rembg", "rembg[gpu]", "AI背景移除 (核心功能)"),
        ("onnxruntime", "onnxruntime", "AI推理引擎 (CPU)"),
    ]
    
    results = {}
    missing_required = []
    missing_optional = []
    install_commands = []
    
    @classmethod
    def check_all(cls):
        cls.results = {}
        cls.missing_required = []
        cls.missing_optional = []
        cls.install_commands = []
        
        for module_name, pip_name, desc in cls.REQUIRED_PACKAGES:
            try:
                __import__(module_name)
                cls.results[module_name] = ("ok", desc)
            except ImportError:
                cls.results[module_name] = ("missing", desc)
                cls.missing_required.append((pip_name, desc))
                cls.install_commands.append(f"pip install {pip_name}")
        
        for module_name, pip_name, desc in cls.OPTIONAL_PACKAGES:
            try:
                __import__(module_name)
                cls.results[module_name] = ("ok", desc)
            except ImportError:
                cls.results[module_name] = ("missing", desc)
                cls.missing_optional.append((pip_name, desc))
        
        return cls
    
    @classmethod
    def get_install_command(cls):
        if cls.missing_required:
            pkgs = [p[0] for p in cls.missing_required]
            return f"pip install {' '.join(pkgs)}"
        return None
    
    @classmethod
    def get_full_install_command(cls):
        return "pip install opencv-python Pillow numpy imageio imageio-ffmpeg rembg[gpu] onnxruntime-gpu"
    
    @classmethod
    def has_critical_missing(cls):
        return len(cls.missing_required) > 0

pass

# 尝试导入可能缺失的库
try:
    import winsound
    HAS_WINSOUND = True
except:
    HAS_WINSOUND = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("错误: Pillow 未安装")

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    print("错误: numpy 未安装")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("错误: opencv-python 未安装")

try:
    import imageio
    HAS_IMAGEIO = True
except ImportError:
    HAS_IMAGEIO = False
    print("错误: imageio 未安装")

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QListWidget, QSpinBox, QCheckBox,
    QHBoxLayout, QVBoxLayout, QGridLayout, QFileDialog, QProgressBar, QMessageBox,
    QTextEdit, QComboBox, QRadioButton, QButtonGroup, QGroupBox, QDoubleSpinBox,
    QTabWidget, QLineEdit, QDialog, QFrame, QToolTip, QSplitter, QPlainTextEdit,
    QListWidgetItem, QColorDialog, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView, QSizePolicy, QSlider, QSpacerItem, QStackedWidget, QFormLayout,
    QProgressDialog
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QObject, QSize, QSignalBlocker
from PySide6.QtGui import QFont, QColor, QPalette, QTextCursor, QIcon, QPixmap, QImage, QPainter, QPen, QBrush

if False:
    import rembg
    import rembg.sessions.u2net
    import rembg.sessions.isnet
    import onnxruntime
    import onnxruntime.capi.onnxruntime_pybind11_state

# ==================== 图像处理辅助函数 ====================
def make_square_with_padding(pil_img, padding=1):
    """
    将图片裁剪/扩展成正方形，保留指定像素的边距，确保内容居中
    """
    if pil_img is None:
        return None
        
    width, height = pil_img.size
    
    # 1. 找到内容的边界框（非透明区域）
    if pil_img.mode == 'RGBA':
        bbox = pil_img.getbbox()  # 返回 (left, top, right, bottom)
    else:
        # 如果不是RGBA，假设整个图片都是内容
        bbox = (0, 0, width, height)
    
    if bbox is None:
        # 图片完全透明，直接返回一个正方形透明图
        max_dim = max(width, height)
        return Image.new('RGBA', (max_dim, max_dim), (0, 0, 0, 0))
    
    left, top, right, bottom = bbox
    content_width = right - left
    content_height = bottom - top
    
    # 2. 计算正方形边长（取内容最大边 + padding*2）
    square_size = max(content_width, content_height) + padding * 2
    
    # 3. 计算内容在正方形中的居中位置
    center_x = (left + right) // 2
    center_y = (top + bottom) // 2
    
    # 4. 计算裁剪区域
    crop_left = center_x - square_size // 2
    crop_top = center_y - square_size // 2
    crop_right = crop_left + square_size
    crop_bottom = crop_top + square_size
    
    # 5. 创建新的正方形画布并粘贴内容
    new_img = Image.new('RGBA', (square_size, square_size), (0, 0, 0, 0))
    
    # 计算偏移量，将原图内容居中放置
    offset_x = max(0, -crop_left)
    offset_y = max(0, -crop_top)
    
    # 调整裁剪区域到有效范围
    src_left = max(0, crop_left)
    src_top = max(0, crop_top)
    src_right = min(width, crop_right)
    src_bottom = min(height, crop_bottom)
    
    # 裁剪并粘贴
    cropped = pil_img.crop((src_left, src_top, src_right, src_bottom))
    new_img.paste(cropped, (offset_x, offset_y))
    
    return new_img

# ==================== 配置管理器 ====================
class ConfigManager:
    """统一配置管理 - 所有路径都在 biemo 文件夹下"""
    
    BIEMO_BASE = Path.cwd() / "biemo"
    CONFIG_FILE = BIEMO_BASE / "config.json"
    MODELS_CONFIG_FILE = BIEMO_BASE / "models_config.json"
    LICENSE_FILE = BIEMO_BASE / "tools" / "license.key"
    
    DEFAULT_CONFIG = {
        "model_dir": str(BIEMO_BASE / "models"),
        "output_paths": {
            "sprite": str(BIEMO_BASE / "output_sprites"),
            "extract": str(BIEMO_BASE / "output_images"),
            "video": str(BIEMO_BASE / "output_videos"),
            "gif": str(BIEMO_BASE / "output_gifs"),
            "single": str(BIEMO_BASE / "output_single"),
            "beiou": str(BIEMO_BASE / "output_beiou"),
        },
        "default_model": "isnet-general-use",
        "default_threads": 4,
        "enable_sound": True,
        "auto_open_folder": True,
        "model_mirrors": {
            "global": "",
            "cn": ""
        }
    }
    
    _config = None
    
    @classmethod
    def init_directories(cls):
        """初始化所有目录"""
        cls.BIEMO_BASE.mkdir(parents=True, exist_ok=True)
        (cls.BIEMO_BASE / "models").mkdir(parents=True, exist_ok=True)
        (cls.BIEMO_BASE / "tools").mkdir(parents=True, exist_ok=True)
        
        for key in cls.DEFAULT_CONFIG["output_paths"]:
            path = Path(cls.DEFAULT_CONFIG["output_paths"][key])
            path.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_biemo_dir(cls):
        return cls.BIEMO_BASE
    
    @classmethod
    def get_license_file(cls):
        return str(cls.LICENSE_FILE)
    
    @classmethod
    def load(cls):
        if cls._config is not None:
            return cls._config
        
        cls.init_directories()
        cls._config = cls.DEFAULT_CONFIG.copy()
        
        try:
            if cls.CONFIG_FILE.exists():
                with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    for key, value in saved.items():
                        if key == "output_paths":
                            cls._config["output_paths"].update(value)
                        else:
                            cls._config[key] = value
        except Exception as e:
            print(f"配置加载失败: {e}")
        
        return cls._config
    
    @classmethod
    def save(cls):
        try:
            cls.BIEMO_BASE.mkdir(parents=True, exist_ok=True)
            with open(cls.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(cls._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"配置保存失败: {e}")
    
    @classmethod
    def get(cls, key, default=None):
        config = cls.load()
        return config.get(key, default)
    
    @classmethod
    def set(cls, key, value):
        config = cls.load()
        config[key] = value
        cls.save()
    
    @classmethod
    def get_model_dir(cls):
        return str(cls.BIEMO_BASE / "models")
    
    @classmethod
    def get_output_path(cls, key):
        paths = cls.get("output_paths", cls.DEFAULT_CONFIG["output_paths"])
        base_path = paths.get(key, str(cls.BIEMO_BASE / f"output_{key}"))
        Path(base_path).mkdir(parents=True, exist_ok=True)
        return base_path

    @classmethod
    def get_tools_dir(cls):
        p = cls.BIEMO_BASE / "tools"
        p.mkdir(parents=True, exist_ok=True)
        return str(p)

    @classmethod
    def get_tool_path(cls, name: str):
        p = Path(cls.get_tools_dir()) / (name + (".exe" if os.name == "nt" else ""))
        return str(p) if p.exists() else name

    @classmethod
    def get_model_mirrors(cls):
        mirrors = cls.get("model_mirrors", {"global": "", "cn": ""})
        return mirrors if isinstance(mirrors, dict) else {"global": "", "cn": ""}

ConfigManager.load()
os.environ["U2NET_HOME"] = ConfigManager.get_model_dir()
os.environ["REMBG_HOME"] = ConfigManager.get_model_dir()

# ==================== 全局日志系统 ====================
class LogManager(QObject):
    log_signal = Signal(str, str)
    
    _instance = None
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        super().__init__()
        self.logs = []
    
    def log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        self.logs.append((formatted, level))
        self.log_signal.emit(formatted, level)
        print(f"[{level.upper()}] {message}")
    
    def info(self, msg): self.log(msg, "info")
    def warning(self, msg): self.log(msg, "warning")
    def error(self, msg): self.log(msg, "error")
    def success(self, msg): self.log(msg, "success")

    def pipe(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        self.logs.append((formatted, level))
        self.log_signal.emit(formatted, level)

logger = LogManager.instance()

# ==================== 硬件检测 ====================
class HardwareInfo:
    gpu_available = False
    gpu_name = "N/A"
    gpu_memory_mb = 0
    cpu_threads = os.cpu_count() or 4
    onnx_providers = []
    available_memory_mb = 4096
    
    @classmethod
    def detect(cls):
        try:
            import onnxruntime as ort
            cls.onnx_providers = ort.get_available_providers()
            
            if 'CUDAExecutionProvider' in cls.onnx_providers:
                cls.gpu_available = True
                cls.gpu_name = "CUDA GPU"
                try:
                    import torch
                    if torch.cuda.is_available():
                        cls.gpu_memory_mb = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
                except:
                    cls.gpu_memory_mb = 4096
                logger.success("✓ GPU 加速已开启 (CUDA)")
            elif 'DmlExecutionProvider' in cls.onnx_providers:
                cls.gpu_available = True
                cls.gpu_name = "DirectML GPU"
                cls.gpu_memory_mb = 4096
                logger.success("✓ GPU 加速已开启 (DirectML)")
            else:
                logger.warning("○ 正在使用 CPU 模式")
                
        except ImportError:
            logger.error("✗ onnxruntime 未安装")
        except Exception as e:
            logger.error(f"硬件检测失败: {e}")
        
        if HAS_PSUTIL:
            try:
                cls.available_memory_mb = psutil.virtual_memory().available // (1024 * 1024)
            except:
                pass
        
        logger.info(f"CPU 线程数: {cls.cpu_threads}")
        logger.info(f"可用内存: {cls.available_memory_mb} MB")
        if cls.gpu_available:
            logger.info(f"GPU 显存: {cls.gpu_memory_mb} MB")
        return cls
    
    @classmethod
    def has_sufficient_resources(cls, model_size_mb: int = 900) -> bool:
        """检查是否有足够的资源处理大模型"""
        if cls.gpu_available and cls.gpu_memory_mb >= model_size_mb * 2:
            return True
        if cls.available_memory_mb >= model_size_mb * 3:
            return True
        return False

# ==================== 模型管理器 ====================
class ModelManager:
    """模型管理：统一文件名，支持用户导入模型"""
    
    MODELS = {
        "birefnet-general": {
            "name": "BiRefNet 通用 (SOTA)",
            "desc": "最高质量，需要较多资源",
            "file": "BiRefNet-general-epoch_244.onnx",
            "size_mb": 900,
            "quality": 5,
            "large": True
        },
        "birefnet-general-lite": {
            "name": "BiRefNet Lite",
            "desc": "快速高质量",
            "file": "BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx",
            "size_mb": 200,
            "quality": 4,
            "large": False
        },
        "birefnet-portrait": {
            "name": "BiRefNet 人像",
            "desc": "人像优化，需要较多资源",
            "file": "BiRefNet-portrait-epoch_150.onnx",
            "size_mb": 900,
            "quality": 5,
            "large": True
        },
        "isnet-general-use": {
            "name": "ISNet 通用 ★推荐",
            "desc": "推荐，平衡质量和速度",
            "file": "isnet-general-use.onnx",
            "size_mb": 170,
            "quality": 4,
            "large": False
        },
        "isnet-anime": {
            "name": "ISNet 动漫",
            "desc": "二次元/插画优化",
            "file": "isnet-anime.onnx",
            "size_mb": 170,
            "quality": 4,
            "large": False
        },
        "u2net": {
            "name": "U²-Net 标准",
            "desc": "经典稳定，兼容性好",
            "file": "u2net.onnx",
            "size_mb": 170,
            "quality": 3,
            "large": False
        },
        "u2netp": {
            "name": "U²-Net 轻量 ★低配",
            "desc": "最快速度，低配首选",
            "file": "u2netp.onnx",
            "size_mb": 4,
            "quality": 2,
            "large": False
        },
        "u2net_human_seg": {
            "name": "U²-Net 人像",
            "desc": "人体分割优化",
            "file": "u2net_human_seg.onnx",
            "size_mb": 170,
            "quality": 3,
            "large": False
        },
        "u2net_cloth_seg": {
            "name": "U²-Net 服装",
            "desc": "衣物分割",
            "file": "u2net_cloth_seg.onnx",
            "size_mb": 170,
            "quality": 3,
            "large": False
        },
        "silueta": {
            "name": "Silueta",
            "desc": "轮廓优化",
            "file": "silueta.onnx",
            "size_mb": 40,
            "quality": 3,
            "large": False
        },
    }
    
    _sessions = {}
    _lock = threading.Lock()
    _models_status = {}
    
    @classmethod
    def get_model_dir(cls) -> Path:
        model_dir = Path(ConfigManager.get_model_dir())
        model_dir.mkdir(parents=True, exist_ok=True)
        return model_dir
    
    @classmethod
    def get_models_config_file(cls) -> Path:
        return ConfigManager.MODELS_CONFIG_FILE
    
    @classmethod
    def load_models_config(cls):
        """从配置文件加载模型状态"""
        config_file = cls.get_models_config_file()
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    cls._models_status = json.load(f)
            except:
                cls._models_status = {}
        return cls._models_status
    
    @classmethod
    def save_models_config(cls):
        """保存模型状态到配置文件"""
        config_file = cls.get_models_config_file()
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(cls._models_status, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存模型配置失败: {e}")
    
    @classmethod
    def scan_models(cls) -> dict:
        """扫描模型目录，更新模型状态"""
        model_dir = cls.get_model_dir()
        cls._models_status = {}
        found_count = 0
        
        for model_id, info in cls.MODELS.items():
            model_file = model_dir / info["file"]
            exists = model_file.exists()
            
            if exists:
                found_count += 1
                file_size = model_file.stat().st_size // (1024 * 1024)
                cls._models_status[model_id] = {
                    "exists": True,
                    "file": info["file"],
                    "path": str(model_file),
                    "size_mb": file_size,
                    "scan_time": datetime.now().isoformat()
                }
            else:
                cls._models_status[model_id] = {
                    "exists": False,
                    "file": info["file"],
                    "path": str(model_file),
                    "size_mb": 0,
                    "scan_time": datetime.now().isoformat()
                }
        
        # 扫描用户自定义模型
        for onnx_file in model_dir.glob("*.onnx"):
            is_known = False
            for model_id, info in cls.MODELS.items():
                if onnx_file.name == info["file"]:
                    is_known = True
                    break
            
            if not is_known:
                custom_id = onnx_file.stem
                file_size = onnx_file.stat().st_size // (1024 * 1024)
                cls._models_status[f"custom_{custom_id}"] = {
                    "exists": True,
                    "file": onnx_file.name,
                    "path": str(onnx_file),
                    "size_mb": file_size,
                    "custom": True,
                    "scan_time": datetime.now().isoformat()
                }
                found_count += 1
        
        cls.save_models_config()
        logger.info(f"扫描完成: {found_count} 个模型")
        return cls._models_status

    @classmethod
    def ensure_model(cls, model_id: str, parent=None) -> bool:
        return False

    @classmethod
    def download_model(cls, model_id: str, parent=None) -> bool:
        return False
        sha = info.get("sha256")
        if sha:
            try:
                h = hashlib.sha256()
                with open(target, "rb") as f:
                    for b in iter(lambda: f.read(256 * 1024), b""):
                        h.update(b)
                if h.hexdigest().lower() != sha.lower():
                    try:
                        target.unlink()
                    except:
                        pass
                    QMessageBox.critical(parent, "错误", "校验失败")
                    return False
            except Exception as e:
                QMessageBox.critical(parent, "错误", str(e))
                return False
        size_mb = target.stat().st_size // (1024 * 1024)
        cls._models_status[model_id] = {
            "exists": True,
            "file": target.name,
            "path": str(target),
            "size_mb": size_mb,
            "scan_time": datetime.now().isoformat()
        }
        cls.save_models_config()
        logger.success(f"模型已下载: {target}")
        return True
    
    @classmethod
    def check_model_exists(cls, model_id: str) -> bool:
        """检查模型文件是否存在"""
        model_dir = cls.get_model_dir()
        
        if model_id in cls.MODELS:
            model_file = model_dir / cls.MODELS[model_id]["file"]
            return model_file.exists()
        
        if model_id.startswith("custom_"):
            status = cls._models_status.get(model_id, {})
            if status.get("path"):
                return Path(status["path"]).exists()
        
        return False
    
    @classmethod
    def get_model_status(cls, model_id: str) -> dict:
        """获取模型状态"""
        if model_id in cls._models_status:
            cached = cls._models_status[model_id]
            cached["exists"] = cls.check_model_exists(model_id)
            return cached
        
        if not cls._models_status:
            cls.scan_models()
        
        return cls._models_status.get(model_id, {
            "exists": False,
            "file": cls.MODELS.get(model_id, {}).get("file", f"{model_id}.onnx")
        })
    
    @classmethod
    def is_large_model(cls, model_id: str) -> bool:
        """判断是否是大模型"""
        info = cls.MODELS.get(model_id, {})
        return info.get("large", False)
    
    @classmethod
    def should_scale_down(cls, model_id: str) -> bool:
        """判断是否需要缩小处理"""
        if not cls.is_large_model(model_id):
            return False
        
        info = cls.MODELS.get(model_id, {})
        model_size = info.get("size_mb", 200)
        
        if HardwareInfo.has_sufficient_resources(model_size):
            return False
        
        return True
    
    @classmethod
    def load_model(cls, model_id: str):
        """加载模型"""
        global USE_REMBG, rembg_new_session
        
        if not USE_REMBG:
            logger.error("rembg 未安装，无法加载模型")
            return None
        
        with cls._lock:
            if model_id in cls._sessions:
                logger.info(f"模型 {model_id} 已在缓存中")
                return cls._sessions[model_id]
        
        exists = cls.check_model_exists(model_id)
        if not exists:
            logger.warning(f"模型文件不存在，将在首次使用时自动下载")
        
        try:
            logger.info(f"加载模型: {model_id}...")
            start = time.time()
            
            gc.collect()
            
            old_out, old_err = sys.stdout, sys.stderr
            class _LoggerStream:
                def __init__(self, level):
                    self.buf = ""
                    self.level = level
                def write(self, s):
                    self.buf += s
                    while "\n" in self.buf:
                        line, self.buf = self.buf.split("\n", 1)
                        line = line.strip()
                        if line:
                            logger.pipe(line, self.level)
                def flush(self):
                    pass
            sys.stdout = _LoggerStream("info")
            sys.stderr = _LoggerStream("warning")
            try:
                session = rembg_new_session(model_id)
            finally:
                sys.stdout, sys.stderr = old_out, old_err
            
            elapsed = time.time() - start
            logger.success(f"模型加载成功 ({elapsed:.1f}s)")
            
            with cls._lock:
                cls._sessions[model_id] = session
            
            cls._models_status[model_id] = cls._models_status.get(model_id, {})
            cls._models_status[model_id]["exists"] = True
            cls._models_status[model_id]["loaded"] = True
            cls.save_models_config()
            
            return session
            
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            traceback.print_exc()
            
            if model_id != "u2netp":
                logger.warning("尝试回退到 u2netp 轻量模型...")
                return cls.load_model("u2netp")
            
            return None
    
    @classmethod
    def get_session(cls, model_id: str):
        with cls._lock:
            return cls._sessions.get(model_id)
    
    @classmethod
    def clear_cache(cls):
        with cls._lock:
            cls._sessions.clear()
        gc.collect()
        logger.info("模型缓存已清除")

# ==================== rembg 导入（增强错误处理）====================
USE_REMBG = False
rembg_remove = None
rembg_new_session = None
REMBG_ERROR_MSG = ""

def _try_import_rembg():
    """尝试导入 rembg，返回 (success, error_message)"""
    global USE_REMBG, rembg_remove, rembg_new_session, REMBG_ERROR_MSG
    
    try:
        # 首先检查 onnxruntime
        try:
            import onnxruntime
        except ImportError:
            REMBG_ERROR_MSG = "onnxruntime 未安装"
            return False, REMBG_ERROR_MSG
        except Exception as e:
            REMBG_ERROR_MSG = f"onnxruntime 加载失败: {e}"
            return False, REMBG_ERROR_MSG
        
        # 然后导入 rembg
        try:
            from rembg import remove as _remove, new_session as _new_session
            rembg_remove = _remove
            rembg_new_session = _new_session
            USE_REMBG = True
            return True, None
        except ImportError:
            REMBG_ERROR_MSG = "rembg 模块未安装"
            return False, REMBG_ERROR_MSG
        except Exception as e:
            REMBG_ERROR_MSG = f"rembg 加载失败: {e}"
            return False, REMBG_ERROR_MSG
            
    except Exception as e:
        REMBG_ERROR_MSG = f"导入过程发生未知错误: {e}"
        return False, REMBG_ERROR_MSG

# 执行导入
_import_success, _import_msg = _try_import_rembg()
if _import_success:
    logger.success("✓ rembg 模块加载成功")
else:
    logger.error(f"✗ rembg 模块不可用: {_import_msg}")

# 执行硬件检测和模型扫描
HardwareInfo.detect()
ModelManager.scan_models()

# ==================== 激活验证模块 ====================
MAGIC_VALUE = "788990"

class LicenseManager:
    @staticmethod
    def get_license_file():
        return ConfigManager.get_license_file()
    
    @staticmethod
    def get_machine_code():
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            def get_cmd(c):
                try: 
                    return subprocess.check_output(c, startupinfo=si).decode().split('\n')[1].strip()
                except: 
                    return ""
            raw = f"{get_cmd('wmic cpu get processorid')}{get_cmd('wmic baseboard get serialnumber')}{get_cmd('wmic diskdrive where index=0 get serialnumber')}".replace(" ", "")
            if len(raw) < 5: 
                import uuid
                raw = str(uuid.getnode())
            hashed = hashlib.md5(raw.encode()).hexdigest().upper()
            return f"{hashed[0:4]}-{hashed[4:8]}-{hashed[8:12]}-{hashed[12:16]}"
        except: 
            return "ERROR-ID"

    @staticmethod
    def verify_key(machine_code, input_key):
        try:
            clean_mac = machine_code.replace("-", "").replace(" ", "")
            today_str = date.today().strftime("%Y%m%d")
            input_str = f"{clean_mac}{today_str}{MAGIC_VALUE}"
            sha = hashlib.sha256(input_str.encode()).hexdigest().upper()
            correct = "-".join([sha[i:i+5] for i in range(0, 25, 5)])
            return input_key.strip().upper() == correct
        except: 
            return False

    @staticmethod
    def check_license_file():
        license_file = LicenseManager.get_license_file()
        if not os.path.exists(license_file): 
            return False
        try:
            with open(license_file, "r") as f: 
                saved = f.read().strip()
            curr = hashlib.md5(LicenseManager.get_machine_code().encode()).hexdigest()
            return saved == curr
        except: 
            return False

    @staticmethod
    def save_license():
        license_file = LicenseManager.get_license_file()
        os.makedirs(os.path.dirname(license_file), exist_ok=True)
        with open(license_file, "w") as f:
            f.write(hashlib.md5(LicenseManager.get_machine_code().encode()).hexdigest())
# ==================== 第二部分：UI组件、颜色选择器、图像处理、Workers ====================

# ==================== 颜色选择器组件 ====================
class ColorPickerWidget(QWidget):
    """带颜色选择器的输入组件"""
    
    # 预设常用颜色
    PRESET_COLORS = [
        ("#FFFFFF", "白色"),
        ("#000000", "黑色"),
        ("#00FF00", "绿幕"),
        ("#0000FF", "蓝幕"),
        ("#FF0000", "红色"),
        ("#FFFF00", "黄色"),
        ("#00FFFF", "青色"),
        ("#FF00FF", "品红"),
        ("#808080", "灰色"),
        ("#F5F5DC", "米色"),
    ]
    
    color_changed = Signal(str)
    
    def __init__(self, default_color: str = "#FFFFFF", parent=None):
        super().__init__(parent)
        self.current_color = default_color
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # 颜色预览框
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(24, 24)
        self.color_preview.setStyleSheet(f"""
            QLabel {{
                background-color: {self.current_color};
                border: 1px solid #666;
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.color_preview)
        
        # 颜色代码输入框
        self.color_edit = QLineEdit(self.current_color)
        self.color_edit.setFixedWidth(80)
        self.color_edit.setPlaceholderText("#RRGGBB")
        self.color_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.color_edit)
        
        # 选择颜色按钮
        self.pick_btn = QPushButton("选色")
        self.pick_btn.setFixedWidth(45)
        self.pick_btn.setToolTip("打开颜色选择器")
        self.pick_btn.clicked.connect(self._open_color_dialog)
        layout.addWidget(self.pick_btn)
        
        # 预设颜色下拉框
        self.preset_combo = QComboBox()
        self.preset_combo.setFixedWidth(70)
        self.preset_combo.addItem("预设...")
        for color, name in self.PRESET_COLORS:
            self.preset_combo.addItem(name, color)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        layout.addWidget(self.preset_combo)
        
        self.setLayout(layout)

    def _on_text_changed(self, text: str):
        text = text.strip()
        if self._is_valid_color(text):
            self.current_color = text
            self._update_preview()
            self.color_changed.emit(text)

    def _is_valid_color(self, color: str) -> bool:
        if not color.startswith('#'):
            return False
        color = color[1:]
        if len(color) not in (3, 6):
            return False
        try:
            int(color, 16)
            return True
        except ValueError:
            return False

    def _update_preview(self):
        self.color_preview.setStyleSheet(f"""
            QLabel {{
                background-color: {self.current_color};
                border: 1px solid #666;
                border-radius: 3px;
            }}
        """)

    def _open_color_dialog(self):
        initial_color = QColor(self.current_color)
        color = QColorDialog.getColor(initial_color, self, "选择背景颜色")
        if color.isValid():
            hex_color = color.name().upper()
            self.current_color = hex_color
            self.color_edit.setText(hex_color)
            self._update_preview()
            self.color_changed.emit(hex_color)

    def _on_preset_selected(self, index: int):
        if index <= 0:
            return
        color = self.preset_combo.itemData(index)
        if color:
            self.current_color = color
            self.color_edit.setText(color)
            self._update_preview()
            self.color_changed.emit(color)
        self.preset_combo.setCurrentIndex(0)

    def get_color(self) -> str:
        return self.current_color

    def set_color(self, color: str):
        if self._is_valid_color(color):
            self.current_color = color
            self.color_edit.setText(color)
            self._update_preview()

class SpritePreviewDialog(QDialog):
    def __init__(self, frames, fps=12, parent=None):
        super().__init__(parent)
        self.setWindowTitle("精灵预览")
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.frames = frames
        self.idx = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._next)
        self.timer.start(int(1000/max(1,fps)))
        self._next()
    def _to_pix(self, pil):
        img = pil.convert('RGBA')
        data = img.tobytes('raw', 'RGBA')
        qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qimg)
    def _next(self):
        if not self.frames:
            return
        pix = self._to_pix(self.frames[self.idx % len(self.frames)])
        self.label.setPixmap(pix)
        self.idx += 1

class SpriteEditorDialog(QDialog):
    def __init__(self, parent=None, source_sprite_path: str = None, frames: list = None, source_frames: list = None):
        super().__init__(parent)
        self.setWindowTitle("编辑精灵图")
        self.setMinimumSize(1200, 820)
        self.frames = []
        self.index_map = []
        self.scale_percent = 100
        self.base_w, self.base_h = (128, 128)
        main_layout = QHBoxLayout()
        self.table = QTableWidget()
        self.table.setSelectionMode(QAbstractItemView.MultiSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        left_panel = self._build_slice_params_panel()
        left_panel.setMinimumWidth(300)
        main_layout.addWidget(left_panel, 0)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.table, 1)
        bottom_ctrl = self._build_output_controls()
        # 预览列数来源于主窗口设置，但输出列数保持编辑器自身默认值
        right_layout.addLayout(bottom_ctrl)
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        main_layout.addWidget(right_widget, 1)
        self.setLayout(main_layout)
        try:
            self._on_seg_mode_changed(self.seg_mode.currentIndex())
        except Exception:
            pass
        provided_frames = source_frames if source_frames is not None else frames
        if provided_frames:
            self.frames = provided_frames
            try:
                self.base_w, self.base_h = self.frames[0].size
            except:
                pass
            preview_cols = None
            try:
                if parent is not None and hasattr(parent, 'sprite_cols'):
                    preview_cols = max(1, int(parent.sprite_cols.value()))
            except Exception:
                preview_cols = None
            if preview_cols is None:
                preview_cols = 10
            self._populate(preview_cols)
            try:
                self.display_cols = preview_cols
                if hasattr(self, 'preview_cols_spin'):
                    self.preview_cols_spin.setValue(preview_cols)
                self._capture_origin_state()
            except Exception:
                pass
        elif source_sprite_path:
            self.source_img = Image.open(source_sprite_path).convert('RGBA')
            w, h = self.source_img.size
            # 安全默认：不自动猜测超大行列，初始为 1x1，并默认自动检测
            guess_rows = 1
            guess_cols = 1
            self.seg_mode.setCurrentIndex(0)
            if hasattr(self, 'src_rows_spin') and hasattr(self, 'src_cols_spin'):
                self.src_rows_spin.setValue(guess_rows)
                self.src_cols_spin.setValue(guess_cols)
                self.src_rows_spin.valueChanged.connect(lambda _: self._update_cell_size_label())
                self.src_cols_spin.valueChanged.connect(lambda _: self._update_cell_size_label())
            # 不在参数变化时自动切分，改为点击“应用分割”触发
            self.frames = [self.source_img]
            try:
                self.base_w, self.base_h = self.source_img.size
            except:
                pass
            # 输出列数保持编辑器默认 5，不从主窗口设置同步
            try:
                self._update_cell_size_label()
            except Exception:
                pass
            self._populate(1)
            try:
                self.display_cols = 1
                if hasattr(self, 'preview_cols_spin'):
                    self.preview_cols_spin.setValue(1)
                self._capture_origin_state()
            except Exception:
                pass
        self.col_spin.valueChanged.connect(lambda _: self._populate(getattr(self, 'display_cols', max(1, int(self.col_spin.value())))))
        if hasattr(self, 'preview_row_gap'):
            self.preview_row_gap.valueChanged.connect(lambda _: self._populate(getattr(self, 'display_cols', max(1, int(self.col_spin.value())))))
        self.table.itemSelectionChanged.connect(self._update_count)
        try:
            self._left_preview_update_timer()
        except Exception:
            pass
        self.select_cols.toggled.connect(lambda s: self.table.setSelectionBehavior(QAbstractItemView.SelectColumns if self.select_cols.isChecked() else QAbstractItemView.SelectItems))
        self.btn_select_all.clicked.connect(self._select_all)
        self.btn_clear.clicked.connect(self._clear_selection)
        self.scale_slider.valueChanged.connect(self._on_scale_changed)
        if hasattr(self, 'preview_cols_spin'):
            self.preview_cols_spin.valueChanged.connect(lambda v: [setattr(self, 'display_cols', max(1, int(v))), self._populate(max(1, int(v)))])
        self._update_count()

    def _pil_to_pixmap(self, pil, idx):
        img = pil.convert('RGBA')
        data = img.tobytes('raw', 'RGBA')
        qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
        pix = QPixmap.fromImage(qimg)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(0, 0, 22, 18, QBrush(QColor(0, 0, 0, 140)))
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Microsoft YaHei UI", 9, QFont.Bold))
        painter.drawText(4, 14, str(idx+1))
        painter.end()
        return pix

    def _populate(self, cols):
        total = len(self.frames)
        selected_before = set(it.data(Qt.UserRole) for it in self.table.selectedItems())
        use_grouping = hasattr(self, 'row_counts') and isinstance(getattr(self, 'row_counts'), list) and sum(getattr(self, 'row_counts')) == total and len(getattr(self, 'row_counts')) > 0
        if use_grouping:
            rows = len(self.row_counts)
        else:
            rows = math.ceil(total / max(1, cols))
        self.table.clear()
        self.table.setRowCount(rows)
        self.table.setColumnCount(cols)
        self.table.horizontalHeader().setVisible(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.verticalHeader().setDefaultSectionSize(0)
        self.index_map = []
        tw = max(16, int(self.base_w * self.scale_percent / 100))
        th = max(16, int(self.base_h * self.scale_percent / 100))
        self.table.setIconSize(QSize(tw, th))
        for c in range(cols):
            self.table.setColumnWidth(c, tw + 16)
        if use_grouping:
            i = 0
            for r in range(rows):
                cnt = max(0, int(self.row_counts[r]))
                offset = max(0, (cols - cnt) // 2)
                for j in range(cnt):
                    if i >= total:
                        break
                    cc = offset + j
                    item = QTableWidgetItem()
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    item.setData(Qt.UserRole, i)
                    pix = self._pil_to_pixmap(self.frames[i], i).scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    item.setIcon(QIcon(pix))
                    self.table.setItem(r, cc, item)
                    self.index_map.append((r, cc, i))
                    i += 1
        else:
            for i in range(total):
                r = i // cols
                c = i % cols
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                item.setData(Qt.UserRole, i)
                pix = self._pil_to_pixmap(self.frames[i], i).scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                item.setIcon(QIcon(pix))
                self.table.setItem(r, c, item)
                self.index_map.append((r, c, i))
        gap = 0
        try:
            gap = int(self.preview_row_gap.value()) if hasattr(self, 'preview_row_gap') else 0
        except Exception:
            gap = 0
        for r in range(rows):
            self.table.setRowHeight(r, th + 16 + max(0, gap))
        self.table.setHorizontalHeaderLabels([str(i+1) for i in range(cols)])
        if selected_before:
            for r, c, idx in self.index_map:
                if idx in selected_before:
                    it = self.table.item(r, c)
                    if it:
                        it.setSelected(True)
        self.count_label.setText(f"{len(self.table.selectedItems())}/{total}")

    def _on_scale_changed(self, val):
        self.scale_percent = int(val)
        self.scale_label.setText(f"{self.scale_percent}%")
        self._populate(getattr(self, 'display_cols', max(1, int(self.col_spin.value()))))

    def _update_count(self):
        items = self.table.selectedItems()
        total = len(self.frames)
        self.count_label.setText(f"{len(items)}/{total}")

    def _select_all(self):
        self.table.selectAll()

    def _clear_selection(self):
        self.table.clearSelection()
        self._update_count()

    def get_selected_frames(self):
        items = self.table.selectedItems()
        idxs = sorted([it.data(Qt.UserRole) for it in items])
        return [self.frames[i] for i in idxs]

    def get_output_cols(self):
        return max(1, int(self.col_spin.value()))

    def _build_slice_params_panel(self):
        panel = QGroupBox("分割设置")
        panel.setFixedWidth(280)
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        mode_group = QGroupBox("分割方式")
        mode_layout = QVBoxLayout()
        mode_layout.setContentsMargins(4, 4, 4, 4)
        mode_layout.setSpacing(4)
        mode_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        mode_group.setMaximumHeight(60)
        self.seg_mode = QComboBox()
        self.seg_mode.addItems(["网格 (Grid)", "固定尺寸 (Fixed Size)", "自动检测 (Auto)", "配置文件 (Atlas)"])
        self.seg_mode.currentIndexChanged.connect(self._on_seg_mode_changed)
        mode_layout.addWidget(self.seg_mode)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        self.params_stack = QStackedWidget()
        self.params_stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.params_stack.addWidget(self._build_grid_params())
        self.params_stack.addWidget(self._build_fixed_size_params())
        self.params_stack.addWidget(self._build_auto_detect_params())
        self.params_stack.addWidget(self._build_atlas_params())
        layout.addWidget(self.params_stack)
        btn_row = QHBoxLayout()
        apply_btn = QPushButton("应用分割")
        apply_btn.clicked.connect(self._slice_source_sprite)
        btn_row.addWidget(apply_btn)
        self.undo_btn = QPushButton("撤销分割")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._undo_slice)
        btn_row.addWidget(self.undo_btn)
        layout.addLayout(btn_row)
        preview_group = QGroupBox("选中帧预览")
        pg_layout = QVBoxLayout()
        pg_layout.setContentsMargins(4, 4, 4, 4)
        pg_layout.setSpacing(4)
        self.left_preview_label = QLabel()
        self.left_preview_label.setAlignment(Qt.AlignCenter)
        self.left_preview_label.setMinimumHeight(280)
        pg_layout.addWidget(self.left_preview_label)
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("速度 (fps):"))
        self.left_preview_fps = QSpinBox()
        self.left_preview_fps.setRange(1, 60)
        self.left_preview_fps.setValue(12)
        self.left_preview_fps.valueChanged.connect(self._left_preview_update_timer)
        ctrl_row.addWidget(self.left_preview_fps)
        ctrl_row.addStretch()
        pg_layout.addLayout(ctrl_row)
        preview_group.setLayout(pg_layout)
        layout.addWidget(preview_group)
        ok_cancel = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        gif_btn = QPushButton("生成透明GIF")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        ok_cancel.addStretch()
        gif_btn.clicked.connect(self._on_generate_gif)
        ok_cancel.addWidget(gif_btn)
        ok_cancel.addWidget(ok_btn)
        ok_cancel.addWidget(cancel_btn)
        layout.addLayout(ok_cancel)
        panel.setLayout(layout)
        return panel

    def _on_seg_mode_changed(self, idx):
        self.params_stack.setCurrentIndex(idx)
        try:
            w = self.params_stack.currentWidget()
            if w:
                h = w.sizeHint().height()
                self.params_stack.setMinimumHeight(h)
                self.params_stack.setMaximumHeight(h)
        except Exception:
            pass

    def _build_output_controls(self):
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("输出列数:"))
        self.col_spin = QSpinBox(); self.col_spin.setRange(1, 1000); self.col_spin.setValue(5)
        ctrl.addWidget(self.col_spin)
        ctrl.addWidget(QLabel("预览列数:"))
        self.preview_cols_spin = QSpinBox(); self.preview_cols_spin.setRange(1, 1000); self.preview_cols_spin.setValue(getattr(self, 'display_cols', 10))
        ctrl.addWidget(self.preview_cols_spin)
        self.select_cols = QCheckBox("按列选择")
        ctrl.addWidget(self.select_cols)
        ctrl.addWidget(QLabel("行间距:"))
        self.preview_row_gap = QSpinBox()
        self.preview_row_gap.setRange(0, 64)
        self.preview_row_gap.setValue(0)
        ctrl.addWidget(self.preview_row_gap)
        ctrl.addWidget(QLabel("缩放:"))
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(10, 200)
        self.scale_slider.setValue(self.scale_percent)
        self.scale_slider.setTickInterval(5)
        self.scale_slider.setSingleStep(5)
        ctrl.addWidget(self.scale_slider)
        self.scale_label = QLabel(f"{self.scale_percent}%")
        ctrl.addWidget(self.scale_label)
        self.btn_select_all = QPushButton("全选")
        self.btn_clear = QPushButton("全不选")
        ctrl.addWidget(self.btn_select_all)
        ctrl.addWidget(self.btn_clear)
        self.count_label = QLabel("0/")
        ctrl.addWidget(self.count_label)
        ctrl.addStretch()
        return ctrl

    def _pil_to_pixmap_raw(self, pil):
        img = pil.convert('RGBA')
        data = img.tobytes('raw', 'RGBA')
        qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qimg)

    def _left_preview_update_timer(self):
        try:
            fps = max(1, int(self.left_preview_fps.value()))
            if not hasattr(self, 'left_preview_timer'):
                self.left_preview_timer = QTimer(self)
                self.left_preview_timer.timeout.connect(self._left_preview_next)
            self.left_preview_timer.start(int(1000/max(1,fps)))
        except Exception:
            pass

    def _left_preview_next(self):
        try:
            frames = self._get_selected_or_all_frames()
            if not frames:
                self.left_preview_label.clear()
                return
            if not hasattr(self, 'left_preview_idx'):
                self.left_preview_idx = 0
            pix = self._pil_to_pixmap_raw(frames[self.left_preview_idx % len(frames)])
            sw = self.left_preview_label.width() if self.left_preview_label.width() > 0 else pix.width()
            sh = self.left_preview_label.height() if self.left_preview_label.height() > 0 else pix.height()
            pix = pix.scaled(sw, sh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.left_preview_label.setPixmap(pix)
            self.left_preview_idx += 1
        except Exception:
            pass

    def _get_selected_or_all_frames(self):
        try:
            items = self.table.selectedItems()
            if items:
                idxs = sorted([it.data(Qt.UserRole) for it in items])
                return [self.frames[i] for i in idxs]
            return list(self.frames)
        except Exception:
            return []

    def _on_generate_gif(self):
        try:
            frames = self._get_selected_or_all_frames()
            if not frames:
                QMessageBox.warning(self, "提示", "没有可用帧")
                return
            fps = max(1, int(self.left_preview_fps.value())) if hasattr(self, 'left_preview_fps') else 12
            dur = 1.0 / float(max(1, fps))
            default_dir = os.path.dirname(self.source_sprite_path) if getattr(self, 'source_sprite_path', None) else str(Path.cwd())
            default_name = (Path(self.source_sprite_path).stem + "_prev.gif") if getattr(self, 'source_sprite_path', None) else "preview.gif"
            save_path, _ = QFileDialog.getSaveFileName(self, "保存透明GIF", str(Path(default_dir) / default_name), "GIF (*.gif)")
            if not save_path:
                return
            imgs = []
            for im in frames:
                if im.mode != 'RGBA':
                    im = im.convert('RGBA')
                imgs.append(np.array(im))
            imageio.mimsave(save_path, imgs, format='GIF', duration=dur, loop=0)
            QMessageBox.information(self, "完成", f"GIF 已保存:\n{save_path}")
        except Exception as e:
            try:
                QMessageBox.critical(self, "错误", str(e))
            except:
                pass
    def _build_grid_params(self):
        w = QWidget()
        fl = QFormLayout()
        fl.setContentsMargins(4, 2, 4, 2)
        fl.setSpacing(2)
        fl.setRowWrapPolicy(QFormLayout.DontWrapRows)
        self.src_cols_spin = QSpinBox(); self.src_cols_spin.setRange(1, 100); self.src_cols_spin.setValue(1)
        self.src_rows_spin = QSpinBox(); self.src_rows_spin.setRange(1, 100); self.src_rows_spin.setValue(1)
        fl.addRow("列数:", self.src_cols_spin)
        fl.addRow("行数:", self.src_rows_spin)
        self.cell_size_label = QLabel("单帧尺寸: -- x --")
        self.cell_size_label.setWordWrap(False)
        fl.addRow(self.cell_size_label)
        self.src_cols_spin.valueChanged.connect(lambda _: self._update_cell_size_label())
        self.src_rows_spin.valueChanged.connect(lambda _: self._update_cell_size_label())
        w.setLayout(fl)
        return w
    def _build_fixed_size_params(self):
        w = QWidget()
        fl = QFormLayout()
        self.fix_w_spin = QSpinBox(); self.fix_w_spin.setRange(1, 4096); self.fix_w_spin.setValue(64)
        self.fix_h_spin = QSpinBox(); self.fix_h_spin.setRange(1, 4096); self.fix_h_spin.setValue(64)
        self.fix_pad_spin = QSpinBox(); self.fix_pad_spin.setRange(0, 256); self.fix_pad_spin.setValue(0)
        self.fix_margin_spin = QSpinBox(); self.fix_margin_spin.setRange(0, 256); self.fix_margin_spin.setValue(0)
        fl.addRow("帧宽度:", self.fix_w_spin)
        fl.addRow("帧高度:", self.fix_h_spin)
        fl.addRow("帧间距:", self.fix_pad_spin)
        fl.addRow("边缘留白:", self.fix_margin_spin)
        w.setLayout(fl)
        return w
    def _build_auto_detect_params(self):
        w = QWidget()
        fl = QFormLayout()
        self.alpha_thr_spin = QSpinBox(); self.alpha_thr_spin.setRange(0, 255); self.alpha_thr_spin.setValue(10)
        self.min_size_spin = QSpinBox(); self.min_size_spin.setRange(1, 100000); self.min_size_spin.setValue(64)
        fl.addRow("透明度阈值:", self.alpha_thr_spin)
        fl.addRow("最小面积:", self.min_size_spin)
        hint = QLabel("自动检测连通的不透明区域")
        hint.setStyleSheet("color: #666; font-size: 9pt;")
        hint.setWordWrap(True)
        fl.addRow(hint)
        w.setLayout(fl)
        return w
    def _build_atlas_params(self):
        w = QWidget()
        vl = QVBoxLayout()
        self.atlas_edit = QLineEdit(); self.atlas_edit.setPlaceholderText("选择 JSON 配置文件...")
        vl.addWidget(self.atlas_edit)
        self.atlas_btn = QPushButton("浏览...")
        self.atlas_btn.clicked.connect(self._select_atlas_file)
        vl.addWidget(self.atlas_btn)
        hint = QLabel("支持 TexturePacker 导出的 JSON 格式")
        hint.setStyleSheet("color: #666; font-size: 9pt;")
        hint.setWordWrap(True)
        vl.addWidget(hint)
        vl.addStretch()
        w.setLayout(vl)
        return w
    def _update_cell_size_label(self):
        try:
            if hasattr(self, 'source_img'):
                w, h = self.source_img.size
                cols = max(1, int(self.src_cols_spin.value())) if hasattr(self, 'src_cols_spin') else 1
                rows = max(1, int(self.src_rows_spin.value())) if hasattr(self, 'src_rows_spin') else 1
                cw0 = w // max(1, cols)
                ch0 = h // max(1, rows)
                rem_w = w % max(1, cols)
                rem_h = h % max(1, rows)
                if rem_w == 0 and rem_h == 0:
                    self.cell_size_label.setStyleSheet("")
                    self.cell_size_label.setText(f"单帧尺寸: {cw0} x {ch0}")
                else:
                    self.cell_size_label.setStyleSheet("color:#666;")
                    self.cell_size_label.setText(f"单帧尺寸约: {cw0}~{cw0+1} x {ch0}~{ch0+1}")
            else:
                self.cell_size_label.setText("单帧尺寸: -- x --")
        except Exception:
            pass
    def _select_atlas_file(self):
        try:
            p, _ = QFileDialog.getOpenFileName(self, "选择配置文件", "", "JSON (*.json)")
            if p:
                self.atlas_edit.setText(p)
                self._slice_source_sprite()
        except Exception:
            pass
    def _slice_source_sprite(self):
        try:
            if not hasattr(self, 'source_img'):
                return
            text = self.seg_mode.currentText() if hasattr(self, 'seg_mode') else "网格 (Grid)"
            w, h = self.source_img.size
            self.frames = []
            if text.startswith("网格"):
                rows = max(1, int(self.src_rows_spin.value())) if self.src_rows_spin else 1
                cols = max(1, int(self.src_cols_spin.value())) if self.src_cols_spin else 1
                rows = min(rows, 100)
                cols = min(cols, 100)
                def make_cuts(total_size, parts):
                    base = total_size // parts
                    rem = total_size % parts
                    widths = [base] * parts
                    if rem > 0:
                        order = []
                        if parts % 2 == 1:
                            mid = parts // 2
                            order = [mid]
                            k = 1
                            while len(order) < parts:
                                if mid - k >= 0:
                                    order.append(mid - k)
                                if mid + k < parts:
                                    order.append(mid + k)
                                k += 1
                        else:
                            lm = parts // 2 - 1
                            rm = parts // 2
                            order = [lm, rm]
                            k = 1
                            while len(order) < parts:
                                if lm - k >= 0:
                                    order.append(lm - k)
                                if rm + k < parts:
                                    order.append(rm + k)
                                k += 1
                        for i in range(rem):
                            widths[order[i]] += 1
                    cuts = [0]
                    acc = 0
                    for wi in widths:
                        acc += wi
                        cuts.append(acc)
                    return cuts
                xcuts = make_cuts(w, cols)
                ycuts = make_cuts(h, rows)
                total = rows * cols
                for idx in range(total):
                    c = idx % cols
                    r = idx // cols
                    box = (xcuts[c], ycuts[r], xcuts[c+1], ycuts[r+1])
                    self.frames.append(self.source_img.crop(box))
                self.display_cols = cols
                self.row_counts = [cols] * rows
                if hasattr(self, 'undo_btn'):
                    self.undo_btn.setEnabled(True)
                if hasattr(self, 'preview_cols_spin'):
                    self.preview_cols_spin.setValue(self.display_cols)
            elif text.startswith("固定尺寸"):
                mw = max(0, int(self.fix_margin_spin.value()))
                mh = mw
                pw = max(0, int(self.fix_pad_spin.value()))
                fw = max(1, int(self.fix_w_spin.value()))
                fh = max(1, int(self.fix_h_spin.value()))
                x_start = mw; x_end = w - mw
                y_start = mh; y_end = h - mh
                avail_w = max(0, x_end - x_start)
                avail_h = max(0, y_end - y_start)
                cols = max(1, (avail_w + pw) // (fw + pw))
                rows = max(1, (avail_h + pw) // (fh + pw))
                extra_w = avail_w - (cols * fw + max(0, cols-1) * pw)
                extra_h = avail_h - (rows * fh + max(0, rows-1) * pw)
                def make_cuts_fixed(avail, parts, size, gap, extra):
                    if parts <= 0:
                        return [0]
                    gaps_count = max(0, parts-1)
                    gaps = [gap] * gaps_count
                    if extra > 0 and gaps_count > 0:
                        order = []
                        if parts % 2 == 1:
                            mid = parts // 2
                            k = 1
                            # 将额外像素优先分配到中间相邻的间隙：mid-1 与 mid
                            if mid-1 >= 0:
                                order.append(mid-1)
                            if mid < gaps_count:
                                order.append(mid)
                            while len(order) < gaps_count:
                                if mid-1-k >= 0:
                                    order.append(mid-1-k)
                                if mid+k < gaps_count:
                                    order.append(mid+k)
                                k += 1
                        else:
                            lm = parts // 2 - 1
                            rm = parts // 2 - 0
                            order = [lm, rm]
                            k = 1
                            while len(order) < gaps_count:
                                if lm- k >= 0:
                                    order.append(lm- k)
                                if rm+ k < gaps_count:
                                    order.append(rm+ k)
                                k += 1
                        for i in range(extra):
                            gaps[order[i % gaps_count]] += 1
                    cuts = [0]
                    acc = 0
                    for i in range(parts):
                        acc += size
                        cuts.append(acc)
                        if i < gaps_count:
                            acc += gaps[i]
                    return cuts
                xcuts_rel = make_cuts_fixed(avail_w, cols, fw, pw, max(0, extra_w))
                ycuts_rel = make_cuts_fixed(avail_h, rows, fh, pw, max(0, extra_h))
                xcuts = [x_start + v for v in xcuts_rel]
                ycuts = [y_start + v for v in ycuts_rel]
                for r in range(rows):
                    for c in range(cols):
                        box = (xcuts[c], ycuts[r], xcuts[c+1], ycuts[r+1])
                        self.frames.append(self.source_img.crop(box))
                self.display_cols = max(1, cols)
                self.row_counts = [cols] * rows
                if hasattr(self, 'undo_btn'):
                    self.undo_btn.setEnabled(True)
                if hasattr(self, 'preview_cols_spin'):
                    self.preview_cols_spin.setValue(self.display_cols)
            else:
                if text.startswith("自动检测"):
                    thr = max(0, min(255, int(self.alpha_thr_spin.value())))
                    min_area = max(1, int(self.min_size_spin.value()))
                    px = self.source_img.load()
                    visited = [[False]*w for _ in range(h)]
                    dirs = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]
                    boxes = []
                    for yy in range(h):
                        for xx in range(w):
                            if visited[yy][xx]:
                                continue
                            if px[xx, yy][3] <= thr:
                                visited[yy][xx] = True
                                continue
                            stack = [(xx, yy)]
                            minx = xx; miny = yy; maxx = xx; maxy = yy; area = 0
                            while stack:
                                x0, y0 = stack.pop()
                                if x0 < 0 or x0 >= w or y0 < 0 or y0 >= h:
                                    continue
                                if visited[y0][x0]:
                                    continue
                                visited[y0][x0] = True
                                if px[x0, y0][3] <= thr:
                                    continue
                                area += 1
                                if x0 < minx: minx = x0
                                if x0 > maxx: maxx = x0
                                if y0 < miny: miny = y0
                                if y0 > maxy: maxy = y0
                                for dx, dy in dirs:
                                    nx = x0 + dx; ny = y0 + dy
                                    if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                                        stack.append((nx, ny))
                            if area >= min_area:
                                boxes.append((minx, miny, maxx+1, maxy+1))
                    boxes.sort(key=lambda b: (b[1], b[0]))
                    if boxes:
                        avg_h = int(sum(b[3]-b[1] for b in boxes) / max(1, len(boxes)))
                        thresh = max(8, avg_h // 2)
                    else:
                        thresh = 0
                    groups = []
                    current = []
                    last_y = None
                    for b in boxes:
                        y0 = b[1]
                        if last_y is None or abs(y0 - last_y) <= thresh:
                            current.append(b)
                        else:
                            groups.append(current)
                            current = [b]
                        last_y = y0
                    if current:
                        groups.append(current)
                    self.frames = []
                    for g in groups:
                        for b in g:
                            self.frames.append(self.source_img.crop(b))
                    self.display_cols = max(len(g) for g in groups) if groups else max(1, int(self.col_spin.value()))
                    self.row_counts = [len(g) for g in groups]
                    if hasattr(self, 'undo_btn'):
                        self.undo_btn.setEnabled(True)
                    if hasattr(self, 'preview_cols_spin'):
                        self.preview_cols_spin.setValue(self.display_cols)
                else:
                    p = self.atlas_edit.text() if hasattr(self, 'atlas_edit') else ''
                    if p and os.path.exists(p):
                        try:
                            with open(p, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            infos = []
                            if isinstance(data.get('frames'), dict):
                                for name, fr in data['frames'].items():
                                    if 'frame' in fr:
                                        x = int(fr['frame']['x']); y = int(fr['frame']['y']);
                                        fw = int(fr['frame']['w']); fh = int(fr['frame']['h'])
                                        rot = bool(fr.get('rotated', False))
                                    else:
                                        x = int(fr.get('x', 0)); y = int(fr.get('y', 0));
                                        fw = int(fr.get('w', fr.get('width', 0))); fh = int(fr.get('h', fr.get('height', 0)))
                                        rot = bool(fr.get('rotated', False))
                                    infos.append((x, y, fw, fh, rot))
                            elif isinstance(data.get('frames'), list):
                                for fr in data['frames']:
                                    frame_obj = fr.get('frame', {})
                                    x = int(frame_obj.get('x', fr.get('x', 0)))
                                    y = int(frame_obj.get('y', fr.get('y', 0)))
                                    fw = int(frame_obj.get('w', fr.get('w', fr.get('width', 0))))
                                    fh = int(frame_obj.get('h', fr.get('h', fr.get('height', 0))))
                                    rot = bool(fr.get('rotated', False))
                                    infos.append((x, y, fw, fh, rot))
                            infos.sort(key=lambda t: (t[1], t[0]))
                            frames = []
                            for x, y, fw, fh, rot in infos:
                                crop = self.source_img.crop((x, y, x+fw, y+fh))
                                if rot:
                                    crop = crop.rotate(-90, expand=True)
                                frames.append(crop)
                            self.frames = frames
                            if infos:
                                avg_h = int(sum(hh for _,_,_,hh,_ in infos) / max(1, len(infos)))
                                thresh = max(8, avg_h // 2)
                                groups = []
                                current = []
                                last_y = None
                                for x,y,fw,fh,rot in infos:
                                    if last_y is None or abs(y - last_y) <= thresh:
                                        current.append((x,y,fw,fh,rot))
                                    else:
                                        groups.append(current)
                                        current = [(x,y,fw,fh,rot)]
                                    last_y = y
                                if current:
                                    groups.append(current)
                                self.display_cols = max(len(g) for g in groups) if groups else max(1, int(self.col_spin.value()))
                                self.row_counts = [len(g) for g in groups]
                                if hasattr(self, 'undo_btn'):
                                    self.undo_btn.setEnabled(True)
                                if hasattr(self, 'preview_cols_spin'):
                                    self.preview_cols_spin.setValue(self.display_cols)
                        except Exception:
                            pass
            try:
                self.base_w, self.base_h = self.frames[0].size
            except:
                pass
            self._populate(getattr(self, 'display_cols', max(1, int(self.col_spin.value()))))
        except Exception:
            pass

    def _capture_origin_state(self):
        try:
            self._origin_state = {
                'frames': [self.source_img] if hasattr(self, 'source_img') else (list(self.frames) if hasattr(self, 'frames') else []),
                'display_cols': 1,
                'row_counts': [1],
                'base_w': getattr(self, 'base_w', None),
                'base_h': getattr(self, 'base_h', None)
            }
            if hasattr(self, 'undo_btn'):
                self.undo_btn.setEnabled(False)
        except Exception:
            pass

    def _undo_slice(self):
        try:
            if hasattr(self, '_origin_state'):
                self.frames = list(self._origin_state.get('frames', []))
                self.display_cols = self._origin_state.get('display_cols', 1)
                self.row_counts = self._origin_state.get('row_counts', [1])
                self.base_w = self._origin_state.get('base_w', self.base_w)
                self.base_h = self._origin_state.get('base_h', self.base_h)
                self._populate(getattr(self, 'display_cols', 1))
                if hasattr(self, 'undo_btn'):
                    self.undo_btn.setEnabled(False)
        except Exception:
            pass

# ==================== 自定义UI组件 ====================
class FileDropLineEdit(QLineEdit):
    def __init__(self, parent=None, placeholder="可以直接拖入文件..."):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText(placeholder)
    
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        try:
            path = e.mimeData().urls()[0].toLocalFile()
            self.setText(path)
            self.editingFinished.emit()
        except:
            pass

class LogWidget(QPlainTextEdit):
    """系统日志显示组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(1000)
        self.setFont(QFont("Consolas", 9))
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
        """)
        logger.log_signal.connect(self.append_log)
    
    def append_log(self, message: str, level: str):
        colors = {
            "info": "#d4d4d4",
            "warning": "#dcdcaa",
            "error": "#f14c4c",
            "success": "#4ec9b0"
        }
        color = colors.get(level, "#d4d4d4")
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        self.appendHtml(f'<span style="color: {color};">{message}</span>')
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

class ModelSelector(QComboBox):
    """模型选择器：带状态指示"""
    
    model_changed = Signal(str, dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.refresh_models()
        self.currentIndexChanged.connect(self._on_selection_changed)
    
    def refresh_models(self):
        """刷新模型列表"""
        blocker = QSignalBlocker(self)
        self.clear()
        ModelManager.scan_models()
        for model_id, info in ModelManager.MODELS.items():
            exists = ModelManager.check_model_exists(model_id)
            loaded = model_id in ModelManager._sessions
            status_icon = "★" if loaded else ("✓" if exists else "○")
            large_mark = "🔴" if info.get("large") else ""
            quality_stars = "★" * info.get("quality", 3)
            display_text = f"{status_icon} {large_mark}{info['name']} [{quality_stars}]"
            self.addItem(display_text, model_id)
        for model_id, status in ModelManager._models_status.items():
            if status.get("custom"):
                display_text = f"✓ [自定义] {status['file']}"
                self.addItem(display_text, model_id)
        default_model = ConfigManager.get("default_model", "isnet-general-use")
        for i in range(self.count()):
            if self.itemData(i) == default_model:
                self.setCurrentIndex(i)
                break
    
    def _on_selection_changed(self, index):
        # 安全检查：如果 loader 存在但已停止，强制清除
        if getattr(self, '_loader', None) and not self._loader.isRunning():
            self._loader = None

        model_id = self.currentData()
        if model_id:
            exists = ModelManager.check_model_exists(model_id)
            info = ModelManager.MODELS.get(model_id, {})
            
            status = {
                "exists": exists,
                "info": info,
                "large": info.get("large", False)
            }
            self.model_changed.emit(model_id, status)
            
            if exists:
                logger.info(f"已选择模型: {info.get('name', model_id)}")
            else:
                if getattr(self, '_loader', None) and self._loader.isRunning():
                    logger.info("正在下载/加载模型，请稍候...")
                    # 恢复之前的选择，或者保持当前显示但状态为下载中
                    # 这里为了简单，我们暂不自动回退，因为用户可能就是想下载
                    return
                logger.info("模型缺失，开始自动下载并加载...")
                self.setEnabled(False)
                self._loader = ModelLoadWorker(model_id)
                def _on_done(s, mid):
                    logger.success("模型下载并加载完成")
                    self.setEnabled(True)
                    self._loader = None # 清除 loader 引用
                    # 只更新状态，不刷新列表，避免触发递归
                    ModelManager.scan_models()
                    # 使用 blockSignals 阻止信号触发
                    self.blockSignals(True)
                    current_idx = self.currentIndex()
                    self.refresh_models()
                    self.setCurrentIndex(current_idx)
                    self.blockSignals(False)
                def _on_err(e):
                    logger.error(f"模型加载失败: {e}")
                    self.setEnabled(True)
                    self._loader = None # 清除 loader 引用，允许后续操作
                    # 可以在这里重置选择到默认模型，或者保持当前选择但标记为无效
                self._loader.finished.connect(_on_done)
                self._loader.error.connect(_on_err)
                self._loader.start()
            
            if info.get("large"):
                if HardwareInfo.has_sufficient_resources(info.get("size_mb", 900)):
                    logger.info("资源充足，将使用原始分辨率处理")
                else:
                    logger.info("大模型将使用缩放处理以节省内存")
    
    def get_current_model(self) -> str:
        return self.currentData() or "isnet-general-use"

# ==================== 激活对话框 ====================
class ActivationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("软件激活验证")
        self.setFixedSize(500, 480) # 宽减100(600->500), 高减50(530->480)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        self.activated = False
        self.trial_mode = False
        self.machine_code = LicenseManager.get_machine_code()
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("别快视频精灵图 v7.6 极速专业版")
        title.setFont(QFont("Microsoft YaHei UI", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #2c3e50;")
        main_layout.addWidget(title)

        subtitle = QLabel("请完成激活以使用完整功能")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #7f8c8d; font-size: 11pt;")
        main_layout.addWidget(subtitle)
        
        info_group = QGroupBox("第一步：获取机器码")
        info_layout = QVBoxLayout()
        code_layout = QHBoxLayout()
        self.mac_edit = QLineEdit()
        self.mac_edit.setText(self.machine_code)
        self.mac_edit.setReadOnly(True)
        self.mac_edit.setAlignment(Qt.AlignCenter)
        self.mac_edit.setFont(QFont("Consolas", 12, QFont.Bold))
        self.mac_edit.setFixedHeight(40)
        
        copy_btn = QPushButton("复制")
        copy_btn.setFixedSize(77, 40) # 宽减3(80->77)
        copy_btn.clicked.connect(self.copy_machine_code)
        
        code_layout.addWidget(self.mac_edit)
        code_layout.addWidget(copy_btn)
        info_layout.addLayout(code_layout)
        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)
        
        input_group = QGroupBox("第二步：输入激活密钥")
        input_layout = QVBoxLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setAlignment(Qt.AlignCenter)
        self.key_edit.setFont(QFont("Consolas", 12))
        self.key_edit.setPlaceholderText("在此处粘贴激活密钥")
        self.key_edit.setFixedHeight(45)
        input_layout.addWidget(self.key_edit)
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)
        
        btn_layout = QHBoxLayout()
        activate_btn = QPushButton("立即激活")
        activate_btn.setFixedHeight(50)
        activate_btn.clicked.connect(self.activate)
        
        trial_btn = QPushButton("试用 (15分钟)")
        trial_btn.setFixedHeight(50)
        trial_btn.clicked.connect(self.start_trial)
        
        # 调整边距以间接减少按钮宽度，或直接设置
        # 由于使用了 layout addWidget(..., stretch)，按钮宽度是自适应的。
        # 用户要求"窗口中的控件和按钮的宽都减小三"。
        # 窗口变窄了100，内部控件如果随布局缩放，自然会变窄。
        # 如果有固定宽度的控件（如 copy_btn），需要手动减小。
        # 其他自适应控件会随窗口变窄而变窄，无需额外操作。
        
        btn_layout.addWidget(trial_btn, 1)
        btn_layout.addWidget(activate_btn, 2)
        main_layout.addLayout(btn_layout)
        
        contact = QLabel("联系开发者获取密钥: u788990@163.com")
        contact.setAlignment(Qt.AlignCenter)
        contact.setStyleSheet("color: #95a5a6; font-size: 9pt;")
        main_layout.addWidget(contact)
        
        self.setLayout(main_layout)

    def copy_machine_code(self):
        QApplication.clipboard().setText(self.machine_code)
        QMessageBox.information(self, "复制成功", "机器码已复制到剪贴板！")
    
    def activate(self):
        key = self.key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "提示", "请输入激活密钥！")
            return
        if LicenseManager.verify_key(self.machine_code, key):
            LicenseManager.save_license()
            self.activated = True
            QMessageBox.information(self, "激活成功", "软件已永久激活！")
            self.accept()
        else:
            QMessageBox.critical(self, "激活失败", "激活密钥无效！")
    
    def start_trial(self):
        reply = QMessageBox.question(self, "确认试用", "每次启动仅限使用 15 分钟，确定要继续吗？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.trial_mode = True
            self.accept()

# ==================== 依赖检测对话框 ====================
class DependencyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("依赖检测")
        self.setFixedSize(600, 500)
        
        layout = QVBoxLayout()
        
        title = QLabel("依赖库检测结果")
        title.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        layout.addWidget(title)
        
        list_widget = QListWidget()
        list_widget.setFont(QFont("Consolas", 10))
        
        for module, (status, desc) in DependencyChecker.results.items():
            icon = "✓" if status == "ok" else "✗"
            color = "green" if status == "ok" else "red"
            item = QListWidgetItem(f"{icon} {module}: {desc}")
            item.setForeground(QColor(color))
            list_widget.addItem(item)
        
        layout.addWidget(list_widget)
        
        if DependencyChecker.missing_required or DependencyChecker.missing_optional:
            cmd_group = QGroupBox("安装命令")
            cmd_layout = QVBoxLayout()
            
            full_cmd_edit = QLineEdit(DependencyChecker.get_full_install_command())
            full_cmd_edit.setReadOnly(True)
            cmd_layout.addWidget(full_cmd_edit)
            
            copy_btn = QPushButton("复制安装命令")
            copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(DependencyChecker.get_full_install_command()))
            cmd_layout.addWidget(copy_btn)
            
            cmd_group.setLayout(cmd_layout)
            layout.addWidget(cmd_group)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)

# ==================== 核心图像处理函数 ====================
def play_completion_sound():
    if HAS_WINSOUND:
        try: 
            winsound.MessageBeep(winsound.MB_OK)
        except: 
            pass

def smart_resize_for_model(pil_img: Image.Image, model_id: str) -> tuple:
    """智能调整图片大小"""
    original_size = pil_img.size
    
    if not ModelManager.should_scale_down(model_id):
        return pil_img, original_size, False
    
    info = ModelManager.MODELS.get(model_id, {})
    
    available_mb = HardwareInfo.available_memory_mb
    if available_mb < 2048:
        max_res = 512
    elif available_mb < 4096:
        max_res = 768
    else:
        max_res = 1024
    
    w, h = original_size
    if max(w, h) <= max_res:
        return pil_img, original_size, False
    
    scale = max_res / max(w, h)
    new_w = int(w * scale) // 2 * 2
    new_h = int(h * scale) // 2 * 2
    
    logger.info(f"内存优化缩放: {original_size} -> ({new_w}, {new_h})")
    resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return resized, original_size, True

def remove_bg_with_session_smart(pil_img: Image.Image, session, model_id: str) -> Image.Image:
    """智能背景移除"""
    if not USE_REMBG or not rembg_remove or not session:
        return pil_img.convert("RGBA")
    
    original_size = pil_img.size
    
    try:
        resized_img, orig_size, was_resized = smart_resize_for_model(pil_img, model_id)
        result = rembg_remove(resized_img, session=session)
        
        if was_resized and result.mode == 'RGBA':
            result = result.resize(orig_size, Image.Resampling.LANCZOS)
            original_rgba = pil_img.convert('RGBA')
            r, g, b, _ = original_rgba.split()
            _, _, _, a = result.split()
            result = Image.merge('RGBA', (r, g, b, a))
        
        return result
        
    except MemoryError:
        logger.error("内存不足，尝试强制缩放...")
        gc.collect()
        
        w, h = original_size
        scale = 512 / max(w, h)
        small_size = (int(w * scale) // 2 * 2, int(h * scale) // 2 * 2)
        small_img = pil_img.resize(small_size, Image.Resampling.LANCZOS)
        
        try:
            result = rembg_remove(small_img, session=session)
            result = result.resize(original_size, Image.Resampling.LANCZOS)
            original_rgba = pil_img.convert('RGBA')
            r, g, b, _ = original_rgba.split()
            _, _, _, a = result.split()
            return Image.merge('RGBA', (r, g, b, a))
        except Exception as e:
            logger.error(f"处理失败: {e}")
            return pil_img.convert("RGBA")
    
    except Exception as e:
        logger.error(f"背景移除失败: {e}")
        return pil_img.convert("RGBA")

def remove_bg_with_session(pil_img, session):
    """兼容旧接口"""
    if USE_REMBG and rembg_remove and session:
        try:
            return rembg_remove(pil_img, session=session)
        except Exception as e:
            logger.error(f"背景移除失败: {e}")
            return pil_img.convert("RGBA")
    return pil_img.convert("RGBA")

def cleanup_edge_pixels(pil_img, feather: int = 1, blur: int = 1, gamma: float = 1.2):
    """
    边缘清理 - 增强版 v2
    1. 预清理：清除低透明度的幽灵噪点
    2. 形态学优化：平滑边缘毛刺
    3. 智能羽化：保持主体轮廓
    """
    if not HAS_CV2 or not HAS_NUMPY:
        return pil_img
        
    if pil_img.mode != 'RGBA':
        pil_img = pil_img.convert('RGBA')
    
    img_array = np.array(pil_img)
    # 分离通道
    b, g, r, a = cv2.split(img_array)
    
    # --- 步骤1: 预处理 Alpha 通道 ---
    # 强制截断低透明度噪点 (去除半透明的残留背景)
    # 将 Alpha < 20 的像素直接置 0，大于 20 的保留
    _, hard_alpha = cv2.threshold(a, 20, 255, cv2.THRESH_TOZERO)
    
    # --- 步骤2: 形态学处理 (去除毛刺) ---
    # 使用开运算 (先腐蚀后膨胀) 去除边缘细小的噪点，而不显著缩小物体
    if feather > 0:
        kernel_size = 3
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        hard_alpha = cv2.morphologyEx(hard_alpha, cv2.MORPH_OPEN, kernel, iterations=1)
        if feather > 1:
            erode_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            hard_alpha = cv2.erode(hard_alpha, erode_kernel, iterations=feather - 1)
    
    # --- 步骤3: 边缘羽化 (高斯模糊 + Gamma) ---
    if blur > 0:
        alpha_f = hard_alpha.astype(np.float32) / 255.0
        k_blur = blur * 2 + 1
        alpha_f = cv2.GaussianBlur(alpha_f, (k_blur, k_blur), 0)
        if gamma != 1.0:
            alpha_f = np.power(alpha_f, gamma)
        hard_alpha = np.clip(alpha_f * 255, 0, 255).astype(np.uint8)

    img_array = cv2.merge((b, g, r, hard_alpha))
    
    return Image.fromarray(img_array, mode='RGBA')

def remove_isolated_colors(pil_img, min_area: int, remove_internal: bool = True, internal_max_area: int = 100):
    """
    移除孤立色块 - 智能连通域版 v2
    1. 使用连通组件分析代替轮廓查找，更精准
    2. 智能保护：始终保留面积最大的色块（主体），防止误删
    """
    if not HAS_CV2 or not HAS_NUMPY:
        return pil_img
        
    if min_area <= 0 and not remove_internal:
        return pil_img
        
    if pil_img.mode != 'RGBA':
        pil_img = pil_img.convert('RGBA')
        
    img_array = np.array(pil_img)
    alpha = img_array[:, :, 3].copy()
    
    _, binary = cv2.threshold(alpha, 20, 255, cv2.THRESH_BINARY)
    
    has_change = False
    
    if min_area > 0:
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        if num_labels > 1:
            areas = stats[1:, cv2.CC_STAT_AREA]
            if len(areas) > 0:
                max_area_idx = np.argmax(areas) + 1
                new_alpha = np.zeros_like(alpha)
                for i in range(1, num_labels):
                    area = stats[i, cv2.CC_STAT_AREA]
                    if i == max_area_idx or area >= min_area:
                        component_mask = (labels == i).astype(np.uint8) * 255
                        new_alpha = cv2.bitwise_or(new_alpha, cv2.bitwise_and(alpha, alpha, mask=component_mask))
                    else:
                        has_change = True
                alpha = new_alpha
                _, binary = cv2.threshold(alpha, 20, 255, cv2.THRESH_BINARY)

    if remove_internal and internal_max_area > 0:
        kernel_size = max(3, int(math.sqrt(internal_max_area)))
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        closed_mask = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        holes = cv2.bitwise_and(closed_mask, cv2.bitwise_not(binary))
        if cv2.countNonZero(holes) > 0:
            alpha = cv2.add(alpha, holes)
            has_change = True
    
    if not has_change:
        return pil_img
    
    img_array[:, :, 3] = alpha
    return Image.fromarray(img_array, mode='RGBA')

def fill_alpha_with_bg(pil_img, bg_type: str, bg_color: str = "#FFFFFF", bg_image_path: str = None):
    """填充背景"""
    if pil_img.mode != 'RGBA': 
        pil_img = pil_img.convert('RGBA')
    if bg_type == "none": 
        return pil_img
    
    if bg_type == "color":
        c = bg_color.strip().lstrip('#')
        rgb = tuple(int(c[i:i+2], 16) for i in (0, 2, 4)) if len(c) == 6 else (255,255,255)
        base = Image.new('RGB', pil_img.size, rgb)
    elif bg_type == "image" and bg_image_path and Path(bg_image_path).exists():
        try:
            base = Image.open(bg_image_path).convert('RGB').resize(pil_img.size, Image.Resampling.LANCZOS)
        except: 
            base = Image.new('RGB', pil_img.size, (255, 255, 255))
    else:
        base = Image.new('RGB', pil_img.size, (255, 255, 255))
    
    base.paste(pil_img, mask=pil_img.split()[-1])
    return base

def process_single_frame(frame_data: tuple, session, params: dict, model_id: str = "u2net") -> tuple:
    """处理单帧"""
    idx, frame_rgb = frame_data
    
    try:
        pil = Image.fromarray(frame_rgb)
        
        if params.get("remove_bg"):
            pil = remove_bg_with_session_smart(pil, session, model_id)
            
            if params.get("cleanup_edge"):
                pil = cleanup_edge_pixels(
                    pil, 
                    params.get("edge_feather", 1), 
                    params.get("edge_blur", 1),
                    params.get("edge_gamma", 1.2)
                )
            if params.get("remove_isolated"):
                pil = remove_isolated_colors(
                    pil, 
                    params.get("isolated_area", 50),
                    params.get("remove_internal", True),
                    params.get("internal_max_area", 100)
                )
            if params.get("bg_type", "none") != "none":
                pil = fill_alpha_with_bg(pil, params.get("bg_type"), params.get("bg_color"), params.get("bg_image"))
        else:
            pil = pil.convert("RGBA")
        
        return (idx, pil, None)
    except Exception as e:
        return (idx, None, str(e))

# ==================== Workers ====================
class BaseWorker(QThread):
    """基础 Worker 类"""
    progress = Signal(int, str)
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self):
        super().__init__()
        self._stop = False
    
    def stop(self):
        self._stop = True
        logger.info("正在停止任务...")

class ModelLoadWorker(QThread):
    finished = Signal(object, str)
    error = Signal(str)
    def __init__(self, model_id: str):
        super().__init__()
        self.model_id = model_id
    def run(self):
        try:
            s = ModelManager.load_model(self.model_id)
            if s:
                self.finished.emit(s, self.model_id)
            else:
                self.error.emit("模型加载失败")
        except Exception as e:
            self.error.emit(str(e))

class VideoToImagesWorker(BaseWorker):
    def __init__(self, video_path: str, output_dir: str, params: dict):
        super().__init__()
        self.video_path = Path(video_path)
        self.output_dir = Path(output_dir)
        self.params = params

    def run(self):
        if not HAS_CV2:
            self.error.emit("opencv-python 未安装")
            return
            
        try:
            output_folder = self.output_dir / self.video_path.stem
            output_folder.mkdir(parents=True, exist_ok=True)
            cap = cv2.VideoCapture(str(self.video_path))
            if not cap.isOpened():
                self.error.emit(f"无法打开视频：{self.video_path}")
                return
            
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            step = max(1, int(self.params.get("frame_step", 1)))
            need_remove_bg = self.params.get("remove_bg") and USE_REMBG
            
            if self.params.get("extract_mode") == "first_last":
                frames_idx = [0, max(0, total-1)]
                names = ["_AA", "_BB"]
            else:
                frames_idx = list(range(0, total, step))
                names = [f"_{i+1:06d}" for i in range(len(frames_idx))]
            
            total_frames = len(frames_idx)
            logger.info(f"准备提取 {total_frames} 帧 (共 {total} 帧, 间隔 {step})")
            
            if not need_remove_bg:
                logger.info("快速模式：直接提取帧（无背景处理）")
                saved = 0
                for i, idx in enumerate(frames_idx):
                    if self._stop:
                        break
                    
                    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                    ret, frame = cap.read()
                    if ret:
                        suffix = names[i]
                        out_path = output_folder / f"{self.video_path.stem}{suffix}.png"
                        
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        Image.fromarray(frame_rgb).save(str(out_path))
                        saved += 1
                    
                    self.progress.emit(int((i + 1) / total_frames * 100), f"提取帧 {i+1}/{total_frames}")
                
                cap.release()
                logger.success(f"快速提取完成: 保存 {saved} 张图片")
                self.finished.emit({"count": saved, "folder": str(output_folder)})
                return
            
            model_name = self.params.get("model_name", "isnet-general-use")
            self.progress.emit(0, f"加载模型 {model_name}...")
            session = ModelManager.load_model(model_name)
            if not session:
                self.error.emit(f"模型加载失败")
                cap.release()
                return
            
            frames_data = []
            for i, idx in enumerate(frames_idx):
                if self._stop: break
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frames_data.append((i, frame_rgb))
                self.progress.emit(int((i + 1) / total_frames * 20), f"读取帧 {i+1}/{total_frames}")
            cap.release()
            
            if not frames_data:
                self.error.emit("无有效帧")
                return
            
            num_workers = min(self.params.get("num_threads", 4), len(frames_data))
            processed = 0
            results = {}
            
            logger.info(f"开始处理 {len(frames_data)} 帧 (使用 {num_workers} 线程)")
            
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = {
                    executor.submit(process_single_frame, fd, session, self.params, model_name): fd[0]
                    for fd in frames_data
                }
                
                for future in as_completed(futures):
                    if self._stop:
                        break
                    
                    idx, pil, err = future.result()
                    if err:
                        logger.warning(f"帧 {idx} 处理失败: {err}")
                    else:
                        results[idx] = pil
                    
                    processed += 1
                    self.progress.emit(20 + int(processed / len(frames_data) * 70), f"处理帧 {processed}/{len(frames_data)}")
                    
                    if processed % 10 == 0:
                        gc.collect()
            
            self.progress.emit(90, "保存图片...")
            saved = 0
            for i in range(len(frames_data)):
                if i in results:
                    suffix = names[i] if self.params.get("extract_mode") == "first_last" else f"_{saved+1:06d}"
                    results[i].save(str(output_folder / f"{self.video_path.stem}{suffix}.png"))
                    saved += 1
            
            gc.collect()
            logger.success(f"完成: 保存 {saved} 张图片")
            self.finished.emit({"count": saved, "folder": str(output_folder)})
            
        except Exception as e:
            logger.error(f"处理失败: {e}")
            traceback.print_exc()
            self.error.emit(str(e))

class VideoRemoveBgWorker(BaseWorker):
    """视频扣像 Worker"""

    def __init__(self, video_path: str, output_path: str, params: dict):
        super().__init__()
        self.video_path = Path(video_path)
        self.output_path = Path(output_path)
        self.params = params

    def run(self):
        if not HAS_CV2:
            self.error.emit("opencv-python 未安装")
            return
            
        try:
            cap = cv2.VideoCapture(str(self.video_path))
            if not cap.isOpened():
                self.error.emit(f"无法打开视频：{self.video_path}")
                return
            
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            model_name = self.params.get("model_name", "isnet-general-use")
            self.progress.emit(0, f"加载模型 {model_name}...")
            session = ModelManager.load_model(model_name)
            if not session:
                self.error.emit(f"模型加载失败")
                cap.release()
                return
            
            output_format = self.params.get("output_format", "mp4")
            preserve_alpha = self.params.get("preserve_alpha", False)

            if output_format == "webm" and preserve_alpha:
                self._save_webm_with_alpha(cap, session, model_name, total, width, height, fps)
                return
            elif output_format == "webm":
                fourcc = cv2.VideoWriter_fourcc(*'VP90')
                out_file = str(self.output_path)
            elif output_format == "mov":
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out_file = str(self.output_path)
            else:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out_file = str(self.output_path)
            
            writer = cv2.VideoWriter(out_file, fourcc, fps, (width, height))
            
            if not writer.isOpened():
                self.error.emit("无法创建输出视频")
                cap.release()
                return
            
            frame_idx = 0
            processed = 0
            start_time = time.time()
            
            logger.info(f"开始处理视频: {total} 帧, {width}x{height}, {fps:.1f}fps")
            
            while True:
                if self._stop:
                    break
                
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil = Image.fromarray(frame_rgb)
                
                pil = remove_bg_with_session_smart(pil, session, model_name)
                
                if self.params.get("cleanup_edge"):
                    pil = cleanup_edge_pixels(
                        pil,
                        self.params.get("edge_feather", 1),
                        self.params.get("edge_blur", 1),
                        self.params.get("edge_gamma", 1.2)
                    )
                
                if self.params.get("remove_isolated"):
                    pil = remove_isolated_colors(
                        pil,
                        self.params.get("isolated_area", 50),
                        self.params.get("remove_internal", True),
                        self.params.get("internal_max_area", 100)
                    )
                
                bg_color = self.params.get("bg_color", "#00FF00")
                pil = fill_alpha_with_bg(pil, "color", bg_color)
                
                frame_out = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
                writer.write(frame_out)
                
                frame_idx += 1
                processed += 1
                
                if frame_idx % 10 == 0:
                    dur = time.time() - start_time
                    avg = frame_idx / max(dur, 1e-6)
                    rem = max(0, total - frame_idx)
                    eta = rem / max(avg, 1e-6)
                    m = int(eta // 60)
                    s = int(eta % 60)
                    eta_str = f"{m}:{s:02d}"
                    self.progress.emit(int(frame_idx / total * 100), f"处理帧 {frame_idx}/{total} | {avg:.2f} fps | 剩余 {eta_str}")
                    gc.collect()
            
            cap.release()
            writer.release()
            gc.collect()
            
            dur = round(time.time() - start_time, 2)
            avg_fps = round(processed / max(dur, 1e-6), 2)
            self.progress.emit(100, "处理完成")
            logger.success(f"视频扣像完成: {self.output_path} | 帧数 {processed} | 耗时 {dur}s | 平均 {avg_fps} fps")
            self.finished.emit({
                "video": str(self.output_path),
                "frames": processed,
                "folder": str(self.output_path.parent),
                "duration": dur,
                "avg_fps": avg_fps
            })
            
        except Exception as e:
            logger.error(f"视频扣像失败: {e}")
            traceback.print_exc()
            self.error.emit(str(e))

    def _save_webm_with_alpha(self, cap, session, model_name, total, width, height, fps):
        try:
            import imageio
            import importlib.util
            import subprocess
            use_ffmpeg_plugin = importlib.util.find_spec('imageio_ffmpeg') is not None
            out_crf = int(self.params.get('crf', 32))
            out_cpu = int(self.params.get('cpu_used', 6))
            threads = max(1, (os.cpu_count() or 4))
            include_audio = bool(self.params.get('include_audio', True))
            padded_w = width + (width % 2)
            padded_h = height + (height % 2)
            speed_text = str(self.params.get('speed_mode', '平衡'))
            deadline = 'good'
            tile_cols = '2'
            if speed_text in ['快速', 'fast']:
                out_cpu = max(out_cpu, 8)
                deadline = 'realtime'
                tile_cols = '2'
            elif speed_text in ['高质量', 'quality']:
                out_cpu = min(out_cpu, 4)
                deadline = 'good'
                tile_cols = '1'
            start_time = time.time()

            if use_ffmpeg_plugin and not include_audio:
                writer = imageio.get_writer(
                    str(self.output_path),
                    format='FFMPEG',
                    fps=fps,
                    codec='libvpx-vp9',
                    pixelformat='yuva420p',
                    output_params=['-b:v','0','-crf',str(out_crf),'-deadline',deadline,'-cpu-used',str(out_cpu),'-row-mt','1','-auto-alt-ref','0','-threads',str(threads),'-tile-columns',tile_cols,'-an'],
                    macro_block_size=1
                )
            else:
                ffmpeg_bin = ConfigManager.get_tool_path('ffmpeg')
                cmd = [
                    ffmpeg_bin, '-y',
                    '-f', 'rawvideo',
                    '-vcodec', 'rawvideo',
                    '-pix_fmt', 'rgba',
                    '-s', f'{padded_w}x{padded_h}',
                    '-r', str(fps),
                    '-i', 'pipe:0',
                ]
                if include_audio and getattr(self, 'video_path', None):
                    cmd += ['-i', str(self.video_path)]
                cmd += [
                    '-c:v', 'libvpx-vp9',
                    '-pix_fmt', 'yuva420p',
                    '-b:v','0','-crf',str(out_crf),'-deadline',deadline,'-cpu-used',str(out_cpu),'-row-mt','1','-auto-alt-ref','0','-threads',str(threads),'-tile-columns',tile_cols,
                ]
                if include_audio:
                    cmd += ['-map', '0:v:0', '-map', '1:a?', '-c:a', 'libopus', '-b:a', '128k', '-ar', '48000', '-shortest']
                else:
                    cmd += ['-an']
                cmd += [
                    str(self.output_path)
                ]
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                stderr_lines = []
                def _drain_stderr(p, buf):
                    try:
                        for line in iter(p.stderr.readline, b''):
                            try:
                                buf.append(line.decode(errors='ignore'))
                            except Exception:
                                pass
                    except Exception:
                        pass
                t_err = threading.Thread(target=_drain_stderr, args=(proc, stderr_lines), daemon=True)
                t_err.start()

            frame_idx = 0

            while True:
                if self._stop:
                    break

                ret, frame = cap.read()
                if not ret:
                    break

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil = Image.fromarray(frame_rgb)

                pil = remove_bg_with_session_smart(pil, session, model_name)

                if self.params.get("cleanup_edge"):
                    pil = cleanup_edge_pixels(
                        pil,
                        self.params.get("edge_feather", 1),
                        self.params.get("edge_blur", 1),
                        self.params.get("edge_gamma", 1.2)
                    )

                if self.params.get("remove_isolated"):
                    pil = remove_isolated_colors(
                        pil,
                        self.params.get("isolated_area", 50),
                        self.params.get("remove_internal", True),
                        self.params.get("internal_max_area", 100)
                    )

                if pil.mode != 'RGBA':
                    pil = pil.convert('RGBA')
                if pil.size != (padded_w, padded_h):
                    bg = Image.new('RGBA', (padded_w, padded_h), (0, 0, 0, 0))
                    bg.paste(pil, (0, 0))
                    pil = bg

                if use_ffmpeg_plugin and not include_audio:
                    writer.append_data(np.array(pil))
                else:
                    try:
                        proc.stdin.write(pil.tobytes('raw', 'RGBA'))
                    except Exception:
                        raise

                frame_idx += 1

                if frame_idx % 10 == 0:
                    dur = time.time() - start_time
                    avg = frame_idx / max(dur, 1e-6)
                    rem = max(0, total - frame_idx)
                    eta = rem / max(avg, 1e-6)
                    m = int(eta // 60)
                    s = int(eta % 60)
                    eta_str = f"{m}:{s:02d}"
                    self.progress.emit(int(frame_idx / total * 100), f"处理帧 {frame_idx}/{total} | {avg:.2f} fps | 剩余 {eta_str}")
                    gc.collect()

            cap.release()
            if use_ffmpeg_plugin and not include_audio:
                writer.close()
            else:
                if proc.stdin:
                    try:
                        proc.stdin.close()
                    except:
                        pass
                proc.wait()
                try:
                    t_err.join(timeout=2.0)
                except Exception:
                    pass
                if proc.returncode != 0:
                    err = "\n".join(stderr_lines[-200:]) if stderr_lines else ''
                    raise RuntimeError(f'ffmpeg 写入失败: {err}')
            gc.collect()

            dur = round(time.time() - start_time, 2)
            avg_fps = round(frame_idx / max(dur, 1e-6), 2)
            self.progress.emit(100, "处理完成")
            logger.success(f"透明 WebM 视频生成完成: {self.output_path} | 帧数 {frame_idx} | 耗时 {dur}s | 平均 {avg_fps} fps")
            self.finished.emit({
                "video": str(self.output_path),
                "frames": frame_idx,
                "folder": str(self.output_path.parent),
                "duration": dur,
                "avg_fps": avg_fps
            })

        except Exception as e:
            logger.error(f"透明 WebM 保存失败: {e}")
            traceback.print_exc()
            self.error.emit(str(e))

class SpriteWorker(BaseWorker):
    def __init__(self, source_path: str, output_dir: str, params: dict):
        super().__init__()
        self.source_path = Path(source_path)
        self.output_dir = Path(output_dir)
        self.params = params

    def run(self):
        try:
            need_remove_bg = self.params.get("remove_bg") and USE_REMBG
            model_name = self.params.get("model_name", "isnet-general-use")
            session = None
            
            if need_remove_bg:
                self.progress.emit(0, f"加载模型 {model_name}...")
                session = ModelManager.load_model(model_name)
            
            frames_data = []
            frames_pil = []
            
            if self.params.get("source_type") == "video":
                if not HAS_CV2:
                    self.error.emit("opencv-python 未安装")
                    return
                    
                cap = cv2.VideoCapture(str(self.source_path))
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                step = max(1, self.params.get("frame_step", 1))
                
                frame_count = 0
                for i in range(0, total, step):
                    if self._stop: break
                    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, f = cap.read()
                    if ret:
                        frame_rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
                        if need_remove_bg:
                            frames_data.append((frame_count, frame_rgb))
                        else:
                            frames_pil.append(Image.fromarray(frame_rgb).convert("RGBA"))
                        frame_count += 1
                        self.progress.emit(int(i/total*30), f"采样 {frame_count}")
                cap.release()
            elif self.params.get("source_type") == "sheet":
                img = Image.open(self.source_path).convert("RGBA")
                w, h = img.size
                if self.params.get("auto_detect"):
                    g = math.gcd(w, h)
                    rows = max(1, h // g)
                    cols = max(1, w // g)
                else:
                    rows = max(1, int(self.params.get("existing_rows", 1)))
                    cols = max(1, int(self.params.get("existing_cols", 1)))
                cell_w = w // cols
                cell_h = h // rows
                total_cells = rows * cols
                for idx in range(total_cells):
                    if self._stop: break
                    c = idx % cols
                    r = idx // cols
                    box = (c * cell_w, r * cell_h, (c+1) * cell_w, (r+1) * cell_h)
                    frames_pil.append(img.crop(box))
                    self.progress.emit(int((idx+1)/total_cells*30), f"切片 {idx+1}/{total_cells}")
            else:
                files = sorted([f for f in (self.source_path.glob('*') if self.source_path.is_dir() else [self.source_path]) 
                              if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp']])
                for i, f in enumerate(files):
                    if self._stop: break
                    img = Image.open(f)
                    if need_remove_bg:
                        frames_data.append((i, np.array(img.convert("RGB"))))
                    else:
                        frames_pil.append(img.convert("RGBA"))
                    self.progress.emit(int((i+1)/len(files)*30), f"加载 {i+1}/{len(files)}")

            if need_remove_bg:
                if not frames_data:
                    self.error.emit("无有效帧")
                    return
                
                num_workers = min(self.params.get("num_threads", 4), len(frames_data))
                processed = 0
                results = {}
                
                logger.info(f"处理 {len(frames_data)} 帧 (使用 {num_workers} 线程)")
                
                with ThreadPoolExecutor(max_workers=num_workers) as executor:
                    futures = {
                        executor.submit(process_single_frame, fd, session, self.params, model_name): fd[0]
                        for fd in frames_data
                    }
                    
                    for future in as_completed(futures):
                        if self._stop:
                            break
                        
                        idx, pil, err = future.result()
                        if not err:
                            results[idx] = pil
                        
                        processed += 1
                        self.progress.emit(30 + int(processed / len(frames_data) * 40), f"处理帧 {processed}/{len(frames_data)}")
                        
                        if processed % 10 == 0:
                            gc.collect()
                
                frames = [results[i] for i in range(len(frames_data)) if i in results]
            else:
                frames = frames_pil
                logger.info(f"快速模式：直接使用 {len(frames)} 帧")
            
            if not frames:
                self.error.emit("无有效帧")
                return

            keep_spec = self.params.get("keep_frames")
            if keep_spec:
                def parse_ranges(spec, n):
                    res = set()
                    for part in spec.replace('，', ',').split(','):
                        part = part.strip()
                        if not part: continue
                        if '-' in part:
                            a, b = part.split('-', 1)
                            try:
                                s = max(1, int(a)); e = min(n, int(b))
                                for k in range(s, e+1): res.add(k-1)
                            except: pass
                        else:
                            try:
                                k = int(part); 
                                if 1 <= k <= n: res.add(k-1)
                            except: pass
                    return sorted(res)
                idxs = parse_ranges(keep_spec, len(frames))
                if idxs:
                    frames = [frames[i] for i in idxs]

            fw, fh = frames[0].size
            if self.params.get("scale_mode") == "percent":
                sc = self.params.get("scale_percent", 100) / 100
                tw, th = int(fw*sc), int(fh*sc)
            else:
                tw, th = int(self.params.get("thumb_w", 256)), int(self.params.get("thumb_h", 256))
            
            cols = self.params.get("columns", 10)
            rows = math.ceil(len(frames)/cols)
            sheet = Image.new("RGBA", (cols*tw, rows*th))
            
            for idx, fr in enumerate(frames):
                if self._stop: break
                thumb = fr.resize((tw, th), Image.Resampling.LANCZOS)
                c, r = idx % cols, idx // cols
                sheet.paste(thumb, (c*tw, r*th), thumb)
                self.progress.emit(70 + int((idx+1)/len(frames)*30), "合成中...")
            
            out_name = f"{self.source_path.stem}_sprite_{len(frames)}{'_bj' if self.params.get('edit_mode') else ''}.png"
            out_path = self.output_dir / out_name
            sheet.save(out_path)
            
            gc.collect()
            logger.success(f"精灵图生成完成: {out_path}")
            self.finished.emit({"sheet": str(out_path), "count": len(frames), "folder": str(self.output_dir)})
            
        except Exception as e:
            logger.error(f"精灵图生成失败: {e}")
            traceback.print_exc()
            self.error.emit(str(e))

class SpriteWorkerWithEditor(BaseWorker):
    frames_ready = Signal(list, str)
    def __init__(self, source_path: str, output_dir: str, params: dict, parent_window):
        super().__init__()
        self.source_path = Path(source_path)
        self.output_dir = Path(output_dir)
        self.params = params
        self.parent_window = parent_window
    def run(self):
        try:
            need_remove_bg = self.params.get("remove_bg") and USE_REMBG
            model_name = self.params.get("model_name", "isnet-general-use")
            session = None
            if need_remove_bg:
                self.progress.emit(0, f"加载模型 {model_name}...")
                session = ModelManager.load_model(model_name)
            frames = []
            if self.params.get("source_type") == "video":
                if not HAS_CV2:
                    self.error.emit("opencv-python 未安装")
                    return
                cap = cv2.VideoCapture(str(self.source_path))
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                step = max(1, self.params.get("frame_step", 1))
                data = []
                for i in range(0, total, step):
                    if self._stop: break
                    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, f = cap.read()
                    if ret:
                        frame_rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
                        data.append((len(data), frame_rgb))
                        self.progress.emit(int(i/total*30), f"采样 {len(data)}")
                cap.release()
                if need_remove_bg:
                    # 修复：确保 num_workers 至少为 1，防止 ValueError
                    num_workers = max(1, min(self.params.get("num_threads", 4), len(data)))
                    results = {}
                    processed = 0
                    with ThreadPoolExecutor(max_workers=num_workers) as executor:
                        futures = {executor.submit(process_single_frame, fd, session, self.params, model_name): fd[0] for fd in data}
                        for future in as_completed(futures):
                            if self._stop: break
                            idx, pil, err = future.result()
                            if not err:
                                results[idx] = pil
                            processed += 1
                            self.progress.emit(30 + int(processed / max(1,len(data)) * 40), f"处理帧 {processed}/{len(data)}")
                    frames = [results[i] for i in range(len(data)) if i in results]
                else:
                    for _, rgb in data:
                        frames.append(Image.fromarray(rgb).convert("RGBA"))
            else:
                files = sorted([f for f in (self.source_path.glob('*') if self.source_path.is_dir() else [self.source_path]) if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp']])
                data = []
                for i, fp in enumerate(files):
                    if self._stop: break
                    img = Image.open(fp).convert("RGB")
                    data.append((i, np.array(img)))
                    self.progress.emit(int((i+1)/len(files)*30), f"加载 {i+1}/{len(files)}")
                if need_remove_bg:
                    # 修复：确保 num_workers 至少为 1，防止 ValueError
                    num_workers = max(1, min(self.params.get("num_threads", 4), len(data)))
                    results = {}
                    processed = 0
                    with ThreadPoolExecutor(max_workers=num_workers) as executor:
                        futures = {executor.submit(process_single_frame, fd, session, self.params, model_name): fd[0] for fd in data}
                        for future in as_completed(futures):
                            if self._stop: break
                            idx, pil, err = future.result()
                            if not err:
                                results[idx] = pil
                            processed += 1
                            self.progress.emit(30 + int(processed / max(1,len(data)) * 40), f"处理帧 {processed}/{len(data)}")
                    frames = [results[i] for i in range(len(data)) if i in results]
                else:
                    for _, arr in data:
                        frames.append(Image.fromarray(arr).convert("RGBA"))
            if not frames:
                self.error.emit("无有效帧")
                return
            fw, fh = frames[0].size
            if self.params.get("scale_mode") == "percent":
                sc = self.params.get("scale_percent", 100) / 100
                tw, th = int(fw*sc), int(fh*sc)
            else:
                tw, th = int(self.params.get("thumb_w", 256)), int(self.params.get("thumb_h", 256))
            scaled_frames = [fr.resize((tw, th), Image.Resampling.LANCZOS) for fr in frames]
            self.progress.emit(95, "准备编辑器...")
            self.frames_ready.emit(scaled_frames, str(self.source_path))
        except Exception as e:
            logger.error(f"精灵图生成失败: {e}")
            traceback.print_exc()
            self.error.emit(str(e))

    def _open_editor(self, frames):
        try:
            dialog = SpriteEditorDialog(self.parent_window, source_frames=frames)
            if dialog.exec() == QDialog.Accepted:
                selected_frames = dialog.get_selected_frames()
                output_cols = dialog.get_output_cols()
                if not selected_frames:
                    logger.warning("未选择任何帧")
                    self.finished.emit({"folder": str(self.output_dir)})
                    return
                fw, fh = selected_frames[0].size
                rows = math.ceil(len(selected_frames) / max(1, output_cols))
                sheet = Image.new("RGBA", (output_cols * fw, rows * fh))
                for idx, frame in enumerate(selected_frames):
                    c, r = idx % output_cols, idx // output_cols
                    if frame.mode != 'RGBA':
                        frame = frame.convert('RGBA')
                    sheet.paste(frame, (c * fw, r * fh), frame)
                out_name = f"{self.source_path.stem}_bj_{len(selected_frames)}.png"
                out_path = self.output_dir / out_name
                sheet.save(str(out_path))
                gc.collect()
                logger.success(f"编辑精灵图生成完成: {out_path}")
                self.finished.emit({"sheet": str(out_path), "count": len(selected_frames), "folder": str(self.output_dir)})
            else:
                logger.info("用户取消编辑")
                self.finished.emit({"folder": str(self.output_dir)})
        except Exception as e:
            logger.error(f"编辑器错误: {e}")
            self.error.emit(str(e))

class VideoToGifWorker(BaseWorker):
    def __init__(self, video_path: str, output_path: str, params: dict):
        super().__init__()
        self.video_path = Path(video_path)
        self.output_path = Path(output_path)
        self.params = params

    def run(self):
        if not HAS_CV2:
            self.error.emit("opencv-python 未安装")
            return
            
        try:
            cap = cv2.VideoCapture(str(self.video_path))
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            step = max(1, self.params.get("frame_step", 1))
            
            preserve_transparency = self.params.get("preserve_transparency", False)
            need_remove_bg = self.params.get("remove_bg") and USE_REMBG
            model_name = self.params.get("model_name", "isnet-general-use")
            session = None
            
            if need_remove_bg:
                self.progress.emit(0, f"加载模型 {model_name}...")
                session = ModelManager.load_model(model_name)

            total_to_extract = len(range(0, total, step))
            logger.info(f"准备提取 {total_to_extract} 帧 (共 {total} 帧, 间隔 {step})")
            
            if not need_remove_bg:
                logger.info("快速模式：直接提取帧生成 GIF")
                frames = []
                frame_count = 0
                for i in range(0, total, step):
                    if self._stop: break
                    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, f = cap.read()
                    if ret:
                        frame_rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
                        pil = Image.fromarray(frame_rgb)
                        frames.append(pil)
                        frame_count += 1
                    self.progress.emit(int(frame_count / total_to_extract * 80), f"提取帧 {frame_count}/{total_to_extract}")
                cap.release()
            else:
                frames_data = []
                frame_count = 0
                for i in range(0, total, step):
                    if self._stop: break
                    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, f = cap.read()
                    if ret:
                        frame_rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
                        frames_data.append((frame_count, frame_rgb))
                        frame_count += 1
                    self.progress.emit(int(frame_count / total_to_extract * 20), f"读取帧 {frame_count}/{total_to_extract}")
                cap.release()
                
                if not frames_data:
                    self.error.emit("无帧")
                    return

                num_workers = min(self.params.get("num_threads", 4), len(frames_data))
                processed = 0
                results = {}
                
                logger.info(f"处理 {len(frames_data)} 帧 (使用 {num_workers} 线程)")
                
                with ThreadPoolExecutor(max_workers=num_workers) as executor:
                    futures = {
                        executor.submit(process_single_frame, fd, session, self.params, model_name): fd[0]
                        for fd in frames_data
                    }
                    
                    for future in as_completed(futures):
                        if self._stop:
                            break
                        
                        idx, pil, err = future.result()
                        if not err:
                            results[idx] = pil
                        
                        processed += 1
                        self.progress.emit(20 + int(processed / len(frames_data) * 60), f"处理帧 {processed}/{len(frames_data)}")
                        
                        if processed % 10 == 0:
                            gc.collect()
                
                frames = [results[i] for i in range(len(frames_data)) if i in results]
            
            if not frames:
                self.error.emit("无帧")
                return

            duration = int(1000 / max(1, self.params.get("fps", 10)))
            
            self.progress.emit(90, "生成 GIF...")
            
            save_kwargs = {
                "save_all": True,
                "append_images": frames[1:],
                "duration": duration,
                "loop": 0
            }

            if preserve_transparency and need_remove_bg:
                converted_frames = []
                for frame in frames:
                    if frame.mode != 'RGBA':
                        frame = frame.convert('RGBA')
                    alpha = frame.split()[-1]
                    frame_p = frame.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=255)
                    mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
                    frame_p.paste(255, mask)
                    converted_frames.append(frame_p)
                
                save_kwargs["append_images"] = converted_frames[1:]
                save_kwargs["transparency"] = 255
                save_kwargs["disposal"] = 2
                converted_frames[0].save(str(self.output_path), **save_kwargs)
            else:
                if frames[0].mode == 'RGBA':
                    frames = [fill_alpha_with_bg(f, "color", "#FFFFFF") for f in frames]
                frames[0].save(str(self.output_path), **save_kwargs)

            gc.collect()
            logger.success(f"GIF 生成完成: {self.output_path}")
            self.finished.emit({"gif": str(self.output_path), "count": len(frames), "folder": str(self.output_path.parent)})
            
        except Exception as e:
            logger.error(f"GIF 生成失败: {e}")
            traceback.print_exc()
            self.error.emit(str(e))

class ImagesToGifWorker(BaseWorker):
    def __init__(self, source_path: str, output_path: str, params: dict):
        super().__init__()
        self.source_path = Path(source_path)
        self.output_path = Path(output_path)
        self.params = params

    def run(self):
        try:
            if self.source_path.is_dir():
                files = sorted([f for f in self.source_path.glob('*') if f.suffix.lower() in ['.png', '.jpg', '.jpeg']])
            else: 
                files = [self.source_path]
            
            frames = []
            preserve_transparency = self.params.get("preserve_transparency", False)
            
            for i, f in enumerate(files):
                img = Image.open(f)
                frames.append(img)
                self.progress.emit(int((i+1)/len(files)*100), "加载中")
            
            duration = int(1000 / max(1, self.params.get("fps", 10)))
            save_kwargs = {"save_all": True, "append_images": frames[1:], "duration": duration, "loop": 0}

            if preserve_transparency:
                converted_frames = []
                for frame in frames:
                    if frame.mode != 'RGBA': 
                        frame = frame.convert('RGBA')
                    alpha = frame.split()[-1]
                    frame_p = frame.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=255)
                    mask = Image.eval(alpha, lambda a: 255 if a <= 128 else 0)
                    frame_p.paste(255, mask)
                    converted_frames.append(frame_p)
                save_kwargs["append_images"] = converted_frames[1:]
                save_kwargs["transparency"] = 255
                save_kwargs["disposal"] = 2
                converted_frames[0].save(str(self.output_path), **save_kwargs)
            else:
                frames[0].save(str(self.output_path), **save_kwargs)
                
            logger.success(f"GIF 生成完成")
            self.finished.emit({"gif": str(self.output_path), "count": len(frames), "folder": str(self.output_path.parent)})
        except Exception as e:
            logger.error(f"GIF 生成失败: {e}")
            self.error.emit(str(e))

class ImagesToVideoWorker(BaseWorker):
    def __init__(self, source, output, params):
        super().__init__()
        self.source, self.output, self.params = Path(source), Path(output), params
        
    def run(self):
        if not HAS_CV2:
            self.error.emit("opencv-python 未安装")
            return
            
        try:
            files = sorted([f for f in self.source.glob('*') if f.suffix.lower() in ['.png','.jpg']]) if self.source.is_dir() else [self.source]
            if not files: 
                raise Exception("无图片")
            fps = max(1, self.params.get("fps", 24))
            
            first_img = Image.open(files[0])
            w, h = first_img.size
            
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(str(self.output), fourcc, fps, (w, h))
            
            for i, f in enumerate(files):
                if self._stop: break
                img = Image.open(f).convert("RGBA")
                if img.size != (w, h): 
                    img = img.resize((w, h), Image.Resampling.LANCZOS)
                bg = fill_alpha_with_bg(img, self.params.get("bg_type", "color"), self.params.get("bg_color", "#FFFFFF"), self.params.get("bg_image"))
                frame = cv2.cvtColor(np.array(bg), cv2.COLOR_RGB2BGR)
                writer.write(frame)
                self.progress.emit(int((i+1)/len(files)*100), f"写入 {i+1}/{len(files)}")
            
            writer.release()
            logger.success(f"视频生成完成")
            self.finished.emit({"video": str(self.output), "folder": str(self.output.parent)})
        except Exception as e:
            logger.error(f"视频生成失败: {e}")
            self.error.emit(str(e))

class SingleImageWorker(BaseWorker):
    def __init__(self, input_path, output_path, params):
        super().__init__()
        self.input, self.output, self.params = input_path, output_path, params
        
    def run(self):
        try:
            model_name = self.params.get("model_name", "isnet-general-use")
            
            self.progress.emit(5, f"加载模型 {model_name}...")
            session = ModelManager.load_model(model_name)
            
            if not session:
                self.error.emit(f"模型加载失败")
                return
            
            self.progress.emit(20, "加载图片...")
            pil = Image.open(self.input).convert("RGBA")
            
            self.progress.emit(40, "移除背景...")
            pil = remove_bg_with_session_smart(pil, session, model_name)
            
            if self.params.get("cleanup_edge"): 
                self.progress.emit(60, "清理边缘...")
                pil = cleanup_edge_pixels(
                    pil, 
                    self.params.get("edge_feather", 1), 
                    self.params.get("edge_blur", 1),
                    self.params.get("edge_gamma", 1.2)
                )
            if self.params.get("remove_isolated"): 
                self.progress.emit(75, "移除杂色...")
                pil = remove_isolated_colors(
                    pil, 
                    self.params.get("isolated_area", 50),
                    self.params.get("remove_internal", True),
                    self.params.get("internal_max_area", 100)
                )
            if self.params.get("bg_type", "none") != "none": 
                self.progress.emit(90, "填充背景...")
                pil = fill_alpha_with_bg(pil, self.params.get("bg_type"), self.params.get("bg_color"), self.params.get("bg_image"))
            
            pil.save(self.output)
            
            # ==================== ICO 生成 ====================
            if self.params.get("ico_enabled") and self.params.get("ico_sizes"):
                self.progress.emit(95, "生成 ICO...")
                try:
                    ico_sizes = sorted(self.params["ico_sizes"], reverse=True)
                    
                    # 【优化】先将图片处理成正方形，避免拉伸变形
                    # 使用 1px padding
                    square_pil = make_square_with_padding(pil, padding=1)
                    
                    if square_pil:
                        # 1. 保留透明通道
                        if self.params.get("ico_transparent"):
                            # 遍历所有选中的尺寸，分别生成单独的 ICO 文件
                            for s in ico_sizes:
                                try:
                                    # 构建带尺寸后缀的文件名，如 image_32x32.ico
                                    ico_name = f"{Path(self.output).stem}_{s}x{s}.ico"
                                    ico_path = Path(self.output).parent / ico_name
                                    
                                    resized = square_pil.resize((s, s), Image.LANCZOS)
                                    # 确保是 RGBA 模式
                                    if resized.mode != 'RGBA':
                                        resized = resized.convert('RGBA')
                                    
                                    # 保存单个尺寸的 ICO
                                    resized.save(str(ico_path), format='ICO')
                                except Exception as ex:
                                    logger.error(f"生成 {s}x{s} ICO 失败: {ex}")
                                
                        # 2. 无透明通道 (白底)
                        if self.params.get("ico_opaque"):
                            for s in ico_sizes:
                                try:
                                    # 构建带尺寸后缀的文件名，如 image_32x32_noalpha.ico
                                    ico_name = f"{Path(self.output).stem}_{s}x{s}_noalpha.ico"
                                    ico_path_opaque = Path(self.output).parent / ico_name
                                    
                                    resized = square_pil.resize((s, s), Image.LANCZOS)
                                    bg = Image.new("RGB", resized.size, (255, 255, 255))
                                    if resized.mode == 'RGBA':
                                        bg.paste(resized, mask=resized.split()[3])
                                    else:
                                        bg.paste(resized)
                                    
                                    # 保存单个尺寸的无透明 ICO
                                    bg.save(str(ico_path_opaque), format='ICO')
                                except Exception as ex:
                                    logger.error(f"生成 {s}x{s} (无透明) ICO 失败: {ex}")
                        
                        # 3. 生成 PNG
                        if self.params.get("ico_png"):
                            for s in ico_sizes:
                                try:
                                    png_name = f"{Path(self.output).stem}_{s}x{s}.png"
                                    png_path = Path(self.output).parent / png_name
                                    
                                    resized = square_pil.resize((s, s), Image.LANCZOS)
                                    resized.save(str(png_path), format='PNG')
                                except Exception as ex:
                                    logger.error(f"生成 {s}x{s} PNG 失败: {ex}")
                        
                        # 4. 生成系统 ICO (多尺寸容器)
                        if self.params.get("ico_system"):
                            try:
                                # 系统 ICO 推荐包含的尺寸
                                # 注意：PIL save format='ICO' 时，可以通过 append_images 参数传入其他尺寸的图像
                                # 第一个图像将作为主图像
                                
                                # 过滤出需要的尺寸
                                target_sizes = sorted([s for s in ico_sizes if s in [16, 24, 32, 48, 256]], reverse=True)
                                if not target_sizes:
                                    target_sizes = [256, 48, 32, 16] # 默认回退
                                
                                ico_images = []
                                for s in target_sizes:
                                    resized = square_pil.resize((s, s), Image.LANCZOS)
                                    if resized.mode != 'RGBA':
                                        resized = resized.convert('RGBA')
                                    ico_images.append(resized)
                                
                                if ico_images:
                                    pcico_name = f"{Path(self.output).stem}_pcico.ico"
                                    pcico_path = Path(self.output).parent / pcico_name
                                    
                                    # 第一个图像作为 base，其余作为附加
                                    # 注意：append_images 应该是 Image 对象列表
                                    ico_images[0].save(
                                        str(pcico_path), 
                                        format='ICO', 
                                        append_images=ico_images[1:] if len(ico_images) > 1 else []
                                    )
                                    logger.success(f"系统 ICO 生成成功: {pcico_path}")
                            except Exception as ex:
                                logger.error(f"生成系统 ICO 失败: {ex}")
                                
                    else:
                        logger.error("ICO 生成失败: 图片转正方形处理出错")
                            
                except Exception as e:
                    logger.error(f"ICO 生成失败: {e}")
                    # 不中断主流程
            
            self.progress.emit(100, "完成")
            gc.collect()
            logger.success(f"图片处理完成")
            self.finished.emit({"output": str(self.output), "folder": str(Path(self.output).parent)})
        except Exception as e:
            logger.error(f"图片处理失败: {e}")
            self.error.emit(str(e))
# ==================== 第三部分：主窗口和程序入口 ====================

# ==================== 主窗口 ====================
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        self.activated = False
        self.trial_mode = False
        # 【修复】使用总秒数进行倒计时，更简单可靠
        self.trial_total_seconds = 15 * 60  # 15分钟 = 900秒
        self.current_worker = None
        self.trial_expired = False  # 标记试用是否已过期
        
        if LicenseManager.check_license_file():
            self.activated = True
        else:
            dialog = ActivationDialog(None)
            if dialog.exec() == QDialog.Accepted:
                if dialog.activated: 
                    self.activated = True
                elif dialog.trial_mode: 
                    self.trial_mode = True
            else:
                sys.exit()
        
        gpu_status = f"GPU: {HardwareInfo.gpu_name}" if HardwareInfo.gpu_available else "CPU模式"
        base_title = f"别快视频精灵图 v7.6 [{gpu_status}]"
        self.setWindowTitle(f"{base_title} - {'已激活' if self.activated else f'试用 (15:00)'}")
        self.setFixedWidth(600)
        self.setAcceptDrops(True)
        
        self.enable_sound = ConfigManager.get("enable_sound", True)
        self._setup_style()
        self._build_ui()
        
        # 【修复】试用模式定时器
        if self.trial_mode and not self.activated:
            self.trial_timer = QTimer(self)
            self.trial_timer.timeout.connect(self._update_trial_countdown)
            self.trial_timer.start(1000)  # 每秒更新
        
        logger.info("软件启动完成")
        logger.info(f"模型目录: {ConfigManager.get_model_dir()}")
        logger.info(f"biemo 目录: {ConfigManager.get_biemo_dir()}")

    def _update_trial_countdown(self):
        """【修复】更新试用倒计时 - 使用总秒数，逻辑清晰"""
        if self.activated or self.trial_expired:
            return
        
        # 每秒减1
        self.trial_total_seconds -= 1
        
        # 计算分钟和秒
        mins = self.trial_total_seconds // 60
        secs = self.trial_total_seconds % 60
        
        # 更新窗口标题
        gpu_status = f"GPU: {HardwareInfo.gpu_name}" if HardwareInfo.gpu_available else "CPU模式"
        self.setWindowTitle(f"别快视频精灵图 v7.6 [{gpu_status}] - 试用 ({mins:02d}:{secs:02d})")
        
        if self.trial_total_seconds == 60:
            logger.warning("⚠ 试用时间仅剩 1 分钟！请保存工作。")
        
        # 时间到
        if self.trial_total_seconds <= 0:
            self._handle_trial_expired()
    
    def _handle_trial_expired(self):
        self.trial_expired = True
        if hasattr(self, 'trial_timer'):
            self.trial_timer.stop()
        self._stop_current_task()
        logger.error("试用时间已到！")
        QApplication.quit()
        sys.exit(0)
    
    def _start_exit_countdown(self):
        """启动60秒退出倒计时"""
        self.exit_countdown = 60
        
        self.exit_timer = QTimer(self)
        self.exit_timer.timeout.connect(self._exit_countdown_tick)
        self.exit_timer.start(1000)
        
        logger.warning(f"程序将在 {self.exit_countdown} 秒后退出...")
    
    def _exit_countdown_tick(self):
        """退出倒计时"""
        self.exit_countdown -= 1
        
        if self.exit_countdown <= 0:
            self.exit_timer.stop()
            logger.info("退出程序")
            QApplication.quit()
            sys.exit(0)
        
        if self.exit_countdown % 10 == 0:
            logger.warning(f"程序将在 {self.exit_countdown} 秒后退出...")
    
    def _show_activation_dialog(self):
        """显示激活对话框"""
        dialog = ActivationDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.activated:
            self.activated = True
            self.trial_expired = False
            
            # 停止退出定时器
            if hasattr(self, 'exit_timer'):
                self.exit_timer.stop()
            
            # 更新标题
            gpu_status = f"GPU: {HardwareInfo.gpu_name}" if HardwareInfo.gpu_available else "CPU模式"
            self.setWindowTitle(f"别快视频精灵图 v7.6 [{gpu_status}] - 已激活")
            
            logger.success("软件已激活！")
            QMessageBox.information(self, "激活成功", "软件已永久激活！")
    
    def _stop_current_task(self):
        """停止当前正在运行的任务"""
        if self.current_worker and self.current_worker.isRunning():
            logger.warning("正在停止当前任务...")
            self.current_worker.stop()
            self.current_worker.wait(5000)
            if self.current_worker.isRunning():
                self.current_worker.terminate()
            logger.info("任务已停止")

    def _setup_style(self):
        self.setStyleSheet("""
            QWidget { font-family: 'Microsoft YaHei UI'; font-size: 9pt; }
            QGroupBox { font-weight: bold; border: 1px solid #3498db; border-radius: 4px; margin-top: 8px; padding-top: 8px; background: #f8f9fa; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #2c3e50; }
            QPushButton { background: #3498db; color: white; border-radius: 3px; padding: 6px; font-weight: bold; }
            QPushButton:hover { background: #2980b9; }
            QPushButton#actionButton { background: #27ae60; font-size: 10pt; padding: 8px; }
            QPushButton#stopButton { background: #e74c3c; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { padding: 4px; border: 1px solid #bdc3c7; border-radius: 3px; }
            QProgressBar { border: 1px solid #bdc3c7; text-align: center; height: 20px; }
            QProgressBar::chunk { background: #3498db; }
        """)

    def _build_ui(self):
        main = QVBoxLayout()
        
        # 状态栏
        status_layout = QHBoxLayout()
        
        gpu_label = QLabel(f"{'✓ ' + HardwareInfo.gpu_name if HardwareInfo.gpu_available else '○ CPU模式'}")
        gpu_label.setStyleSheet(f"color: {'#27ae60' if HardwareInfo.gpu_available else '#e74c3c'}; font-weight: bold;")
        status_layout.addWidget(gpu_label)
        
        mem_label = QLabel(f"内存: {HardwareInfo.available_memory_mb}MB")
        status_layout.addWidget(mem_label)
        
        if HardwareInfo.gpu_available:
            gpu_mem_label = QLabel(f"显存: {HardwareInfo.gpu_memory_mb}MB")
            status_layout.addWidget(gpu_mem_label)
        
        rembg_label = QLabel(f"{'✓ rembg' if USE_REMBG else '✗ rembg'}")
        rembg_label.setStyleSheet(f"color: {'#27ae60' if USE_REMBG else '#e74c3c'};")
        status_layout.addWidget(rembg_label)
        
        status_layout.addStretch()
        
        license_label = QLabel(f"{'✓ 已激活' if self.activated else f'试用模式'}")
        license_label.setStyleSheet(f"color: {'#27ae60' if self.activated else '#e74c3c'}; font-weight: bold;")
        status_layout.addWidget(license_label)
        
        main.addLayout(status_layout)

        # 主内容
        self.splitter = QSplitter(Qt.Vertical)
        
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_sprite_tab(), "精灵图")
        self.tabs.addTab(self._build_video_extract_tab(), "视频转图")
        self.tabs.addTab(self._build_video_rembg_tab(), "视频扣像")
        self.tabs.addTab(self._build_images_to_video_tab(), "图片转视频")
        self.tabs.addTab(self._build_gif_tab(), "视频转GIF")
        self.tabs.addTab(self._build_single_image_tab(), "图片扣图")
        self.tabs.addTab(self._build_settings_tab(), "设置")
        tab_layout.addWidget(self.tabs)
        
        self.splitter.addWidget(tab_widget)
        
        # 日志
        log_group = QGroupBox("系统日志")
        log_layout = QVBoxLayout()
        self.log_widget = LogWidget()
        self.log_widget.setMinimumHeight(150)
        log_layout.addWidget(self.log_widget)
        
        log_btn_layout = QHBoxLayout()
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(lambda: self.log_widget.clear())
        log_btn_layout.addWidget(clear_log_btn)
        
        clear_cache_btn = QPushButton("清除模型缓存")
        clear_cache_btn.clicked.connect(ModelManager.clear_cache)
        log_btn_layout.addWidget(clear_cache_btn)
        
        refresh_models_btn = QPushButton("刷新模型状态")
        refresh_models_btn.clicked.connect(self._refresh_all_model_selectors)
        log_btn_layout.addWidget(refresh_models_btn)
        
        stop_btn = QPushButton("停止当前任务")
        stop_btn.setObjectName("stopButton")
        stop_btn.clicked.connect(self._stop_current_task)
        log_btn_layout.addWidget(stop_btn)
        
        # 添加操作按钮到日志区域
        self.action_btns = {}
        
        # 精灵图按钮
        btn = QPushButton("生成精灵图")
        btn.setObjectName("actionButton")
        btn.clicked.connect(self.sprite_run)
        self.action_btns[0] = btn
        log_btn_layout.addWidget(btn)
        
        # 编辑已有精灵图按钮
        edit_existing_btn = QPushButton("编辑已有精灵图")
        edit_existing_btn.clicked.connect(self._edit_existing_sprite)
        # 默认显示 (因为默认 Tab 是 0)
        # 将其添加为特殊的 action button，或者在 tab 切换逻辑中单独处理
        # 这里为了简单，我们把它也加入 action_btns，但 key 可以用个特殊值，或者直接在 tab 0 显示时一起显示
        self.sprite_edit_btn = edit_existing_btn 
        log_btn_layout.addWidget(edit_existing_btn)
        
        # 视频转图按钮
        btn = QPushButton("开始提取")
        btn.setObjectName("actionButton")
        btn.clicked.connect(self.extract_run)
        btn.hide()
        self.action_btns[1] = btn
        log_btn_layout.addWidget(btn)
        
        # 视频扣像按钮
        btn = QPushButton("开始视频扣像")
        btn.setObjectName("actionButton")
        btn.clicked.connect(self.beiou_run)
        btn.hide()
        self.action_btns[2] = btn
        log_btn_layout.addWidget(btn)
        
        # 图片转视频按钮
        btn = QPushButton("合成视频")
        btn.setObjectName("actionButton")
        btn.clicked.connect(self.vid_run)
        btn.hide()
        self.action_btns[3] = btn
        log_btn_layout.addWidget(btn)
        
        # 视频转GIF按钮
        btn = QPushButton("生成 GIF")
        btn.setObjectName("actionButton")
        btn.clicked.connect(self.gif_run)
        btn.hide()
        self.action_btns[4] = btn
        log_btn_layout.addWidget(btn)
        
        # 图片扣图按钮
        btn = QPushButton("处理图片")
        btn.setObjectName("actionButton")
        btn.clicked.connect(self.single_run)
        btn.hide()
        self.action_btns[5] = btn
        log_btn_layout.addWidget(btn)
        
        log_btn_layout.addStretch()
        log_layout.addLayout(log_btn_layout)
        
        log_group.setLayout(log_layout)
        self.splitter.addWidget(log_group)
        
        self.splitter.setSizes([500, 200])
        main.addWidget(self.splitter)
        
        self.setLayout(main)
        self._apply_compact_layout()
        self._adjust_window_size()
        
        # 监听 Tab 切换
        self.tabs.currentChanged.connect(self._on_tab_changed)
        
        # 初始化调用一次，确保按钮状态正确
        self._on_tab_changed(self.tabs.currentIndex())

    def _on_tab_changed(self, index):
        """Tab 切换时显示对应的操作按钮"""
        for i, btn in self.action_btns.items():
            if i == index:
                btn.show()
            else:
                btn.hide()
        
        # 特殊处理编辑已有精灵图按钮
        # 强制更新可见性，确保在任何时候切换回来都能显示
        if index == 0:
            self.sprite_edit_btn.setVisible(True)
            self.sprite_edit_btn.raise_() # 确保在最上层
        else:
            self.sprite_edit_btn.setVisible(False)
        
        self._adjust_splitter_to_tab()

    def _compact_set_width(self, widget, chars):
        try:
            from PySide6.QtWidgets import QStyle, QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit
            fm = widget.fontMetrics()
            txt_w = fm.horizontalAdvance('0' * max(1, int(chars)))
            extra = 10
            try:
                frame_w = widget.style().pixelMetric(QStyle.PM_DefaultFrameWidth, None, widget)
            except Exception:
                frame_w = 2
            if isinstance(widget, QSpinBox):
                extra += frame_w + 28
            elif isinstance(widget, QDoubleSpinBox):
                extra += frame_w + 32
            elif isinstance(widget, QComboBox):
                extra += frame_w + 28
            elif isinstance(widget, QLineEdit):
                extra += frame_w + 10
            widget.setMaximumWidth(txt_w + extra)
        except Exception:
            pass

    def _apply_compact_layout(self):
        self._compact_set_width(self.sprite_path_edit, 36)
        self._compact_set_width(self.extract_path_edit, 36)
        self._compact_set_width(self.vid_src_edit, 36)
        self._compact_set_width(self.gif_src_edit, 36)
        self._compact_set_width(self.single_src_edit, 36)
        self.sprite_step.setRange(1, 99)
        self.extract_step.setRange(1, 99)
        self.gif_step.setRange(1, 99)
        self._compact_set_width(self.sprite_step, 2)
        self._compact_set_width(self.extract_step, 2)
        self._compact_set_width(self.gif_step, 2)
        self.sprite_scale_val.setRange(0, 100)
        self._compact_set_width(self.sprite_scale_val, 3)
        self._compact_set_width(self.sprite_w, 4)
        self._compact_set_width(self.sprite_h, 4)
        self._compact_set_width(self.sprite_cols, 2)
        self._compact_set_width(self.beiou_crf, 2)
        self._compact_set_width(self.vid_fps, 3)
        self._compact_set_width(self.gif_fps, 2)
        self._compact_set_width(self.beiou_format, 18)
        self._compact_set_width(self.beiou_speed, 6)

        # 紧凑化各栅格布局的间距，减少标签与控件间空白
        try:
            # 精灵图设置
            sl = self._find_layout_of_group("设置")
            if sl:
                sl.setContentsMargins(6, 6, 6, 6)
                sl.setHorizontalSpacing(6)
                sl.setVerticalSpacing(4)
                sl.setColumnStretch(0, 0); sl.setColumnStretch(1, 0); sl.setColumnStretch(2, 0); sl.setColumnStretch(3, 1)
            # 视频转图 - 选项与清理
            ol = self._find_layout_of_group("提取选项")
            if ol:
                ol.setContentsMargins(6, 6, 6, 6)
                ol.setHorizontalSpacing(6)
                ol.setVerticalSpacing(4)
            cl = self._find_layout_of_group("清理选项")
            if cl:
                cl.setContentsMargins(6, 6, 6, 6)
                cl.setHorizontalSpacing(6)
                cl.setVerticalSpacing(4)
            # 视频扣像 - 后处理
            pl = self._find_layout_of_group("后处理选项")
            if pl:
                pl.setContentsMargins(6, 6, 6, 6)
                pl.setHorizontalSpacing(6)
                pl.setVerticalSpacing(4)
            # 图片转视频参数
            iv = self._find_layout_of_group("参数")
            if iv:
                iv.setContentsMargins(6, 6, 6, 6)
                iv.setHorizontalSpacing(6)
                iv.setVerticalSpacing(4)
            # GIF 参数与清理
            gf = self._find_layout_of_group("GIF 参数")
            if gf:
                gf.setContentsMargins(6, 6, 6, 6)
                gf.setHorizontalSpacing(6)
                gf.setVerticalSpacing(4)
            gc = self._find_layout_of_group("清理选项")
            if gc:
                gc.setContentsMargins(6, 6, 6, 6)
                gc.setHorizontalSpacing(6)
                gc.setVerticalSpacing(4)
            # 单图处理选项
            so = self._find_layout_of_group("处理选项")
            if so:
                so.setContentsMargins(6, 6, 6, 6)
                so.setHorizontalSpacing(6)
                so.setVerticalSpacing(4)
        except Exception:
            pass

    def _adjust_window_size(self):
        try:
            max_h = 0
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                max_h = max(max_h, w.sizeHint().height())
            logs_min = 160
            total_h = max_h + logs_min + 20
            self.setFixedHeight(750)
        except Exception:
            pass

    def _adjust_splitter_to_tab(self):
        try:
            top_h = self.tabs.currentWidget().sizeHint().height()
            total_h = self.height()
            logs_h = max(140, total_h - top_h)
            self.splitter.setSizes([top_h, logs_h])
        except Exception:
            pass

    def _find_layout_of_group(self, title):
        try:
            # 在当前页中查找指定标题的 QGroupBox 并返回其布局
            page = self.tabs.currentWidget()
            for gb in page.findChildren(QGroupBox):
                if gb.title() == title:
                    return gb.layout()
        except Exception:
            pass
        return None
    
    def _refresh_all_model_selectors(self):
        """刷新所有模型选择器"""
        ModelManager.scan_models()
        for selector in [self.sprite_model, self.extract_model, self.gif_model, self.single_model, self.beiou_model]:
            selector.refresh_models()
        logger.info("模型状态已刷新")

    def create_file_input(self, btn_callback, placeholder="拖入文件或点击选择..."):
        layout = QHBoxLayout()
        line_edit = FileDropLineEdit(placeholder=placeholder)
        btn = QPushButton("选择")
        btn.clicked.connect(btn_callback)
        layout.addWidget(line_edit)
        layout.addWidget(btn)
        return layout, line_edit

    def create_hint_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("color: #7f8c8d; font-size: 8pt; font-style: italic;")
        label.setWordWrap(True)
        return label

    def create_thread_selector(self):
        spin = QSpinBox()
        spin.setRange(1, HardwareInfo.cpu_threads * 2)
        spin.setValue(min(4, HardwareInfo.cpu_threads))
        return spin

    def _on_model_changed(self, model_id: str, status: dict):
        """模型选择变化回调"""
        pass

    def _build_sprite_tab(self):
        w = QWidget()
        layout = QVBoxLayout()
        
        src_grp = QGroupBox("源文件")
        self.sprite_source_type = QButtonGroup(w)
        r1 = QRadioButton("视频"); r1.setChecked(True)
        r2 = QRadioButton("图片文件夹")
        r3 = QRadioButton("已有精灵图")
        self.sprite_source_type.addButton(r1, 0)
        self.sprite_source_type.addButton(r2, 1)
        self.sprite_source_type.addButton(r3, 2)
        
        hl = QHBoxLayout()
        hl.addWidget(r1)
        hl.addWidget(r2)
        hl.addWidget(r3)
        hl.addStretch()
        src_grp.setLayout(QVBoxLayout())
        src_grp.layout().addLayout(hl)
        
        inp_layout, self.sprite_path_edit = self.create_file_input(self.sprite_select_source)
        src_grp.layout().addLayout(inp_layout)
        layout.addWidget(src_grp)

        model_grp = QGroupBox("AI 模型")
        model_grp.setFixedHeight(60)  # 强制限制高度
        ml = QGridLayout()
        ml.setContentsMargins(6,6,6,6)
        ml.setHorizontalSpacing(6)
        ml.setVerticalSpacing(4)
        ml.addWidget(QLabel("选择模型:"), 0, 0)
        self.sprite_model = ModelSelector()
        self.sprite_model.model_changed.connect(self._on_model_changed)
        ml.addWidget(self.sprite_model, 0, 1, 1, 2)
        ml.addWidget(QLabel("并行线程:"), 0, 3)
        self.sprite_threads = self.create_thread_selector()
        ml.addWidget(self.sprite_threads, 0, 4)
        
        model_grp.setToolTip("★ = 已加载 | ✓ = 已下载 | ○ = 需下载 | 🔴 = 大模型")
        model_grp.setLayout(ml)
        layout.addWidget(model_grp)

        set_grp = QGroupBox("设置")
        set_grp.setFixedHeight(60)
        sl = QGridLayout()
        sl.setContentsMargins(6, 6, 6, 6)
        sl.setHorizontalSpacing(6)
        sl.setVerticalSpacing(4)
        sl.addWidget(QLabel("帧间隔:"), 0, 0)
        self.sprite_step = QSpinBox()
        self.sprite_step.setRange(1, 1000)
        self.sprite_step.setValue(1)
        sl.addWidget(self.sprite_step, 0, 1)
        sl.addWidget(QLabel("列数:"), 0, 2)
        self.sprite_cols = QSpinBox()
        self.sprite_cols.setRange(1, 100)
        self.sprite_cols.setValue(10)
        sl.addWidget(self.sprite_cols, 0, 3)
        
        self.sprite_percent = QRadioButton("百分比")
        self.sprite_percent.setChecked(True)
        self.sprite_fixed = QRadioButton("固定尺寸")
        sl.addWidget(self.sprite_percent, 0, 4)
        sl.addWidget(self.sprite_fixed, 0, 5)
        
        self.sprite_scale_val = QDoubleSpinBox()
        self.sprite_scale_val.setValue(100)
        self.sprite_scale_val.setRange(1, 1000)
        sl.addWidget(self.sprite_scale_val, 0, 6)
        
        self.sprite_w = QSpinBox()
        self.sprite_w.setValue(256)
        self.sprite_w.setRange(1, 4096)
        self.sprite_w.setEnabled(False)
        self.sprite_h = QSpinBox()
        self.sprite_h.setValue(256)
        self.sprite_h.setRange(1, 4096)
        self.sprite_h.setEnabled(False)
        
        wh_layout = QHBoxLayout()
        wh_layout.addWidget(self.sprite_w)
        wh_layout.addWidget(QLabel("x"))
        wh_layout.addWidget(self.sprite_h)
        sl.addLayout(wh_layout, 0, 7)
        
        self.sprite_percent.toggled.connect(lambda c: [self.sprite_w.setEnabled(not c), self.sprite_h.setEnabled(not c), self.sprite_scale_val.setEnabled(c)])

        set_grp.setLayout(sl)
        layout.addWidget(set_grp)
        
        bg_grp = QGroupBox("背景移除与清理")
        bl = QGridLayout()
        bl.setContentsMargins(6, 6, 6, 6)
        bl.setHorizontalSpacing(6)
        bl.setVerticalSpacing(4)
        
        self.sprite_rembg = QCheckBox("启用背景移除")
        bl.addWidget(self.sprite_rembg, 0, 0, 1, 2)
        bl.addItem(QSpacerItem(40, 1, QSizePolicy.Fixed, QSizePolicy.Minimum), 0, 2)
        
        bl.addWidget(QLabel("清理预设:"), 0, 3)
        self.sprite_clean_preset = QComboBox()
        self.sprite_clean_preset.addItems(["关闭", "轻度", "标准", "强力", "自定义"])
        self.sprite_clean_preset.setCurrentText("标准")
        bl.addWidget(self.sprite_clean_preset, 0, 4)
        
        self.sprite_clean = QCheckBox("边缘清理")
        self.sprite_clean.setEnabled(False)
        bl.addWidget(self.sprite_clean, 0, 5)
        bl.addWidget(QLabel("腐蚀:"), 0, 6)
        self.sprite_feather = QSpinBox()
        self.sprite_feather.setValue(1)
        self.sprite_feather.setRange(0, 10)
        bl.addWidget(self.sprite_feather, 0, 7)
        bl.addWidget(QLabel("模糊:"), 0, 8)
        self.sprite_blur = QSpinBox()
        self.sprite_blur.setValue(1)
        self.sprite_blur.setRange(0, 10)
        bl.addWidget(self.sprite_blur, 0, 9)
        bl.addWidget(QLabel("Gamma:"), 0, 10)
        self.sprite_gamma = QDoubleSpinBox()
        self.sprite_gamma.setValue(1.2)
        self.sprite_gamma.setRange(0.5, 2.0)
        self.sprite_gamma.setSingleStep(0.1)
        bl.addWidget(self.sprite_gamma, 0, 11)
        
        self.sprite_iso = QCheckBox("移除孤立色块")
        self.sprite_iso.setEnabled(False)
        bl.addWidget(self.sprite_iso, 1, 0, 1, 2)
        bl.addWidget(QLabel("最小保留:"), 1, 2)
        self.sprite_iso_area = QSpinBox()
        self.sprite_iso_area.setValue(50)
        self.sprite_iso_area.setRange(1, 50000)
        bl.addWidget(self.sprite_iso_area, 1, 3)
        
        self.sprite_internal = QCheckBox("清理内部孔洞")
        self.sprite_internal.setEnabled(False)
        self.sprite_internal.setChecked(True)
        bl.addWidget(self.sprite_internal, 1, 4, 1, 2)
        bl.addWidget(QLabel("孔洞最大:"), 1, 6)
        self.sprite_internal_area = QSpinBox()
        self.sprite_internal_area.setValue(100)
        self.sprite_internal_area.setRange(1, 10000)
        bl.addWidget(self.sprite_internal_area, 1, 7)
        
        def _apply_preset(name: str):
            if name == "关闭":
                self.sprite_clean.setChecked(False)
                self.sprite_iso.setChecked(False)
                self.sprite_internal.setChecked(False)
                self.sprite_feather.setValue(0)
                self.sprite_blur.setValue(0)
                self.sprite_gamma.setValue(1.0)
                self.sprite_iso_area.setValue(10)
                self.sprite_internal_area.setValue(50)
                for w in [self.sprite_feather, self.sprite_blur, self.sprite_gamma, self.sprite_iso_area, self.sprite_internal_area]:
                    w.setEnabled(False)
            elif name == "轻度":
                self.sprite_clean.setChecked(True)
                self.sprite_iso.setChecked(True)
                self.sprite_internal.setChecked(True)
                self.sprite_feather.setValue(1)
                self.sprite_blur.setValue(1)
                self.sprite_gamma.setValue(1.0)
                self.sprite_iso_area.setValue(20)
                self.sprite_internal_area.setValue(80)
                for w in [self.sprite_feather, self.sprite_blur, self.sprite_gamma, self.sprite_iso_area, self.sprite_internal_area]:
                    w.setEnabled(False)
            elif name == "标准":
                self.sprite_clean.setChecked(True)
                self.sprite_iso.setChecked(True)
                self.sprite_internal.setChecked(True)
                self.sprite_feather.setValue(1)
                self.sprite_blur.setValue(1)
                self.sprite_gamma.setValue(1.2)
                self.sprite_iso_area.setValue(50)
                self.sprite_internal_area.setValue(100)
                for w in [self.sprite_feather, self.sprite_blur, self.sprite_gamma, self.sprite_iso_area, self.sprite_internal_area]:
                    w.setEnabled(False)
            elif name == "强力":
                self.sprite_clean.setChecked(True)
                self.sprite_iso.setChecked(True)
                self.sprite_internal.setChecked(True)
                self.sprite_feather.setValue(2)
                self.sprite_blur.setValue(2)
                self.sprite_gamma.setValue(1.3)
                self.sprite_iso_area.setValue(150)
                self.sprite_internal_area.setValue(200)
                for w in [self.sprite_feather, self.sprite_blur, self.sprite_gamma, self.sprite_iso_area, self.sprite_internal_area]:
                    w.setEnabled(False)
            else:  # 自定义
                self.sprite_clean.setChecked(True)
                self.sprite_iso.setChecked(True)
                self.sprite_internal.setChecked(True)
                for w in [self.sprite_feather, self.sprite_blur, self.sprite_gamma, self.sprite_iso_area, self.sprite_internal_area]:
                    w.setEnabled(True)
        
        self.sprite_clean_preset.currentTextChanged.connect(_apply_preset)
        
        def _on_sprite_rembg_toggled(checked):
            self.sprite_clean_preset.setEnabled(checked)
            self.sprite_clean.setEnabled(checked)
            self.sprite_iso.setEnabled(checked)
            self.sprite_internal.setEnabled(checked)
            
            if not checked:
                # 禁用所有数值控件
                for w in [self.sprite_feather, self.sprite_blur, self.sprite_gamma, self.sprite_iso_area, self.sprite_internal_area]:
                    w.setEnabled(False)
            else:
                # 恢复预设状态 (如果是自定义则启用，否则禁用)
                _apply_preset(self.sprite_clean_preset.currentText())

        self.sprite_rembg.toggled.connect(_on_sprite_rembg_toggled)
        # 初始化状态
        _on_sprite_rembg_toggled(self.sprite_rembg.isChecked())
        # 确保应用预设值
        _apply_preset(self.sprite_clean_preset.currentText())
        
        bg_grp.setLayout(bl)
        layout.addWidget(bg_grp)

        edit_grp = QGroupBox("编辑模式")
        edit_grp.setFixedHeight(75)  # 2.5行文本高度
        el = QVBoxLayout()
        hdr = QHBoxLayout()
        self.sprite_edit_mode = QCheckBox("启用编辑模式 (生成后可选择帧)")
        hdr.addWidget(self.sprite_edit_mode)
        el.addLayout(hdr)
        edit_hint = self.create_hint_label("启用后，生成精灵图前会打开编辑器，可以选择要保留的帧。输出文件会添加 _bj 后缀。")
        el.addWidget(edit_hint)
        edit_grp.setLayout(el)
        layout.addWidget(edit_grp)
        
        self.sprite_prog = QProgressBar()
        layout.addWidget(self.sprite_prog)
        w.setLayout(layout)
        return w

    def _build_video_extract_tab(self):
        w = QWidget()
        layout = QVBoxLayout()
        
        grp = QGroupBox("视频源")
        grp.setFixedHeight(60)
        l, self.extract_path_edit = self.create_file_input(self.extract_select)
        l.setContentsMargins(6,6,6,6)
        l.setSpacing(6)
        grp.setLayout(l)
        layout.addWidget(grp)
        
        model_grp = QGroupBox("AI 模型")
        model_grp.setFixedHeight(60)  # 强制限制高度
        ml = QGridLayout()
        ml.setContentsMargins(6,6,6,6)
        ml.setHorizontalSpacing(6)
        ml.setVerticalSpacing(4)
        ml.addWidget(QLabel("选择模型:"), 0, 0)
        self.extract_model = ModelSelector()
        self.extract_model.model_changed.connect(self._on_model_changed)
        ml.addWidget(self.extract_model, 0, 1, 1, 2)
        ml.addWidget(QLabel("并行线程:"), 0, 3)
        self.extract_threads = self.create_thread_selector()
        ml.addWidget(self.extract_threads, 0, 4)
        model_grp.setLayout(ml)
        layout.addWidget(model_grp)
        
        opt = QGroupBox("提取选项")
        opt.setFixedHeight(90)  # 3行文本高度
        ol = QGridLayout()
        self.extract_mode = QButtonGroup(w)
        r1 = QRadioButton("首尾帧")
        r1.setChecked(True)
        self.extract_mode.addButton(r1, 0)
        r2 = QRadioButton("全部帧")
        self.extract_mode.addButton(r2, 1)
        ol.addWidget(r1, 0, 0)
        ol.addWidget(r2, 0, 1)
        ol.addWidget(QLabel("间隔:"), 0, 2)
        self.extract_step = QSpinBox()
        self.extract_step.setRange(1, 1000)
        self.extract_step.setValue(1)
        ol.addWidget(self.extract_step, 0, 3)
        
        # 背景图路径控件移动到间隔控件后面
        self.extract_bg_img = QLineEdit("背景图路径...")
        ol.addWidget(self.extract_bg_img, 0, 4, 1, 2)

        self.extract_rembg = QCheckBox("移除背景")
        ol.addWidget(self.extract_rembg, 1, 0)
        self.extract_bg_type = QComboBox()
        self.extract_bg_type.addItems(["none", "color", "image"])
        ol.addWidget(self.extract_bg_type, 1, 1)
        
        # 【修复】使用颜色选择器
        ol.addWidget(QLabel("背景色:"), 1, 2)
        self.extract_bg_color = ColorPickerWidget("#FFFFFF")
        ol.addWidget(self.extract_bg_color, 1, 3)
        
        opt.setLayout(ol)
        layout.addWidget(opt)
        
        clean_grp = QGroupBox("清理选项")
        clean_grp.setFixedHeight(115)  # 增加5px (110 -> 115)
        cl = QGridLayout()
        
        self.extract_clean = QCheckBox("边缘清理")
        cl.addWidget(self.extract_clean, 0, 0)
        cl.addWidget(QLabel("腐蚀:"), 0, 1)
        self.extract_feather = QSpinBox()
        self.extract_feather.setValue(1)
        self.extract_feather.setRange(0, 10)
        cl.addWidget(self.extract_feather, 0, 2)
        cl.addWidget(QLabel("模糊:"), 0, 3)
        self.extract_blur = QSpinBox()
        self.extract_blur.setValue(1)
        self.extract_blur.setRange(0, 10)
        cl.addWidget(self.extract_blur, 0, 4)
        cl.addWidget(QLabel("Gamma:"), 0, 5)
        self.extract_gamma = QDoubleSpinBox()
        self.extract_gamma.setValue(1.2)
        self.extract_gamma.setRange(0.5, 2.0)
        self.extract_gamma.setSingleStep(0.1)
        cl.addWidget(self.extract_gamma, 0, 6)
        cl.addWidget(QLabel("清理预设:"), 0, 7)
        self.extract_clean_preset = QComboBox()
        self.extract_clean_preset.addItems(["关闭", "轻度", "标准", "强力", "自定义"])
        self.extract_clean_preset.setCurrentText("标准")
        cl.addWidget(self.extract_clean_preset, 0, 8)
        
        self.extract_iso = QCheckBox("移除孤立色块")
        cl.addWidget(self.extract_iso, 1, 0)
        cl.addWidget(QLabel("最小保留:"), 1, 1)
        self.extract_iso_area = QSpinBox()
        self.extract_iso_area.setValue(50)
        self.extract_iso_area.setRange(1, 50000)
        cl.addWidget(self.extract_iso_area, 1, 2)
        
        self.extract_internal = QCheckBox("清理内部孔洞")
        self.extract_internal.setChecked(True)
        cl.addWidget(self.extract_internal, 1, 3)
        cl.addWidget(QLabel("孔洞最大:"), 1, 4)
        self.extract_internal_area = QSpinBox()
        self.extract_internal_area.setValue(100)
        self.extract_internal_area.setRange(1, 10000)
        cl.addWidget(self.extract_internal_area, 1, 5)
        def _apply_extract_preset(name: str):
            if name == "关闭":
                self.extract_clean.setChecked(False)
                self.extract_iso.setChecked(False)
                self.extract_internal.setChecked(False)
                self.extract_feather.setValue(0)
                self.extract_blur.setValue(0)
                self.extract_gamma.setValue(1.0)
                self.extract_iso_area.setValue(10)
                self.extract_internal_area.setValue(50)
                for w in [self.extract_feather, self.extract_blur, self.extract_gamma, self.extract_iso_area, self.extract_internal_area]:
                    w.setEnabled(False)
            elif name == "轻度":
                self.extract_clean.setChecked(True)
                self.extract_iso.setChecked(True)
                self.extract_internal.setChecked(True)
                self.extract_feather.setValue(1)
                self.extract_blur.setValue(1)
                self.extract_gamma.setValue(1.0)
                self.extract_iso_area.setValue(20)
                self.extract_internal_area.setValue(80)
                for w in [self.extract_feather, self.extract_blur, self.extract_gamma, self.extract_iso_area, self.extract_internal_area]:
                    w.setEnabled(False)
            elif name == "标准":
                self.extract_clean.setChecked(True)
                self.extract_iso.setChecked(True)
                self.extract_internal.setChecked(True)
                self.extract_feather.setValue(1)
                self.extract_blur.setValue(1)
                self.extract_gamma.setValue(1.2)
                self.extract_iso_area.setValue(50)
                self.extract_internal_area.setValue(100)
                for w in [self.extract_feather, self.extract_blur, self.extract_gamma, self.extract_iso_area, self.extract_internal_area]:
                    w.setEnabled(False)
            elif name == "强力":
                self.extract_clean.setChecked(True)
                self.extract_iso.setChecked(True)
                self.extract_internal.setChecked(True)
                self.extract_feather.setValue(2)
                self.extract_blur.setValue(2)
                self.extract_gamma.setValue(1.3)
                self.extract_iso_area.setValue(150)
                self.extract_internal_area.setValue(200)
                for w in [self.extract_feather, self.extract_blur, self.extract_gamma, self.extract_iso_area, self.extract_internal_area]:
                    w.setEnabled(False)
            else:
                self.extract_clean.setChecked(True)
                self.extract_iso.setChecked(True)
                self.extract_internal.setChecked(True)
                for w in [self.extract_feather, self.extract_blur, self.extract_gamma, self.extract_iso_area, self.extract_internal_area]:
                    w.setEnabled(True)
        self.extract_clean_preset.currentTextChanged.connect(_apply_extract_preset)
        
        def _on_extract_rembg_toggled(checked):
            self.extract_clean_preset.setEnabled(checked)
            self.extract_clean.setEnabled(checked)
            self.extract_iso.setEnabled(checked)
            self.extract_internal.setEnabled(checked)
            
            if not checked:
                for w in [self.extract_feather, self.extract_blur, self.extract_gamma, self.extract_iso_area, self.extract_internal_area]:
                    w.setEnabled(False)
            else:
                _apply_extract_preset(self.extract_clean_preset.currentText())
                
        self.extract_rembg.toggled.connect(_on_extract_rembg_toggled)
        _on_extract_rembg_toggled(self.extract_rembg.isChecked())
        _apply_extract_preset(self.extract_clean_preset.currentText())
        
        clean_grp.setLayout(cl)
        layout.addWidget(clean_grp)
        
        self.extract_prog = QProgressBar()
        layout.addWidget(self.extract_prog)
        w.setLayout(layout)
        return w

    def _build_video_rembg_tab(self):
        """视频扣像 Tab"""
        w = QWidget()
        layout = QVBoxLayout()
        
        src_grp = QGroupBox("视频源")
        src_grp.setFixedHeight(60)
        l, self.beiou_path_edit = self.create_file_input(self.beiou_select)
        l.setContentsMargins(6,6,6,6)
        l.setSpacing(6)
        src_grp.setLayout(l)
        layout.addWidget(src_grp)
        
        model_grp = QGroupBox("AI 模型")
        model_grp.setFixedHeight(60)  # 强制限制高度
        ml = QGridLayout()
        ml.setContentsMargins(6,6,6,6)
        ml.setHorizontalSpacing(6)
        ml.setVerticalSpacing(4)
        ml.addWidget(QLabel("选择模型:"), 0, 0)
        self.beiou_model = ModelSelector()
        self.beiou_model.model_changed.connect(self._on_model_changed)
        ml.addWidget(self.beiou_model, 0, 1, 1, 2)
        ml.addWidget(QLabel("并行线程:"), 0, 3)
        self.beiou_threads = self.create_thread_selector()
        ml.addWidget(self.beiou_threads, 0, 4)
        model_grp.setToolTip("建议使用 ISNet 或 U²-Net 系列模型")
        model_grp.setLayout(ml)
        layout.addWidget(model_grp)
        
        out_grp = QGroupBox("输出设置")
        out_grp.setFixedHeight(150)  # 5行文本高度
        ol = QGridLayout()
        ol.setContentsMargins(8, 8, 8, 8)
        ol.setHorizontalSpacing(8)
        ol.setVerticalSpacing(6)
        
        ol.addWidget(QLabel("输出格式:"), 0, 0)
        self.beiou_format = QComboBox()
        self.beiou_format.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.beiou_format.setMinimumContentsLength(12)
        self.beiou_format.addItems(["mp4 (绿幕/自定义背景)", "avi", "webm (绿幕)", "webm (透明通道)"])
        ol.addWidget(self.beiou_format, 0, 1)
        
        # 【修复】使用颜色选择器
        ol.addWidget(QLabel("背景色:"), 0, 2)
        self.beiou_bg_color = ColorPickerWidget("#00FF00")
        self.beiou_bg_color.setMaximumWidth(180)
        ol.addWidget(self.beiou_bg_color, 0, 3)
        self.beiou_preserve_alpha = QCheckBox("保留透明通道 (仅WebM)")
        self.beiou_preserve_alpha.setEnabled(False)
        ol.addWidget(self.beiou_preserve_alpha, 1, 0, 1, 2)
        ol.addWidget(QLabel("质量(CRF):"), 1, 2)
        self.beiou_crf = QSpinBox()
        self.beiou_crf.setRange(12, 40)
        self.beiou_crf.setValue(28)
        ol.addWidget(self.beiou_crf, 1, 3)
        ol.addWidget(QLabel("速度模式:"), 2, 0)
        self.beiou_speed = QComboBox()
        self.beiou_speed.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.beiou_speed.addItems(["快速", "平衡", "高质量"])
        self.beiou_speed.setCurrentIndex(1)
        ol.addWidget(self.beiou_speed, 2, 1)
        self.beiou_audio = QCheckBox("包含音频 (透明WebM)")
        self.beiou_audio.setEnabled(False)
        self.beiou_audio.setChecked(True)
        ol.addWidget(self.beiou_audio, 2, 2, 1, 2)
        self.beiou_format.currentIndexChanged.connect(self._on_beiou_format_changed)
        format_hint = self.create_hint_label("选择'webm (透明通道)'可保存带Alpha通道的视频，适合后期合成")
        ol.addWidget(format_hint, 4, 0, 1, 4)

        ol.setColumnStretch(1, 1)
        ol.setColumnStretch(3, 1)
        
        out_grp.setLayout(ol)
        layout.addWidget(out_grp)
        
        post_grp = QGroupBox("后处理选项")
        post_grp.setFixedHeight(90)
        pl = QGridLayout()
        
        self.beiou_clean = QCheckBox("边缘清理")
        pl.addWidget(self.beiou_clean, 0, 0)
        pl.addWidget(QLabel("腐蚀:"), 0, 1)
        self.beiou_feather = QSpinBox()
        self.beiou_feather.setValue(1)
        self.beiou_feather.setRange(0, 10)
        pl.addWidget(self.beiou_feather, 0, 2)
        pl.addWidget(QLabel("模糊:"), 0, 3)
        self.beiou_blur = QSpinBox()
        self.beiou_blur.setValue(1)
        self.beiou_blur.setRange(0, 10)
        pl.addWidget(self.beiou_blur, 0, 4)
        pl.addWidget(QLabel("Gamma:"), 0, 5)
        self.beiou_gamma = QDoubleSpinBox()
        self.beiou_gamma.setValue(1.2)
        self.beiou_gamma.setRange(0.5, 2.0)
        self.beiou_gamma.setSingleStep(0.1)
        pl.addWidget(self.beiou_gamma, 0, 6)
        pl.addWidget(QLabel("清理预设:"), 0, 7)
        self.beiou_clean_preset = QComboBox()
        self.beiou_clean_preset.addItems(["关闭", "轻度", "标准", "强力", "自定义"])
        self.beiou_clean_preset.setCurrentText("标准")
        pl.addWidget(self.beiou_clean_preset, 0, 8)
        
        self.beiou_iso = QCheckBox("移除孤立色块")
        pl.addWidget(self.beiou_iso, 1, 0)
        pl.addWidget(QLabel("最小保留:"), 1, 1)
        self.beiou_iso_area = QSpinBox()
        self.beiou_iso_area.setValue(50)
        self.beiou_iso_area.setRange(1, 50000)
        pl.addWidget(self.beiou_iso_area, 1, 2)
        
        self.beiou_internal = QCheckBox("清理内部孔洞")
        self.beiou_internal.setChecked(True)
        pl.addWidget(self.beiou_internal, 1, 3)
        pl.addWidget(QLabel("孔洞最大:"), 1, 4)
        self.beiou_internal_area = QSpinBox()
        self.beiou_internal_area.setValue(100)
        self.beiou_internal_area.setRange(1, 10000)
        pl.addWidget(self.beiou_internal_area, 1, 5)
        def _apply_beiou_preset(name: str):
            if name == "关闭":
                self.beiou_clean.setChecked(False)
                self.beiou_iso.setChecked(False)
                self.beiou_internal.setChecked(False)
                self.beiou_feather.setValue(0)
                self.beiou_blur.setValue(0)
                self.beiou_gamma.setValue(1.0)
                self.beiou_iso_area.setValue(10)
                self.beiou_internal_area.setValue(50)
                for w in [self.beiou_feather, self.beiou_blur, self.beiou_gamma, self.beiou_iso_area, self.beiou_internal_area]:
                    w.setEnabled(False)
            elif name == "轻度":
                self.beiou_clean.setChecked(True)
                self.beiou_iso.setChecked(True)
                self.beiou_internal.setChecked(True)
                self.beiou_feather.setValue(1)
                self.beiou_blur.setValue(1)
                self.beiou_gamma.setValue(1.0)
                self.beiou_iso_area.setValue(20)
                self.beiou_internal_area.setValue(80)
                for w in [self.beiou_feather, self.beiou_blur, self.beiou_gamma, self.beiou_iso_area, self.beiou_internal_area]:
                    w.setEnabled(False)
            elif name == "标准":
                self.beiou_clean.setChecked(True)
                self.beiou_iso.setChecked(True)
                self.beiou_internal.setChecked(True)
                self.beiou_feather.setValue(1)
                self.beiou_blur.setValue(1)
                self.beiou_gamma.setValue(1.2)
                self.beiou_iso_area.setValue(50)
                self.beiou_internal_area.setValue(100)
                for w in [self.beiou_feather, self.beiou_blur, self.beiou_gamma, self.beiou_iso_area, self.beiou_internal_area]:
                    w.setEnabled(False)
            elif name == "强力":
                self.beiou_clean.setChecked(True)
                self.beiou_iso.setChecked(True)
                self.beiou_internal.setChecked(True)
                self.beiou_feather.setValue(2)
                self.beiou_blur.setValue(2)
                self.beiou_gamma.setValue(1.3)
                self.beiou_iso_area.setValue(150)
                self.beiou_internal_area.setValue(200)
                for w in [self.beiou_feather, self.beiou_blur, self.beiou_gamma, self.beiou_iso_area, self.beiou_internal_area]:
                    w.setEnabled(False)
            else:
                self.beiou_clean.setChecked(True)
                self.beiou_iso.setChecked(True)
                self.beiou_internal.setChecked(True)
                for w in [self.beiou_feather, self.beiou_blur, self.beiou_gamma, self.beiou_iso_area, self.beiou_internal_area]:
                    w.setEnabled(True)
        self.beiou_clean_preset.currentTextChanged.connect(_apply_beiou_preset)
        _apply_beiou_preset(self.beiou_clean_preset.currentText())
        
        post_grp.setLayout(pl)
        layout.addWidget(post_grp)
        
        self.beiou_prog = QProgressBar()
        layout.addWidget(self.beiou_prog)
        w.setLayout(layout)
        return w

    def _build_images_to_video_tab(self):
        w = QWidget()
        layout = QVBoxLayout()
        
        grp = QGroupBox("图片源")
        grp.setFixedHeight(60)
        l, self.vid_src_edit = self.create_file_input(self.vid_select)
        grp.setLayout(l)
        layout.addWidget(grp)
        
        opt = QGroupBox("参数")
        ol = QGridLayout()
        ol.addWidget(QLabel("FPS:"), 0, 0)
        self.vid_fps = QSpinBox()
        self.vid_fps.setValue(24)
        self.vid_fps.setRange(1, 120)
        ol.addWidget(self.vid_fps, 0, 1)
        ol.addWidget(QLabel("背景填充:"), 0, 2)
        self.vid_bg_type = QComboBox()
        self.vid_bg_type.addItems(["none", "color", "image"])
        ol.addWidget(self.vid_bg_type, 0, 3)
        
        # 【修复】使用颜色选择器
        ol.addWidget(QLabel("背景色:"), 1, 0)
        self.vid_bg_color = ColorPickerWidget("#FFFFFF")
        ol.addWidget(self.vid_bg_color, 1, 1, 1, 3)
        
        opt.setLayout(ol)
        layout.addWidget(opt)
        
        self.vid_prog = QProgressBar()
        layout.addWidget(self.vid_prog)
        layout.addStretch()
        w.setLayout(layout)
        return w

    def _build_gif_tab(self):
        w = QWidget()
        layout = QVBoxLayout()
        
        src_grp = QGroupBox("源")
        src_grp.setFixedHeight(60)  # 2行文本高度
        self.gif_src_type = QButtonGroup(w)
        r1 = QRadioButton("视频")
        r1.setChecked(True)
        r2 = QRadioButton("图片文件夹")
        self.gif_src_type.addButton(r1)
        self.gif_src_type.addButton(r2)
        hl = QHBoxLayout()
        hl.addWidget(r1)
        hl.addWidget(r2)
        
        l, self.gif_src_edit = self.create_file_input(self.gif_select)
        hl.addLayout(l) # 将文件选择控件添加到同一行
        
        src_grp.setLayout(QVBoxLayout())
        src_grp.layout().addLayout(hl)
        layout.addWidget(src_grp)
        
        model_grp = QGroupBox("AI 模型")
        model_grp.setFixedHeight(60)  # 强制限制高度
        ml = QGridLayout()
        ml.setContentsMargins(6,6,6,6)
        ml.setHorizontalSpacing(6)
        ml.setVerticalSpacing(4)
        ml.addWidget(QLabel("选择模型:"), 0, 0)
        self.gif_model = ModelSelector()
        self.gif_model.model_changed.connect(self._on_model_changed)
        ml.addWidget(self.gif_model, 0, 1, 1, 2)
        ml.addWidget(QLabel("并行线程:"), 0, 3)
        self.gif_threads = self.create_thread_selector()
        ml.addWidget(self.gif_threads, 0, 4)
        model_grp.setLayout(ml)
        layout.addWidget(model_grp)
        
        opt = QGroupBox("GIF 参数")
        opt.setFixedHeight(60)
        ol = QGridLayout()
        ol.setContentsMargins(6,6,6,6)
        ol.setHorizontalSpacing(1)  # 减少间距 (5px -> 1px)
        ol.setVerticalSpacing(2)
        fps_l = QLabel("FPS:")
        ol.addWidget(fps_l, 0, 0)
        self.gif_fps = QSpinBox(); self.gif_fps.setValue(10); self.gif_fps.setRange(1, 60)
        ol.addWidget(self.gif_fps, 0, 1)
        step_l = QLabel("间隔:")
        ol.addWidget(step_l, 0, 2)
        self.gif_step = QSpinBox(); self.gif_step.setRange(1, 1000); self.gif_step.setValue(1)
        ol.addWidget(self.gif_step, 0, 3)
        
        self.gif_transparency = QCheckBox("保留透明通道")
        ol.addWidget(self.gif_transparency, 0, 4)
        self.gif_rembg = QCheckBox("移除背景")
        ol.addWidget(self.gif_rembg, 0, 5)
        
        opt.setLayout(ol)
        layout.addWidget(opt)
        
        clean_grp = QGroupBox("清理选项")
        clean_grp.setFixedHeight(115)  # 增加5px (110 -> 115)
        cl = QGridLayout()
        
        self.gif_clean = QCheckBox("边缘清理")
        cl.addWidget(self.gif_clean, 0, 0)
        cl.addWidget(QLabel("腐蚀:"), 0, 1)
        self.gif_feather = QSpinBox()
        self.gif_feather.setValue(1)
        self.gif_feather.setRange(0, 10)
        cl.addWidget(self.gif_feather, 0, 2)
        cl.addWidget(QLabel("模糊:"), 0, 3)
        self.gif_blur = QSpinBox()
        self.gif_blur.setValue(1)
        self.gif_blur.setRange(0, 10)
        cl.addWidget(self.gif_blur, 0, 4)
        cl.addWidget(QLabel("Gamma:"), 0, 5)
        self.gif_gamma = QDoubleSpinBox()
        self.gif_gamma.setValue(1.2)
        self.gif_gamma.setRange(0.5, 2.0)
        self.gif_gamma.setSingleStep(0.1)
        cl.addWidget(self.gif_gamma, 0, 6)
        cl.addWidget(QLabel("清理预设:"), 0, 7)
        self.gif_clean_preset = QComboBox()
        self.gif_clean_preset.addItems(["关闭", "轻度", "标准", "强力", "自定义"])
        self.gif_clean_preset.setCurrentText("标准")
        cl.addWidget(self.gif_clean_preset, 0, 8)
        
        self.gif_iso = QCheckBox("移除孤立色块")
        cl.addWidget(self.gif_iso, 1, 0)
        cl.addWidget(QLabel("最小保留:"), 1, 1)
        self.gif_iso_area = QSpinBox()
        self.gif_iso_area.setValue(50)
        self.gif_iso_area.setRange(1, 50000)
        cl.addWidget(self.gif_iso_area, 1, 2)
        
        self.gif_internal = QCheckBox("清理内部孔洞")
        self.gif_internal.setChecked(True)
        cl.addWidget(self.gif_internal, 1, 3)
        cl.addWidget(QLabel("孔洞最大:"), 1, 4)
        self.gif_internal_area = QSpinBox()
        self.gif_internal_area.setValue(100)
        self.gif_internal_area.setRange(1, 10000)
        cl.addWidget(self.gif_internal_area, 1, 5)
        def _apply_gif_preset(name: str):
            if name == "关闭":
                self.gif_clean.setChecked(False)
                self.gif_iso.setChecked(False)
                self.gif_internal.setChecked(False)
                self.gif_feather.setValue(0)
                self.gif_blur.setValue(0)
                self.gif_gamma.setValue(1.0)
                self.gif_iso_area.setValue(10)
                self.gif_internal_area.setValue(50)
                for w in [self.gif_feather, self.gif_blur, self.gif_gamma, self.gif_iso_area, self.gif_internal_area]:
                    w.setEnabled(False)
            elif name == "轻度":
                self.gif_clean.setChecked(True)
                self.gif_iso.setChecked(True)
                self.gif_internal.setChecked(True)
                self.gif_feather.setValue(1)
                self.gif_blur.setValue(1)
                self.gif_gamma.setValue(1.0)
                self.gif_iso_area.setValue(20)
                self.gif_internal_area.setValue(80)
                for w in [self.gif_feather, self.gif_blur, self.gif_gamma, self.gif_iso_area, self.gif_internal_area]:
                    w.setEnabled(False)
            elif name == "标准":
                self.gif_clean.setChecked(True)
                self.gif_iso.setChecked(True)
                self.gif_internal.setChecked(True)
                self.gif_feather.setValue(1)
                self.gif_blur.setValue(1)
                self.gif_gamma.setValue(1.2)
                self.gif_iso_area.setValue(50)
                self.gif_internal_area.setValue(100)
                for w in [self.gif_feather, self.gif_blur, self.gif_gamma, self.gif_iso_area, self.gif_internal_area]:
                    w.setEnabled(False)
            elif name == "强力":
                self.gif_clean.setChecked(True)
                self.gif_iso.setChecked(True)
                self.gif_internal.setChecked(True)
                self.gif_feather.setValue(2)
                self.gif_blur.setValue(2)
                self.gif_gamma.setValue(1.3)
                self.gif_iso_area.setValue(150)
                self.gif_internal_area.setValue(200)
                for w in [self.gif_feather, self.gif_blur, self.gif_gamma, self.gif_iso_area, self.gif_internal_area]:
                    w.setEnabled(False)
            else:
                self.gif_clean.setChecked(True)
                self.gif_iso.setChecked(True)
                self.gif_internal.setChecked(True)
                for w in [self.gif_feather, self.gif_blur, self.gif_gamma, self.gif_iso_area, self.gif_internal_area]:
                    w.setEnabled(True)
        self.gif_clean_preset.currentTextChanged.connect(_apply_gif_preset)
        
        def _on_gif_rembg_toggled(checked):
            self.gif_clean_preset.setEnabled(checked)
            self.gif_clean.setEnabled(checked)
            self.gif_iso.setEnabled(checked)
            self.gif_internal.setEnabled(checked)
            
            if not checked:
                for w in [self.gif_feather, self.gif_blur, self.gif_gamma, self.gif_iso_area, self.gif_internal_area]:
                    w.setEnabled(False)
            else:
                _apply_gif_preset(self.gif_clean_preset.currentText())

        self.gif_rembg.toggled.connect(_on_gif_rembg_toggled)
        _on_gif_rembg_toggled(self.gif_rembg.isChecked())
        _apply_gif_preset(self.gif_clean_preset.currentText())
        
        self.gif_bg_type = QComboBox()
        self.gif_bg_type.addItems(["none", "color"])
        cl.addWidget(QLabel("背景:"), 2, 0)
        cl.addWidget(self.gif_bg_type, 2, 1)
        
        # 【修复】使用颜色选择器
        self.gif_bg_color = ColorPickerWidget("#FFFFFF")
        cl.addWidget(self.gif_bg_color, 2, 2, 1, 2)
        
        self.gif_transparency.toggled.connect(lambda s: [self.gif_bg_type.setEnabled(not s), self.gif_bg_color.setEnabled(not s)])

        clean_grp.setLayout(cl)
        layout.addWidget(clean_grp)
        
        self.gif_prog = QProgressBar()
        layout.addWidget(self.gif_prog)
        w.setLayout(layout)
        return w

    def _build_single_image_tab(self):
        w = QWidget()
        layout = QVBoxLayout()
        
        grp = QGroupBox("单图")
        grp.setFixedHeight(60)
        l, self.single_src_edit = self.create_file_input(self.single_select)
        grp.setLayout(l)
        layout.addWidget(grp)
        
        model_grp = QGroupBox("AI 模型")
        model_grp.setFixedHeight(60)  # 强制限制高度
        ml = QGridLayout()
        ml.setContentsMargins(6,6,6,6)
        ml.setHorizontalSpacing(6)
        ml.setVerticalSpacing(4)
        ml.addWidget(QLabel("选择模型:"), 0, 0)
        self.single_model = ModelSelector()
        self.single_model.model_changed.connect(self._on_model_changed)
        ml.addWidget(self.single_model, 0, 1, 1, 2)
        ml.addWidget(QLabel("并行线程:"), 0, 3)
        self.single_threads = self.create_thread_selector()
        ml.addWidget(self.single_threads, 0, 4)
        model_grp.setLayout(ml)
        layout.addWidget(model_grp)
        
        opt = QGroupBox("处理选项")
        ol = QGridLayout()
        
        self.single_clean = QCheckBox("边缘清理")
        ol.addWidget(self.single_clean, 0, 0)
        ol.addWidget(QLabel("腐蚀:"), 0, 1)
        self.single_feather = QSpinBox()
        self.single_feather.setValue(1)
        self.single_feather.setRange(0, 10)
        ol.addWidget(self.single_feather, 0, 2)
        ol.addWidget(QLabel("模糊:"), 0, 3)
        self.single_blur = QSpinBox()
        self.single_blur.setValue(1)
        self.single_blur.setRange(0, 10)
        ol.addWidget(self.single_blur, 0, 4)
        ol.addWidget(QLabel("Gamma:"), 0, 5)
        self.single_gamma = QDoubleSpinBox()
        self.single_gamma.setValue(1.2)
        self.single_gamma.setRange(0.5, 2.0)
        self.single_gamma.setSingleStep(0.1)
        ol.addWidget(self.single_gamma, 0, 6)
        ol.addWidget(QLabel("清理预设:"), 0, 7)
        self.single_clean_preset = QComboBox()
        self.single_clean_preset.addItems(["关闭", "轻度", "标准", "强力", "自定义"])
        self.single_clean_preset.setCurrentText("标准")
        ol.addWidget(self.single_clean_preset, 0, 8)
        
        self.single_iso = QCheckBox("去杂色")
        ol.addWidget(self.single_iso, 1, 0)
        ol.addWidget(QLabel("最小保留:"), 1, 1)
        self.single_iso_area = QSpinBox()
        self.single_iso_area.setValue(50)
        self.single_iso_area.setRange(1, 50000)
        ol.addWidget(self.single_iso_area, 1, 2)
        
        self.single_internal = QCheckBox("清理内部孔洞")
        self.single_internal.setChecked(True)
        ol.addWidget(self.single_internal, 1, 3)
        ol.addWidget(QLabel("孔洞最大:"), 1, 4)
        self.single_internal_area = QSpinBox()
        self.single_internal_area.setValue(100)
        self.single_internal_area.setRange(1, 10000)
        ol.addWidget(self.single_internal_area, 1, 5)
        def _apply_single_preset(name: str):
            if name == "关闭":
                self.single_clean.setChecked(False)
                self.single_iso.setChecked(False)
                self.single_internal.setChecked(False)
                self.single_feather.setValue(0)
                self.single_blur.setValue(0)
                self.single_gamma.setValue(1.0)
                self.single_iso_area.setValue(10)
                self.single_internal_area.setValue(50)
                for w in [self.single_feather, self.single_blur, self.single_gamma, self.single_iso_area, self.single_internal_area]:
                    w.setEnabled(False)
            elif name == "轻度":
                self.single_clean.setChecked(True)
                self.single_iso.setChecked(True)
                self.single_internal.setChecked(True)
                self.single_feather.setValue(1)
                self.single_blur.setValue(1)
                self.single_gamma.setValue(1.0)
                self.single_iso_area.setValue(20)
                self.single_internal_area.setValue(80)
                for w in [self.single_feather, self.single_blur, self.single_gamma, self.single_iso_area, self.single_internal_area]:
                    w.setEnabled(False)
            elif name == "标准":
                self.single_clean.setChecked(True)
                self.single_iso.setChecked(True)
                self.single_internal.setChecked(True)
                self.single_feather.setValue(1)
                self.single_blur.setValue(1)
                self.single_gamma.setValue(1.2)
                self.single_iso_area.setValue(50)
                self.single_internal_area.setValue(100)
                for w in [self.single_feather, self.single_blur, self.single_gamma, self.single_iso_area, self.single_internal_area]:
                    w.setEnabled(False)
            elif name == "强力":
                self.single_clean.setChecked(True)
                self.single_iso.setChecked(True)
                self.single_internal.setChecked(True)
                self.single_feather.setValue(2)
                self.single_blur.setValue(2)
                self.single_gamma.setValue(1.3)
                self.single_iso_area.setValue(150)
                self.single_internal_area.setValue(200)
                for w in [self.single_feather, self.single_blur, self.single_gamma, self.single_iso_area, self.single_internal_area]:
                    w.setEnabled(False)
            else:
                self.single_clean.setChecked(True)
                self.single_iso.setChecked(True)
                self.single_internal.setChecked(True)
                for w in [self.single_feather, self.single_blur, self.single_gamma, self.single_iso_area, self.single_internal_area]:
                    w.setEnabled(True)
        self.single_clean_preset.currentTextChanged.connect(_apply_single_preset)
        _apply_single_preset(self.single_clean_preset.currentText())
        
        self.single_bg_type = QComboBox()
        self.single_bg_type.addItems(["none", "color"])
        ol.addWidget(self.single_bg_type, 2, 0)
        
        # 【修复】使用颜色选择器
        self.single_bg_color = ColorPickerWidget("#FFFFFF")
        ol.addWidget(self.single_bg_color, 2, 1, 1, 3)
        
        opt.setLayout(ol)
        layout.addWidget(opt)
        
        # ==================== ICO 生成 ====================
        ico_grp = QGroupBox("ICO 生成 (可选)")
        il = QGridLayout()
        il.setContentsMargins(6,6,6,6)
        
        self.ico_enabled = QCheckBox("启用 ICO 生成")
        il.addWidget(self.ico_enabled, 0, 0, 1, 6)
        
        self.ico_system = QCheckBox("系统 ICO (多尺寸容器)")
        self.ico_system.setToolTip("生成包含多个尺寸的 .ico 文件，让系统自动选择最佳显示效果。")
        self.ico_system.toggled.connect(self._on_ico_system_toggled)
        il.addWidget(self.ico_system, 0, 4, 1, 2)
        
        self.ico_sizes = {}
        # 16x16 ... 480x480
        sizes = [16, 24, 32, 48, 64, 72, 80, 96, 128, 256, 320, 480]
        row = 1
        col = 0
        for s in sizes:
            cb = QCheckBox(f"{s}x{s}")
            self.ico_sizes[s] = cb
            il.addWidget(cb, row, col)
            col += 1
            if col >= 6:
                col = 0
                row += 1
        
        self.ico_transparent = QCheckBox("保留透明通道")
        self.ico_transparent.setChecked(True)
        il.addWidget(self.ico_transparent, row+1, 0, 1, 3)
        
        self.ico_opaque = QCheckBox("生成无透明版本(白底)")
        il.addWidget(self.ico_opaque, row+1, 3, 1, 3)
        
        self.ico_png = QCheckBox("生成 PNG")
        il.addWidget(self.ico_png, row+2, 0, 1, 3)
        
        def _toggle_ico(checked):
            for w in self.ico_sizes.values():
                w.setEnabled(checked)
            self.ico_transparent.setEnabled(checked)
            self.ico_opaque.setEnabled(checked)
            self.ico_png.setEnabled(checked)
            self.ico_system.setEnabled(checked)
            
        self.ico_enabled.toggled.connect(_toggle_ico)
        # 强制初始化状态
        _toggle_ico(self.ico_enabled.isChecked())
        # 确保初始未选中时是禁用的，选中时是启用的。
        # 如果默认 self.ico_enabled 是未选中的，那么 checkState() 是 0 (Unchecked)，enabled 为 False。
        # 如果默认是选中的，checkState() 是 2 (Checked)，enabled 为 True。
        # 注意：Qt.Checked 枚举值通常为 2。
        
        ico_grp.setLayout(il)
        layout.addWidget(ico_grp)
        # ================================================
        
        self.single_prog = QProgressBar()
        layout.addWidget(self.single_prog)
        layout.addStretch()
        w.setLayout(layout)
        return w

    def _build_settings_tab(self):
        w = QWidget()
        layout = QVBoxLayout()
        
        model_grp = QGroupBox("模型设置")
        ml = QGridLayout()
        
        ml.addWidget(QLabel("模型存储目录:"), 0, 0)
        self.model_dir_edit = QLineEdit(ConfigManager.get_model_dir())
        self.model_dir_edit.setReadOnly(True)
        ml.addWidget(self.model_dir_edit, 0, 1)
        
        open_model_dir_btn = QPushButton("打开目录")
        open_model_dir_btn.clicked.connect(lambda: os.startfile(ConfigManager.get_model_dir()) if os.path.exists(ConfigManager.get_model_dir()) else None)
        ml.addWidget(open_model_dir_btn, 0, 2)
        
        hint = self.create_hint_label('将 .onnx 模型文件放入此目录，然后点击"刷新模型状态"即可使用自定义模型')
        ml.addWidget(hint, 1, 0, 1, 3)
        
        model_grp.setLayout(ml)
        layout.addWidget(model_grp)
        
        # 硬件信息与输出路径并排布局
        hw_paths_layout = QHBoxLayout()
        
        # 硬件信息 (减少 120px 宽度)
        hw_grp = QGroupBox("硬件信息")
        hw_grp.setFixedHeight(220)  # 增加10px (210 -> 220)
        hw_grp.setFixedWidth(200)   # 假设原宽约320，减120后设为200 (实际通过layout stretch控制，这里尝试固定宽度或调整stretch)
        # 由于是 QHBoxLayout，更推荐调整 stretch。
        # 原比例 3:7。要减少左边增加右边。
        # 假设总宽1000，左300右700。减少120 -> 左180右820。
        # 比例约为 1.8 : 8.2 -> 9 : 41。或者直接用固定宽度。
        # 用户要求“硬件信息宽度减小120像素”，如果之前是自动拉伸，现在最好给硬件信息设置固定宽度或者最大宽度。
        # 之前代码：hw_paths_layout.addWidget(hw_grp, 3) ... addWidget(pg, 7)
        # 这里我们尝试调整 stretch 或者直接设置FixedWidth。
        # 考虑到响应式，调整 stretch 可能不够精确，但更灵活。
        # 不过用户说了具体像素，可能更希望是固定变化。
        # 让我们尝试设置 hw_grp 的 MaximumWidth，并调整 stretch。
        
        hl = QGridLayout()
        hl.setContentsMargins(6,6,6,6)
        hl.setHorizontalSpacing(8)
        hl.setVerticalSpacing(4)
        
        # 一行显示一项内容
        hl.addWidget(QLabel("GPU:"), 0, 0)
        hl.addWidget(QLabel(f"{'✓ ' + HardwareInfo.gpu_name if HardwareInfo.gpu_available else '○ 未检测到'}"), 0, 1)
        
        hl.addWidget(QLabel("GPU 显存:"), 1, 0)
        hl.addWidget(QLabel(f"{HardwareInfo.gpu_memory_mb} MB" if HardwareInfo.gpu_available else "N/A"), 1, 1)
        
        hl.addWidget(QLabel("CPU 线程:"), 2, 0)
        hl.addWidget(QLabel(str(HardwareInfo.cpu_threads)), 2, 1)
        
        hl.addWidget(QLabel("可用内存:"), 3, 0)
        hl.addWidget(QLabel(f"{HardwareInfo.available_memory_mb} MB"), 3, 1)
        
        hl.addWidget(QLabel("rembg:"), 4, 0)
        hl.addWidget(QLabel(f"{'✓ 已安装' if USE_REMBG else '✗ 未安装'}"), 4, 1)
        
        hl.addWidget(QLabel("ONNX:"), 5, 0)
        # ONNX 内容分两行显示
        onnx_text = ", ".join(HardwareInfo.onnx_providers) if HardwareInfo.onnx_providers else "N/A"
        # 简单的换行处理，例如每25个字符换行，或者直接设置 WordWrap
        onnx_label = QLabel(onnx_text)
        onnx_label.setWordWrap(True)
        hl.addWidget(onnx_label, 5, 1, 2, 1) # 占两行高度
        
        hw_grp.setLayout(hl)
        hw_paths_layout.addWidget(hw_grp) # 不再设置stretch，使用FixedWidth
        
        # 输出路径 (增加 120px 宽度)
        pg = QGroupBox("输出路径 (biemo 目录)")
        pg.setFixedHeight(220)  # 增加10px (210 -> 220)
        pgl = QGridLayout()
        self.path_edits = {}
        output_paths = ConfigManager.get("output_paths", ConfigManager.DEFAULT_CONFIG["output_paths"])
        for i, (k, v) in enumerate(output_paths.items()):
            pgl.addWidget(QLabel(k), i, 0)
            le = QLineEdit(ConfigManager.get_output_path(k))
            le.setReadOnly(True)
            self.path_edits[k] = le
            pgl.addWidget(le, i, 1)
            btn = QPushButton("打开")
            btn.setFixedWidth(50)
            btn.clicked.connect(lambda _, path=ConfigManager.get_output_path(k): os.startfile(path) if os.path.exists(path) else None)
            pgl.addWidget(btn, i, 2)
        
        pg.setLayout(pgl)
        hw_paths_layout.addWidget(pg) # 剩余空间自动给输出路径
        
        layout.addLayout(hw_paths_layout)
        
        act = QGroupBox("激活信息")
        act.setFixedHeight(80)  # 增加10px (70 -> 80)
        al = QVBoxLayout()
        al.setContentsMargins(6,6,6,6)
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel(f"机器码: {LicenseManager.get_machine_code()}"))
        if not self.activated:
            btn = QPushButton("输入激活码")
            btn.clicked.connect(self._show_activation_dialog)
            row1.addWidget(btn)
        row1.addStretch()
        al.addLayout(row1)
        
        al.addWidget(QLabel(f"激活文件: {LicenseManager.get_license_file()}"))
        
        act.setLayout(al)
        layout.addWidget(act)
        
        s_box = QCheckBox("开启完成音效")
        s_box.setChecked(self.enable_sound)
        s_box.toggled.connect(lambda s: [setattr(self, 'enable_sound', s), ConfigManager.set("enable_sound", s)])
        layout.addWidget(s_box)
        
        layout.addStretch()
        w.setLayout(layout)
        return w

    def sprite_select_source(self): 
        sid = self.sprite_source_type.checkedId()
        if sid == 0:
            self._select_file(self.sprite_path_edit, file_mode=True, filter="Video (*.mp4 *.avi *.mov *.mkv *.webm)")
        elif sid == 1:
            self._select_file(self.sprite_path_edit, file_mode=False)
        else:
            self._select_file(self.sprite_path_edit, file_mode=True, filter="PNG 图片 (*.png)")
    def extract_select(self): 
        self._select_file(self.extract_path_edit, file_mode=True)
    def vid_select(self): 
        self._select_file(self.vid_src_edit, file_mode=False)
    def gif_select(self): 
        self._select_file(self.gif_src_edit, file_mode=self.gif_src_type.checkedButton().text()=="视频")
    def single_select(self): 
        self._select_file(self.single_src_edit, file_mode=True, filter="Img (*.png *.jpg *.bmp)")
    def beiou_select(self):
        self._select_file(self.beiou_path_edit, file_mode=True, filter="Video (*.mp4 *.avi *.mov *.mkv *.webm)")

    def _select_file(self, edit_widget, file_mode=True, filter="Video (*.mp4 *.avi *.mov *.mkv)"):
        if file_mode: 
            f, _ = QFileDialog.getOpenFileName(self, "选择文件", "", filter)
        else: 
            f = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if f: 
            edit_widget.setText(f)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        try:
            if not e.mimeData().hasUrls():
                return
            path = e.mimeData().urls()[0].toLocalFile()
            idx = self.tabs.currentIndex()
            if idx == 0:
                self.sprite_path_edit.setText(path)
            elif idx == 1:
                self.extract_path_edit.setText(path)
            elif idx == 2:
                self.beiou_path_edit.setText(path)
            elif idx == 3:
                self.vid_src_edit.setText(path)
            elif idx == 4:
                self.gif_src_edit.setText(path)
            elif idx == 5:
                self.single_src_edit.setText(path)
        except Exception:
            pass

    def show_result_dialog(self, result):
        if isinstance(result, dict):
            folder_path = result.get('folder')
            video_path = result.get('video')
            frames = result.get('frames')
            duration = result.get('duration')
            avg_fps = result.get('avg_fps')
        else:
            folder_path = result
            video_path = None
            frames = None
            duration = None
            avg_fps = None
        if self.enable_sound:
            play_completion_sound()
        msg = QMessageBox(self)
        msg.setWindowTitle("任务完成")
        if video_path or frames or duration is not None or avg_fps is not None:
            parts = []
            if video_path:
                parts.append(f"输出: {Path(video_path).name}")
            if isinstance(frames, int):
                parts.append(f"帧数: {frames}")
            if isinstance(duration, (int, float)):
                parts.append(f"耗时: {duration}s")
            if isinstance(avg_fps, (int, float)):
                parts.append(f"速度: {avg_fps} fps")
            msg.setText("处理已完成！\n" + "\n".join(parts))
        else:
            msg.setText("处理已完成！")
        msg.setIcon(QMessageBox.Information)
        open_btn = msg.addButton("打开文件夹", QMessageBox.ActionRole)
        msg.addButton("关闭", QMessageBox.RejectRole)
        msg.exec()
        if msg.clickedButton() == open_btn and folder_path:
            try:
                os.startfile(folder_path)
            except:
                try:
                    subprocess.Popen(['xdg-open', folder_path])
                except:
                    pass

    def sprite_run(self):
        path = self.sprite_path_edit.text()
        if not path:
            logger.warning("请先选择源文件")
            return
        edit_mode = self.sprite_edit_mode.isChecked()
        params = {
            "source_type": "video" if self.sprite_source_type.checkedId()==0 else "images",
            "model_name": self.sprite_model.get_current_model(),
            "num_threads": self.sprite_threads.value(),
            "frame_step": max(1, self.sprite_step.value()),
            "columns": max(1, self.sprite_cols.value()),
            "scale_mode": "percent" if self.sprite_percent.isChecked() else "fixed",
            "scale_percent": self.sprite_scale_val.value(),
            "thumb_w": self.sprite_w.value(),
            "thumb_h": self.sprite_h.value(),
            "remove_bg": self.sprite_rembg.isChecked(),
            "cleanup_edge": self.sprite_clean.isChecked(),
            "edge_feather": self.sprite_feather.value(),
            "edge_blur": self.sprite_blur.value(),
            "edge_gamma": self.sprite_gamma.value(),
            "remove_isolated": self.sprite_iso.isChecked(),
            "isolated_area": self.sprite_iso_area.value(),
            "remove_internal": self.sprite_internal.isChecked(),
            "internal_max_area": self.sprite_internal_area.value(),
            "edit_mode": edit_mode,
        }
        logger.info(f"开始生成精灵图: {path}")
        out = Path(ConfigManager.get_output_path("sprite"))
        out.mkdir(parents=True, exist_ok=True)
        if edit_mode:
            self.current_worker = SpriteWorkerWithEditor(path, str(out), params, self)
        else:
            self.current_worker = SpriteWorker(path, str(out), params)
        self.current_worker.progress.connect(lambda v, m: [self.sprite_prog.setValue(v), self.sprite_prog.setFormat(m)])
        if edit_mode and hasattr(self.current_worker, 'frames_ready'):
            self.current_worker.frames_ready.connect(self._on_sprite_frames_ready)
        self.current_worker.error.connect(lambda e: logger.error(e))
        self.current_worker.finished.connect(lambda d: self.show_result_dialog(d))
        self.current_worker.start()

    def sprite_preview(self):
        path = self.sprite_path_edit.text()
        if not path:
            return
        stype = "video" if self.sprite_source_type.checkedId()==0 else ("images" if self.sprite_source_type.checkedId()==1 else "sheet")
        frames = []
        try:
            if stype == "video" and HAS_CV2:
                cap = cv2.VideoCapture(str(path))
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                step = max(1, self.sprite_step.value())
                count = 0
                for i in range(0, total, step):
                    if count >= 50: break
                    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, f = cap.read()
                    if not ret: break
                    frame_rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
                    frames.append(Image.fromarray(frame_rgb).convert('RGBA'))
                    count += 1
                cap.release()
            elif stype == "images":
                files = sorted([f for f in (Path(path).glob('*') if Path(path).is_dir() else [Path(path)]) if f.suffix.lower() in ['.png','.jpg','.jpeg','.bmp']])
                for i, fp in enumerate(files[:50]):
                    img = Image.open(fp).convert('RGBA')
                    frames.append(img)
            else:
                img = Image.open(path).convert('RGBA')
                w, h = img.size
                rows = max(1, int(self.sprite_rows.value()))
                cols = max(1, int(self.sprite_cols_existing.value()))
                cell_w = w // cols
                cell_h = h // rows
                total_cells = rows * cols
                for idx in range(min(total_cells, 200)):
                    c = idx % cols
                    r = idx // cols
                    box = (c*cell_w, r*cell_h, (c+1)*cell_w, (r+1)*cell_h)
                    frames.append(img.crop(box))
            spec = self.sprite_keep_frames.text()
            if spec:
                def parse_ranges(spec, n):
                    res = set()
                    for part in spec.replace('，', ',').split(','):
                        part = part.strip()
                        if not part: continue
                        if '-' in part:
                            a, b = part.split('-', 1)
                            try:
                                s = max(1, int(a)); e = min(n, int(b))
                                for k in range(s, e+1): res.add(k-1)
                            except: pass
                        else:
                            try:
                                k = int(part);
                                if 1 <= k <= n: res.add(k-1)
                            except: pass
                    return sorted(res)
                idxs = parse_ranges(spec, len(frames))
                if idxs:
                    frames = [frames[i] for i in idxs]
            dlg = SpritePreviewDialog(frames, fps=12, parent=self)
            dlg.exec()
        except Exception:
            pass

    def _on_sprite_frames_ready(self, frames, source_path):
        try:
            if self.current_worker:
                self.current_worker._open_editor(frames)
        except Exception as e:
            logger.error(str(e))

    def _edit_existing_sprite(self):
        # 优先使用当前输入框中的文件
        file_path = self.sprite_path_edit.text().strip()
        
        # 如果输入框为空或者不是文件，则弹出选择框
        if not file_path or not os.path.isfile(file_path):
            file_path, _ = QFileDialog.getOpenFileName(self, "选择精灵图", "", "PNG 图片 (*.png)")
        
        if not file_path:
            return
        try:
            dialog = SpriteEditorDialog(self, source_sprite_path=file_path)
            if dialog.exec() == QDialog.Accepted:
                selected_frames = dialog.get_selected_frames()
                output_cols = dialog.get_output_cols()
                if not selected_frames:
                    QMessageBox.warning(self, "提示", "请至少选择一帧")
                    return
                    
                self._generate_sprite_from_frames(selected_frames, output_cols, file_path)
        except Exception as e:
            logger.error(f"编辑精灵图失败: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"编辑失败: {e}")

    def _generate_sprite_from_frames(self, frames, cols, source_path=None):
        if not frames:
            return
        try:
            fw, fh = frames[0].size
            rows = math.ceil(len(frames) / max(1, cols))
            sheet = Image.new("RGBA", (cols * fw, rows * fh))
            for idx, frame in enumerate(frames):
                c, r = idx % cols, idx // cols
                if frame.mode != 'RGBA':
                    frame = frame.convert('RGBA')
                sheet.paste(frame, (c * fw, r * fh), frame)
            out_dir = Path(ConfigManager.get_output_path("sprite"))
            out_dir.mkdir(parents=True, exist_ok=True)
            if source_path:
                base_name = Path(source_path).stem
                if base_name.endswith('_bj'):
                    base_name = base_name[:-3]
                out_name = f"{base_name}_bj_{len(frames)}.png"
            else:
                out_name = f"sprite_bj_{len(frames)}_{datetime.now():%H%M%S}.png"
            out_path = out_dir / out_name
            sheet.save(str(out_path))
            logger.success(f"编辑精灵图生成完成: {out_path}")
            self.show_result_dialog(str(out_dir))
        except Exception as e:
            logger.error(f"生成精灵图失败: {e}")
            QMessageBox.critical(self, "错误", f"生成失败: {e}")

    def _on_beiou_format_changed(self, index):
        format_text = self.beiou_format.currentText()
        is_webm_alpha = "透明通道" in format_text
        self.beiou_preserve_alpha.setEnabled(is_webm_alpha)
        self.beiou_preserve_alpha.setChecked(is_webm_alpha)
        self.beiou_bg_color.setEnabled(not is_webm_alpha)
        self.beiou_audio.setEnabled(is_webm_alpha)
        self.beiou_audio.setChecked(is_webm_alpha)
        self.beiou_speed.setEnabled(is_webm_alpha)

    def extract_run(self):
        path = self.extract_path_edit.text()
        if not path:
            logger.warning("请先选择视频文件")
            return
        
        params = {
            "extract_mode": "first_last" if self.extract_mode.checkedId()==0 else "all",
            "model_name": self.extract_model.get_current_model(),
            "num_threads": self.extract_threads.value(),
            "frame_step": max(1, self.extract_step.value()),
            "remove_bg": self.extract_rembg.isChecked(),
            "bg_type": self.extract_bg_type.currentText(),
            "bg_color": self.extract_bg_color.get_color(),  # 【修复】使用颜色选择器
            "bg_image": self.extract_bg_img.text(),
            "cleanup_edge": self.extract_clean.isChecked(),
            "edge_feather": self.extract_feather.value(), 
            "edge_blur": self.extract_blur.value(),
            "edge_gamma": self.extract_gamma.value(),
            "remove_isolated": self.extract_iso.isChecked(), 
            "isolated_area": self.extract_iso_area.value(),
            "remove_internal": self.extract_internal.isChecked(),
            "internal_max_area": self.extract_internal_area.value(),
        }
        
        logger.info(f"开始提取视频帧: {path}")
        
        out = Path(ConfigManager.get_output_path("extract"))
        self.current_worker = VideoToImagesWorker(path, str(out), params)
        self.current_worker.progress.connect(lambda v, m: [self.extract_prog.setValue(v), self.extract_prog.setFormat(m)])
        self.current_worker.error.connect(lambda e: logger.error(e))
        self.current_worker.finished.connect(lambda d: self.show_result_dialog(d['folder']))
        self.current_worker.start()

    def beiou_run(self):
        """视频扣像"""
        path = self.beiou_path_edit.text()
        if not path:
            logger.warning("请先选择视频文件")
            return
        
        format_text = self.beiou_format.currentText()
        preserve_alpha = "透明通道" in format_text
        if "mp4" in format_text:
            output_format = "mp4"
            ext = ".mp4"
        elif "avi" in format_text:
            output_format = "avi"
            ext = ".avi"
        else:
            output_format = "webm"
            ext = ".webm"
        
        params = {
            "model_name": self.beiou_model.get_current_model(),
            "output_format": output_format,
            "preserve_alpha": preserve_alpha,
            "crf": self.beiou_crf.value(),
            "include_audio": self.beiou_audio.isChecked(),
            "speed_mode": self.beiou_speed.currentText(),
            "bg_color": self.beiou_bg_color.get_color(),
            "cleanup_edge": self.beiou_clean.isChecked(),
            "edge_feather": self.beiou_feather.value(),
            "edge_blur": self.beiou_blur.value(),
            "edge_gamma": self.beiou_gamma.value(),
            "remove_isolated": self.beiou_iso.isChecked(),
            "isolated_area": self.beiou_iso_area.value(),
            "remove_internal": self.beiou_internal.isChecked(),
            "internal_max_area": self.beiou_internal_area.value(),
        }
        
        logger.info(f"开始视频扣像: {path}")
        
        out_dir = Path(ConfigManager.get_output_path("beiou"))
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{Path(path).stem}_rembg_{datetime.now():%H%M%S}{ext}"
        
        self.current_worker = VideoRemoveBgWorker(path, str(out_path), params)
        self.current_worker.progress.connect(lambda v, m: [self.beiou_prog.setValue(v), self.beiou_prog.setFormat(m)])
        self.current_worker.error.connect(lambda e: logger.error(e))
        self.current_worker.finished.connect(lambda d: self.show_result_dialog(d['folder']))
        self.current_worker.start()

    def vid_run(self):
        path = self.vid_src_edit.text()
        if not path:
            logger.warning("请先选择图片文件夹")
            return
        
        params = {
            "fps": max(1, self.vid_fps.value()),
            "bg_type": self.vid_bg_type.currentText(),
            "bg_color": self.vid_bg_color.get_color()  # 【修复】使用颜色选择器
        }
        
        logger.info(f"开始合成视频: {path}")
        
        out = Path(ConfigManager.get_output_path("video")) / f"video_{datetime.now():%H%M%S}.mp4"
        out.parent.mkdir(exist_ok=True)
        self.current_worker = ImagesToVideoWorker(path, str(out), params)
        self.current_worker.progress.connect(lambda v, m: [self.vid_prog.setValue(v), self.vid_prog.setFormat(m)])
        self.current_worker.error.connect(lambda e: logger.error(e))
        self.current_worker.finished.connect(lambda d: self.show_result_dialog(d['folder']))
        self.current_worker.start()

    def gif_run(self):
        path = self.gif_src_edit.text()
        if not path:
            logger.warning("请先选择源文件")
            return
        
        params = {
            "model_name": self.gif_model.get_current_model(),
            "num_threads": self.gif_threads.value(),
            "fps": max(1, self.gif_fps.value()),
            "frame_step": max(1, self.gif_step.value()),
            "preserve_transparency": self.gif_transparency.isChecked(),
            "remove_bg": self.gif_rembg.isChecked(),
            "bg_type": self.gif_bg_type.currentText(),
            "bg_color": self.gif_bg_color.get_color(),  # 【修复】使用颜色选择器
            "cleanup_edge": self.gif_clean.isChecked(), 
            "edge_feather": self.gif_feather.value(), 
            "edge_blur": self.gif_blur.value(),
            "edge_gamma": self.gif_gamma.value(),
            "remove_isolated": self.gif_iso.isChecked(), 
            "isolated_area": self.gif_iso_area.value(),
            "remove_internal": self.gif_internal.isChecked(),
            "internal_max_area": self.gif_internal_area.value(),
        }
        
        logger.info(f"开始生成 GIF: {path}")
        
        out = Path(ConfigManager.get_output_path("gif")) / f"gif_{datetime.now():%H%M%S}.gif"
        out.parent.mkdir(exist_ok=True)
        
        if self.gif_src_type.checkedButton().text() == "视频":
            self.current_worker = VideoToGifWorker(path, str(out), params)
        else:
            self.current_worker = ImagesToGifWorker(path, str(out), params)
            
        self.current_worker.progress.connect(lambda v, m: [self.gif_prog.setValue(v), self.gif_prog.setFormat(m)])
        self.current_worker.error.connect(lambda e: logger.error(e))
        self.current_worker.finished.connect(lambda d: self.show_result_dialog(d['folder']))
        self.current_worker.start()

    def _on_ico_system_toggled(self, checked):
        """系统 ICO 选中时自动勾选推荐尺寸"""
        if checked:
            recommended = [16, 24, 32, 48, 256]
            for s, cb in self.ico_sizes.items():
                if s in recommended:
                    cb.setChecked(True)
                # 不强制取消其他的，用户可能想保留

    def single_run(self):
        path = self.single_src_edit.text()
        if not path:
            logger.warning("请先选择图片文件")
            return
        
        params = {
            "model_name": self.single_model.get_current_model(),
            "cleanup_edge": self.single_clean.isChecked(),
            "edge_feather": self.single_feather.value(), 
            "edge_blur": self.single_blur.value(),
            "edge_gamma": self.single_gamma.value(),
            "remove_isolated": self.single_iso.isChecked(),
            "isolated_area": self.single_iso_area.value(),
            "remove_internal": self.single_internal.isChecked(),
            "internal_max_area": self.single_internal_area.value(),
            "bg_type": self.single_bg_type.currentText(),
            "bg_color": self.single_bg_color.get_color(),  # 【修复】使用颜色选择器
            "ico_enabled": self.ico_enabled.isChecked(),
            "ico_sizes": [s for s, cb in self.ico_sizes.items() if cb.isChecked()],
            "ico_transparent": self.ico_transparent.isChecked(),
            "ico_opaque": self.ico_opaque.isChecked(),
            "ico_png": self.ico_png.isChecked(),
            "ico_system": self.ico_system.isChecked(),
        }
        
        logger.info(f"开始处理图片: {path}")
        
        out = Path(ConfigManager.get_output_path("single")) / f"proc_{Path(path).name}"
        out.parent.mkdir(exist_ok=True)
        self.current_worker = SingleImageWorker(path, str(out), params)
        self.current_worker.progress.connect(lambda v, m: [self.single_prog.setValue(v), self.single_prog.setFormat(m)])
        self.current_worker.error.connect(lambda e: logger.error(e))
        self.current_worker.finished.connect(lambda d: self.show_result_dialog(d['folder']))
        self.current_worker.start()

# ==================== 程序入口 ====================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    pass
    
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
